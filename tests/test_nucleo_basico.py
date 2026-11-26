from __future__ import annotations

import pytest
from typer.testing import CliRunner

from ultron.capas import shell
from ultron.capas.base import Contexto
from ultron.cli import app
from ultron.nucleo import config, registro
from ultron.nucleo.esquema import ErrorEsquema, cargar
from ultron.ui import banner, tema

MODOS = ["netanyahu", "focus", "gaming", "presentacion", "fantasma"]


def test_cinco_modos_en_orden():
    assert registro.ids()[:5] == MODOS


def test_obtener_sugiere_parecido():
    with pytest.raises(registro.ModoNoEncontrado, match="netanyahu"):
        registro.obtener("netanyau")


@pytest.mark.parametrize(
    "contenido, mensaje",
    [
        ("nombre: X\n", "falta la clave obligatoria «id»"),
        ("id: Mal Id\nnombre: X\n", "inválido"),
        ("id: ok\nnombre: X\ncapas: [1, 2]\n", "«capas» debe ser"),
        ("id: ok\nnombre: X\ncapas:\n  shell: 3\n", "«shell» debe ser"),
        ("id: ok\nnombre: [\n", "YAML inválido"),
        ("- a\n- b\n", "diccionario"),
    ],
)
def test_esquema_errores_claros(tmp_path, contenido, mensaje):
    f = tmp_path / "modo.yaml"
    f.write_text(contenido, encoding="utf-8")
    with pytest.raises(ErrorEsquema, match=mensaje):
        cargar(f)


def test_recurso_usuario_tiene_prioridad(tmp_home):
    modo = registro.obtener("netanyahu")
    assert modo.recurso("tema.toml") == modo.dir / "tema.toml"
    propio = modo.dir_usuario() / "tema" / "fondo.png"
    propio.parent.mkdir(parents=True)
    propio.write_bytes(b"x")
    assert modo.recurso("tema/fondo.png") == propio


@pytest.mark.parametrize("id_modo", MODOS)
def test_temas_completos(id_modo):
    t = tema.cargar_tema(id_modo)
    for clave in ("primario", "secundario", "acento", "ok", "aviso", "error", "apagado", "texto"):
        assert t.paleta.get(clave, "").startswith("#"), clave
    assert t.banner and t.banner_compacto and t.prompt
    assert t.glifos.get("marca")
    lineas = banner.lineas_banner(t, 120)
    assert len(lineas) >= 1


def test_fallback_ascii(monkeypatch):
    monkeypatch.setenv("ULTRON_ASCII", "1")
    t = tema.cargar_tema("netanyahu")
    assert t.glifo("marca") == "*"
    assert t.glifo("ok") == "+"
    texto = "\n".join(linea.plain for linea in banner.lineas_banner(t, 120))
    assert "SHALOM" in texto and "שלום" not in texto


def test_banner_compacto_en_terminal_estrecha():
    t = tema.cargar_tema("gaming")
    assert len(banner.lineas_banner(t, 60)) < len(banner.lineas_banner(t, 120))


def test_degradado():
    assert banner.interpolar(["#000000", "#ffffff"], 0.5) == "#808080"
    assert banner.interpolar(["#ff0000", "#00ff00", "#0000ff"], 1.0) == "#0000ff"


def test_config_permisos_y_roundtrip():
    config.fijar("ia", "modelo", "llama3.2")
    assert config.obtener("ia", "modelo") == "llama3.2"
    import os
    import stat

    if os.name == "posix":
        assert stat.S_IMODE(config.ruta().stat().st_mode) == 0o600


# --- capa shell ----------------------------------------------------------------


def _ctx(id_modo="netanyahu"):
    modo = registro.obtener(id_modo)
    return Contexto(modo=modo, dir_modo=modo.dir)


def test_prompt_renderizado():
    t = tema.cargar_tema("netanyahu")
    ps1 = shell.renderizar_prompt(t.prompt, t, "NETANYAHU")
    assert "\\u" in ps1 and "\\w" in ps1 and "$(__ultron_extra)" in ps1
    assert "38;2;" in ps1 and "{c:" not in ps1


def test_shell_idempotente_y_restaura(ej, tmp_home):
    bashrc = tmp_home / ".bashrc"
    original = "export A=1"  # sin salto final a propósito
    bashrc.write_text(original, encoding="utf-8")
    capa = shell.CapaShell(ej, _ctx())
    cfg = {"alias": {"op": "ultron osint"}, "historial": False}
    previo = capa.capturar(cfg)
    capa.aplicar(cfg)
    capa.aplicar(cfg)  # idempotente
    texto = bashrc.read_text(encoding="utf-8")
    assert texto.count(shell.INICIO) == 1
    sh = shell.ruta_sh().read_text(encoding="utf-8")
    assert "alias op='ultron osint'" in sh
    assert "HISTFILE=/dev/null" in sh
    capa.restaurar(previo)
    assert bashrc.read_text(encoding="utf-8") == original
    assert not shell.ruta_sh().exists()


def test_shell_respeta_bloque_previo(ej, tmp_home):
    bashrc = tmp_home / ".bashrc"
    bashrc.write_text("x\n" + shell.bloque_bashrc(), encoding="utf-8")
    capa = shell.CapaShell(ej, _ctx("focus"))
    previo = capa.capturar({})
    capa.aplicar({})
    capa.restaurar(previo)
    assert shell.INICIO in bashrc.read_text(encoding="utf-8")


def test_prompt_extra(tmp_home):
    import time

    from ultron.nucleo import panel
    from ultron.prompt_extra import texto

    assert texto() == ""
    ahora = time.time()
    panel.escribir(pomodoro={"fin": ahora + 125, "total": 1500}, tareas={"total": 8, "hechas": 3})
    salida = texto(ahora)
    assert "02:05" in salida and "3/8" in salida


# --- CLI -------------------------------------------------------------------------

runner = CliRunner()


def test_cli_modos():
    r = runner.invoke(app, ["modos"])
    assert r.exit_code == 0, r.output
    for nombre in ("NETANYAHU", "FOCUS", "GAMING", "FANTASMA"):
        assert nombre in r.output


def test_cli_entrar_simular_no_cambia(tmp_home):
    r = runner.invoke(app, ["entrar", "netanyahu", "--simular"])
    assert r.exit_code == 0, r.output
    assert "simular" in r.output.lower()
    assert not (tmp_home / ".bashrc").exists()


def test_cli_entrar_salir_real_en_home_temporal(tmp_home):
    r = runner.invoke(app, ["entrar", "focus", "--si"])
    assert r.exit_code == 0, r.output
    assert shell.ruta_sh().exists()
    r = runner.invoke(app, ["estado"])
    assert "FOCUS" in r.output
    r = runner.invoke(app, ["salir"])
    assert r.exit_code == 0, r.output
    assert not shell.ruta_sh().exists()


def test_cli_detalle_y_doctor():
    r = runner.invoke(app, ["modos", "-d", "gaming"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["doctor", "--sin-ia"])
    assert r.exit_code in (0, 1), r.output
    assert "Sistema operativo" in r.output
