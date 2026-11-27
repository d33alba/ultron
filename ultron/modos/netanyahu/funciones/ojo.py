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


CAPAS = {"vuelos": "f", "satelites": "s", "satélites": "s"}
CAPAS_DEFECTO = "vuelos,satelites"


def url_vista(lat: float = 40.4, lon: float = -3.7, alt: float = 20_000_000,
              capas: str = CAPAS_DEFECTO) -> str:
    """Enlace que abre el globo ya situado y con capas (formato de enlace v2 del proyecto)."""
    from urllib.parse import urlencode

    fichas = [CAPAS[c.strip().lower()] for c in capas.split(",") if c.strip().lower() in CAPAS]
    vista = {"v": 2, "lat": f"{lat:.4f}", "lon": f"{lon:.4f}", "alt": int(alt), "heading": 0,
             "pitch": -90, "roll": 0}
    if fichas:
        vista["l"] = ".".join(dict.fromkeys(fichas))
    return f"{URL}/?welcome=0#{urlencode(vista)}"


NODE_DIST = "https://nodejs.org/dist/latest-v24.x/"


def dir_node() -> Path:
    return rutas.datos() / "node"


def _usar_node_portatil() -> bool:
    """Pone el Node portátil de Ultron delante en el PATH (lo heredan npm y vite)."""
    binario = dir_node() / "bin"
    if not (binario / "node").is_file():
        return False
    if str(binario) not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = f"{binario}{os.pathsep}{os.environ.get('PATH', '')}"
    return True


def descargar_node(ej: Ejecutor) -> None:
    """Descarga el Node 24 oficial de nodejs.org, comprueba su SHA-256 y lo descomprime en
    ~/.local/share/ultron/node. No toca el Node del sistema ni pide sudo."""
    import hashlib
    import platform
    import tarfile
    import tempfile

    arq = {"x86_64": "x64", "amd64": "x64", "aarch64": "arm64", "arm64": "arm64"}.get(
        platform.machine().lower())
    if arq is None:
        fallo(f"No hay Node portátil para {platform.machine()}.", 2)
    with httpx.Client(timeout=60, follow_redirects=True) as cliente:
        sumas = cliente.get(NODE_DIST + "SHASUMS256.txt")
        sumas.raise_for_status()
        linea = next((x for x in sumas.text.splitlines()
                      if x.endswith(f"-linux-{arq}.tar.xz")), None)
        if linea is None:
            fallo("No encuentro Node 24 en nodejs.org.", 2)
        huella, nombre = linea.split()
        with tempfile.TemporaryDirectory() as tmp:
            archivo = Path(tmp) / nombre
            h = hashlib.sha256()
            with cliente.stream("GET", NODE_DIST + nombre) as r, archivo.open("wb") as f:
                r.raise_for_status()
                for trozo in r.iter_bytes(1 << 16):
                    h.update(trozo)
                    f.write(trozo)
            if h.hexdigest() != huella:
                fallo("La descarga de Node no coincide con su huella SHA-256. Cancelado.", 1)
            with tarfile.open(archivo) as tar:
                try:
                    tar.extractall(tmp, filter="data")
                except TypeError:  # Python < 3.11.4
                    tar.extractall(tmp)  # noqa: S202 (archivo oficial con huella comprobada)
            origen = Path(tmp) / nombre.removesuffix(".tar.xz")
            if dir_node().exists():
                import shutil

                shutil.rmtree(dir_node())
            dir_node().parent.mkdir(parents=True, exist_ok=True)
            origen.rename(dir_node())


def comprobar_node(ej: Ejecutor, si: bool = False) -> None:
    if ej.simular:
        ej.run(["node", "--version"])
        return
    _usar_node_portatil()
    if ej.existe("node") and version_valida(ej.run(["node", "--version"]).salida):
        requerir(ej, "npm")
        return
    t = interfaz()
    t.info("El Ojo de Dios necesita Node 24 y este sistema tiene otra versión.")
    if not si and not typer.confirm("¿Descargo Node 24 oficial (nodejs.org, unos 30 MB) solo "
                                    "para Ultron, sin tocar el del sistema?", default=True):
        fallo("Sin Node 24 no se puede abrir el Ojo de Dios.", 2)
    with t.spinner_ctx("DESCARGANDO NODE 24"):
        descargar_node(ej)
    if not _usar_node_portatil() or not version_valida(ej.run(["node", "--version"]).salida):
        fallo("No se pudo preparar Node 24.", 1)
    t.ok("Node 24 listo.")


def preparar(ej: Ejecutor, destino: Path, si: bool = False) -> None:
    comprobar_node(ej, si)
    if not ej.simular:
        requerir(ej, "git")
        destino.parent.mkdir(parents=True, exist_ok=True)
    with (nullcontext() if ej.simular else interfaz().spinner_ctx("INSTALANDO GOD'S EYE VIEW")):
        if not (destino / ".git").exists():
            ej.run(["git", "clone", "--depth", "1", REPO, str(destino)], timeout=180)
        ej.run(["npm", "ci"], directorio=destino, timeout=900)
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


def _abrir(ctx: typer.Context, kiosko: bool, url: str = URL, si: bool = False) -> None:
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
        t.info("Primera vez: hay que instalar God's Eye View (unos minutos).")
        if not si and not typer.confirm("¿Lo instalo ahora?", default=True):
            raise typer.Exit(2)
        preparar(ej, destino, si=True)
    if _proceso() is None:
        if _responde():
            fallo("El puerto 4173 ya está ocupado por otro servidor.")
        comprobar_node(ej, si=True)
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


SI = typer.Option(False, "--si", help="Sin preguntas (instala lo que falte).")
CAPAS_OPC = typer.Option(CAPAS_DEFECTO, "--capas",
                         help="Capas al abrir: vuelos, satelites (separadas por comas) o ninguna.")


@app.callback(invoke_without_command=True)
def entrada(ctx: typer.Context, kiosko: bool = typer.Option(False, "--kiosko"),
            si: bool = SI, capas: str = CAPAS_OPC) -> None:
    """Abre el globo 3D local con vuelos y satélites en directo."""
    if ctx.invoked_subcommand is None:
        _abrir(ctx, kiosko, url_vista(capas=capas), si=si)


@app.command("abrir")
def abrir(ctx: typer.Context, kiosko: bool = typer.Option(False, "--kiosko"),
          si: bool = SI, capas: str = CAPAS_OPC) -> None:
    """Abre el globo con vuelos y satélites en directo (lo instala si hace falta)."""
    _abrir(ctx, kiosko, url_vista(capas=capas), si=si)


@app.command("instalar")
def instalar(ctx: typer.Context, si: bool = SI) -> None:
    """Clona el proyecto, prepara Node 24 si hace falta y comprueba la instalación."""
    preparar(ejecutor(ctx), carpeta(), si=si)


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
    """Vuela con el globo hasta un lugar o coordenadas, con vuelos y satélites."""
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
    _abrir(ctx, False, url_vista(lat, lon, 80000))
