from __future__ import annotations

import json
import zipfile
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest
from falsos import EjecutorFalso
from typer.testing import CliRunner

from ultron.cli import app
from ultron.compartidas import ordenar
from ultron.ia import cliente
from ultron.modos.focus import algoritmos, bm25, datos, estudio, extraer, pomodoro
from ultron.nucleo import config, hosts, panel

runner = CliRunner()


def _pdf(ruta: Path, paginas: list[str]) -> Path:
    """PDF mínimo válido con una línea de texto por página (sin dependencias)."""
    objetos = ["<< /Type /Catalog /Pages 2 0 R >>", ""]
    kids = []
    for i, texto in enumerate(paginas):
        n_pag, n_cont = 3 + i * 2, 4 + i * 2
        kids.append(f"{n_pag} 0 R")
        contenido = f"BT /F1 12 Tf 40 700 Td ({texto}) Tj ET"
        objetos.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       f"/Resources << /Font << /F1 {3 + len(paginas) * 2} 0 R >> >> "
                       f"/Contents {n_cont} 0 R >>")
        objetos.append(f"<< /Length {len(contenido)} >>\nstream\n{contenido}\nendstream")
    objetos[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(paginas)} >>"
    objetos.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    salida = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objetos, 1):
        offsets.append(len(salida))
        salida += f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(salida)
    salida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        salida += f"{off:010d} 00000 n \n".encode()
    salida += (f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF"
               ).encode()
    ruta.write_bytes(salida)
    return ruta


TEXTO_P1 = "La mitocondria produce la energia de la celula mediante la respiracion celular."
TEXTO_P2 = "La fotosintesis ocurre en los cloroplastos y transforma la luz en glucosa."


@pytest.fixture
def pdf(tmp_path):
    return _pdf(tmp_path / "biologia.pdf", [TEXTO_P1, TEXTO_P2])


@pytest.fixture
def ia_falsa(monkeypatch):
    """IA falsa: devuelve en orden las respuestas de la lista (texto o dict → JSON)."""
    def instalar(respuestas):
        cola = list(respuestas)
        vistas: list[str] = []

        def m(req):
            cuerpo = json.loads(req.content)
            vistas.append(cuerpo["messages"][-1]["content"])
            r = cola.pop(0) if len(cola) > 1 else cola[0]
            texto = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
            if cuerpo.get("stream"):
                return httpx.Response(200, text=f'data: {json.dumps({"choices": [{"delta": {"content": texto}}]})}\n\ndata: [DONE]\n\n')
            return httpx.Response(200, json={"choices": [{"message": {"content": texto}}]})

        monkeypatch.setattr(cliente, "TRANSPORTE", httpx.MockTransport(m))
        config.fijar("ia", "url_base", "http://ia.test/v1")
        config.fijar("ia", "modelo", "m")
        return vistas

    return instalar


# --- extracción y búsqueda ----------------------------------------------------------


def test_extraer_pdf_por_paginas(pdf):
    paginas = extraer.extraer(pdf, EjecutorFalso(programas=set()))
    assert [n for n, _ in paginas] == [1, 2]
    assert "mitocondria" in paginas[0][1] and "fotosintesis" in paginas[1][1]


def test_extraer_docx(tmp_path):
    ruta = tmp_path / "a.docx"
    with zipfile.ZipFile(ruta, "w") as z:
        z.writestr("word/document.xml",
                   '<w:document><w:body><w:p><w:r><w:t>Hola &amp; adiós</w:t></w:r></w:p>'
                   '<w:p><w:r><w:t>Segundo</w:t></w:r></w:p></w:body></w:document>')
    assert extraer.extraer(ruta) == [(1, "Hola & adiós\n\nSegundo")]


def test_extraer_formato_no_soportado(tmp_path):
    (tmp_path / "x.exe").write_bytes(b"x")
    with pytest.raises(extraer.ErrorExtraccion, match="no soportado"):
        extraer.extraer(tmp_path / "x.exe")


def test_bm25_trozo_correcto():
    paginas = [(1, TEXTO_P1), (2, TEXTO_P2), (3, "La revolucion francesa empezo en 1789.")]
    mejor = bm25.mejores(paginas, "¿dónde ocurre la fotosíntesis?", 1)
    assert mejor[0][0] == 2
    assert bm25.mejores(paginas, "revoluciones francesas", 1)[0][0] == 3


def test_raiz_espanol():
    assert bm25.raiz("revoluciones") == bm25.raiz("revolucion")
    assert bm25.raiz("celulares")[:5] == "celul"


# --- algoritmos ------------------------------------------------------------------------


def test_sm2_secuencia():
    e = algoritmos.EstadoTarjeta()
    e = algoritmos.sm2(e, 3)
    assert e.intervalo == 1 and e.repeticiones == 1
    e = algoritmos.sm2(e, 3)
    assert e.intervalo == 6
    e = algoritmos.sm2(e, 3)
    assert e.intervalo == round(6 * e.facilidad)
    fallo = algoritmos.sm2(e, 1)
    assert fallo.intervalo == 1 and fallo.repeticiones == 0
    assert fallo.facilidad < e.facilidad
    facil = algoritmos.sm2(algoritmos.EstadoTarjeta(), 4)
    assert facil.intervalo >= 2 and facil.facilidad > 2.5


def test_plan_reparto_y_repasos():
    hoy = date(2026, 12, 1)
    ev = algoritmos.Evento("Matemáticas", hoy + timedelta(days=10),
                           ["derivadas", "integrales", "límites"], horas=12)
    plan = algoritmos.generar_plan([ev], hoy)
    assert len(plan) == 10 and hoy + timedelta(days=10) not in plan
    total = sum(b.horas for bloques in plan.values() for b in bloques)
    assert abs(total - 12) < 0.1
    ultimos = [plan[hoy + timedelta(days=d)][0] for d in (8, 9)]
    assert all(b.tipo == "repaso final" for b in ultimos)
    assert ultimos[0].horas == pytest.approx(2 * plan[hoy][0].horas)
    estudiados = [b.tema for bs in plan.values() for b in bs if b.tipo == "estudio"]
    assert {"derivadas", "integrales", "límites"} <= set(", ".join(estudiados).split(", "))
    assert plan[hoy][0].tipo == "estudio"
    assert plan[hoy + timedelta(days=1)][0].tipo == "repaso"  # repaso a 1 día


def test_plan_examen_pasado_se_ignora():
    hoy = date(2026, 12, 1)
    assert algoritmos.generar_plan([algoritmos.Evento("X", hoy)], hoy) == {}


def test_rachas_y_mapa_calor():
    hoy = date(2026, 12, 3)
    dias = {hoy, hoy - timedelta(days=1), hoy - timedelta(days=2), hoy - timedelta(days=10),
            hoy - timedelta(days=11)}
    assert algoritmos.rachas(dias, hoy) == (3, 3)
    mapa = algoritmos.mapa_calor({hoy: 150, hoy - timedelta(days=1): 20}, hoy, semanas=4)
    assert len(mapa) == 7 and len(mapa[0]) == 4
    assert mapa[hoy.weekday()][-1] == 4
    assert mapa[(hoy - timedelta(days=1)).weekday()][-1] == 1
    assert mapa[6][-1] == -1  # el domingo de esta semana aún no ha llegado


# --- estudio con IA ---------------------------------------------------------------------


def test_flashcards_json_roto_y_dedup(pdf, ia_falsa):
    ia_falsa(['Aquí tienes:\n```json\n{"tarjetas": [{"pregunta": "¿Qué produce la mitocondria?", '
              '"respuesta": "Energía", "pagina": 1}, {"pregunta": "¿Que produce la mitocondria?", '
              '"respuesta": "ATP", "pagina": 1},]}\n```'])
    tarjetas = estudio.generar_tarjetas(pdf, 5)
    assert len(tarjetas) == 1 and tarjetas[0]["pagina"] == 1
    assert estudio.generar_tarjetas(pdf, 5) == tarjetas  # cacheado


def test_exportar_anki(tmp_path):
    salida = estudio.exportar_anki("Biología", [{"pregunta": "a", "respuesta": "b",
                                                  "pagina": 1}], tmp_path / "m.apkg")
    assert zipfile.is_zipfile(salida)


def test_examen_normaliza(pdf, ia_falsa):
    ia_falsa([{"preguntas": [
        {"tipo": "test", "pregunta": "¿Dónde ocurre la fotosíntesis?",
         "opciones": ["núcleo", "cloroplasto", "ribosoma", "pared"], "correcta": "1", "pagina": 2},
        {"tipo": "corta", "pregunta": "¿Qué hace la mitocondria?", "respuesta": "energía"},
        {"basura": True},
    ]}])
    preguntas = estudio.generar_examen(pdf, 5, "mixto")
    assert [p["tipo"] for p in preguntas] == ["test", "corta"]
    assert preguntas[0]["correcta"] == 1


def test_pregunta_contexto_cita_paginas(pdf):
    prompt, paginas = estudio.contexto_pregunta(pdf, "¿qué hace la fotosíntesis?")
    assert paginas[0] == 2 and "[p. 2]" in prompt


def test_esquema_podado_y_mermaid(pdf, ia_falsa, tmp_path):
    ia_falsa([{"concepto": "Célula", "hijos": [{"concepto": "Mitocondria", "hijos": [
        {"concepto": "ATP", "hijos": [{"concepto": "demasiado hondo", "hijos": []}]}]}]}])
    arbol = estudio.generar_esquema(pdf)
    assert arbol["hijos"][0]["hijos"][0]["hijos"] == []
    assert estudio.a_mermaid(arbol).startswith("mindmap")
    png = estudio.a_png(arbol, tmp_path / "e.png", {})
    assert png.exists()


def test_cli_resumen(pdf, ia_falsa):
    ia_falsa(["**Resumen**: la célula obtiene energía."])
    r = runner.invoke(app, ["resumen", str(pdf), "--nivel", "corto", "--guardar"])
    assert r.exit_code == 0, r.output
    assert pdf.with_suffix(".resumen.md").exists()


def test_cli_flashcards_y_lista(pdf, ia_falsa):
    ia_falsa([{"tarjetas": [{"pregunta": "p1", "respuesta": "r1", "pagina": 1}]}])
    r = runner.invoke(app, ["flashcards", str(pdf)])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["flashcards", "lista"])
    assert "biologia" in r.output


# --- pomodoro ---------------------------------------------------------------------------


class RelojFalso:
    def __init__(self):
        self.t = 1000.0

    def ahora(self):
        return self.t

    def dormir(self, s):
        self.t += s


def test_pomodoro_bloquea_y_desbloquea(tmp_path, monkeypatch):
    archivo_hosts = tmp_path / "hosts"
    archivo_hosts.write_text("127.0.0.1 localhost\n", encoding="utf-8")
    monkeypatch.setattr(hosts, "HOSTS", archivo_hosts)
    estados = []

    def tick(f):
        estados.append((f.nombre, hosts.activo(pomodoro.ETIQUETA, archivo_hosts)))
        assert panel.leer()["pomodoro"]["fase"] == f.nombre

    trabajados = pomodoro.ejecutar(minutos=0.05, descanso=0.05, ciclos=2, ej=EjecutorFalso(),
                                   reloj=RelojFalso(), al_tick=tick, lista_webs=["youtube.com"])
    assert trabajados == pytest.approx(0.1)
    assert ("trabajo", True) in estados and ("descanso", False) in estados
    assert archivo_hosts.read_text(encoding="utf-8") == "127.0.0.1 localhost\n"
    assert "pomodoro" not in panel.leer()


def test_pomodoro_ctrl_c_desbloquea(tmp_path, monkeypatch):
    archivo_hosts = tmp_path / "hosts"
    archivo_hosts.write_text("", encoding="utf-8")
    monkeypatch.setattr(hosts, "HOSTS", archivo_hosts)

    def interrumpir(_f):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        pomodoro.ejecutar(minutos=1, ciclos=1, ej=EjecutorFalso(), reloj=RelojFalso(),
                          al_tick=interrumpir, lista_webs=["x.com"])
    assert not hosts.activo(pomodoro.ETIQUETA, archivo_hosts)


def test_digitos_grandes():
    filas = pomodoro.digitos_grandes("18:42")
    assert len(filas) == 5 and all(filas)


# --- stats / repasar demo ------------------------------------------------------------------


def test_cli_demos():
    r = runner.invoke(app, ["stats", "--demo"])
    assert r.exit_code == 0, r.output
    assert "racha" in r.output and "■" in r.output
    r = runner.invoke(app, ["repasar", "--demo"])
    assert r.exit_code == 0, r.output
    assert "mitocondria" in r.output.lower()


def test_cli_plan():
    hoy = date.today()
    r = runner.invoke(app, ["plan", "añadir", "Historia", (hoy + timedelta(days=5)).isoformat(),
                            "--temas", "tema 1, tema 2", "--horas", "5"])
    assert r.exit_code == 0, r.output
    r = runner.invoke(app, ["plan", "ver", "--dias", "6"])
    assert "Historia" in r.output and "EXAMEN" in r.output
    r = runner.invoke(app, ["plan", "hoy"])
    assert "Historia" in r.output


def test_repasar_guarda_sm2():
    estudio.guardar_tarjetas("m", [{"pregunta": "p", "respuesta": "r", "pagina": 1}])
    r = runner.invoke(app, ["repasar", "m"])
    assert r.exit_code == 0, r.output
    with datos.conectar() as con:
        fila = con.execute("select * from tarjetas").fetchone()
        assert fila["intervalo"] == 1 and fila["proxima"]
        assert con.execute("select count(*) from revisiones").fetchone()[0] == 1


# --- ordenar ---------------------------------------------------------------------------------


@pytest.fixture
def desorden(tmp_path):
    d = tmp_path / "Descargas"
    d.mkdir()
    for nombre in ("apuntes-mates.pdf", "foto.jpg", "cancion.mp3", "script.py", "raro.xyz"):
        (d / nombre).write_bytes(b"x")
    (d / "Universidad").mkdir()
    (d / ".oculto").write_bytes(b"x")
    return d


def test_ordenar_sin_ia_y_deshacer(desorden):
    archivos = ordenar.inventario(desorden, con_extracto=False)
    assert ".oculto" not in {a.rel for a in archivos}
    plan = ordenar.plan_reglas(archivos)
    assert plan["foto.jpg"] == "Imágenes" and plan["raro.xyz"] == "Otros"
    diario = ordenar.aplicar(desorden, plan)
    assert (desorden / "Imágenes" / "foto.jpg").exists()
    assert len(diario["movimientos"]) == 5
    assert ordenar.deshacer() == 5
    assert (desorden / "foto.jpg").exists() and not (desorden / "Imágenes").exists()
    assert (desorden / "Universidad").exists()


def test_ordenar_conflicto_de_nombre(desorden):
    (desorden / "Imágenes").mkdir()
    (desorden / "Imágenes" / "foto.jpg").write_bytes(b"previa")
    ordenar.aplicar(desorden, {"foto.jpg": "Imágenes"})
    assert (desorden / "Imágenes" / "foto (2).jpg").exists()
    assert (desorden / "Imágenes" / "foto.jpg").read_bytes() == b"previa"


@pytest.mark.parametrize("destino, esperado", [
    ("Universidad/Matemáticas", "Universidad/Matemáticas"),
    ("/etc/passwd", None), ("../fuera", None), ("a/../../b", None), ("C:/Windows", None),
    ("~/x", None), ("a/b/c/d", None), (".oculta", None), ("", None), (5, None),
    ("Docs\\Trabajo", "Docs/Trabajo"),
])
def test_validar_destino(destino, esperado):
    assert ordenar.validar_destino(destino) == esperado


def test_ordenar_con_ia(desorden, ia_falsa):
    ia_falsa([{"asignaciones": {"apuntes-mates.pdf": "Universidad/Matemáticas",
                                "foto.jpg": "../../fuera", "inventado.txt": "X"}}])
    archivos = ordenar.inventario(desorden, con_extracto=False)
    plan = ordenar.plan_ia(archivos, desorden)
    assert plan["apuntes-mates.pdf"] == "Universidad/Matemáticas"
    assert plan["foto.jpg"] == "Imágenes"  # destino peligroso → regla por tipo
    assert "inventado.txt" not in plan


def test_cli_ordenar_simular_no_mueve(desorden):
    r = runner.invoke(app, ["ordenar", str(desorden), "--sin-ia", "--simular"])
    assert r.exit_code == 0, r.output
    assert "Imágenes" in r.output and (desorden / "foto.jpg").exists()


def test_cli_ordenar_y_deshacer(desorden):
    r = runner.invoke(app, ["ordenar", str(desorden), "--sin-ia", "--si"])
    assert r.exit_code == 0, r.output
    assert (desorden / "Música" / "cancion.mp3").exists()
    r = runner.invoke(app, ["ordenar", "--deshacer"])
    assert r.exit_code == 0, r.output
    assert (desorden / "cancion.mp3").exists()


# --- recursos -----------------------------------------------------------------------------------


def test_generar_recursos(tmp_path):
    from ultron.modos.focus import generar_recursos

    f = generar_recursos.fondo(tmp_path / "f.png", 640, 360)
    c = generar_recursos.campana(tmp_path / "c.wav", 0.2)
    from PIL import Image

    assert Image.open(f).size == (640, 360)
    import wave

    with wave.open(str(c)) as w:
        assert w.getnframes() == int(44100 * 0.2)
