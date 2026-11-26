"""Configuraciones neón y estado reversible de turbo."""

from pathlib import Path

import psutil

from ultron.capas.sistema import NOTIF
from ultron.nucleo import jsonio, rutas
from ultron.nucleo.ejecutor import Ejecutor, ErrorEjecucion

MANGOHUD = """legacy_layout=false
position=top-left
fps
frametime
cpu_stats
gpu_stats
background_color=0B0B16
text_color=00F0FF
cpu_color=FF00E6
gpu_color=8A2BE2
fps_color=39FF14
font_size=22
font_scale=1.0
"""
CAVA = """[general]
framerate = 60
bars = 36

[color]
background = '#0B0B16'
gradient = 1
gradient_count = 4
gradient_color_1 = '#FF00E6'
gradient_color_2 = '#8A2BE2'
gradient_color_3 = '#00F0FF'
gradient_color_4 = '#39FF14'
"""
MINERO = "tracker-miner-fs-3.service"


def archivo_turbo():
    return rutas.estado() / "gaming-turbo.json"


def leer_turbo() -> dict:
    return jsonio.leer(archivo_turbo(), {})


def activar(ej, vaciar: bool = False) -> dict:
    previo = leer_turbo()
    if previo:
        return previo
    perfil = ej.leer(["powerprofilesctl", "get"]).salida.strip() if (
        ej.existe("powerprofilesctl")
    ) else ""
    aviso = ej.gsettings_get(NOTIF, "show-banners")
    activo = ej.existe("systemctl") and ej.leer(
        ["systemctl", "--user", "is-active", MINERO]
    ).salida.strip() == "active"
    pausar = ej.existe("tracker3") and (activo or not ej.existe("systemctl"))
    previo = {"perfil": perfil, "aviso": aviso, "minero": activo and not pausar,
              "pausar": pausar}
    if not ej.simular:
        jsonio.escribir(archivo_turbo(), previo)
    try:
        _aplicar(ej, previo, vaciar)
    except (OSError, psutil.Error, ErrorEjecucion):
        desactivar(ej, previo)
        raise
    return previo


def _aplicar(ej: Ejecutor, previo: dict, vaciar: bool) -> None:
    perfil, aviso, activo = previo["perfil"], previo["aviso"], previo["minero"]
    if perfil and perfil != "performance":
        ej.run(["powerprofilesctl", "set", "performance"])
    if aviso is not None:
        ej.gsettings_set(NOTIF, "show-banners", "false")
    if activo:
        ej.run(["systemctl", "--user", "stop", MINERO])
    elif previo["pausar"]:
        # Tracker reanuda el indexado automáticamente al terminar este cliente.
        resultado = ej.run(
            ["tracker3", "daemon", "--miner", "Files", "--pause-for-process", "Ultron Gaming"],
            fondo=True,
        )
        if resultado.salida.isdigit() and not ej.simular:
            proceso = psutil.Process(int(resultado.salida))
            previo["tracker"] = [proceso.pid, proceso.create_time()]
            jsonio.escribir(archivo_turbo(), previo)
    if vaciar:
        ej.escribir(Path("/proc/sys/vm/drop_caches"), "3\n", sudo=True)


def desactivar(ej, previo: dict | None = None) -> None:
    previo = leer_turbo() if previo is None else previo
    if not previo:
        return
    if previo.get("perfil") and previo["perfil"] != "performance":
        ej.run(["powerprofilesctl", "set", previo["perfil"]])
    if previo.get("aviso") is not None:
        ej.gsettings_set(NOTIF, "show-banners", previo["aviso"])
    if previo.get("minero"):
        ej.run(["systemctl", "--user", "start", MINERO])
    if previo.get("tracker") and not ej.simular:
        pid, inicio = previo["tracker"]
        try:
            proceso = psutil.Process(pid)
            if proceso.create_time() == inicio:
                proceso.terminate()
        except psutil.NoSuchProcess:
            pass
    ej.borrar(archivo_turbo())

