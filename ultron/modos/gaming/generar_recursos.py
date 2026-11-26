"""Genera la ciudad, el arranque y los efectos de audio de Gaming."""

import io
import random
import wave
from math import pi, sin
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ultron.nucleo import rutas
from ultron.nucleo.ejecutor import Ejecutor

CIUDAD = "tema/fondo.png"
BLOQUEO = "tema/bloqueo.png"
SONIDOS = {
    "entrada": (300, 1050), "salida": (1100, 210), "logro": (450, 1650),
    "message-new-instant": (520, 980), "dialog-error": (450, 100),
}


def fondo(semilla: int = 2077, ancho: int = 3840, alto: int = 2160) -> Image.Image:
    rng = random.Random(semilla)
    imagen = Image.new("RGB", (ancho, alto))
    dibujo = ImageDraw.Draw(imagen)
    horizonte = int(alto * 0.73)
    for y in range(alto):
        t = y / alto
        dibujo.line((0, y, ancho, y), fill=(int(11 + 65*t), int(8 + 15*t), int(22 + 65*t)))
    radio = int(alto * 0.23)
    cx, cy = ancho // 2, alto * 41 // 100
    for dy in range(-radio, radio):
        if (dy + radio) // max(2, alto // 120) % 5 == 4:
            continue
        dx = int((radio**2 - dy**2)**0.5)
        dibujo.line((cx-dx, cy+dy, cx+dx, cy+dy),
                    fill=(255, int(42 + 160 * (radio-dy)/(2*radio)), 115))
    for profundidad in range(3):
        x = -ancho // 30
        while x < ancho:
            w = rng.randint(max(2, ancho // 65), max(3, ancho // 19))
            y = horizonte - rng.randint(alto//12, alto//(3+profundidad))
            color = (29 - 7*profundidad, 15 - 3*profundidad, 49 - 10*profundidad)
            dibujo.rectangle((x, y, x+w, horizonte), fill=color)
            dibujo.line((x, y, x+w, y), fill=(91, 31, 122))
            paso = max(3, alto//105)
            for wx in range(x+paso, x+w-paso//2, paso):
                for wy in range(y+paso, horizonte-paso//2, paso):
                    if rng.random() < 0.27:
                        dibujo.rectangle((wx, wy, wx+paso//3, wy+paso//4),
                                         fill=rng.choice(("#FF00E6", "#00F0FF", "#8A2BE2")))
            x += w + rng.randint(2, max(2, ancho // 80))
    dibujo.rectangle((0, horizonte+1, ancho, alto), fill="#130d25")
    brillo = Image.new("RGB", imagen.size)
    luces = ImageDraw.Draw(brillo)
    for i in range(-12, 13):
        luces.line((cx, horizonte, cx+i*ancho//10, alto), fill="#00A0B0",
                   width=max(1, ancho//1400))
    for i in range(1, 13):
        y = horizonte + int((alto-horizonte)*(i/12)**2)
        luces.line((0, y, ancho, y), fill="#D300BE", width=max(1, alto//850))
    fuente = ImageFont.load_default(size=max(12, alto//10))
    luces.text((cx, alto*14//100), "ULTRON", font=fuente, anchor="mm", fill="#00F0FF")
    from PIL import ImageChops

    imagen = ImageChops.lighter(imagen, brillo.filter(ImageFilter.GaussianBlur(alto/120)))
    imagen = ImageChops.lighter(imagen, brillo)
    dibujo = ImageDraw.Draw(imagen)
    for y in range(0, alto, max(4, alto//250)):
        dibujo.line((0, y, ancho, y), fill="#100d24")
    return imagen


def png(imagen: Image.Image) -> bytes:
    destino = io.BytesIO()
    imagen.save(destino, format="PNG", compress_level=3)
    return destino.getvalue()


def barrido(inicio: int, final: int) -> bytes:
    destino = io.BytesIO()
    muestras = 8820
    with wave.open(destino, "wb") as audio:
        audio.setparams((1, 2, 22050, 0, "NONE", ""))
        audio.writeframes(b"".join(
            int(13000 * sin(2*pi*(inicio*i+(final-inicio)*i*i/(2*muestras))/22050)
                * sin(pi*i/muestras)**2).to_bytes(2, "little", signed=True)
            for i in range(muestras)
        ))
    return destino.getvalue()


def ruta_recurso(nombre: str) -> Path:
    return rutas.datos() / "recursos" / "gaming" / nombre


def regenerar(ej: Ejecutor, semilla: int) -> Path:
    ciudad = ruta_recurso(CIUDAD)
    bloqueo = ruta_recurso(BLOQUEO)
    if ej.simular:
        ej.escribir(ciudad, b"")
        ej.escribir(bloqueo, b"")
    else:
        imagen = fondo(semilla)
        ej.escribir(ciudad, png(imagen))
        ej.escribir(bloqueo, png(imagen.filter(ImageFilter.GaussianBlur(25))))
    return ciudad


def recurso_generado(relativa: str | Path, ej: Ejecutor) -> Path | None:
    nombre = Path(relativa).as_posix()
    destino = ruta_recurso(nombre)
    if nombre in (CIUDAD, BLOQUEO):
        if not destino.is_file():
            regenerar(ej, 2077)
        return destino
    if nombre.startswith("tema/sonidos/") and destino.suffix == ".wav":
        if destino.stem not in SONIDOS:
            return None
        if not destino.is_file() and not ej.simular:
            ej.escribir(destino, barrido(*SONIDOS[destino.stem]))
        return destino
    fotogramas = {f"estrella-{i:02}.png": i for i in range(1, 13)}
    if nombre.startswith("tema/arranque/") and (
        destino.name in fotogramas or destino.name == "logo.png"
    ):
        if not destino.is_file() and not ej.simular:
            imagen = Image.new("RGBA", (500, 180))
            dibujo = ImageDraw.Draw(imagen)
            fuente = ImageFont.load_default(size=92)
            dibujo.text((250, 90), "ULTRON", font=fuente, fill="#00F0FF", anchor="mm")
            if i := fotogramas.get(destino.name):
                rng = random.Random(i)
                for _ in range(14):
                    x, y = rng.randrange(490), rng.randrange(180)
                    dibujo.rectangle((x, y, x+rng.randrange(6, 50), y+rng.randrange(1, 6)),
                                     fill=rng.choice(("#FF00E6", "#8A2BE2", "#00F0FF")))
            ej.escribir(destino, png(imagen))
        return destino
    return None



def generar(ej: Ejecutor | None = None) -> None:
    """Precarga los recursos locales al instalar el modo."""
    ej = ej or Ejecutor()
    for nombre in (
        CIUDAD, BLOQUEO, "tema/arranque/logo.png",
        *(f"tema/arranque/estrella-{i:02}.png" for i in range(1, 13)),
        *(f"tema/sonidos/{n}.wav" for n in ("entrada", "salida", "logro")),
        *(f"tema/sonidos/stereo/{n}.wav" for n in ("message-new-instant", "dialog-error")),
    ):
        recurso_generado(nombre, ej)
