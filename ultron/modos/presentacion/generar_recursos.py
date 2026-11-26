"""Recursos de PRESENTACIÓN: telón con foco de luz y un aplauso sintético."""

from __future__ import annotations

import math
import random
import struct
import wave
from pathlib import Path


def _dir_tema() -> Path:
    from ultron.nucleo import registro

    return registro.obtener("presentacion").dir_usuario() / "tema"


def fondo(destino: Path, ancho: int = 3840, alto: int = 2160) -> Path:
    from PIL import Image, ImageDraw, ImageFilter

    img = Image.new("RGB", (ancho, alto), (20, 6, 10))
    d = ImageDraw.Draw(img)
    pliegues = 28
    for i in range(pliegues):
        x0 = i * ancho / pliegues
        luz = 0.55 + 0.45 * math.sin(i * 1.7) ** 2
        d.rectangle([x0, 0, x0 + ancho / pliegues, alto],
                    fill=(round(120 * luz), round(14 * luz), round(28 * luz)))
    img = img.filter(ImageFilter.GaussianBlur(ancho / pliegues / 3))
    foco = Image.new("L", (ancho, alto), 0)
    ImageDraw.Draw(foco).ellipse([ancho * 0.3, alto * 0.15, ancho * 0.7, alto * 0.95], fill=255)
    foco = foco.filter(ImageFilter.GaussianBlur(alto / 8))
    calido = Image.new("RGB", (ancho, alto), (255, 214, 150))
    img = Image.composite(Image.blend(img, calido, 0.35), img, foco)
    d = ImageDraw.Draw(img)
    d.rectangle([0, alto * 0.93, ancho, alto], fill=(30, 22, 18))
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino)
    return destino


def aplauso(destino: Path, segundos: float = 2.5) -> Path:
    """Muchas palmadas cortas (ruido filtrado) que suben y se apagan."""
    tasa = 22050
    n = int(tasa * segundos)
    rng = random.Random(3)
    muestras = [0.0] * n
    for _ in range(int(segundos * 90)):
        centro = rng.random() ** 0.8 * segundos
        inicio = int(centro * tasa)
        fuerza = rng.uniform(0.3, 1.0)
        for k in range(min(500, n - inicio)):
            muestras[inicio + k] += (rng.random() - 0.5) * fuerza * math.exp(-k / 70)
    envolvente = [min(1, i / (tasa * 0.3)) * min(1, (n - i) / (tasa * 0.8)) for i in range(n)]
    destino.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(tasa)
        pico = max(1e-6, max(abs(m) for m in muestras))
        w.writeframes(b"".join(struct.pack("<h", int(m / pico * e * 20000))
                               for m, e in zip(muestras, envolvente, strict=True)))
    return destino


def generar(forzar: bool = False) -> list[Path]:
    d = _dir_tema()
    hechos = []
    if forzar or not (d / "fondo.png").exists():
        hechos.append(fondo(d / "fondo.png"))
    if forzar or not (d / "sonidos" / "entrada.wav").exists():
        hechos.append(aplauso(d / "sonidos" / "entrada.wav"))
    return hechos
