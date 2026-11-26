"""estado.json: modo activo, capas aplicadas, música y otros datos persistentes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ultron.nucleo import jsonio, rutas


def ruta() -> Path:
    return rutas.estado() / "estado.json"


def leer() -> dict[str, Any]:
    datos = jsonio.leer(ruta(), {})
    return datos if isinstance(datos, dict) else {}


def guardar(datos: dict[str, Any]) -> None:
    jsonio.escribir(ruta(), datos)


def actualizar(**campos: Any) -> dict[str, Any]:
    datos = leer()
    for clave, valor in campos.items():
        if valor is None:
            datos.pop(clave, None)
        else:
            datos[clave] = valor
    guardar(datos)
    return datos


def obtener(clave: str, defecto: Any = None) -> Any:
    return leer().get(clave, defecto)


def modo_activo() -> str | None:
    return leer().get("modo_activo")
