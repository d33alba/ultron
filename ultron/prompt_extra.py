"""Texto extra del prompt (pomodoro, tareas, XP). Muy rápido: solo librería estándar.

Se ejecuta en cada prompt con `python -I -m ultron.prompt_extra`.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def _dir_estado() -> Path:
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg) / "ultron"
    home = Path(os.environ.get("HOME") or Path.home())
    if sys.platform == "win32":
        return home / ".ultron-dev" / "estado"
    return home / ".local" / "state" / "ultron"


def _fase(restante: float, total: float) -> str:
    fases = "○◔◑◕●"
    hecho = 1 - (restante / total if total else 0)
    return fases[min(4, max(0, int(hecho * 4.999)))]


def texto(ahora: float | None = None) -> str:
    try:
        panel = json.loads((_dir_estado() / "panel.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    ahora = time.time() if ahora is None else ahora
    partes: list[str] = []
    pomo = panel.get("pomodoro")
    if isinstance(pomo, dict) and pomo.get("fin"):
        restante = max(0.0, float(pomo["fin"]) - ahora)
        total = float(pomo.get("total", 1500))
        if restante > 0:
            m, s = divmod(int(restante), 60)
            partes.append(f"{_fase(restante, total)} {m:02d}:{s:02d}")
    tareas = panel.get("tareas")
    if isinstance(tareas, dict) and tareas.get("total"):
        partes.append(f"{tareas.get('hechas', 0)}/{tareas['total']}")
    if panel.get("modo") == "gaming" and panel.get("nivel") is not None:
        partes.append(f"LVL {panel['nivel']}")
    return " · ".join(partes)


def main() -> None:
    sys.stdout.write(texto())


if __name__ == "__main__":
    main()
