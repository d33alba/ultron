"""Lectura y escritura atómica de JSON."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def leer(ruta: Path, defecto: Any = None) -> Any:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return defecto


def escribir(ruta: Path, datos: Any) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_name(ruta.name + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporal, ruta)
