"""Capas sonido (tema de sonidos del sistema) y musica (con bocina para silenciar)."""

from __future__ import annotations

from pathlib import Path

from ultron.capas import comun as C
from ultron.capas.base import Capa, registrar_capa
from ultron.nucleo import estado, panel, rutas
from ultron.nucleo.ejecutor import Ejecutor

SONIDO = "org.gnome.desktop.sound"
EXTENSIONES_AUDIO = (".oga", ".ogg", ".wav")


def reproductor_efecto(ej: Ejecutor) -> list[str] | None:
    for prog in ("pw-play", "paplay", "aplay"):
        if ej.existe(prog):
            return [prog]
    return None


@registrar_capa
class CapaSonido(Capa):
    nombre = "sonido"
    orden = 45
    descripcion = "Sonidos del sistema propios del modo"

    def _dir(self) -> Path:
        return rutas.xdg_datos_raiz() / "sounds" / f"Ultron-{self.ctx.modo.id}"

    def capturar(self, cfg: dict) -> dict:
        return {"claves": C.capturar_claves(
            self.ej, [(SONIDO, "theme-name"), (SONIDO, "event-sounds")])}

    def aplicar(self, cfg: dict) -> None:
        origen = self.ctx.recurso(cfg.get("carpeta", "tema/sonidos"))
        destino = self._dir()
        if origen.is_dir():
            for f in origen.iterdir():
                if f.suffix.lower() in EXTENSIONES_AUDIO:
                    self.ej.copiar(f, destino / "stereo" / f.name)
        if self.ctx.modo.id in {"netanyahu", "gaming"}:
            for nombre in ("message-new-instant.wav", "dialog-error.wav"):
                if not any((origen / nombre).with_suffix(e).is_file() for e in EXTENSIONES_AUDIO):
                    archivo = self.ctx.respaldo(f"tema/sonidos/stereo/{nombre}", self.ej)
                    self.ej.copiar(archivo, destino / "stereo" / nombre)
        self.ej.escribir(destino / "index.theme", (
            f"[Sound Theme]\nName={destino.name}\nInherits=Yaru,freedesktop\n"
            "Directories=stereo\n\n[stereo]\nOutputProfile=stereo\n"))
        previo = C.capturar_claves(self.ej, [(SONIDO, "theme-name"), (SONIDO, "event-sounds")])
        C.fijar_si_existe(self.ej, previo, SONIDO, "theme-name", C.gv_str(destino.name))
        C.fijar_si_existe(self.ej, previo, SONIDO, "event-sounds",
                          C.gv_bool(cfg.get("eventos", True)))
        entrada = self.ctx.recurso(cfg.get("entrada", "tema/sonidos/entrada.oga"))
        if not entrada.exists():
            entrada = self.ctx.respaldo(
                Path(cfg.get("entrada", "tema/sonidos/entrada.oga")).with_suffix(".wav"),
                self.ej,
            )
            if self.ctx.modo.id == "netanyahu" and not entrada.is_relative_to(origen):
                from ultron.modos.netanyahu.generar_recursos import entrada_sonora

                entrada = entrada_sonora(entrada, self.ej)
        prog = reproductor_efecto(self.ej)
        if entrada.exists() and prog:
            self.ej.run([*prog, str(entrada)], check=False, fondo=True)

    def restaurar(self, previo: dict) -> None:
        if self.ctx.modo.id == "gaming" and not self.ej.simular:
            salida = self.ctx.respaldo("tema/sonidos/salida.wav", self.ej)
            if prog := reproductor_efecto(self.ej):
                self.ej.run([*prog, str(salida)], check=False, fondo=True)
        C.restaurar_claves(self.ej, previo.get("claves", {}))
        self.ej.borrar(self._dir())


# --- música ------------------------------------------------------------------------


def detener_musica(ej: Ejecutor | None = None) -> None:
    ej = ej or Ejecutor()
    pid = estado.obtener("musica_pid")
    if not ej.simular:
        try:  # se lanzó en su propia sesión: así cae también el paplay del bucle
            import os
            import signal

            os.killpg(int(pid), signal.SIGTERM)
        except (AttributeError, OSError, TypeError, ValueError):
            pass
        C.matar(pid)
        estado.actualizar(musica_pid=None)
        panel.escribir(musica_sonando=False)


def silenciar(ej: Ejecutor | None = None) -> None:
    """Para la música y oculta la bocina hasta la próxima vez que se entre en el modo."""
    detener_musica(ej)
    estado.actualizar(musica_silenciada=True)
    panel.escribir(musica_silenciada=True, musica_sonando=False)


SIN_MP3 = (".ogg", ".oga", ".wav", ".flac")


def orden_musica(ej: Ejecutor, archivo: Path, cfg: dict) -> list[str] | None:
    """mpv si está; si no (PC sin sudo), VLC, ffplay o paplay en bucle con la copia .ogg."""
    volumen = int(cfg.get("volumen", 80))
    bucle = cfg.get("bucle", True)
    if ej.existe("mpv"):
        cmd = ["mpv", "--no-video", "--really-quiet", "--no-terminal", f"--volume={volumen}"]
        if bucle:
            cmd.append("--loop-file=inf")
        fundido = float(cfg.get("fundido_entrada_s", 0))
        if fundido > 0:
            cmd.append(f"--af=lavfi=[afade=t=in:d={fundido}]")
        return [*cmd, str(archivo)]
    if ej.existe("cvlc"):
        return ["cvlc", "--intf", "dummy", "--no-video", "--quiet", f"--gain={volumen / 100:.2f}",
                *(["--loop"] if bucle else []), str(archivo)]
    if ej.existe("ffplay"):
        return ["ffplay", "-nodisp", "-loglevel", "quiet", "-volume", str(volumen),
                *(["-loop", "0"] if bucle else ["-autoexit"]), str(archivo)]
    compatible = archivo if archivo.suffix.lower() in SIN_MP3 else next(
        (archivo.with_suffix(s) for s in SIN_MP3 if archivo.with_suffix(s).is_file()), None)
    if compatible and ej.existe("paplay"):
        vol = int(65536 * volumen / 100)
        repetir = "while :; do" if bucle else "for _ in 1; do"
        return ["bash", "-c", f'{repetir} paplay --volume={vol} "$0" || exit; done',
                str(compatible)]
    return None


def reproducir(ej: Ejecutor, archivo: Path, cfg: dict) -> bool:
    cmd = orden_musica(ej, archivo, cfg) if archivo.exists() else None
    if cmd is None:
        return False
    detener_musica(ej)
    res = ej.run(cmd, check=False, fondo=True)
    if not ej.simular:
        estado.actualizar(musica_pid=int(res.salida) if res.salida.isdigit() else None,
                          musica_archivo=str(archivo), musica_silenciada=False)
        panel.escribir(musica_sonando=True, musica_silenciada=False)
    return True


def generar_ambiente(tipo: str, ej: Ejecutor, segundos: int = 40) -> Path:
    """Sonido ambiente original (ruido marrón con olas de lluvia), en bucle sin cortes."""
    import math
    import random
    import struct
    import wave

    destino = rutas.cache() / "ambiente" / f"{tipo}.wav"
    if destino.exists() or ej.simular:
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    tasa, n = 22050, 22050 * segundos
    rng = random.Random(7)
    valor, muestras = 0.0, []
    for i in range(n):
        valor = (valor + rng.uniform(-1, 1) * 0.02) * 0.998
        ola = 0.75 + 0.25 * math.sin(2 * math.pi * i / (tasa * (segundos / 4)))
        gota = rng.uniform(-1, 1) * 0.04 if tipo == "lluvia" else 0.0
        muestras.append(max(-1.0, min(1.0, (valor * 3.2 + gota) * ola)))
    funde = tasa  # 1 s de fundido cruzado para que el bucle no se note
    for i in range(funde):
        t = i / funde
        muestras[i] = muestras[i] * t + muestras[n - funde + i] * (1 - t)
    muestras = muestras[: n - funde]
    with wave.open(str(destino), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(tasa)
        w.writeframes(b"".join(struct.pack("<h", int(m * 30000)) for m in muestras))
    return destino


@registrar_capa
class CapaMusica(Capa):
    nombre = "musica"
    orden = 90
    descripcion = "Música del modo, con una bocina en la barra para silenciarla"

    def capturar(self, cfg: dict) -> dict:
        return {}

    def aplicar(self, cfg: dict) -> None:
        if not self.ej.simular:
            estado.actualizar(musica_silenciada=False, musica_cfg=cfg)
        archivo = self.ctx.recurso(cfg.get("archivo", "tema/musica.mp3"))
        if not archivo.exists() and cfg.get("ambiente"):
            archivo = generar_ambiente(str(cfg["ambiente"]), self.ej)
        if not archivo.exists():
            if self.ctx.consola is not None:
                self.ctx.consola.print(
                    f"[apagado]  sin música: falta {archivo.name} "
                    f"(ultron musica importar <url> --modo {self.ctx.modo.id})[/]")
            return
        if not reproducir(self.ej, archivo, cfg) and self.ctx.consola is not None:
            self.ctx.consola.print("[aviso]  falta mpv para la música: sudo apt install mpv[/]")

    def restaurar(self, previo: dict) -> None:
        detener_musica(self.ej)
        if not self.ej.simular:
            estado.actualizar(musica_silenciada=None, musica_archivo=None, musica_cfg=None)
