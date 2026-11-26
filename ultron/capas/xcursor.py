"""Lectura y recoloreado de archivos Xcursor sin herramientas externas."""

from __future__ import annotations

import struct
from collections.abc import Callable

TIPO_IMAGEN = 0xFFFD0002
MAGIA = b"Xcur"


def es_xcursor(datos: bytes) -> bool:
    return datos[:4] == MAGIA


def recolorear(datos: bytes, transformar: Callable) -> bytes:
    """Aplica `transformar(imagen_rgba) -> imagen_rgba` a cada imagen del cursor."""
    from PIL import Image

    if not es_xcursor(datos):
        raise ValueError("no es un archivo Xcursor")
    salida = bytearray(datos)
    _magia, _cab, _version, ntoc = struct.unpack_from("<4sIII", datos, 0)
    for i in range(ntoc):
        tipo, _subtipo, posicion = struct.unpack_from("<III", datos, 16 + i * 12)
        if tipo != TIPO_IMAGEN:
            continue
        cab, _t, _s, _v, ancho, alto = struct.unpack_from("<IIIIII", datos, posicion)
        inicio = posicion + cab
        fin = inicio + ancho * alto * 4
        img = Image.frombytes("RGBA", (ancho, alto), bytes(datos[inicio:fin]), "raw", "BGRA")
        nueva = transformar(img).convert("RGBA")
        salida[inicio:fin] = nueva.tobytes("raw", "BGRA")
    return bytes(salida)


def crear(imagenes: list[tuple[int, int, int, bytes]]) -> bytes:
    """Crea un Xcursor mínimo: [(tamaño, xhot, yhot, rgba_bytes_BGRA)] (para tests)."""
    ntoc = len(imagenes)
    cabecera = struct.pack("<4sIII", MAGIA, 16, 0x10000, ntoc)
    toc = b""
    cuerpo = b""
    posicion = 16 + ntoc * 12
    for tam, xhot, yhot, pix in imagenes:
        toc += struct.pack("<III", TIPO_IMAGEN, tam, posicion)
        bloque = struct.pack("<IIIIIIIII", 36, TIPO_IMAGEN, tam, 1, tam, tam, xhot, yhot, 0) + pix
        cuerpo += bloque
        posicion += len(bloque)
    return cabecera + toc + cuerpo
