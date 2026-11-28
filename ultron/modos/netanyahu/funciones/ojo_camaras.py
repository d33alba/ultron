"""Catálogos públicos de cámaras de tráfico para el proxy de God's Eye View."""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from time import time
from urllib.parse import urljoin

import httpx

from ultron.nucleo.ejecutor import Ejecutor

MADRID = "https://informo.madrid.es/informo/tmadrid/CCTV.kml"
DGT = "https://nap.dgt.es/datex2/v3/dgt/DevicePublication/camaras_datex2_v37.xml"
MAX_BYTES = 8 * 1024 * 1024
PREFIJOS = {
    "dgt": "https://etraffic.dgt.es/camarasEtraffic/",
    "madrid": "https://informo.madrid.es/informo/Camaras/",
}


def _descargar(cliente: httpx.Client, url: str) -> bytes:
    contenido = bytearray()
    with cliente.stream("GET", url) as respuesta:
        respuesta.raise_for_status()
        for trozo in respuesta.iter_bytes(65536):
            contenido.extend(trozo)
            if len(contenido) > MAX_BYTES:
                raise ValueError("Catálogo demasiado grande.")
    return bytes(contenido)


def _xml(contenido: bytes) -> ET.Element:
    limpio = contenido.decode("utf-8-sig")
    if re.search(r"<!\s*(DOCTYPE|ENTITY)", limpio, re.IGNORECASE):
        raise ValueError("El catálogo contiene declaraciones XML externas.")
    return ET.fromstring(limpio)


def _camaras(contenido: bytes, fuente: str) -> list[dict]:
    dgt = fuente == "dgt"
    organismo = "Dirección General de Tráfico" if dgt else "Ayuntamiento de Madrid"
    licencia = "Creative Commons Attribution" if dgt else "CC BY 4.0"
    registros = {}
    for nodo in _xml(contenido).iterfind(".//{*}" + ("device" if dgt else "Placemark")):
        leer = nodo.findtext
        if dgt:
            if leer(".//{*}typeOfDevice") != "camera":
                continue
            url = leer(".//{*}deviceUrl", "").strip()
            posicion = [leer(".//{*}longitude", ""), leer(".//{*}latitude", "")]
            nombre = " ".join(leer(".//{*}" + c, "") for c in
                              ("roadName", "kilometerPoint", "province")).strip()
        else:
            descripcion = leer(".//{*}description", "")
            imagen = re.search(r"""<img\b[^>]*?\bsrc\s*=\s*["']?([^"'\s>]+)""",
                               descripcion, re.IGNORECASE)
            url = urljoin(MADRID, imagen[1]).replace(
                "http://informo.madrid.es/", "https://informo.madrid.es/", 1
            ) if imagen else ""
            posicion = leer(".//{*}Point/{*}coordinates", "").strip().split(",")[:2]
            nombre = leer("{*}name", "").strip()
        if not re.fullmatch(re.escape(PREFIJOS[fuente]) +
                            r"(?:[\w-]+/)*[\w.-]+\.(?:jpe?g|png|gif)", url, re.ASCII):
            continue
        try:
            lon, lat = map(float, posicion)
        except ValueError:
            continue
        if not (-19 <= lon <= 5 and 27 <= lat <= 44):
            continue
        identificador = fuente + "-" + url.removeprefix(PREFIJOS[fuente]).replace("/", "-")
        registros[identificador] = {
            "id": identificador, "name": nombre[:160] or organismo, "provider": organismo,
            "city": "España" if dgt else "Madrid", "credit": organismo, "license": licencia,
            "lat": lat, "lon": lon, "feedType": "image", "sourceKind": "ultron-" + fuente,
            "url": url, "snapshotUrl": url,
        }
        if len(registros) >= 3000:
            break
    return list(registros.values())


def actualizar_camaras(ej: Ejecutor, destino: Path) -> list[str]:
    """Actualiza cada archivo por separado y conserva la última copia válida."""
    problemas = []
    with httpx.Client(timeout=4, follow_redirects=False) as cliente:
        for fuente, url in (("dgt", DGT), ("madrid", MADRID)):
            archivo = destino / "config" / f"ultron-{fuente}.json"
            try:
                if archivo.is_file() and time() - archivo.stat().st_mtime < 3600:
                    continue
                datos = _camaras(_descargar(cliente, url), fuente)
                if not datos:
                    raise ValueError("Catálogo sin cámaras compatibles.")
                ej.escribir(archivo, json.dumps(datos, ensure_ascii=False))
            except (httpx.HTTPError, ValueError, ET.ParseError, OSError):
                problemas.append("DGT" if fuente == "dgt" else "Madrid")
    return problemas
