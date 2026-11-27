"""Utilidades que comparten las capas: gsettings/dconf, GVariant, colores, procesos."""

from __future__ import annotations

import ast
import colorsys
import hashlib
import os
import signal
import uuid as _uuid
from pathlib import Path
from typing import Any

from ultron.nucleo.ejecutor import Ejecutor


# --- GVariant ----------------------------------------------------------------
def gv_str(texto: str) -> str:
    return "'" + str(texto).replace("\\", "\\\\").replace("'", "\\'") + "'"


def gv_bool(valor: Any) -> str:
    return "true" if valor else "false"


def gv_lista(valores: list[str]) -> str:
    return "[" + ", ".join(gv_str(v) for v in valores) + "]"


def leer_lista(texto: str | None) -> list[str]:
    """Interpreta una lista GVariant como "['a', 'b']" o "@as []"."""
    if not texto:
        return []
    texto = texto.strip()
    if texto.startswith("@as"):
        texto = texto[3:].strip()
    try:
        valor = ast.literal_eval(texto)
    except (ValueError, SyntaxError):
        return []
    return [str(v) for v in valor] if isinstance(valor, (list, tuple)) else []


# --- gsettings agrupado ------------------------------------------------------
def capturar_claves(ej: Ejecutor, pares: list[tuple[str, str]]) -> dict[str, str | None]:
    return {f"{esq}::{clave}": ej.gsettings_get(esq, clave) for esq, clave in pares}


def restaurar_claves(ej: Ejecutor, previo: dict[str, str | None]) -> None:
    for k, valor in previo.items():
        if valor is None or "::" not in k:
            continue
        esq, clave = k.split("::", 1)
        ej.gsettings_set(esq, clave, valor)


def fijar_si_existe(
    ej: Ejecutor, previo: dict[str, str | None], esq: str, clave: str, valor: str
) -> bool:
    """Solo escribe la clave si existía al capturar (así no falla en otras versiones)."""
    if previo.get(f"{esq}::{clave}") is None:
        return False
    ej.gsettings_set(esq, clave, valor)
    return True


# --- dconf -----------------------------------------------------------------------
def dconf_leer(ej: Ejecutor, ruta: str) -> str | None:
    if not ej.existe("dconf"):
        return None
    r = ej.leer(["dconf", "read", ruta])
    valor = r.salida.strip()
    return valor if r.codigo == 0 and valor else None


def dconf_escribir(ej: Ejecutor, ruta: str, valor: str) -> None:
    if not ej.existe("dconf"):
        return
    ej.run(["dconf", "write", ruta, valor])


def dconf_restaurar(ej: Ejecutor, ruta: str, previo: str | None) -> None:
    if not ej.existe("dconf"):
        return
    if previo is None:
        ej.run(["dconf", "reset", ruta], check=False)
    else:
        ej.run(["dconf", "write", ruta, previo])


# --- colores -----------------------------------------------------------------------
def hex_a_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_a_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def mezclar(a: str, b: str, t: float) -> str:
    ra, rb = hex_a_rgb(a), hex_a_rgb(b)
    return rgb_a_hex(tuple(ra[i] + (rb[i] - ra[i]) * t for i in range(3)))


def aclarar(color: str, t: float = 0.25) -> str:
    return mezclar(color, "#ffffff", t)


def oscurecer(color: str, t: float = 0.25) -> str:
    return mezclar(color, "#000000", t)


def tono(color: str) -> float:
    r, g, b = (c / 255 for c in hex_a_rgb(color))
    return colorsys.rgb_to_hsv(r, g, b)[0]


def paleta_terminal(p: dict[str, str]) -> list[str]:
    """16 colores ANSI derivados de la paleta del modo."""
    fondo = p.get("fondo", "#101010")
    base = [
        fondo, p.get("error", "#cc3333"), p.get("ok", "#33cc33"), p.get("aviso", "#cccc33"),
        p.get("primario", "#3366cc"), p.get("secundario", "#cc33cc"), p.get("acento", "#33cccc"),
        p.get("texto", "#dddddd"),
    ]
    brillantes = [aclarar(c, 0.3) for c in base]
    brillantes[0] = p.get("apagado", aclarar(fondo, 0.3))
    return base + brillantes


# --- otros ---------------------------------------------------------------------------
def uuid_modo(id_modo: str, espacio: str = "terminal") -> str:
    return str(_uuid.uuid5(_uuid.NAMESPACE_URL, f"ultron:{espacio}:{id_modo}"))


def huella(*partes: Any) -> str:
    h = hashlib.sha256()
    for p in partes:
        h.update(repr(p).encode("utf-8"))
    return h.hexdigest()[:16]


def matar(pid: int | None, forzar: bool = False) -> None:
    """Termina un proceso. `forzar` usa SIGKILL (conky se cuelga al cerrarse en Wayland y
    Ubuntu enseñaría un aviso de «la aplicación se cerró inesperadamente»)."""
    if not pid:
        return
    senal = getattr(signal, "SIGKILL", signal.SIGTERM) if forzar else signal.SIGTERM
    try:
        os.kill(int(pid), senal)
    except (OSError, ValueError):
        pass


def uri(ruta: Path) -> str:
    return Path(ruta).resolve().as_uri()
