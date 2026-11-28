"""Configuración de usuario en ~/.config/ultron/config.toml (permisos 600)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

import tomli_w

from ultron.nucleo import rutas


def ruta() -> Path:
    return rutas.config() / "config.toml"


def leer() -> dict[str, Any]:
    try:
        with open(ruta(), "rb") as f:
            return tomllib.load(f)
    except (FileNotFoundError, tomllib.TOMLDecodeError, OSError):
        return {}


def guardar(datos: dict[str, Any]) -> None:
    destino = ruta()
    destino.parent.mkdir(parents=True, exist_ok=True)
    contenido = tomli_w.dumps(_sin_nulos(datos)).encode("utf-8")
    with tempfile.NamedTemporaryFile(dir=destino.parent, delete=False) as archivo:
        temporal = Path(archivo.name)
        try:
            archivo.write(contenido)
            archivo.close()
            os.replace(temporal, destino)
        finally:
            archivo.close()
            temporal.unlink(missing_ok=True)


def _sin_nulos(d: dict[str, Any]) -> dict[str, Any]:
    salida: dict[str, Any] = {}
    for k, v in d.items():
        if v is None:
            continue
        salida[k] = _sin_nulos(v) if isinstance(v, dict) else v
    return salida


def obtener(seccion: str, clave: str, defecto: Any = None) -> Any:
    return leer().get(seccion, {}).get(clave, defecto)


def fijar(seccion: str, clave: str, valor: Any) -> None:
    datos = leer()
    datos.setdefault(seccion, {})
    if valor is None:
        datos[seccion].pop(clave, None)
    else:
        datos[seccion][clave] = valor
    guardar(datos)
