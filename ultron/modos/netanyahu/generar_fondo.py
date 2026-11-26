"""Identidad visual reproducible del modo Netanyahu."""

from math import cos, pi, sin

from PIL import Image, ImageDraw, ImageFilter, ImageFont

AZUL = "#0038B8"


def estrella(imagen: Image.Image, radio: float, fraccion: float = 1) -> None:
    """Traza los dos triángulos desde el centro de la imagen."""
    x, y = imagen.width / 2, imagen.height / 2
    dibujo = ImageDraw.Draw(imagen)
    for giro in (0, pi):
        puntos = [
            (x + radio * sin(giro + i * 2 * pi / 3),
             y - radio * cos(giro + i * 2 * pi / 3))
            for i in range(3)
        ]
        for i, (a, b) in enumerate(zip(puntos, puntos[1:] + puntos[:1], strict=True)):
            tramo = min(1, max(0, 3 * fraccion - i))
            if tramo:
                fin = tuple(p + (q - p) * tramo for p, q in zip(a, b, strict=True))
                dibujo.line([a, fin], fill=AZUL, width=max(2, int(radio / 10)))
                dibujo.line([a, fin], fill="white", width=max(1, int(radio / 20)))


def fondo(ancho: int = 1920, alto: int = 1080) -> Image.Image:
    imagen = Image.new("RGB", (ancho, alto))
    dibujo = ImageDraw.Draw(imagen)
    for y in range(alto):
        dibujo.line((0, y, ancho, y), fill=(8, 16 + 24*y//alto, 40 + 50*y//alto))
    for x in range(0, ancho, 64):
        dibujo.line((x, 0, x, alto), fill="#183369")
    for y in range(0, alto, 64):
        dibujo.line((0, y, ancho, y), fill="#183369")
    for y in (alto // 8, 7 * alto // 8):
        dibujo.rectangle((0, y, ancho, y + alto // 35), fill=AZUL)
    capa = Image.new("RGBA", imagen.size)
    estrella(capa, alto * 0.24)
    imagen = imagen.convert("RGBA")
    imagen.alpha_composite(capa.filter(ImageFilter.GaussianBlur(12)))
    imagen.alpha_composite(capa)
    ImageDraw.Draw(imagen).text(
        (ancho / 2, alto * 0.8), "ULTRON // NETANYAHU", fill="white",
        anchor="mm", font=ImageFont.load_default(size=max(12, alto // 28)),
    )
    return imagen.convert("RGB")
