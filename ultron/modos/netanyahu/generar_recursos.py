"""Generación de recursos originales en el directorio XDG de Ultron."""

import io
import wave
from math import pi, sin
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ultron.nucleo import rutas
from ultron.nucleo.ejecutor import Ejecutor

from .generar_fondo import estrella, fondo


def _png(imagen: Image.Image) -> bytes:
    archivo = io.BytesIO()
    imagen.save(archivo, format="PNG")
    return archivo.getvalue()


def _pitido(frecuencia: int) -> bytes:
    destino = io.BytesIO()
    with wave.open(destino, "wb") as audio:
        audio.setparams((1, 2, 22050, 0, "NONE", ""))
        audio.writeframes(b"".join(
            int(10000 * sin(2*pi*frecuencia*i/22050) * sin(pi*i/4400)**2
                * (i % 1100 < 800)).to_bytes(2, "little", signed=True)
            for i in range(4400)
        ))
    return destino.getvalue()


def recurso_generado(relativa: str | Path, ej: Ejecutor | None = None) -> Path | None:
    """Genera solo el recurso solicitado y conserva las personalizaciones del usuario."""
    relativa = Path(relativa).as_posix()
    destino = rutas.datos() / "recursos" / "netanyahu" / relativa
    sonidos = {
        "tema/sonidos/entrada.wav": 1250,
        "tema/sonidos/stereo/message-new-instant.wav": 850,
        "tema/sonidos/stereo/dialog-error.wav": 320,
    }
    es_fotograma = relativa in {f"tema/arranque/estrella-{i:02}.png" for i in range(1, 13)}
    if relativa not in {"tema/fondo.png", "tema/emblema.png", "tema/arranque/logo.png"}:
        if relativa not in sonidos and not es_fotograma:
            return None
    if destino.is_file() or (ej is not None and ej.simular):
        return destino
    ej = ej or Ejecutor()
    if relativa in sonidos:
        datos = _pitido(sonidos[relativa])
    elif relativa == "tema/fondo.png":
        datos = _png(fondo())
    else:
        emblema = relativa == "tema/emblema.png"
        imagen = Image.new("RGBA", (128, 128) if emblema else (400, 320))
        progreso = int(destino.stem.split("-")[-1]) / 12 if es_fotograma else 1
        estrella(imagen, 49 if emblema else 110, progreso)
        if not emblema:
            ImageDraw.Draw(imagen).text(
                (200, 291), "ULTRON", fill="white", anchor="mm",
                font=ImageFont.load_default(size=28),
            )
        datos = _png(imagen)
    ej.escribir(destino, datos)
    return destino


def entrada_sonora(wav: Path, ej: Ejecutor) -> Path:
    ogg = wav.with_suffix(".oga")
    if wav.exists() and not ogg.exists() and not ej.simular and ej.existe("ffmpeg"):
        ej.run(["ffmpeg", "-nostdin", "-n", "-i", str(wav), "-c:a", "libvorbis",
                str(ogg)], check=False)
    return ogg if ogg.is_file() else wav


def generar(ej: Ejecutor | None = None) -> None:
    ej = ej or Ejecutor()
    for nombre in (
        "tema/fondo.png", "tema/emblema.png", "tema/arranque/logo.png",
        "tema/sonidos/entrada.wav", "tema/sonidos/stereo/message-new-instant.wav",
        "tema/sonidos/stereo/dialog-error.wav",
        *(f"tema/arranque/estrella-{i:02}.png" for i in range(1, 13)),
    ):
        recurso_generado(nombre, ej)
    wav = recurso_generado("tema/sonidos/entrada.wav", ej)
    if wav is not None:
        entrada_sonora(wav, ej)
