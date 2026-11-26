"""Bloqueo de webs con un bloque propio en /etc/hosts (idempotente y reversible)."""

from __future__ import annotations

import re
from pathlib import Path

from ultron.nucleo.ejecutor import Ejecutor

HOSTS = Path("/etc/hosts")


def _marcas(etiqueta: str) -> tuple[str, str]:
    return f"# >>> ultron {etiqueta} >>>", f"# <<< ultron {etiqueta} <<<"


def bloque(dominios: list[str], etiqueta: str = "bloqueo") -> str:
    inicio, fin = _marcas(etiqueta)
    lineas = [inicio]
    for d in sorted({d.strip().lower() for d in dominios if d.strip()}):
        d = re.sub(r"^https?://", "", d).split("/")[0]
        variantes = [d] if d.startswith("www.") else [d, f"www.{d}"]
        lineas += [f"0.0.0.0 {v}" for v in variantes]
    lineas.append(fin)
    return "\n".join(lineas) + "\n"


def quitar(texto: str, etiqueta: str = "bloqueo") -> str:
    inicio, fin = _marcas(etiqueta)
    patron = re.compile(rf"{re.escape(inicio)}.*?{re.escape(fin)}\n?", re.S)
    return patron.sub("", texto)


def poner(texto: str, dominios: list[str], etiqueta: str = "bloqueo") -> str:
    base = quitar(texto, etiqueta)
    if base and not base.endswith("\n"):
        base += "\n"
    return base + bloque(dominios, etiqueta)


def bloquear(ej: Ejecutor, dominios: list[str], etiqueta: str = "bloqueo",
             ruta: Path | None = None) -> None:
    ruta = ruta or HOSTS
    actual = ruta.read_text(encoding="utf-8") if ruta.exists() else ""
    nuevo = poner(actual, dominios, etiqueta)
    if nuevo != actual:
        ej.escribir(ruta, nuevo, sudo=necesita_sudo(ruta))


def desbloquear(ej: Ejecutor, etiqueta: str = "bloqueo", ruta: Path | None = None) -> None:
    ruta = ruta or HOSTS
    if not ruta.exists():
        return
    actual = ruta.read_text(encoding="utf-8")
    nuevo = quitar(actual, etiqueta)
    if nuevo != actual:
        ej.escribir(ruta, nuevo, sudo=necesita_sudo(ruta))


def activo(etiqueta: str = "bloqueo", ruta: Path | None = None) -> bool:
    ruta = ruta or HOSTS
    try:
        return _marcas(etiqueta)[0] in ruta.read_text(encoding="utf-8")
    except OSError:
        return False


def necesita_sudo(ruta: Path) -> bool:
    """Solo hace falta sudo si no se puede escribir el archivo (como /etc/hosts)."""
    import os

    return not os.access(ruta if ruta.exists() else ruta.parent, os.W_OK)
