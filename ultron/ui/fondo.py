"""Superficie de fondo que deja la composición y el teclado a Textual."""

from __future__ import annotations

import os
import time
from collections.abc import Sequence
from functools import lru_cache

from rich.color import ColorSystem
from rich.segment import Segment
from rich.style import Style
from rich.text import Text
from textual.app import App
from textual.color import Color
from textual.filter import LineFilter, NoColor
from textual.screen import Screen
from textual.widgets import Static

from ultron.ui import pantalla_pixel, tema


@lru_cache(maxsize=4096)
def _reducir(estilo: Style, sistema: ColorSystem) -> Style:
    fg = estilo.color.downgrade(sistema) if estilo.color else None
    bg = estilo.bgcolor.downgrade(sistema) if estilo.bgcolor else None
    return estilo + Style.from_color(fg, bg)


class _ReducirColor(LineFilter):
    def __init__(self, sistema: ColorSystem) -> None:
        super().__init__()
        self.sistema = sistema

    def apply(self, segments: list[Segment], background: Color) -> list[Segment]:
        return [Segment(s.text, _reducir(s.style, self.sistema) if s.style else None,
                        s.control) for s in segments]


class AppPixel(App):
    """Adapta el color de todos los paneles al compositor de la terminal."""

    def __init__(self) -> None:
        super().__init__()
        sistema = tema.cargar_tema().consola.color_system
        self.filtro_color = None
        if tema.OPCIONES.sin_color or "NO_COLOR" in os.environ:
            self.filtro_color = NoColor()
        elif sistema == "256":
            self.filtro_color = _ReducirColor(ColorSystem.EIGHT_BIT)
        elif sistema == "standard":
            self.filtro_color = _ReducirColor(ColorSystem.STANDARD)

    def get_line_filters(self) -> Sequence[LineFilter]:
        filtros = super().get_line_filters()
        if self.filtro_color is not None:
            return (*filtros, self.filtro_color)
        return filtros

    def cambiar(self, destino: Screen) -> None:
        """Disuelve brevemente la pantalla nueva al cambiar de sección."""
        self.switch_screen(destino)
        if tema.animaciones_activas():
            destino.styles.opacity = 0.8
            destino.styles.animate("opacity", value=1.0, duration=0.22)


class Fondo(Static):
    """Lienzo decorativo en una capa inferior, sin foco ni captura de teclado."""

    DEFAULT_CSS = """
    Fondo {
        layer: paisaje;
        position: absolute;
        width: 100%;
        height: 100%;
    }
    """

    def __init__(self) -> None:
        super().__init__(id="paisaje")
        self.tema = tema.cargar_tema()
        self.inicio = time.monotonic()
        self.transicion = False
        self.proximo = 0.0
        self.ultimo: float | None = None
        self.fps = 0
        self.ritmo = pantalla_pixel.Ritmo(30)

    def on_mount(self) -> None:
        if not pantalla_pixel.habilitada(self.tema):
            self.display = False
        elif tema.animaciones_activas():
            self.set_interval(1 / self.ritmo.maximo, self.dibujar)

    def on_resize(self) -> None:
        self.dibujar(forzar=True)

    def elegir(self, nuevo: tema.Tema) -> None:
        if nuevo.id != self.tema.id:
            self.tema = nuevo
            self.inicio = time.monotonic()
            self.transicion = True
            self.ultimo = None
            self.fps = 0
        self.dibujar(forzar=True)

    def dibujar(self, forzar: bool = False) -> None:
        if not self.display or not self.screen.is_current or not pantalla_pixel.habilitada(
            self.tema
        ):
            return
        ahora = time.monotonic()
        if ahora + 0.002 < self.proximo and not forzar:
            return
        ancho, disponible = self.size
        alto = min(disponible, 6 if ancho >= 105 else 5)
        if ancho < 12 or alto < 4:
            return
        animado = tema.animaciones_activas()
        segundos = ahora - self.inicio if animado else 1.0
        self.fps = round(1 / max(0.001, ahora - self.ultimo)) if animado and self.ultimo else 0
        # En las pantallas con paneles, el indicador vive en la cabecera.
        velo = max(0.0, 1 - segundos / 0.28) if self.transicion else 0.0
        fotograma = pantalla_pixel.vista(self.tema, ancho, alto, segundos, velo=velo)
        self.update(Text("\n\n") + fotograma)
        self.ultimo = ahora
        self.ritmo.medir(time.monotonic() - ahora)
        intervalo = self.ritmo.intervalo
        if self.tema.id in {"focus", "presentacion"} and segundos > 0.55:
            intervalo = max(intervalo, 0.12 if self.tema.id == "focus" else 1)
        self.proximo = ahora + intervalo
