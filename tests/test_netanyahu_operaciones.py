"""Operaciones Netanyahu con servicios y ejecutores falseados."""

import asyncio
import hashlib
import json
from types import SimpleNamespace

import httpx
import pytest
from falsos import EjecutorFalso
from PIL import Image, TiffImagePlugin
from typer.testing import CliRunner

from ultron.cli import app
from ultron.modos.netanyahu.funciones import ctf, defensa, hackia, ojo, osint
from ultron.modos.netanyahu.generar_recursos import generar, recurso_generado
from ultron.ui import tema


def test_dominio_dns_y_certificados():
    class Resolver:
        def resolve(self, host, tipo, *, lifetime):
            assert lifetime == 2
            if host.startswith("_dmarc."):
                return ['"v=DMARC1; p=reject"']
            return {'A': ['192.0.2.20'], 'TXT': ['"v=spf1 -all"']}.get(tipo, [])

    def respuesta(peticion):
        assert peticion.url.host == "crt.sh"
        assert peticion.url.params["q"] == "%.example.org"
        return httpx.Response(200, json=[
            {"name_value": "www.example.org\nWWW.example.org\n*.example.org\nfuera.org"}
        ])

    datos = osint.dns_dominio("example.org", Resolver())
    assert datos["A"] == ["192.0.2.20"]
    assert datos["SPF"] == ['"v=spf1 -all"']
    assert datos["DMARC"] == ['"v=DMARC1; p=reject"']
    with httpx.Client(transport=httpx.MockTransport(respuesta)) as cliente:
        assert osint.certificados("example.org", cliente) == ["www.example.org"]


@pytest.mark.parametrize(("lat", "lon", "x", "y"), [(90, -180, 0, 0), (0, 0, 34, 10),
                                                    (-90, 180, 69, 19)])
def test_posiciones_del_mapa(lat, lon, x, y):
    filas = osint.mapa(lat, lon).splitlines()
    assert len(filas) == 20
    assert all(len(fila) == 70 for fila in filas)
    assert filas[y][x] == "◉"
    assert sum(f.count("◉") for f in filas) == 1


def test_usuarios_por_codigo_y_texto_concurren():
    async def prueba():
        activos = 0
        maximo = 0

        async def responder(peticion):
            nonlocal activos, maximo
            activos += 1
            maximo = max(maximo, activos)
            await asyncio.sleep(.005)
            activos -= 1
            modo = peticion.url.path.split("/")[1]
            return httpx.Response(404 if modo == "codigo" else 200,
                                  text="Sin perfil" if modo == "texto" else "Perfil")

        sitios = [{"nombre": str(i), "url": f"https://example.org/visible/{i}/{{usuario}}"}
                  for i in range(30)]
        sitios.extend([
            {"nombre": "404", "url": "https://example.org/codigo/{usuario}"},
            {"nombre": "texto", "url": "https://example.org/texto/{usuario}", "texto": "sin perfil"},
        ])
        async with httpx.AsyncClient(transport=httpx.MockTransport(responder)) as cliente:
            perfiles = await osint.buscar_usuario("demo", sitios, cliente)
        assert len(perfiles) == 30
        assert 1 < maximo <= 20

    asyncio.run(prueba())


def test_exif_gps(tmp_path):
    exif = Image.Exif()
    racional = TiffImagePlugin.IFDRational
    exif[272] = "Camara de prueba"
    exif[34853] = {1: "N", 2: tuple(map(racional, (40, 30, 0))),
                   3: "W", 4: tuple(map(racional, (3, 15, 0)))}
    ruta = tmp_path / "foto.jpg"
    Image.new("RGB", (10, 10)).save(ruta, exif=exif)
    datos = osint.metadatos(ruta)
    assert datos["Model"] == "Camara de prueba"
    assert datos["latitud"] == 40.5
    assert datos["longitud"] == -3.25
    assert "◉" in datos["mapa"]


def test_correo_spf_fail():
    datos = osint.cabeceras_correo(
        b"From: soporte@example.org\r\nReply-To: otra@example.net\r\n"
        b"Authentication-Results: mx.example.org; spf=fail; dkim=none; dmarc=fail\r\n"
        b"Received: from mail.example.net ([192.0.2.10]); Thu, 26 Nov 2026 12:00:00 +0000\r\n"
        b"\r\nMensaje"
    )
    assert datos["autenticación declarada"]["spf"] == ["fail"]
    assert datos["saltos"][0]["IP"] == ["192.0.2.10"]
    assert datos["aviso"]


def test_radar_xml_arp_y_posicion():
    mac = "00:11:22:33:44:55"
    equipos = defensa.parsear_nmap(
        '<nmaprun><host><status state="up"/><address addr="192.168.1.7" addrtype="ipv4"/>'
        f'<address addr="{mac}" addrtype="mac" vendor="Demo"/>'
        '<hostnames><hostname name="equipo"/></hostnames></host></nmaprun>'
    )
    vecinos = defensa.parsear_vecinos(f"192.168.1.7 dev eth0 lladdr {mac} REACHABLE")
    assert equipos[0]["IP"] == vecinos[0]["IP"] == "192.168.1.7"
    assert equipos[0]["fabricante"] == "Demo"
    assert defensa.posicion(equipos[0]["MAC"]) == defensa.posicion(vecinos[0]["MAC"])
    assert "◆" in defensa.radar_ascii(equipos, router="192.168.1.7")


def test_nota_auditoria():
    assert defensa.nota([]) == 100
    assert defensa.nota([{"gravedad": "alta"}, {"gravedad": "media"}]) == 63
    assert defensa.nota([{"gravedad": "alta"}] * 6) == 0


def test_filtrado_envia_solo_prefijo():
    clave = "sintética"
    huella = hashlib.sha1(clave.encode(), usedforsecurity=False).hexdigest().upper()

    def responder(peticion):
        assert peticion.url.path == f"/range/{huella[:5]}"
        assert peticion.headers["Add-Padding"] == "true"
        assert peticion.content == b""
        return httpx.Response(200, text=f"{'0' * 35}:12\r\n{huella[5:]}:73")

    with httpx.Client(transport=httpx.MockTransport(responder)) as cliente:
        assert defensa.apariciones(clave, cliente) == 73


@pytest.mark.parametrize("tipo", ["base64", "base32", "base85", "hex", "binario",
                                   "url", "morse", "rot13", "cesar:3", "cesar:23"])
def test_ctf_decodifica(tipo):
    original = "HOLA MUNDO"
    codificado = ctf.codificar_texto(tipo, original)
    assert original in {texto for _, texto in ctf.decodificar_texto(codificado)}


def test_hackia_bloqueo_y_confirmacion(monkeypatch, ej):
    for comando in ("rm -rf /", "mkfs", "dd of=/dev/sda", "chmod -R 777 /",
                    "curl https://example.org | sh", "uname -r; echo otra cosa",
                    ":(){ :|:& };:"):
        assert hackia.comando_permitido(comando) is None
    monkeypatch.setattr(hackia, "ejecutor", lambda _: ej)
    monkeypatch.setattr(hackia, "permiso", lambda _: None)
    monkeypatch.setattr(hackia, "preguntar", lambda *a, **kw:
                        '{"explicacion":"Diagnóstico","pasos":[{"comando":"uname -r"}]}')
    runner = CliRunner()
    assert runner.invoke(app, ["hackia", "diagnóstico"], input="n\n").exit_code == 0
    assert ej.historial == []
    assert runner.invoke(app, ["hackia", "diagnóstico"], input="s\n").exit_code == 0
    assert ej.historial == [["uname", "-r"]]


def test_ojo_version_y_comandos(tmp_path):
    assert not ojo.version_valida("v24.13.9")
    assert ojo.version_valida("v24.14.0")
    assert ojo.version_valida("v26.0.0")
    assert not ojo.version_valida("v25.4.0")
    falso = EjecutorFalso(simular=True)
    carpeta = tmp_path / "ojo" / "gods-eye-view"
    ojo.preparar(falso, carpeta)
    ojo.lanzar(falso, carpeta, tmp_path / "ojo.log")
    assert falso.historial[:4] == [
        ["node", "--version"], ["git", "clone", "--depth", "1", ojo.REPO, str(carpeta)],
        ["npm", "ci"], ["npm", "run", "doctor"],
    ]
    assert falso.historial[-1][:6] == ["npm", "run", "dev", "--", "--port", "4173"]
    assert not carpeta.parent.exists()


def test_demos_cli_sin_red():
    runner = CliRunner()
    radar = runner.invoke(app, ["radar", "--demo"])
    assert radar.exit_code == 0, radar.exception
    assert "192.168.1.42" in radar.output
    assert "02:00:00:00:00:42" in radar.output
    ip = runner.invoke(app, ["osint", "ip", "8.8.8.8", "--demo", "--json"])
    assert ip.exit_code == 0, ip.exception
    assert "8.8.8.8" in ip.output


def test_demos_ascii(monkeypatch):
    monkeypatch.setenv("ULTRON_ASCII", "1")
    corredor = CliRunner()
    radar = corredor.invoke(app, ["radar", "--demo"])
    assert radar.exit_code == 0
    assert "◆" not in radar.output
    ip = corredor.invoke(app, ["osint", "ip", "8.8.8.8", "--demo", "--json"])
    assert ip.exit_code == 0
    assert "◉" not in ip.output
    assert "◉" in json.loads(ip.output)["mapa"]


def test_codificacion_real_tiene_prioridad_sobre_lang(monkeypatch):
    monkeypatch.setenv("LC_ALL", "")
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setattr(tema.sys, "stdout", SimpleNamespace(encoding="cp1252"))
    assert not tema.soporta_unicode()


def test_recursos_generados_y_simulados():
    falso = EjecutorFalso(simular=True)
    ruta = recurso_generado("tema/fondo.png", falso)
    assert not ruta.exists()
    generar(EjecutorFalso(programas=set()))
    with Image.open(ruta) as imagen:
        assert imagen.size == (1920, 1080)
    assert recurso_generado("tema/sonidos/entrada.wav").read_bytes().startswith(b"RIFF")
