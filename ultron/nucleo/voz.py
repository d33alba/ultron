"""Voz de ULTRON: anuncia los modos, lee respuestas y avisa de hallazgos.

Motores, por orden: Piper (voz neuronal, sin internet; `ultron voz instalar` la descarga en
~/.local/share/ultron/voz), espeak-ng (paquete apt, más robótica) y spd-say. Cada modo tiene su
forma de hablar (velocidad, tono y volumen). Se apaga con `ultron voz off` o ULTRON_SIN_VOZ=1.
Nunca bloquea ni falla: si no hay altavoz ni motor, simplemente no habla.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ultron.nucleo import config, rutas

PIPER_URL = ("https://github.com/rhasspy/piper/releases/download/2023.11.14-2/"
             "piper_linux_x86_64.tar.gz")
VOZ_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/davefx/medium/"
VOZ_NOMBRE = "es_ES-davefx-medium"


@dataclass(frozen=True)
class Estilo:
    velocidad: float = 1.0  # >1 más lento (Piper length_scale)
    tono: int = 45  # espeak-ng: 0-99
    volumen: int = 100  # 0-100
    variante: str = "m3"  # espeak-ng


ESTILOS = {
    None: Estilo(1.0, 40, 100, "m3"),
    "netanyahu": Estilo(1.05, 30, 100, "m7"),  # grave y seco, informe de operaciones
    "focus": Estilo(1.15, 45, 75, "f2"),  # tranquila
    "gaming": Estilo(0.88, 60, 100, "m3"),  # rápida y con energía
    "presentacion": Estilo(1.0, 50, 100, "m1"),  # presentador
    "fantasma": Estilo(1.25, 20, 55, "whisper"),  # susurro
}

FRASES_ENTRADA = {
    "netanyahu": "Modo Netanyahu activado. Acceso concedido. Unidad de inteligencia en línea.",
    "focus": "Modo foco activado. Distracciones bloqueadas. Solo tú y tus apuntes.",
    "gaming": "Modo gaming activado. Sistemas al máximo. Que empiece la partida.",
    "presentacion": "Modo presentación activado. El escenario es tuyo.",
    "fantasma": "Modo fantasma activado. Nadie te ve.",
}


def dir_voz() -> Path:
    return rutas.datos() / "voz"


def activa() -> bool:
    if os.environ.get("ULTRON_SIN_VOZ") or os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return bool(config.obtener("voz", "activa", True))


def _piper() -> tuple[Path, Path] | None:
    binario = dir_voz() / "piper" / "piper"
    modelo = dir_voz() / f"{VOZ_NOMBRE}.onnx"
    return (binario, modelo) if binario.is_file() and modelo.is_file() else None


def motor() -> str | None:
    if _piper() and _reproductor():
        return "piper"
    for programa in ("espeak-ng", "spd-say"):
        if shutil.which(programa):
            return programa
    return None


def _reproductor() -> list[str] | None:
    for prog, args in (("paplay", ["--raw", "--rate=22050", "--channels=1",
                                   "--format=s16le"]),
                       ("pw-play", ["--rate=22050", "--channels=1", "--format=s16", "-"]),
                       ("aplay", ["-q", "-r", "22050", "-f", "S16_LE", "-c", "1", "-t", "raw"])):
        if shutil.which(prog):
            return [prog, *args]
    return None


def limpiar(texto: str, maximo: int = 600) -> str:
    """Quita Markdown, emojis y símbolos que una voz leería mal."""
    texto = re.sub(r"```.*?```", " ", texto, flags=re.S)
    texto = re.sub(r"[`*_#>|\[\]{}<>~=]+", " ", texto)
    texto = re.sub(r"https?://\S+", "enlace", texto)
    texto = "".join(c for c in texto if c.isalnum() or c.isspace() or c in ".,;:¿?¡!-'()%")
    texto = re.sub(r"\s+", " ", texto).strip()
    if len(texto) > maximo:
        corte = texto.rfind(".", 0, maximo)
        texto = texto[: corte + 1 if corte > 80 else maximo]
    return texto


def comando(texto: str, id_modo: str | None) -> list[list[str]] | None:
    """Tubería de órdenes que pronuncia el texto (lista de procesos encadenados)."""
    e = ESTILOS.get(id_modo, ESTILOS[None])
    m = motor()
    if m == "piper":
        binario, modelo = _piper()  # type: ignore[misc]
        reproducir = _reproductor() or []
        if reproducir and reproducir[0] == "paplay":
            reproducir = [*reproducir, f"--volume={int(65536 * e.volumen / 100)}"]
        return [[str(binario), "--model", str(modelo), "--output-raw", "--length_scale",
                 str(e.velocidad)], reproducir]
    if m == "espeak-ng":
        velocidad = int(165 / e.velocidad)
        return [["espeak-ng", "-v", f"es+{e.variante}", "-s", str(velocidad), "-p", str(e.tono),
                 "-a", str(int(e.volumen * 1.8)), texto]]
    if m == "spd-say":
        return [["spd-say", "-l", "es", "-r", str(int((1 / e.velocidad - 1) * 100)), texto]]
    return None


def hablar(texto: str, id_modo: str | None = None, esperar: bool = False) -> bool:
    """Pronuncia el texto en segundo plano. Devuelve False si no se ha podido."""
    if not activa():
        return False
    if id_modo is None:
        from ultron.nucleo import estado

        id_modo = estado.modo_activo()
    texto = limpiar(texto)
    tuberia = comando(texto, id_modo) if texto else None
    if not tuberia:
        return False
    try:
        if len(tuberia) == 1:
            proc = subprocess.Popen(tuberia[0], stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, start_new_session=True)
        else:
            sintesis = subprocess.Popen(tuberia[0], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                        start_new_session=True)
            proc = subprocess.Popen(tuberia[1], stdin=sintesis.stdout,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    start_new_session=True)
            assert sintesis.stdin is not None
            sintesis.stdin.write(texto.encode("utf-8"))
            sintesis.stdin.close()
            if sintesis.stdout:
                sintesis.stdout.close()
        if esperar:
            proc.wait(timeout=120)
        return True
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def anunciar_modo(id_modo: str | None) -> None:
    if id_modo is None:
        hablar("Sistema restaurado. Todo ha vuelto a su estado original.", None)
    else:
        hablar(FRASES_ENTRADA.get(id_modo, f"Modo {id_modo} activado."), id_modo)


def instalar(progreso=None) -> Path:
    """Descarga Piper y la voz española (unos 80 MB) en ~/.local/share/ultron/voz."""
    import tarfile
    import tempfile

    import httpx

    destino = dir_voz()
    destino.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=120, follow_redirects=True) as cliente:
        if not (destino / "piper" / "piper").is_file():
            with tempfile.TemporaryDirectory() as tmp:
                archivo = Path(tmp) / "piper.tar.gz"
                with cliente.stream("GET", PIPER_URL) as r, archivo.open("wb") as f:
                    r.raise_for_status()
                    for trozo in r.iter_bytes(1 << 16):
                        f.write(trozo)
                with tarfile.open(archivo) as tar:
                    try:
                        tar.extractall(destino, filter="data")
                    except TypeError:  # Python < 3.11.4
                        tar.extractall(destino)  # noqa: S202
        for extension in (".onnx", ".onnx.json"):
            final = destino / f"{VOZ_NOMBRE}{extension}"
            if final.is_file():
                continue
            parcial = final.with_suffix(final.suffix + ".part")
            with cliente.stream("GET", VOZ_BASE + VOZ_NOMBRE + extension) as r, \
                    parcial.open("wb") as f:
                r.raise_for_status()
                for trozo in r.iter_bytes(1 << 16):
                    f.write(trozo)
            parcial.rename(final)
    binario = destino / "piper" / "piper"
    if binario.exists():
        binario.chmod(0o755)
    return destino
