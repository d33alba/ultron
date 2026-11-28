"""Lienzo de paleta RGB y salidas gráficas de terminal."""

from __future__ import annotations

import base64
from collections.abc import Iterator, Mapping
from functools import lru_cache
from itertools import groupby

from rich.color import Color, ColorSystem
from rich.style import Style
from rich.text import Text

RGB = tuple[int, int, int]
Celda = tuple[str, int, int]
Span = tuple[int, int, tuple[Celda, ...]]
PUNTOS = (1, 8, 2, 16, 4, 32, 64, 128)


def protocolo(entorno: Mapping[str, str], *, tty: bool, color: bool,
              unicode: bool = True) -> str:
    """Detecta capacidades anunciadas sin consultar la entrada del usuario."""
    term = entorno.get("TERM", "")
    if not tty or not color or "NO_COLOR" in entorno or term == "dumb" or not unicode:
        return "simple"
    if (not term.startswith(("tmux", "screen")) and not entorno.get("TMUX")
            and not entorno.get("STY") and not entorno.get("SSH_CONNECTION")):
        if "KITTY_WINDOW_ID" in entorno or term == "xterm-kitty":
            return "kitty"
        if "sixel" in term or term == "mlterm":
            return "sixel"
        if entorno.get("TERM_PROGRAM") == "iTerm.app":
            return "iterm"
    return "bloques"


class Lienzo:
    """Cada índice de un byte representa un pixel RGB de la paleta."""

    def __init__(self, ancho: int, filas: int, paleta: tuple[RGB, ...]) -> None:
        self.ancho, self.filas, self.alto = ancho, filas, filas * 2
        self.paleta = paleta
        self.pixeles = bytearray(ancho * self.alto)
        self.puntos = bytearray(ancho * filas)
        self.tinta = bytearray(ancho * filas)

    def rect(self, x: int, y: int, ancho: int, alto: int, color: int) -> None:
        inicio, fin = max(0, x), min(self.ancho, x + ancho)
        if inicio >= fin:
            return
        tira = bytes([color]) * (fin - inicio)
        for fila in range(max(0, y), min(self.alto, y + alto)):
            base = fila * self.ancho
            self.pixeles[base + inicio:base + fin] = tira

    def punto(self, x: int, y: int, color: int) -> None:
        if 0 <= x < self.ancho and 0 <= y < self.alto:
            self.pixeles[y * self.ancho + x] = color

    def velar(self, columnas: int) -> None:
        """Borra una franja desde la izquierda, incluidos sus puntos finos."""
        columnas = max(0, min(self.ancho, columnas))
        self.rect(0, 0, columnas, self.alto, 0)
        ceros = bytes(columnas)
        for i in range(0, len(self.puntos), self.ancho):
            self.puntos[i:i + columnas] = ceros
            self.tinta[i:i + columnas] = ceros

    def fino(self, x: int, y: int, color: int) -> None:
        if 0 <= x < self.ancho * 2 and 0 <= y < self.filas * 4:
            i = (y // 4) * self.ancho + x // 2
            self.puntos[i] |= PUNTOS[(y % 4) * 2 + x % 2]
            self.tinta[i] = color

    def linea(self, x: int, y: int, xf: int, yf: int, color: int) -> None:
        pasos = max(abs(xf - x), abs(yf - y), 1)
        for i in range(pasos + 1):
            self.punto(round(x + (xf - x) * i / pasos),
                       round(y + (yf - y) * i / pasos), color)

    def celdas(self) -> Iterator[tuple[Celda, ...]]:
        n = self.ancho
        for y in range(self.filas):
            base, puntos = 2 * y * n, y * n
            yield tuple(map(_celda, self.pixeles[base:base + n],
                            self.pixeles[base + n:base + 2 * n],
                            self.puntos[puntos:puntos + n], self.tinta[puntos:puntos + n]))


def ampliar(lienzo: Lienzo, escala: int) -> Lienzo:
    """Amplía por vecino más próximo para una imagen en píxeles físicos."""
    ancho = lienzo.ancho
    salida = Lienzo(ancho * escala, lienzo.filas * escala, lienzo.paleta)
    colores = [bytes([i]) * escala for i in range(len(lienzo.paleta))]
    salida.pixeles[:] = b"".join(
        b"".join(map(colores.__getitem__, lienzo.pixeles[i:i + ancho])) * escala
        for i in range(0, len(lienzo.pixeles), ancho)
    )
    return salida


def _rgb_bytes(lienzo: Lienzo) -> bytes:
    # La ruta opcional solo se usa al codificar una portada nativa.
    try:
        import numpy as np
    except ImportError:
        colores = [bytes(c) for c in lienzo.paleta]
        return b"".join(map(colores.__getitem__, lienzo.pixeles))
    return np.asarray(lienzo.paleta, dtype=np.uint8)[
        np.frombuffer(lienzo.pixeles, dtype=np.uint8)
    ].tobytes()


@lru_cache(maxsize=4096)
def _celda(a: int, b: int, puntos: int, tinta: int) -> Celda:
    if puntos:
        return chr(0x2800 + puntos), tinta, b
    return (" ", a, a) if a == b else ("▀", a, b)


def _colores(celda: Celda) -> tuple[int, int]:
    return celda[1:]


def _tramos(celdas: tuple[Celda, ...]) -> Iterator[tuple[tuple[int, int], str]]:
    for colores, grupo in groupby(celdas, _colores):
        yield colores, "".join(c[0] for c in grupo)


@lru_cache(maxsize=4096)
def _estilo(a: RGB, b: RGB) -> Style:
    return Style(color=Color.from_rgb(*a), bgcolor=Color.from_rgb(*b))


def texto(lienzo: Lienzo) -> Text:
    """Entrega filas agrupadas al compositor de Rich o Textual."""
    salida = Text(no_wrap=True, overflow="crop")
    for y, fila in enumerate(lienzo.celdas()):
        if y:
            salida.append("\n")
        for (a, b), tramo in _tramos(fila):
            salida.append(tramo, _estilo(lienzo.paleta[a], lienzo.paleta[b]))
    return salida


class Diferencial:
    """Conserva las celdas visibles y emite solo los intervalos modificados."""

    def __init__(self) -> None:
        self.previo: list[tuple[Celda, ...]] = []
        self.formato: tuple[int, int, tuple[RGB, ...]] | None = None

    def spans(self, lienzo: Lienzo) -> list[Span]:
        formato = lienzo.ancho, lienzo.filas, lienzo.paleta
        if formato != self.formato:
            self.previo = []
            self.formato = formato
        filas = list(lienzo.celdas())
        cambios = []
        for y, fila in enumerate(filas):
            if y >= len(self.previo):
                cambios.append((y, 0, fila))
            elif fila != self.previo[y]:
                inicio = None
                for x, (a, b) in enumerate(zip(fila, self.previo[y], strict=True)):
                    if a != b:
                        if inicio is None:
                            inicio = x
                    elif inicio is not None:
                        cambios.append((y, inicio, fila[inicio:x]))
                        inicio = None
                if inicio is not None:
                    cambios.append((y, inicio, fila[inicio:]))
        self.previo = filas
        return cambios

    def ansi(self, lienzo: Lienzo, sistema: ColorSystem) -> str:
        piezas = []
        for y, x, fila in self.spans(lienzo):
            piezas.append(f"\x1b[{y + 1};{x + 1}H")
            for (a, b), tramo in _tramos(fila):
                piezas.append(_ansi(lienzo.paleta[a], lienzo.paleta[b], sistema))
                piezas.append(tramo)
        return "".join(piezas)


@lru_cache(maxsize=4096)
def _ansi(a: RGB, b: RGB, sistema: ColorSystem) -> str:
    fg = Color.from_rgb(*a).downgrade(sistema).get_ansi_codes()
    bg = Color.from_rgb(*b).downgrade(sistema).get_ansi_codes(foreground=False)
    return "\x1b[" + ";".join((*fg, *bg)) + "m"


def imagen(lienzo: Lienzo, formato: str) -> str:
    """Codifica el lienzo para kitty, iTerm2 o sixel."""
    if formato == "kitty":
        datos = base64.b64encode(_rgb_bytes(lienzo)).decode("ascii")
        parametros = f"a=T,q=2,f=24,i=1431524434,s={lienzo.ancho},v={lienzo.alto},"
        parametros += f"c={lienzo.ancho},r={lienzo.filas},C=1,"
        piezas = []
        for i in range(0, len(datos), 4096):
            piezas.append(f"\x1b_G{parametros}m={int(i + 4096 < len(datos))};"
                          f"{datos[i:i + 4096]}\x1b\\")
            parametros = ""
        return "".join(piezas)
    if formato == "sixel":
        return _sixel(lienzo)
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    png = Image.frombytes("P", (lienzo.ancho, lienzo.alto), bytes(lienzo.pixeles))
    png.putpalette([v for color in lienzo.paleta for v in color])
    png.save(buffer, format="PNG")
    datos = base64.b64encode(buffer.getvalue()).decode("ascii")
    return (f"\x1b]1337;File=inline=1;width={lienzo.ancho};height={lienzo.filas};"
            f"preserveAspectRatio=0:{datos}\x07")


def _sixel(lienzo: Lienzo) -> str:
    """Usa píxeles nativos y comprime las repeticiones de cada plano de color."""
    n, h = lienzo.ancho, lienzo.alto
    piezas = [f'\x1bP0;0;0q"1;1;{n};{h}']
    for i, (r, g, b) in enumerate(lienzo.paleta):
        piezas.append(f"#{i};2;{round(r / 2.55)};{round(g / 2.55)};{round(b / 2.55)}")
    for y in range(0, h, 6):
        planos: dict[int, bytearray] = {}
        for j in range(min(6, h - y)):
            for x, color in enumerate(lienzo.pixeles[(y + j) * n:(y + j + 1) * n]):
                if color not in planos:
                    planos[color] = bytearray(n)
                planos[color][x] |= 1 << j
        for i, plano in planos.items():
            piezas.append(f"#{i}")
            for mascara, repetidas in groupby(plano):
                cuenta = sum(1 for _ in repetidas)
                letra = chr(63 + mascara)
                piezas.append(f"!{cuenta}{letra}" if cuenta > 3 else letra * cuenta)
            piezas.append("$")
        piezas.append("-")
    piezas.append("\x1b\\")
    return "".join(piezas)
