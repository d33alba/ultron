"""Banners de modo: degradados, respaldo del hebreo y animación de entrada."""

from __future__ import annotations

import re
import unicodedata

from rich.text import Text

from ultron.ui import animaciones, pantalla_pixel
from ultron.ui.escenas import titulo
from ultron.ui.tema import Tema, soporta_unicode

_HEBREO = re.compile(r"[֐-׿]+")
_ASCII = str.maketrans({"█": "#", "▀": "=", "▄": "_", "░": ".", "▒": ":", "▓": "#",
                       "✡": "*", "◆": "*", "·": ".", "─": "-", "—": "-", "│": "|"})


def _hex_a_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def interpolar(colores: list[str], t: float) -> str:
    """Color en la posición t (0–1) de un degradado de varios colores."""
    if not colores:
        return ""
    if len(colores) == 1:
        return colores[0]
    t = max(0.0, min(1.0, t))
    tramo = t * (len(colores) - 1)
    i = min(int(tramo), len(colores) - 2)
    f = tramo - i
    a, b = _hex_a_rgb(colores[i]), _hex_a_rgb(colores[i + 1])
    r, g, bl = (round(a[k] + (b[k] - a[k]) * f) for k in range(3))
    return f"#{r:02x}{g:02x}{bl:02x}"


def aplicar_degradado(linea: Text, colores: list[str], ancho: int) -> Text:
    if not colores or ancho <= 1:
        return linea
    for i, car in enumerate(linea.plain):
        if not car.isspace():
            linea.stylize(interpolar(colores, i / (ancho - 1)), i, i + 1)
    return linea


def _sin_hebreo(texto: str) -> str:
    return _HEBREO.sub("SHALOM", texto)


def lineas_banner(
    tema: Tema, ancho_terminal: int = 100, compacto: bool | None = None
) -> list[Text]:
    """Líneas del banner ya estilizadas (con degradado si el tema lo define)."""
    if compacto is None:
        compacto = ancho_terminal < 80 or not tema.banner
    fuente = (tema.banner_compacto or tema.banner) if compacto else tema.banner
    if not soporta_unicode():
        fuente = unicodedata.normalize("NFKD", _sin_hebreo(fuente).translate(_ASCII))
        fuente = fuente.encode("ascii", "ignore").decode("ascii")
    lineas = [Text.from_markup(linea) for linea in fuente.splitlines()]
    if tema.degradado:
        ancho = max((len(t.plain) for t in lineas), default=1)
        lineas = [aplicar_degradado(t, tema.degradado, ancho) for t in lineas]
    return lineas


def mostrar_banner(tema: Tema, animado: bool = True, compacto: bool | None = None) -> None:
    consola = tema.consola
    if (compacto is not True and consola.width >= 80
            and pantalla_pixel.habilitada(tema) and animaciones.activas()):
        if animado:
            pantalla_pixel.avance(tema)
        ancho = min(120, consola.width)
        consola.print(pantalla_pixel.vista(tema, ancho, 8, 1.25), crop=True)
        consola.print(titulo(tema.nombre, tema.paleta.get("primario", "cyan"), ancho=ancho))
        return
    lineas = lineas_banner(tema, consola.width, compacto)
    if animado and animaciones.activas():
        animaciones.entrada(consola, lineas, tema.entrada)
    else:
        for linea in lineas:
            consola.print(linea)
