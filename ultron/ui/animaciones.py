"""Animaciones de texto (escritura, glitch, fundido). Todas duran menos de 1,5 s."""

from __future__ import annotations

import random
import time

from rich.console import Console, Group
from rich.live import Live
from rich.text import Text

from ultron.ui.tema import Tema, animaciones_activas, soporta_unicode

RUIDO = "░▒▓█▀▄■◆"
RUIDO_ASCII = "#%@&*+=-"


def activas() -> bool:
    return animaciones_activas()


def _ruido() -> str:
    return RUIDO if soporta_unicode() else RUIDO_ASCII


def fotograma_glitch(lineas: list[Text], progreso: float, rng: random.Random) -> list[Text]:
    """Mezcla el texto final con ruido; con progreso=1 devuelve el texto tal cual."""
    ruido = _ruido()
    salida = []
    for linea in lineas:
        plano = linea.plain
        mezcla = "".join(
            c if c.isspace() or rng.random() < progreso else rng.choice(ruido) for c in plano
        )
        nueva = linea.copy()
        nueva.plain = mezcla
        salida.append(nueva)
    return salida


def glitch(consola: Console, lineas: list[Text], duracion: float = 0.8, pasos: int = 10) -> None:
    rng = random.Random()
    with Live(console=consola, refresh_per_second=30, transient=False) as live:
        for k in range(pasos + 1):
            live.update(Group(*fotograma_glitch(lineas, k / pasos, rng)))
            time.sleep(duracion / pasos)


def escritura(consola: Console, lineas: list[Text], duracion: float = 1.2) -> None:
    total = sum(len(t.plain) for t in lineas) or 1
    pasos = min(total, 60)
    with Live(console=consola, refresh_per_second=60, transient=False) as live:
        for k in range(pasos + 1):
            limite = round(total * k / pasos)
            visibles, resto = [], limite
            for t in lineas:
                visibles.append(t[: max(0, resto)])
                resto -= len(t.plain)
            live.update(Group(*visibles))
            time.sleep(duracion / pasos)


def fundido(consola: Console, lineas: list[Text], duracion: float = 0.9) -> None:
    capas = ["bright_black", "dim", ""]
    with Live(console=consola, refresh_per_second=20, transient=False) as live:
        for estilo in capas:
            fotograma = []
            for t in lineas:
                copia = t.copy()
                if estilo:
                    copia.stylize(estilo)
                fotograma.append(copia)
            live.update(Group(*fotograma))
            time.sleep(duracion / len(capas))


def entrada(consola: Console, lineas: list[Text], tipo: str) -> None:
    {"glitch": glitch, "escritura": escritura}.get(tipo, fundido)(consola, lineas)


def transicion(viejo: Tema | None, nuevo: Tema) -> None:
    """Línea de "desmontando" el modo anterior con glitch."""
    if not activas() or viejo is None:
        return
    a, b = ("░▒▓", "▓▒░") if soporta_unicode() else ("##", "##")
    texto = Text.from_markup(f"[apagado]{a} desmontando modo {viejo.nombre.lower()} {b}[/]")
    glitch(viejo.consola, [texto], duracion=0.5, pasos=6)
