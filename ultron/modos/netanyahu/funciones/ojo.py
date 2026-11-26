"""Ciclo de vida del globo local God's Eye View."""

import math
import os
import re
import time
from contextlib import nullcontext
from pathlib import Path

import httpx
import psutil
import typer
from rich.live import Live
from rich.text import Text

from ultron.nucleo import jsonio, rutas
from ultron.nucleo.ejecutor import Ejecutor
from ultron.ui.tema import animaciones_activas

from .comun import ejecutor, fallo, interfaz, mostrar, requerir, texto_terminal

app = typer.Typer(help="Instala y abre el globo 3D de God's Eye View.")
REPO = "https://github.com/bilawalsidhu/gods-eye-view.git"
URL = "http://127.0.0.1:4173"


def carpeta() -> Path:
    return rutas.datos() / "ojo" / "gods-eye-view"


def archivo_estado() -> Path:
    return rutas.estado() / "ojo.json"


def version_valida(salida: str) -> bool:
    version = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", salida.strip())
    if version is None:
        return False
    mayor, menor, parche = map(int, version.groups())
    return mayor == 26 or (mayor == 24 and (menor, parche) >= (14, 0))


def comprobar_node(ej: Ejecutor) -> None:
    if ej.simular:
        ej.run(["node", "--version"])
        return
    if ej.existe("node") and version_valida(ej.run(["node", "--version"]).salida):
        requerir(ej, "npm")
        return
    shell = os.environ.get("SHELL", "")
    nvm = rutas.home() / ".nvm" / "nvm.sh"
    if Path(shell).name in {"bash", "zsh"} and nvm.is_file() and typer.confirm(
        "¿Instalar Node 24 mediante el nvm del usuario?"
    ):
        ej.run([shell, "-c", '. "$1" && nvm install 24', "ultron", str(nvm)], timeout=300)
    fallo("Activa Node 24.14 o posterior de la rama 24 con nvm use 24 y vuelve a intentarlo. "
          "También puedes instalar Node 24 desde NodeSource.", 2)


def preparar(ej: Ejecutor, destino: Path) -> None:
    comprobar_node(ej)
    if not ej.simular:
        requerir(ej, "git")
        destino.parent.mkdir(parents=True, exist_ok=True)
    if not (destino / ".git").exists():
        ej.run(["git", "clone", "--depth", "1", REPO, str(destino)], timeout=180)
    ej.run(["npm", "ci"], directorio=destino, timeout=600)
    ej.run(["npm", "run", "doctor"], directorio=destino, timeout=180)
    ej.escribir(destino.parent / "instalado", "ok\n")


def lanzar(ej: Ejecutor, destino: Path, log: Path):
    return ej.run(["npm", "run", "dev", "--", "--port", "4173", "--strictPort",
                   "--host", "127.0.0.1"], fondo=True, directorio=destino, registro=log)


def _proceso() -> psutil.Process | None:
    datos = jsonio.leer(archivo_estado(), {})
    try:
        proc = psutil.Process(datos["pid"])
        if proc.create_time() == datos["inicio"] and proc.status() != psutil.STATUS_ZOMBIE:
            return proc
    except (KeyError, TypeError, ValueError, psutil.Error):
        return None
    return None


def _responde() -> bool:
    try:
        return httpx.get(URL, timeout=1, trust_env=False).is_success
    except httpx.HTTPError:
        return False


def _globo(fase: int) -> Text:
    filas = []
    for y in range(-4, 5):
        radio = 9 * math.sqrt(1 - (y / 5)**2)
        filas.append("".join(
            " " if abs(x) > radio else "·" if abs(x) > radio - 1 else
            "│" if (x + fase) % 4 == 0 else "─" if y in (-2, 0, 2) else " "
            for x in range(-9, 10)
        ))
    return Text(texto_terminal("ESTABLECIENDO ENLACE SATELITAL\n\n" + "\n".join(filas)),
                style="acento")


def _detener(ej: Ejecutor, proc: psutil.Process) -> None:
    requerir(ej, "kill", "procps")
    ej.run(["kill", "-TERM", "--", f"-{proc.pid}"], check=False)
    if ej.simular:
        return
    try:
        proc.wait(timeout=4)
    except psutil.TimeoutExpired:
        fallo("El servidor sigue activo. Consulta ultron ojo estado.")
    ej.borrar(archivo_estado())


def _abrir(ctx: typer.Context, kiosko: bool, url: str = URL) -> None:
    ej = ejecutor(ctx)
    t = interfaz()
    destino = carpeta()
    navegador = ["firefox", "--kiosk"] if kiosko else ["xdg-open"]
    log = rutas.estado() / "ojo.log"
    if ej.simular:
        lanzar(ej, destino, log)
        ej.run([*navegador, url], fondo=True)
        return
    requerir(ej, navegador[0], "firefox" if kiosko else "xdg-utils")
    if not (destino.parent / "instalado").is_file():
        if not typer.confirm("¿Instalar God's Eye View?"):
            raise typer.Exit(2)
        preparar(ej, destino)
    if _proceso() is None:
        if _responde():
            fallo("El puerto 4173 ya está ocupado por otro servidor.")
        comprobar_node(ej)
        log.parent.mkdir(parents=True, exist_ok=True)
        resultado = lanzar(ej, destino, log)
        try:
            proc = psutil.Process(int(resultado.salida))
            jsonio.escribir(archivo_estado(), {"pid": proc.pid, "inicio": proc.create_time(),
                                               "registro": str(log)})
        except (ValueError, psutil.Error):
            fallo(f"No se pudo iniciar el servidor. Consulta {log}.")
    animar = animaciones_activas()
    pantalla = (Live(console=t.consola, auto_refresh=False, transient=True)
                if animar else nullcontext())
    if not animar:
        t.info("ESTABLECIENDO ENLACE SATELITAL")
    with pantalla as vivo:
        for i in range(35):
            if vivo is not None:
                vivo.update(t.panel(_globo(i % 10)), refresh=True)
            if _proceso() is None:
                break
            if _responde():
                ej.run([*navegador, url], fondo=True)
                return
            time.sleep(.25)
    pendiente = _proceso()
    if pendiente is not None:
        _detener(ej, pendiente)
    fallo(f"God's Eye View no respondió. Consulta {log}.")


@app.callback(invoke_without_command=True)
def entrada(ctx: typer.Context, kiosko: bool = typer.Option(False, "--kiosko")) -> None:
    """Abre el globo 3D local."""
    if ctx.invoked_subcommand is None:
        _abrir(ctx, kiosko)


@app.command("abrir")
def abrir(ctx: typer.Context, kiosko: bool = typer.Option(False, "--kiosko")) -> None:
    """Inicia el servidor y abre su interfaz en el navegador."""
    _abrir(ctx, kiosko)


@app.command("instalar")
def instalar(ctx: typer.Context) -> None:
    """Clona el proyecto y comprueba su instalación."""
    with interfaz().spinner_ctx("INSTALANDO GOD'S EYE VIEW"):
        preparar(ejecutor(ctx), carpeta())


@app.command("estado")
def estado() -> None:
    """Muestra si el globo está instalado y si su servidor sigue activo."""
    proc = _proceso()
    mostrar("OJO", {"instalado": (carpeta().parent / "instalado").is_file(),
                    "PID": proc.pid if proc else None,
                    "registro": str(rutas.estado() / "ojo.log")})


@app.command("parar")
def parar(ctx: typer.Context) -> None:
    """Detiene el servidor iniciado por Ultron."""
    proc = _proceso()
    if proc is None:
        interfaz().info("El servidor está detenido.")
        return
    _detener(ejecutor(ctx), proc)


@app.command("actualizar")
def actualizar(ctx: typer.Context) -> None:
    """Actualiza el repositorio y reinstala las dependencias bloqueadas."""
    ej = ejecutor(ctx)
    destino = carpeta()
    if not ej.simular:
        if _proceso():
            fallo("Detén el servidor con ultron ojo parar antes de actualizar.")
        if not (destino / ".git").is_dir():
            fallo("Instala el proyecto con ultron ojo instalar.", 2)
        requerir(ej, "git")
    comprobar_node(ej)
    ej.run(["git", "pull", "--ff-only"], directorio=destino, timeout=180)
    preparar(ej, destino)


@app.command("objetivo")
def objetivo(ctx: typer.Context, lugar: str) -> None:
    """Abre la vista con las coordenadas indicadas cuando el proyecto admite el enlace."""
    from urllib.parse import urlencode

    try:
        lat, lon = map(float, lugar.split(","))
    except ValueError:
        if ejecutor(ctx).simular:
            interfaz().info("Se buscaría el lugar indicado.")
            _abrir(ctx, False)
            return
        try:
            respuesta = httpx.get("https://geocoding-api.open-meteo.com/v1/search",
                                  params={"name": lugar, "count": 1, "language": "es"}, timeout=8)
            respuesta.raise_for_status()
            punto = respuesta.json()["results"][0]
            lat, lon = float(punto["latitude"]), float(punto["longitude"])
        except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError):
            fallo("No se encontró el lugar. Introduce latitud y longitud separadas por coma.", 2)
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        fallo("Coordenadas fuera de rango.", 2)
    url = URL
    formato = carpeta() / "src" / "view" / "index.js"
    if formato.is_file() and "viewToParams" in formato.read_text(encoding="utf-8"):
        url += "/#" + urlencode({"v": 2, "lat": f"{lat:.4f}", "lon": f"{lon:.4f}",
                                  "alt": 80000, "pitch": -90, "heading": 0, "roll": 0})
    else:
        interfaz().aviso("La instalación no reconoce el formato de enlace de coordenadas.")
    _abrir(ctx, False, url)
