"""Ritmo adaptativo y presentación del lienzo en terminal."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from importlib.util import find_spec

from rich.color import ColorSystem
from rich.text import Text

from ultron.ui import escenas, pixel, tema

_SISTEMAS = {"truecolor": ColorSystem.TRUECOLOR, "256": ColorSystem.EIGHT_BIT,
             "standard": ColorSystem.STANDARD}


@dataclass
class Ritmo:
    maximo: int
    intervalo: float = 0.0

    def __post_init__(self) -> None:
        if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"):
            self.maximo = min(self.maximo, 15)
        self.intervalo = 1 / self.maximo

    def medir(self, duracion: float) -> None:
        """Reserva margen para la composición y el transporte del siguiente cuadro."""
        objetivo = min(0.25, max(1 / self.maximo, duracion * 3))
        self.intervalo = max(objetivo, self.intervalo * 0.95)


def salida(t: tema.Tema) -> str:
    c = t.consola
    return pixel.protocolo(os.environ, tty=c.is_terminal,
                           color=not c.no_color and c.color_system is not None,
                           unicode=tema.soporta_unicode())


def habilitada(t: tema.Tema) -> bool:
    return salida(t) != "simple"


def escena(t: tema.Tema, ancho: int, alto: int, segundos: float) -> pixel.Lienzo:
    return escenas.fotograma(t.id, t.paleta, ancho, alto, segundos,
                             reloj=time.strftime("%H:%M"))


def vista(t: tema.Tema, ancho: int, alto: int, segundos: float, fps: int = 0,
          velo: float = 0.0) -> Text:
    lienzo = escena(t, ancho, alto, segundos)
    if velo:
        lienzo.velar(round(ancho * velo))
    resultado = pixel.texto(lienzo)
    if t.id == "gaming" and fps:
        marca = f" {fps:02d} FPS "
        resultado = Text(marca, style="bold black on " + t.paleta.get("acento", "cyan"),
                         no_wrap=True, overflow="crop") + resultado[len(marca):]
    return resultado


def avance(t: tema.Tema, duracion: float = 0.55, *, cerrar: bool = False) -> bool:
    """Escena breve en una superficie propia, con restauración incluso al interrumpir."""
    c = t.consola
    formato = salida(t)
    sistema = _SISTEMAS.get(c.color_system)
    if (formato == "simple" or sistema is None or c.legacy_windows or not tema.animaciones_activas()
            or c.width < 28 or c.height < 10):
        return False
    ancho, alto = min(120, c.width - 1), min(40, c.height - 2)
    diferencial = pixel.Diferencial()
    ritmo = Ritmo(60)
    archivo = c.file
    # Los protocolos de imagen son una portada estática. Los cuadros con movimiento
    # conservan el detalle de braille y reutilizan los spans de texto.
    nativo = not cerrar and formato != "bloques" and t.id not in {"netanyahu", "fantasma"}
    if formato == "iterm" and find_spec("PIL") is None:
        nativo = False
    try:
        archivo.write("\x1b[?1049h\x1b[?25l")
        if nativo:
            lienzo = escena(t, ancho, alto, 0.65)
            if formato == "sixel":
                # Sixel usa dimensiones físicas y dibuja píxeles cuadrados.
                lienzo = pixel.ampliar(lienzo, 4)
            archivo.write("\x1b[H" + pixel.imagen(lienzo, formato))
            archivo.flush()
            time.sleep(duracion)
            return True
        inicio = time.monotonic()
        anterior = inicio
        while (ahora := time.monotonic()) - inicio < duracion:
            lienzo = escena(t, ancho, alto, ahora - inicio)
            if cerrar:
                lienzo.velar(round(ancho * (ahora - inicio) / duracion))
            datos = diferencial.ansi(lienzo, sistema)
            if t.id == "gaming" and not cerrar:
                fps = round(1 / max(ritmo.intervalo, ahora - anterior))
                datos += f"\x1b[1;1H\x1b[0m {fps:02d} FPS "
            if datos:
                archivo.write(datos)
                archivo.flush()
            anterior = ahora
            coste = time.monotonic() - ahora
            ritmo.medir(coste)
            time.sleep(max(0, ritmo.intervalo - coste))
    finally:
        if nativo and formato == "kitty":
            archivo.write("\x1b_Ga=d,d=I,i=1431524434,q=2;\x1b\\")
        archivo.write("\x1b[0m\x1b[?1049l\x1b[?25h")
        archivo.flush()
    return True
