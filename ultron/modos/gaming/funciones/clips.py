"""Grabación de pantalla con búfer en disco y exportación de clips."""

import math
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import psutil

from ultron.nucleo import jsonio, rutas
from ultron.nucleo.ejecutor import Ejecutor

SEGMENTO = 5


def carpeta() -> Path:
    return rutas.cache() / "gaming-clips"


def destino() -> Path:
    origen = os.environ.get("XDG_VIDEOS_DIR")
    if not origen:
        archivo = rutas.xdg_config_raiz() / "user-dirs.dirs"
        if archivo.is_file():
            for linea in archivo.read_text(encoding="utf-8").splitlines():
                if linea.startswith("XDG_VIDEOS_DIR="):
                    origen = linea.split("=", 1)[1].strip('"').replace("$HOME", str(rutas.home()))
                    break
    return (Path(origen) if origen else rutas.home() / "Vídeos") / "Ultron"


def segmentos(directorio: Path, segundos: int) -> list[Path]:
    archivos = sorted(directorio.glob("tramo-*.mkv"))
    return archivos[-math.ceil(segundos / SEGMENTO):]


def concatenacion(archivos: list[Path], salida: Path, segundos: int) -> list[str]:
    return ["ffmpeg", "-nostdin", "-n", "-f", "concat", "-safe", "0",
            "-protocol_whitelist", "file,pipe", "-i", "pipe:0",
            "-ss", str((-segundos) % SEGMENTO if len(archivos) * SEGMENTO >= segundos else 0),
            "-t", str(segundos), "-c:v", "libx264", "-preset", "fast", str(salida)]


def lista_concat(archivos: list[Path]) -> str:
    return "".join("file 'file:" + p.resolve().as_posix().replace("'", "'\\''") + "'\n"
                   for p in archivos)


def _proceso(datos: dict) -> psutil.Process | None:
    try:
        proceso = psutil.Process(datos["pid"])
        if proceso.create_time() == datos["inicio"] and proceso.status() != psutil.STATUS_ZOMBIE:
            return proceso
    except (KeyError, psutil.NoSuchProcess):
        pass
    return None


def iniciar(ej: Ejecutor, segundos: int) -> str:
    registro = carpeta() / "grabador.json"
    if _proceso(jsonio.leer(registro, {})):
        return "El búfer ya está grabando."
    if sys.platform != "linux" and not ej.simular:
        raise ValueError("El grabador requiere una sesión gráfica de Linux.")
    sesion = os.environ.get("XDG_SESSION_TYPE", "").lower()
    videos = destino()
    if ej.existe("gpu-screen-recorder"):
        motor = "gpu"
        comando = ["gpu-screen-recorder", "-w", "portal" if sesion == "wayland" else "screen",
                   "-f", "60", "-r", str(segundos), "-o", str(videos)]
    elif ej.existe("ffmpeg") and (sesion == "wayland" or os.environ.get("DISPLAY")):
        motor = "segmentos"
        if sesion != "wayland":
            fuente = "x11"
        elif "gnome" in os.environ.get("XDG_CURRENT_DESKTOP", "").casefold():
            fuente = "gnome"
        elif ej.existe("wf-recorder"):
            fuente = "wlroots"
        else:
            raise ValueError("Instala wf-recorder o usa gpu-screen-recorder para Wayland.")
        comando = [sys.executable, "-m", __name__, fuente, str(segundos)]
    else:
        raise ValueError("Instala ffmpeg y wf-recorder en Wayland, o usa gpu-screen-recorder.")
    if not ej.simular:
        carpeta().mkdir(parents=True, exist_ok=True)
        videos.mkdir(parents=True, exist_ok=True)
        for archivo in carpeta().glob("tramo-*.mkv"):
            ej.borrar(archivo)
        ej.borrar(carpeta() / "grabador.log")
    resultado = ej.run(comando, fondo=True, registro=carpeta() / "grabador.log")
    if not ej.simular:
        proceso = psutil.Process(int(resultado.salida))
        inicio = proceso.create_time()
        time.sleep(0.3)
        if not _proceso({"pid": proceso.pid, "inicio": inicio}):
            raise ValueError(f"No arrancó el grabador. Consulta {carpeta() / 'grabador.log'}.")
        jsonio.escribir(registro, {"pid": proceso.pid, "inicio": inicio,
                                 "motor": motor, "segundos": segundos})
    return f"Búfer iniciado ({segundos} s). Usa «ultron clip guardar» o «ultron clip parar»."


def guardar(ej: Ejecutor) -> str:
    datos = jsonio.leer(carpeta() / "grabador.json", {})
    proceso = _proceso(datos)
    if not proceso:
        raise ValueError("Inicia el búfer con «ultron clip» antes de guardar.")
    if datos["motor"] == "gpu":
        if not ej.simular:
            proceso.send_signal(signal.SIGUSR1)
        return f"Guardado solicitado al grabador en {destino()}."
    if not ej.existe("ffmpeg"):
        raise ValueError("Instala ffmpeg con «sudo apt install ffmpeg».")
    archivos = segmentos(carpeta(), datos["segundos"])
    if not archivos:
        raise ValueError("Aún no hay segmentos completos. Espera unos segundos.")
    salida = destino() / datetime.now().strftime("clip-%Y%m%d-%H%M%S-%f.mkv")
    if ej.simular:
        ej.run(concatenacion(archivos, salida, datos["segundos"]), entrada=lista_concat(archivos))
    else:
        with TemporaryDirectory(dir=carpeta()) as temporal:
            copias = []
            for archivo in archivos:
                copia = Path(temporal) / archivo.name
                try:
                    os.link(archivo, copia)
                except FileNotFoundError:
                    continue
                copias.append(copia)
            if not copias:
                raise ValueError("El búfer acaba de rotar. Vuelve a solicitar el clip.")
            ej.run(concatenacion(copias, salida, datos["segundos"]),
                   entrada=lista_concat(copias), timeout=120)
    return str(salida)


def parar(ej: Ejecutor) -> None:
    registro = carpeta() / "grabador.json"
    proceso = _proceso(jsonio.leer(registro, {}))
    if proceso and not ej.simular:
        proceso.send_signal(signal.SIGINT)
        proceso.wait(timeout=10)
    ej.borrar(registro)


def comando_tramo(fuente: str, parcial: Path) -> list[str]:
    if fuente == "x11":
        return ["ffmpeg", "-nostdin", "-y", "-f", "x11grab", "-framerate", "30",
                "-i", os.environ["DISPLAY"], "-t", str(SEGMENTO), "-c:v", "libx264",
                "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(parcial)]
    if fuente == "gnome":
        return ["/usr/bin/python3", str(Path(__file__).with_name("captura_gnome.py")),
                str(parcial), str(SEGMENTO)]
    return ["wf-recorder", "-c", "libx264", "-f", str(parcial)]


def grabar(fuente: str, segundos: int) -> None:
    from ultron.nucleo.ejecutor import ErrorEjecucion

    ej = Ejecutor()
    conservar = math.ceil(segundos / SEGMENTO) + 1
    parcial = carpeta() / "captura.mkv"
    hijo = None
    try:
        while True:
            ej.borrar(parcial)
            comando = comando_tramo(fuente, parcial)
            if fuente == "wlroots":
                resultado = ej.run(comando, fondo=True, registro=carpeta() / "grabador.log")
                hijo = psutil.Process(int(resultado.salida))
                time.sleep(SEGMENTO)
                hijo.send_signal(signal.SIGINT)
                hijo.wait(timeout=8)
                hijo = None
            else:
                try:
                    ej.run(comando, timeout=SEGMENTO + 15)
                except ErrorEjecucion:
                    if fuente != "gnome":
                        raise
                    helper = Path(__file__).with_name("captura_portal.py")
                    resultado = ej.run(
                        ["/usr/bin/python3", str(helper), str(carpeta()), str(conservar)],
                        fondo=True, registro=carpeta() / "grabador.log",
                    )
                    hijo = psutil.Process(int(resultado.salida))
                    if hijo.wait() != 0:
                        raise ErrorEjecucion(
                            "Falló la grabación por el portal. Consulta el registro."
                        ) from None
                    return
            os.replace(parcial, carpeta() / f"tramo-{time.time_ns()}.mkv")
            for anterior in sorted(carpeta().glob("tramo-*.mkv"))[:-conservar]:
                ej.borrar(anterior)
    except KeyboardInterrupt:
        if hijo and hijo.is_running():
            hijo.send_signal(signal.SIGINT)
            hijo.wait(timeout=8)
    except (ErrorEjecucion, OSError, psutil.Error) as error:
        from ultron.ui import tema

        tema.actual().error(f"Se detuvo la grabación: {error}")
    finally:
        ej.borrar(parcial)


if __name__ == "__main__":
    grabar(sys.argv[1], int(sys.argv[2]))

