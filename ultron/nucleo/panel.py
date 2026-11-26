"""panel.json: lo que lee la extensión de GNOME y el prompt (modo, música, pomodoro, XP)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ultron.nucleo import jsonio, rutas


def ruta() -> Path:
    return rutas.estado() / "panel.json"


def leer() -> dict[str, Any]:
    datos = jsonio.leer(ruta(), {})
    return datos if isinstance(datos, dict) else {}


def escribir(**campos: Any) -> dict[str, Any]:
    datos = leer()
    for clave, valor in campos.items():
        if valor is None:
            datos.pop(clave, None)
        else:
            datos[clave] = valor
    jsonio.escribir(ruta(), datos)
    return datos
