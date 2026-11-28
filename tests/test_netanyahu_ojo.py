"""Configuración, catálogos y parche local del Ojo de Dios."""

import os
from urllib.parse import parse_qs, urlsplit

import pytest
from falsos import EjecutorFalso
from typer.testing import CliRunner

from ultron.cli import app
from ultron.modos.netanyahu.funciones import ojo, ojo_camaras, ojo_parche
from ultron.nucleo import config


def test_clave_sin_exposicion_y_con_simulacion():
    runner = CliRunner()
    assert runner.invoke(app, ["--simular", "ojo", "clave", "cesium", "simulada"]).exit_code == 0
    assert not config.ruta().exists()
    config.fijar("ia", "modelo", "local")
    resultado = runner.invoke(app, ["ojo", "clave", "tomtom", "secreto-prueba"])
    assert resultado.exit_code == 0
    assert "secreto-prueba" not in resultado.output
    datos = config.leer()
    assert datos["ia"]["modelo"] == "local"
    assert ojo.entorno_servidor(datos["ojo"]) == {"TOMTOM_API_KEY": "secreto-prueba"}
    if os.name != "nt":
        assert config.ruta().stat().st_mode & 0o777 == 0o600


def test_servidor_recibe_claves_fuera_del_comando(tmp_path, monkeypatch):
    ejecutor = ojo.Ejecutor()
    capturado = {}

    def ejecutar(cmd, **opciones):
        capturado.update(opciones)
        return ojo.Resultado(0, "1234", "")

    monkeypatch.setattr(ejecutor, "_ejecutar", ejecutar)
    orden = ["npm", "run", "dev", "--", "--port", "4173", "--strictPort", "--host", "127.0.0.1"]
    ojo.lanzar(ejecutor, tmp_path, tmp_path / "ojo.log", {"tomtom": "secreto"})
    assert capturado["entorno"]["TOMTOM_API_KEY"] == "secreto"
    assert capturado["fondo"] is True
    assert ejecutor.historial == [orden]
    simulado = EjecutorFalso(simular=True)
    ojo.lanzar(simulado, tmp_path, tmp_path / "ojo.log", {"tomtom": "secreto"})
    assert simulado.historial == [orden]


def test_apertura_espana_y_calidad(monkeypatch):
    llamadas = []
    monkeypatch.setattr(ojo, "_abrir", lambda ctx, kiosko, url, **kw: llamadas.append(url))
    runner = CliRunner()
    assert runner.invoke(app, ["ojo", "--calidad", "baja"]).exit_code == 0
    assert runner.invoke(app, ["ojo", "abrir", "--calidad", "media"]).exit_code == 0
    assert runner.invoke(app, ["ojo", "--calidad", "inválida"]).exit_code == 2
    for url, calidad in zip(llamadas, ("baja", "media"), strict=True):
        partes = urlsplit(url)
        assert parse_qs(partes.query)["ultronCalidad"] == [calidad]
        assert parse_qs(partes.fragment)["heading"] == ["18"]


def test_parche_detecta_cambio_incompatible(tmp_path, monkeypatch):
    archivo = tmp_path / "src" / "prueba.js"
    archivo.parent.mkdir()
    archivo.write_text("const ejemplo = 1;\n", encoding="utf-8")
    monkeypatch.setattr(ojo_parche, "EDICIONES", {
        "src/prueba.js": (("const ejemplo = 1;", "const ejemplo = 2;"),),
    })
    parche = ojo_parche.generar_parche(tmp_path)
    assert "--- a/src/prueba.js" in parche
    assert "+const ejemplo = 2;" in parche
    assert "new file mode 100644" in parche
    assert "failIfMajorPerformanceCaveat" in parche
    archivo.write_text("const ejemplo = 3;\n", encoding="utf-8")
    with pytest.raises(ValueError, match="src/prueba.js"):
        ojo_parche.generar_parche(tmp_path)


def test_camaras_dgt_descarta_dispositivos_y_hosts_no_permitidos():
    def dispositivo(tipo, url):
        return f"""<d:device><d:typeOfDevice>{tipo}</d:typeOfDevice>
        <d:latitude>42.3</d:latitude><d:longitude>-0.42</d:longitude>
        <d:roadName>A-23</d:roadName><d:deviceUrl>{url}</d:deviceUrl></d:device>"""

    url = ojo_camaras.PREFIJOS["dgt"] + "168408.jpg"
    contenido = "<d:publicacion xmlns:d='urn:datex'>" + "".join([
        dispositivo("camera", url),
        dispositivo("camera", "https://otro.example/168408.jpg"),
        dispositivo("vms", ojo_camaras.PREFIJOS["dgt"] + "99.jpg"),
    ]) + "</d:publicacion>"
    registros = ojo_camaras._camaras(contenido.encode(), "dgt")
    assert [r["snapshotUrl"] for r in registros] == [url]
    assert registros[0]["credit"] == "Dirección General de Tráfico"


def test_camara_madrid_kml_con_atribucion():
    contenido = b"""<kml xmlns="http://www.opengis.net/kml/2.2"><Document><Placemark>
      <name>Gran Via</name>
      <description><![CDATA[<img src="../Camaras/Camara00079.jpg">]]></description>
      <Point><coordinates>-3.70,40.42,0</coordinates></Point>
      </Placemark></Document></kml>"""
    registro, = ojo_camaras._camaras(contenido, "madrid")
    assert registro["provider"] == "Ayuntamiento de Madrid"
    assert registro["license"] == "CC BY 4.0"
    assert registro["url"] == ojo_camaras.PREFIJOS["madrid"] + "Camara00079.jpg"


def test_catalogo_rechaza_entidades_xml():
    with pytest.raises(ValueError, match="XML externas"):
        ojo_camaras._camaras(b'<!DOCTYPE a [<!ENTITY b "contenido">]><a/>', "dgt")
