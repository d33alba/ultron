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


def documentos() -> Path:
    """Carpeta visible para lo que se abre en el navegador (~/Documentos/Ultron).

    Firefox snap (Ubuntu 22.04+) no puede leer carpetas ocultas como ~/.local, así que los
    informes HTML van a la carpeta de documentos del usuario.
    """
    if os.environ.get("ULTRON_DOCUMENTOS"):
        return Path(os.environ["ULTRON_DOCUMENTOS"])
    if sys.platform == "win32":
        return home() / ".ultron-dev" / "documentos"
    return _dir_documentos() / "Ultron"


def _dir_documentos() -> Path:
    """XDG_DOCUMENTS_DIR de user-dirs.dirs, o ~/Documentos, ~/Documents o el home."""
    try:
        texto = (xdg_config_raiz() / "user-dirs.dirs").read_text(encoding="utf-8")
    except OSError:
        texto = ""
    for linea in texto.splitlines():
        if linea.startswith("XDG_DOCUMENTS_DIR="):
            valor = linea.split("=", 1)[1].strip().strip('"').replace("$HOME", str(home()))
            ruta = Path(valor)
            if ruta != home() and ruta.is_absolute():
                return ruta
    for nombre in ("Documentos", "Documents"):
        if (home() / nombre).is_dir():
            return home() / nombre
    return home()


def paquete() -> Path:
    return Path(__file__).resolve().parent.parent


def modos_paquete() -> Path:
    return paquete() / "modos"


def modos_usuario() -> Path:
    return datos() / "modos"


def offline() -> Path | None:
    """Carpeta con todo lo descargable ya preparado (USB sin red): `ULTRON_OFFLINE`."""
    valor = os.environ.get("ULTRON_OFFLINE")
    return Path(valor) if valor and Path(valor).is_dir() else None


def asegurar(ruta: Path) -> Path:
    ruta.mkdir(parents=True, exist_ok=True)
    return ruta
