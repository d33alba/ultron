"""Escenas procedurales del hangar y las pantallas de entrada."""

from __future__ import annotations

from functools import lru_cache
from math import cos, pi, sin, sqrt, tau
from random import Random

from rich.color import Color
from rich.text import Text

from ultron.modos.presentacion.letras import grandes
from ultron.ui.pixel import RGB, Lienzo
from ultron.ui.tema import soporta_unicode

_COSTAS = (
    ((70, -150), (56, -132), (49, -125), (31, -116), (22, -105), (18, -88),
     (28, -82), (47, -57), (60, -65), (72, -100), (70, -150)),
    ((12, -77), (6, -55), (-6, -35), (-27, -49), (-54, -68), (-40, -74),
     (-14, -77), (12, -77)),
    ((66, -12), (71, 27), (63, 57), (52, 45), (37, 30), (30, 33), (11, 51),
     (-34, 19), (-6, 11), (5, -9), (17, -17), (34, -6), (50, -6), (66, -12)),
    ((69, 28), (74, 80), (70, 147), (61, 172), (46, 146), (21, 110), (3, 105),
     (20, 85), (8, 77), (27, 57), (37, 30)),
    ((-13, 130), (-24, 113), (-35, 116), (-38, 149), (-25, 154), (-13, 143), (-13, 130)),
)


@lru_cache(maxsize=128)
def _paleta(fondo: str, primario: str, acento: str, texto: str) -> tuple[RGB, ...]:
    base, prim, ac, claro = (Color.parse(c).get_truecolor() for c in
                              (fondo, primario, acento, texto))

    def mezcla(destino: RGB, f: float) -> RGB:
        r, g, b = (round(a + (z - a) * f) for a, z in zip(base, destino, strict=True))
        return r, g, b

    return (base, *(mezcla(prim, i / 8) for i in range(1, 9)),
            *(mezcla(ac, i / 8) for i in range(1, 9)), claro)


@lru_cache(maxsize=8)
def _semillas(cantidad: int) -> tuple[tuple[float, float, float], ...]:
    rng = Random(2718)
    return tuple((rng.random(), rng.random(), rng.random()) for _ in range(cantidad))


@lru_cache(maxsize=64)
def _letras(cadena: str) -> tuple[str, ...]:
    return tuple(grandes(cadena, "#"))


def titulo(cadena: str, color: str, *, ancho: int) -> Text:
    """Empaqueta la fuente de cinco píxeles en tres filas de semibloques."""
    filas = _letras(cadena)
    columnas = (max(map(len, filas)) + 1) // 2
    if columnas > ancho or not soporta_unicode():
        return Text(cadena, style=f"bold {color}", justify="center")
    bits = [fila[::2].ljust(columnas) for fila in (*filas, "")]
    glifos = " ▀▄█"
    forma = ["".join(glifos[(a == "#") + 2 * (b == "#")]
                     for a, b in zip(*bits[i:i + 2], strict=True))
             for i in range(0, 6, 2)]
    return Text("\n".join(forma), style=color, justify="center", no_wrap=True)


def rotulo(lienzo: Lienzo, cadena: str, *, y: int | None = None, color: int = 17,
           corte: int = -1) -> None:
    filas = _letras(cadena)
    ancho = max(map(len, filas))
    if ancho > lienzo.ancho:
        return
    x = (lienzo.ancho - ancho) // 2
    y = (lienzo.alto - len(filas)) // 2 if y is None else y
    for dy, fila in enumerate(filas):
        if dy != corte:
            for dx, punto in enumerate(fila):
                if punto == "#":
                    lienzo.punto(x + dx, y + dy, color)


def _gaming(lienzo: Lienzo, t: float) -> None:
    w, h = lienzo.ancho, lienzo.alto
    horizonte = h * 3 // 5
    radio = min(horizonte * 0.45, w * 0.12)
    cx, cy = w // 2, horizonte - int(radio * 0.55)
    for y in range(max(0, cy - int(radio)), horizonte):
        dy = (y - cy) / max(1, radio)
        if abs(dy) <= 1 and (dy < 0 or y % 4 < 2):
            dx = round(sqrt(1 - dy * dy) * radio)
            lienzo.rect(cx - dx, y, 2 * dx + 1, 1, round(12 - dy * 4))
    for x, y, s in _semillas(74):
        lienzo.punto(int((x + t * s * 0.015) % 1 * w), int(y * horizonte),
                10 + int((sin(t * 2 + x * 20) + 1) * 2))
    for i in range(-6, 7):
        lienzo.linea(cx + i * 2, horizonte, cx + i * w // 9, h - 1, 4)
    for i in range(10):
        z = ((i + t * 3) % 10) / 10
        lienzo.rect(0, horizonte + int(z ** 3 * (h - horizonte)), w, 1, 1 + int(z * 6))


@lru_cache(maxsize=1)
def _esfera() -> tuple[tuple[float, float, float, int], ...]:
    puntos = []
    for i in range(144):
        a = i * tau / 144
        for j in range(-3, 4):
            b = j * pi / 8
            puntos.append((cos(b) * cos(a), sin(b), cos(b) * sin(a), 4))
        if i % 2 == 0:
            for j in range(6):
                b = j * pi / 6
                puntos.append((cos(b) * cos(a), sin(a), sin(b) * cos(a), 4))
        # Dos arcos elevados sobre el meridiano, con extremos en la superficie.
        if i < 44:
            b = i * pi / 64 - 1
            r = 1 + 0.24 * sin(pi * i / 43)
            puntos.append((r * cos(b), r * sin(b), 0, 16))
            puntos.append((0, r * sin(b), r * cos(b), 13))
    for costa in _COSTAS:
        for (lat, lon), (fin_lat, fin_lon) in zip(costa, costa[1:], strict=False):
            pasos = max(1, round(max(abs(fin_lat - lat), abs(fin_lon - lon)) / 3))
            for i in range(pasos):
                phi = (lat + (fin_lat - lat) * i / pasos) * pi / 180
                theta = (lon + (fin_lon - lon) * i / pasos) * pi / 180
                puntos.append((cos(phi) * cos(theta), sin(phi), cos(phi) * sin(theta), 8))
    return tuple(sorted(puntos, key=lambda punto: punto[3]))


def _globo(lienzo: Lienzo, t: float) -> None:
    x0, y0 = lienzo.ancho, lienzo.alto
    r = min(y0, x0) * 0.65
    ca, sa = cos(t * 0.6), sin(t * 0.6)
    for x, y, z, color in _esfera():
        frente = z * ca - x * sa
        if frente >= 0:
            lienzo.fino(round(x0 + r * (x * ca + z * sa)),
                       round(y0 - r * y), color)
    a = t * 1.7
    c, s = cos(a), sin(a)
    for i in range(int(r * 1.3)):
        lienzo.fino(round(x0 + i * c), round(y0 + i * s), 11)


def _focus(lienzo: Lienzo, t: float, reloj: str) -> None:
    for x, y, s in _semillas(34):
        lienzo.punto(int((x + t * 0.008 * s) % 1 * lienzo.ancho),
                int((y + t * 0.004 * s) % 1 * lienzo.alto),
                1 + int(1 + sin(t * 0.7 + s * tau)))
    rotulo(lienzo, reloj, color=15)


def _diapositiva(lienzo: Lienzo, t: float) -> None:
    f = min(1.0, (max(0.0, t) + 0.12) / 0.55)
    margen = 2 - (1 - f) ** 3
    x = round(lienzo.ancho * (margen - 1) * 0.12)
    y = max(1, lienzo.alto // 7)
    ancho = max(1, round((lienzo.ancho - 2 * x) * f))
    lienzo.rect(x, y, ancho, lienzo.alto - y * 2, 1)
    lienzo.rect(x, y, ancho, 1, 7)
    lienzo.rect(x, lienzo.alto - y - 1, ancho, 1, 11)
    if f > 0.65:
        rotulo(lienzo, "EN ESCENA")


def _fantasma(lienzo: Lienzo, t: float) -> None:
    for x, y, s in _semillas(110):
        px = int(x * lienzo.ancho)
        py = int((y + t * (0.15 + s * 0.54)) % 1 * lienzo.alto)
        lienzo.rect(px, py - 2, 1, 2, 1)
        lienzo.punto(px, py, 2 + int(s * 5))
    for x, y, s in _semillas(34):
        lienzo.punto(int((x + int(t * 11) * 0.173) % 1 * lienzo.ancho),
                int(y * lienzo.alto), 1 + int(s * 3))
    fase = t % 3
    if fase < 2.8:
        corte = int(fase * 28) % 5 if fase > 2.4 else -1
        rotulo(lienzo, "FANTASMA", color=12, corte=corte)
    if fase > 2.4:
        lienzo.rect(0, int(fase * 43) % lienzo.alto, lienzo.ancho, 1, 3)


def _estrellas(lienzo: Lienzo, t: float) -> None:
    for x, y, z in _semillas(100):
        distancia = (z - t * 0.18) % 1
        escala = 0.4 / (0.15 + distancia)
        lienzo.punto(int(lienzo.ancho * (0.5 + (x - 0.5) * escala)),
                int(lienzo.alto * (0.5 + (y - 0.5) * escala)), 1 + int(6 * (1 - distancia)))


def fotograma(modo: str, paleta: dict[str, str], ancho: int, filas: int, t: float,
              *, reloj: str = "00:00") -> Lienzo:
    """Render determinista en función del instante, tamaño y paleta."""
    colores = _paleta(paleta.get("fondo", "#101418"), paleta.get("primario", "#00D7FF"),
                      paleta.get("acento", "#88DFFF"), paleta.get("texto", "#FFFFFF"))
    lienzo = Lienzo(ancho, filas, colores)
    if modo == "focus":
        _focus(lienzo, t, reloj)
    else:
        _ESCENAS.get(modo, _estrellas)(lienzo, t)
    return lienzo


_ESCENAS = {"gaming": _gaming, "netanyahu": _globo, "presentacion": _diapositiva,
            "fantasma": _fantasma}
