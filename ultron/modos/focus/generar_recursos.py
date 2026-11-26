"""Recursos de FOCUS generados en local (sin derechos de terceros): fondo y campana."""

from __future__ import annotations

import math
import random
import struct
import wave
from datetime import date
from pathlib import Path

FRASES = [
    "lo que haces cada día importa más que lo que haces de vez en cuando.",
    "un paso cada vez.",
    "la concentración es decir no a mil cosas.",
    "estudia como si fueras a enseñarlo mañana.",
    "poco a poco se llega lejos.",
]


def _dir_tema() -> Path:
    from ultron.nucleo import registro

    return registro.obtener("focus").dir_usuario() / "tema"


def fondo(destino: Path, ancho: int = 3840, alto: int = 2160, frase: str | None = None) -> Path:
    """Gris cálido liso, una línea fina y la frase del día en tipografía ligera."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (ancho, alto), (30, 31, 34))
    d = ImageDraw.Draw(img)
    # viñeta muy suave
    for r in range(0, max(ancho, alto) // 2, 8):
        tono = 30 + round(6 * (1 - r / (max(ancho, alto) / 2)))
        d.ellipse([ancho / 2 - r * 1.8, alto / 2 - r, ancho / 2 + r * 1.8, alto / 2 + r],
                  outline=(tono, tono + 1, tono + 4))
    y = round(alto * 0.62)
    d.line([(ancho * 0.38, y), (ancho * 0.62, y)], fill=(143, 188, 143), width=max(2, alto // 900))
    frase = frase or FRASES[date.today().toordinal() % len(FRASES)]
    try:
        fuente = ImageFont.truetype("DejaVuSans-ExtraLight.ttf", alto // 40)
    except OSError:
        try:
            fuente = ImageFont.truetype("DejaVuSans.ttf", alto // 40)
        except OSError:
            fuente = ImageFont.load_default()
    caja = d.textbbox((0, 0), frase, font=fuente)
    d.text(((ancho - (caja[2] - caja[0])) / 2, y + alto // 40), frase, fill=(150, 150, 150),
           font=fuente)
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino)
    return destino


def campana(destino: Path, segundos: float = 2.2, frecuencia: float = 880.0) -> Path:
    """Campana suave sintética: dos parciales con decaimiento exponencial."""
    tasa = 44100
    destino.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(1)
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(tasa)
        marcos = bytearray()
        for i in range(int(tasa * segundos)):
            t = i / tasa
            env = math.exp(-t * 2.4) * min(1.0, t * 200)
            muestra = (math.sin(2 * math.pi * frecuencia * t) * 0.6
                       + math.sin(2 * math.pi * frecuencia * 2.76 * t) * 0.25 * math.exp(-t * 4)
                       + (rng.random() - 0.5) * 0.002)
            marcos += struct.pack("<h", int(max(-1, min(1, muestra * env)) * 22000))
        w.writeframes(bytes(marcos))
    return destino


def generar(forzar: bool = False) -> list[Path]:
    d = _dir_tema()
    hechos = []
    if forzar or not (d / "fondo.png").exists():
        hechos.append(fondo(d / "fondo.png"))
    if forzar or not (d / "sonidos" / "campana.wav").exists():
        hechos.append(campana(d / "sonidos" / "campana.wav"))
    return hechos
