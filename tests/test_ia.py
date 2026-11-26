from __future__ import annotations

import json
import os
import stat

import httpx
import pytest
from typer.testing import CliRunner

from ultron.cli import app
from ultron.ia import ajustes, cliente, util
from ultron.ia import errores as E
from ultron.ia.ajustes import AjustesIA
from ultron.ia.anthropic import ClienteAnthropic
from ultron.ia.openai_compat import ClienteOpenAI, normalizar_url
from ultron.nucleo import config


def _transporte(manejador):
    return httpx.MockTransport(manejador)


def _aj(**kw):
    base = {"proveedor": "local", "url_base": "http://ia.test/v1", "modelo": "m1"}
    base.update(kw)
    return AjustesIA(**base)


def _ok_openai(texto="hola"):
    return {"choices": [{"message": {"content": texto}}]}


@pytest.fixture
def servidor(monkeypatch):
    """Instala un servidor falso para cliente.obtener_cliente()."""
    def instalar(manejador):
        monkeypatch.setattr(cliente, "TRANSPORTE", _transporte(manejador))
    return instalar


# --- URL ---------------------------------------------------------------------


@pytest.mark.parametrize("url, esperada", [
    ("http://localhost:11434", "http://localhost:11434/v1"),
    ("http://localhost:11434/", "http://localhost:11434/v1"),
    ("http://localhost:11434/v1/", "http://localhost:11434/v1"),
    ("https://openrouter.ai/api/v1", "https://openrouter.ai/api/v1"),
])
def test_normalizar_url(url, esperada):
    assert normalizar_url(url) == esperada


def test_reintento_con_v1():
    vistas = []

    def m(req):
        vistas.append(req.url.path)
        if req.url.path == "/api/models":
            return httpx.Response(404, text="not found")
        return httpx.Response(200, json={"data": [{"id": "llama3.2"}]})

    c = ClienteOpenAI(_aj(url_base="http://ia.test/api"), _transporte(m))
    assert c.modelos() == ["llama3.2"]
    assert vistas == ["/api/models", "/api/v1/models"]


# --- mapa de errores ---------------------------------------------------------

CASOS = [
    (401, "unauthorized", E.ClaveInvalida),
    (403, "forbidden", E.ClaveInvalida),
    (402, "payment required", E.SinSaldo),
    (429, '{"error":{"code":"insufficient_quota"}}', E.SinSaldo),
    (400, "This model's maximum context length is 4096 tokens", E.ContextoExcedido),
    (413, "payload too large", E.ContextoExcedido),
    (404, '{"error":"model \\"x\\" not found"}', E.ModeloNoExiste),
    (404, "<html>404</html>", E.URLIncorrecta),
]


@pytest.mark.parametrize("codigo, cuerpo, error", CASOS)
def test_errores_openai(codigo, cuerpo, error):
    c = ClienteOpenAI(_aj(), _transporte(lambda r: httpx.Response(codigo, text=cuerpo)))
    with pytest.raises(error) as info:
        c.chat([{"role": "user", "content": "hola"}])
    assert info.value.mensaje


@pytest.mark.parametrize("codigo, cuerpo, error", CASOS)
def test_errores_anthropic(codigo, cuerpo, error):
    c = ClienteAnthropic(_aj(proveedor="anthropic", url_base="https://a.test"),
                         _transporte(lambda r: httpx.Response(codigo, text=cuerpo)))
    with pytest.raises(error):
        c.chat([{"role": "user", "content": "hola"}])


def test_sin_conexion_y_timeout():
    def caido(req):
        raise httpx.ConnectError("refused", request=req)

    def lento(req):
        raise httpx.ReadTimeout("lento", request=req)

    with pytest.raises(E.SinConexion) as info:
        ClienteOpenAI(_aj(), _transporte(caido)).chat([{"role": "user", "content": "x"}])
    assert "curl" in info.value.sugerencia
    with pytest.raises(E.TiempoAgotado):
        ClienteOpenAI(_aj(), _transporte(lento)).chat([{"role": "user", "content": "x"}])


def test_respuesta_sin_choices():
    c = ClienteOpenAI(_aj(), _transporte(lambda r: httpx.Response(200, json={"hola": 1})))
    with pytest.raises(E.RespuestaInvalida):
        c.chat([{"role": "user", "content": "x"}])


def test_json_rechazado_reintenta_sin_response_format():
    cuerpos = []

    def m(req):
        cuerpo = json.loads(req.content)
        cuerpos.append(cuerpo)
        if "response_format" in cuerpo:
            return httpx.Response(400, text="response_format not supported")
        return httpx.Response(200, json=_ok_openai('{"a": 1}'))

    c = ClienteOpenAI(_aj(), _transporte(m))
    assert c.chat([{"role": "user", "content": "x"}], json=True) == '{"a": 1}'
    assert "response_format" not in cuerpos[-1]


def test_clave_opcional_y_bearer():
    cabeceras = []

    def m(req):
        cabeceras.append(req.headers.get("authorization"))
        return httpx.Response(200, json=_ok_openai())

    ClienteOpenAI(_aj(), _transporte(m)).chat([{"role": "user", "content": "x"}])
    ClienteOpenAI(_aj(clave="sk-1"), _transporte(m)).chat([{"role": "user", "content": "x"}])
    assert cabeceras == [None, "Bearer sk-1"]


# --- streaming -----------------------------------------------------------------


def test_stream_openai():
    sse = (
        'data: {"choices":[{"delta":{"content":"Ho"}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"la"}}]}\n\n'
        "data: [DONE]\n\n"
    )
    c = ClienteOpenAI(_aj(), _transporte(lambda r: httpx.Response(200, text=sse)))
    assert "".join(c.chat_stream([{"role": "user", "content": "x"}])) == "Hola"


def test_stream_anthropic():
    sse = (
        'event: content_block_delta\ndata: {"type":"content_block_delta",'
        '"delta":{"type":"text_delta","text":"Sha"}}\n\n'
        'data: {"type":"content_block_delta","delta":{"text":"lom"}}\n\n'
        'data: {"type":"message_stop"}\n\n'
    )
    c = ClienteAnthropic(_aj(proveedor="anthropic"),
                         _transporte(lambda r: httpx.Response(200, text=sse)))
    assert "".join(c.chat_stream([{"role": "user", "content": "x"}])) == "Shalom"


def test_anthropic_separa_system():
    vistos = []

    def m(req):
        vistos.append((req.url.path, req.headers.get("x-api-key"), json.loads(req.content)))
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}]})

    c = ClienteAnthropic(_aj(proveedor="anthropic", url_base="https://a.test/v1", clave="k"),
                         _transporte(m))
    assert c.chat([{"role": "system", "content": "S"}, {"role": "user", "content": "U"}]) == "ok"
    ruta, clave, cuerpo = vistos[0]
    assert ruta == "/v1/messages" and clave == "k"
    assert cuerpo["system"] == "S" and cuerpo["messages"] == [{"role": "user", "content": "U"}]


# --- reparar_json ----------------------------------------------------------------


@pytest.mark.parametrize("texto, esperado", [
    ('{"a": 1}', {"a": 1}),
    ('```json\n{"a": 1}\n```', {"a": 1}),
    ('Claro, aquí tienes: {"a": [1, 2,]} ¡espero que sirva!', {"a": [1, 2]}),
    ("{'a': 'b'}", {"a": "b"}),
    ('{"a": True, "b": None}', {"a": True, "b": None}),
    ('[{"p": "1"}, {"p": "2"},]', [{"p": "1"}, {"p": "2"}]),
    ('{"a": {"b": [1, 2', {"a": {"b": [1, 2]}}),
    ('Respuesta:\n```\n[1, 2, 3]\n```', [1, 2, 3]),
    ('{"texto": "una } llave"}', {"texto": "una } llave"}),
])
def test_reparar_json(texto, esperado):
    assert util.reparar_json(texto) == esperado


def test_reparar_json_imposible():
    with pytest.raises(E.RespuestaInvalida):
        util.reparar_json("no hay json aquí")


def test_trocear():
    texto = "\n\n".join(f"párrafo {i} " + "x" * 90 for i in range(50))
    trozos = util.trocear(texto, max_chars=1000, solape=100)
    assert len(trozos) > 1
    assert all(len(t) <= 1000 for t in trozos)
    assert "párrafo 49" in trozos[-1]


def test_pedir_json_reintenta(servidor):
    respuestas = iter(["esto no es json", '{"ok": true}'])
    servidor(lambda r: httpx.Response(200, json=_ok_openai(next(respuestas))))
    config.fijar("ia", "url_base", "http://ia.test/v1")
    config.fijar("ia", "modelo", "m1")
    assert util.pedir_json("dame", {"ok": True}) == {"ok": True}


def test_resumir_largo_map_reduce(servidor):
    llamadas = []

    def m(req):
        llamadas.append(json.loads(req.content)["messages"][-1]["content"])
        return httpx.Response(200, json=_ok_openai("resumen"))

    servidor(m)
    config.fijar("ia", "url_base", "http://ia.test/v1")
    config.fijar("ia", "modelo", "m1")
    texto = "\n\n".join("y" * 900 for _ in range(10))
    assert util.resumir_largo(texto, "Resume", max_chars=2000) == "resumen"
    assert len(llamadas) > 2 and "RESÚMENES PARCIALES" in llamadas[-1]


# --- prioridad de configuración -----------------------------------------------------


def test_prioridad(monkeypatch):
    assert ajustes.resolver() is None
    config.fijar("ia", "url_base", "http://archivo/v1")
    config.fijar("ia", "modelo", "del-archivo")
    aj = ajustes.resolver()
    assert (aj.url_base, aj.modelo, aj.origen["modelo"]) == ("http://archivo/v1", "del-archivo",
                                                              "config")
    monkeypatch.setenv("ULTRON_MODELO", "del-entorno")
    assert ajustes.resolver().modelo == "del-entorno"
    aj = ajustes.resolver(modelo="del-argumento")
    assert aj.modelo == "del-argumento" and aj.origen["modelo"] == "argumento"
    assert aj.url_base == "http://archivo/v1"


def test_autodeteccion(monkeypatch):
    monkeypatch.setattr(ajustes, "detectar_locales",
                        lambda timeout=0.6: [("ollama", "http://localhost:11434/v1", ["qwen"])])
    aj = ajustes.resolver()
    assert aj.proveedor == "ollama" and aj.modelo == "qwen" and aj.origen["url_base"] == "detectado"


def test_proveedor_rellena_url(monkeypatch):
    monkeypatch.setenv("ULTRON_PROVEEDOR", "groq")
    assert ajustes.resolver().url_base == "https://api.groq.com/openai/v1"


def test_permisos_600():
    ajustes.guardar(_aj(clave="secreta"))
    if os.name == "posix":
        assert stat.S_IMODE(config.ruta().stat().st_mode) == 0o600
    assert config.obtener("ia", "clave") == "secreta"


def test_clave_enmascarada():
    assert _aj(clave="sk-abcdef123456").clave_enmascarada() == "sk-…3456"


def test_modelo_vacio_usa_el_primero(servidor):
    servidor(lambda r: httpx.Response(200, json={"data": [{"id": "b"}, {"id": "a"}]}))
    config.fijar("ia", "url_base", "http://ia.test/v1")
    assert cliente.obtener_cliente().modelo == "a"


# --- CLI ---------------------------------------------------------------------------

runner = CliRunner()


def test_cli_sin_ia_codigo_2():
    r = runner.invoke(app, ["ia", "estado"])
    assert r.exit_code == 2
    assert "ultron ia configurar" in r.output


def test_main_sin_ia_mensaje_y_codigo(monkeypatch, capsys):
    import sys

    from ultron import cli

    monkeypatch.setattr(sys, "argv", ["ultron", "ia", "hola"])
    with pytest.raises(SystemExit) as salida:
        cli.main()
    assert salida.value.code == 2
    assert "Traceback" not in capsys.readouterr().out


def test_cli_pregunta_suelta(servidor):
    sse = 'data: {"choices":[{"delta":{"content":"Shalom"}}]}\n\ndata: [DONE]\n\n'
    servidor(lambda r: httpx.Response(200, text=sse))
    config.fijar("ia", "url_base", "http://ia.test/v1")
    config.fijar("ia", "modelo", "m1")
    r = runner.invoke(app, ["ia", "hola", "qué", "tal"])
    assert r.exit_code == 0, r.output
    assert "Shalom" in r.output


def test_cli_configurar_sin_preguntas(servidor):
    def m(req):
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "llama3.2"}]})
        return httpx.Response(200, json=_ok_openai("OK"))

    servidor(m)
    r = runner.invoke(app, ["ia", "configurar", "--url", "http://ia.test/v1"])
    assert r.exit_code == 0, r.output
    assert config.obtener("ia", "modelo") == "llama3.2"


def test_cli_probar_explica_error(servidor):
    servidor(lambda r: httpx.Response(401, text="bad key"))
    config.fijar("ia", "url_base", "http://ia.test/v1")
    config.fijar("ia", "modelo", "m1")
    r = runner.invoke(app, ["ia", "probar"])
    assert r.exit_code == 1
    assert "clave" in r.output.lower()


def test_doctor_ia(servidor):
    from ultron.ia import chequeos
    from ultron.nucleo.doctor import OpcionesDoctor

    def m(req):
        if req.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "otro"}]})
        return httpx.Response(200, json=_ok_openai("OK"))

    servidor(m)
    config.fijar("ia", "url_base", "http://ia.test/v1")
    config.fijar("ia", "modelo", "m1")
    monkey_crear = cliente.crear
    chequeos.crear = monkey_crear  # usa el transporte falso
    res = {c.nombre: c for c in chequeos._ia(None, OpcionesDoctor())}
    assert res["Modelo existe"].estado == "error" and "otro" in res["Modelo existe"].solucion
