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
        self.ej.escribir(destino / "index.theme", (
            f"[Sound Theme]\nName={destino.name}\nInherits=Yaru,freedesktop\n"
            "Directories=stereo\n\n[stereo]\nOutputProfile=stereo\n"))
        previo = C.capturar_claves(self.ej, [(SONIDO, "theme-name"), (SONIDO, "event-sounds")])
        C.fijar_si_existe(self.ej, previo, SONIDO, "theme-name", C.gv_str(destino.name))
        C.fijar_si_existe(self.ej, previo, SONIDO, "event-sounds",
                          C.gv_bool(cfg.get("eventos", True)))
        entrada = self.ctx.recurso(cfg.get("entrada", "tema/sonidos/entrada.oga"))
        if not entrada.exists():
            entrada = entrada.with_suffix(".wav")
        prog = reproductor_efecto(self.ej)
        if entrada.exists() and prog:
            self.ej.run([*prog, str(entrada)], check=False, fondo=True)

    def restaurar(self, previo: dict) -> None:
        C.restaurar_claves(self.ej, previo.get("claves", {}))
        self.ej.borrar(self._dir())


# --- música ------------------------------------------------------------------------


def detener_musica(ej: Ejecutor | None = None) -> None:
    ej = ej or Ejecutor()
    pid = estado.obtener("musica_pid")
    if not ej.simular:
        C.matar(pid)
        estado.actualizar(musica_pid=None)
        panel.escribir(musica_sonando=False)


def silenciar(ej: Ejecutor | None = None) -> None:
    """Para la música y oculta la bocina hasta la próxima vez que se entre en el modo."""
    detener_musica(ej)
    estado.actualizar(musica_silenciada=True)
    panel.escribir(musica_silenciada=True, musica_sonando=False)


def reproducir(ej: Ejecutor, archivo: Path, cfg: dict) -> bool:
    if not archivo.exists() or not ej.existe("mpv"):
        return False
    detener_musica(ej)
    cmd = ["mpv", "--no-video", "--really-quiet", "--no-terminal",
           f"--volume={int(cfg.get('volumen', 80))}"]
    if cfg.get("bucle", True):
        cmd.append("--loop-file=inf")
    fundido = float(cfg.get("fundido_entrada_s", 0))
    if fundido > 0:
        cmd.append(f"--af=lavfi=[afade=t=in:d={fundido}]")
    cmd.append(str(archivo))
    res = ej.run(cmd, check=False, fondo=True)
    if not ej.simular:
        estado.actualizar(musica_pid=int(res.salida) if res.salida.isdigit() else None,
                          musica_archivo=str(archivo), musica_silenciada=False)
        panel.escribir(musica_sonando=True, musica_silenciada=False)
    return True


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
        if not archivo.exists():
            if self.ctx.consola is not None:
                self.ctx.consola.print(
                    f"[apagado]  sin música: falta {archivo.name} "
                    f"(ultron musica importar <url> --modo {self.ctx.modo.id})[/]")
            return
        if not self.ej.existe("mpv"):
            if self.ctx.consola is not None:
                self.ctx.consola.print("[aviso]  falta mpv para la música: sudo apt install mpv[/]")
            return
        reproducir(self.ej, archivo, cfg)

    def restaurar(self, previo: dict) -> None:
        detener_musica(self.ej)
        if not self.ej.simular:
            estado.actualizar(musica_silenciada=None, musica_archivo=None, musica_cfg=None)
