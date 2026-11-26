"""Recursos de FANTASMA: fondo de niebla con una silueta difusa."""

from __future__ import annotations

import random
from pathlib import Path


def _dir_tema() -> Path:
    from ultron.nucleo import registro

    return registro.obtener("fantasma").dir_usuario() / "tema"


def fondo(destino: Path, ancho: int = 3840, alto: int = 2160, semilla: int = 13) -> Path:
    """Niebla gris sobre negro (ruido de valor en varias octavas) y una figura que se desvanece."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter

    rng = random.Random(semilla)
    niebla = Image.new("L", (ancho, alto), 0)
    for octava, peso in ((8, 0.5), (24, 0.3), (64, 0.2)):
        pequena = Image.new("L", (octava * 16 // 9 + 1, octava))
        pequena.putdata([rng.randint(0, 255) for _ in range(pequena.width * pequena.height)])
        capa = pequena.resize((ancho, alto), Image.BICUBIC).point(lambda v, p=peso: v * p)
        niebla = ImageChops.add(niebla, capa)
    niebla = niebla.filter(ImageFilter.GaussianBlur(alto / 60)).point(lambda v: v * 0.35)
    figura = Image.new("L", (ancho, alto), 0)
    d = ImageDraw.Draw(figura)
    cx, cy = ancho * 0.68, alto * 0.55
    d.ellipse([cx - alto * 0.07, cy - alto * 0.3, cx + alto * 0.07, cy - alto * 0.16], fill=110)
    d.polygon([(cx - alto * 0.12, cy + alto * 0.3), (cx - alto * 0.08, cy - alto * 0.14),
               (cx + alto * 0.08, cy - alto * 0.14), (cx + alto * 0.12, cy + alto * 0.3)],
              fill=80)
    figura = figura.filter(ImageFilter.GaussianBlur(alto / 40))
    final = ImageChops.add(niebla, figura)
    img = Image.merge("RGB", (final, final, final.point(lambda v: min(255, v + 4))))
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino)
    return destino


def generar(forzar: bool = False) -> list[Path]:
    d = _dir_tema()
    if forzar or not (d / "fondo.png").exists():
        return [fondo(d / "fondo.png")]
    return []
