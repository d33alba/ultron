"""Rutas XDG de Ultron. En Windows (desarrollo) usa ~/.ultron-dev/<tipo>."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP = "ultron"

_XDG = {
    "config": ("XDG_CONFIG_HOME", ".config"),
    "estado": ("XDG_STATE_HOME", ".local/state"),
    "datos": ("XDG_DATA_HOME", ".local/share"),
    "cache": ("XDG_CACHE_HOME", ".cache"),
}


def home() -> Path:
    """Directorio personal (respeta HOME también en Windows para los tests)."""
    return Path(os.environ.get("HOME") or Path.home())


def _base(tipo: str) -> Path:
    var, defecto = _XDG[tipo]
    valor = os.environ.get(var)
    if valor:
        return Path(valor) / APP
    if sys.platform == "win32":
        return home() / ".ultron-dev" / tipo
    return home() / defecto / APP


def config() -> Path:
    return _base("config")


def estado() -> Path:
    return _base("estado")


def datos() -> Path:
    return _base("datos")


def cache() -> Path:
    return _base("cache")


def xdg_datos_raiz() -> Path:
    """~/.local/share (sin el sufijo ultron): temas, iconos, fuentes, extensiones."""
    valor = os.environ.get("XDG_DATA_HOME")
    return Path(valor) if valor else home() / ".local" / "share"


def xdg_config_raiz() -> Path:
    """~/.config (sin el sufijo ultron)."""
    valor = os.environ.get("XDG_CONFIG_HOME")
    return Path(valor) if valor else home() / ".config"


def paquete() -> Path:
    return Path(__file__).resolve().parent.parent


def modos_paquete() -> Path:
    return paquete() / "modos"


def modos_usuario() -> Path:
    return datos() / "modos"


def asegurar(ruta: Path) -> Path:
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta
