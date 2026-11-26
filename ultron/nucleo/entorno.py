"""Detección del sistema: distro, GNOME, tipo de sesión."""

from __future__ import annotations

import os
import platform
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from ultron.nucleo.ejecutor import Ejecutor


@dataclass
class Entorno:
    so: str
    distro: str
    version: str
    gnome: str | None
    sesion: str | None
    grafico: bool

    @property
    def es_linux(self) -> bool:
        return self.so == "Linux"

    @property
    def es_ubuntu(self) -> bool:
        return self.distro.lower() == "ubuntu"

    @property
    def gnome_mayor(self) -> int | None:
        if not self.gnome:
            return None
        m = re.match(r"(\d+)", self.gnome)
        return int(m.group(1)) if m else None

    @property
    def wayland(self) -> bool:
        return self.sesion == "wayland"


def _os_release(ruta: Path = Path("/etc/os-release")) -> dict[str, str]:
    datos: dict[str, str] = {}
    try:
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            if "=" in linea:
                k, v = linea.split("=", 1)
                datos[k.strip()] = v.strip().strip('"')
    except OSError:
        pass
    return datos


def detectar(ej: Ejecutor | None = None) -> Entorno:
    ej = ej or Ejecutor()
    so = platform.system()
    rel = _os_release() if so == "Linux" else {}
    gnome = None
    if ej.existe("gnome-shell"):
        r = ej.leer(["gnome-shell", "--version"])
        m = re.search(r"(\d+(?:\.\d+)*)", r.salida)
        gnome = m.group(1) if m else None
    sesion = os.environ.get("XDG_SESSION_TYPE") or None
    grafico = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    return Entorno(
        so=so,
        distro=rel.get("NAME", "Windows" if sys.platform == "win32" else so).split()[0],
        version=rel.get("VERSION_ID", platform.release()),
        gnome=gnome,
        sesion=sesion,
        grafico=grafico,
    )
