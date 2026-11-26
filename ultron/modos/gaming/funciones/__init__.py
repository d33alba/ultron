"""Comandos de Gaming disponibles desde cualquier modo."""

import os
import sys

import httpx
import psutil
import typer
from rich.columns import Columns
from rich.panel import Panel
from rich.text import Text

from ultron.modos.gaming.generar_recursos import regenerar
from ultron.nucleo import estado, rutas, xp
from ultron.nucleo.ejecutor import Ejecutor, ErrorEjecucion
from ultron.ui import tema

from . import ajustes, biblioteca, clips, hud

app = typer.Typer()
gaming = typer.Typer(help="Recursos del modo Gaming.")
clip = typer.Typer(help="Graba y guarda los últimos segundos.", invoke_without_command=True)
app.add_typer(gaming, name="gaming")
app.add_typer(clip, name="clip")

DEMO = [
    biblioteca.Juego("Portal 2", "Steam", ("steam", "steam://rungameid/620")),
    biblioteca.Juego("Celeste", "Lutris", ("lutris",)),
    biblioteca.Juego("SuperTuxKart", "Flatpak",
                     ("flatpak", "run", "net.supertuxkart.SuperTuxKart")),
]


def _ej() -> Ejecutor:
    from ultron.cli import GLOBAL

    return Ejecutor(simular=GLOBAL["simular"], consola=tema.actual().consola)


def _fallar(mensaje: str, codigo: int = 1) -> None:
    tema.actual().error(mensaje)
    raise typer.Exit(codigo)


def _dependencia(ej: Ejecutor, programa: str, paquete: str | None = None) -> None:
    if not ej.existe(programa) and not ej.simular:
        _fallar(f"Instala {programa} con «sudo apt install {paquete or programa}».", 2)


def _portada(ej: Ejecutor, juego: biblioteca.Juego) -> Text:
    if not juego.portada or not ej.existe("chafa") or ej.simular:
        return Text()
    imagen = rutas.cache() / "portadas" / f"{juego.portada}.jpg"
    try:
        if not imagen.is_file():
            base = "https://cdn.cloudflare.steamstatic.com/steam/apps"
            respuesta = httpx.get(f"{base}/{juego.portada}/header.jpg", timeout=2)
            respuesta.raise_for_status()
            ej.escribir(imagen, respuesta.content)
        salida = ej.leer(["chafa", "--format=symbols", "--size=24x6", str(imagen)], timeout=3)
        return Text.from_ansi(salida.salida) if salida.ok else Text()
    except (OSError, httpx.HTTPError, ErrorEjecucion):
        return Text()


@app.command()
def juegos(juego: str = typer.Argument(None, help="Número o nombre del juego."),
           demo: bool = typer.Option(False, "--demo", help="Muestra juegos de ejemplo.")) -> None:
    """Explora la biblioteca y lanza tus juegos."""
    ej = _ej()
    t = tema.actual()
    lista = DEMO if demo else biblioteca.detectar(ej)
    if juego is None:
        if not lista:
            t.info("No se encontraron juegos instalados.")
            return
        cartas = []
        for i, ficha in enumerate(lista, 1):
            texto = Text(f"{i:02}  {ficha.nombre}\n", style="#00F0FF")
            texto.append(ficha.origen, style="#FF00E6")
            if not demo and (portada := _portada(ej, ficha)):
                texto.append("\n").append_text(portada)
            cartas.append(Panel(texto, width=30, border_style="#8A2BE2"))
        t.consola.print(Columns(cartas, equal=True))
        return
    elegido = biblioteca.buscar(lista, juego)
    if elegido is None:
        _fallar(f"No encuentro el juego «{juego}».")
        return
    if demo:
        t.info(f"Lanzamiento de demostración · {elegido.nombre}")
        return
    comando = list(elegido.comando)
    _dependencia(ej, comando[0], "libglib2.0-bin" if comando[0] == "gio" else None)
    if estado.obtener("gaming_fps"):
        if elegido.origen == "Flatpak":
            comando[2:2] = ["--env=MANGOHUD=1"]
        elif ej.existe("mangohud"):
            comando.insert(0, "mangohud")
    if ajustes.leer_turbo() and ej.existe("gamemoderun"):
        comando.insert(0, "gamemoderun")
    ej.run(comando, fondo=True)
    t.ok(f"Lanzado · {elegido.nombre}")


@app.command()
def fps(accion: str = typer.Argument("on", help="on u off.")) -> None:
    """Configura el contador neón de MangoHud."""
    ej = _ej()
    if accion not in {"on", "off"}:
        _fallar("Usa «ultron fps on» o «ultron fps off».", 2)
    if accion == "on":
        _dependencia(ej, "mangohud")
        fuente = rutas.xdg_datos_raiz() / "fonts/ultron/JetBrainsMonoNerd.ttf"
        conf = ajustes.MANGOHUD
        if fuente.is_file():
            conf += f"font_file={fuente.as_posix()}\n"
        ej.escribir(rutas.xdg_config_raiz() / "MangoHud/MangoHud.conf", conf)
    if not ej.simular:
        estado.actualizar(gaming_fps=accion == "on")
    tema.actual().ok(f"Contador FPS · {'activado' if accion == 'on' else 'desactivado'}")


@app.command()
def visualizador(ventana: bool = typer.Option(False, "--ventana")) -> None:
    """Muestra el espectro de audio en neón con cava."""
    ej = _ej()
    _dependencia(ej, "cava")
    conf = rutas.config() / "cava/gaming.conf"
    ej.escribir(conf, ajustes.CAVA)
    comando = ["cava", "-p", str(conf)]
    if ventana:
        if ej.existe("gnome-terminal"):
            prefijo = ["gnome-terminal", "--"]
        elif ej.existe("x-terminal-emulator") or ej.simular:
            prefijo = ["x-terminal-emulator", "-e"]
        else:
            _fallar("Instala gnome-terminal con «sudo apt install gnome-terminal».", 2)
            return
        ej.run([*prefijo, *comando], fondo=True)
    else:
        ej.run(comando, timeout=None, interactivo=True)


def _recursos(t, etiqueta: str) -> None:
    tabla = t.tabla("PID", "Proceso", "RAM", titulo=etiqueta)
    for pid, nombre, memoria in hud.procesos():
        tabla.add_row(str(pid), Text(nombre), f"{memoria/1024**2:.0f} MiB")
    t.consola.print(tabla)
    t.info(f"RAM disponible · {psutil.virtual_memory().available / 1024**2:.0f} MiB")


@app.command()
def turbo(
    accion: str = typer.Argument("estado", help="on, off o estado."),
    vaciar: bool = typer.Option(False, "--vaciar-cache"),
    matar: int = typer.Option(None, "--matar", min=1, help="PID de la lista a terminar."),
    interactivo: bool = typer.Option(False, "--interactivo", help="Abre el panel de procesos."),
) -> None:
    """Activa o restaura el perfil de rendimiento."""
    ej = _ej()
    t = tema.actual()
    if accion not in {"on", "off", "estado"}:
        _fallar("Usa on, off o estado.", 2)
    if accion == "estado":
        t.info("Turbo activado." if ajustes.leer_turbo() else "Turbo desactivado.")
    else:
        _recursos(t, "Antes")
        if accion == "on":
            _dependencia(ej, "gamemoderun", "gamemode")
            if vaciar and not ej.simular and not typer.confirm("¿Vaciar la caché con sudo?"):
                vaciar = False
            ajustes.activar(ej, vaciar)
        else:
            ajustes.desactivar(ej)
        _recursos(t, "Después")
    if interactivo and sys.stdin.isatty() and t.consola.is_terminal:
        hud.PantallaProcesos(ej.simular).run()
    if matar is not None:
        if matar not in {fila[0] for fila in hud.procesos()} or matar == os.getpid():
            _fallar("Selecciona el PID de un proceso de la lista.")
        try:
            proceso = psutil.Process(matar)
            if not ej.simular and typer.confirm(f"¿Terminar el proceso {matar}?"):
                proceso.terminate()
        except psutil.Error as error:
            _fallar(f"No se pudo terminar el proceso {matar} ({type(error).__name__}).")


@app.command("hud")
def cmd_hud(demo: bool = typer.Option(False, "--demo"),
            una_vez: bool = typer.Option(False, "--una-vez")) -> None:
    """Abre el HUD en directo. Pulsa q para salir."""
    t = tema.actual()
    medidor = hud.Medidor(_ej(), demo)
    if una_vez or not sys.stdin.isatty() or not t.consola.is_terminal:
        t.consola.print(medidor.cuadro(not tema.soporta_unicode()))
    else:
        hud.PantallaHUD(medidor).run()


@clip.callback()
def cmd_clip(ctx: typer.Context, segundos: int = typer.Option(
    30, "--segundos", min=5, max=600, help="Duración del búfer circular."
)) -> None:
    """Inicia el búfer de grabación."""
    if ctx.invoked_subcommand is None:
        try:
            tema.actual().ok(clips.iniciar(_ej(), segundos))
        except (ValueError, OSError, psutil.Error) as error:
            _fallar(str(error), 2)


@clip.command()
def guardar() -> None:
    """Guarda el clip en la carpeta Vídeos."""
    try:
        tema.actual().ok(clips.guardar(_ej()))
    except (ValueError, OSError, psutil.Error) as error:
        _fallar(str(error))


@clip.command()
def parar() -> None:
    """Detiene el grabador."""
    try:
        clips.parar(_ej())
    except (OSError, psutil.Error) as error:
        _fallar(str(error))
    tema.actual().ok("Grabación detenida.")


@gaming.command()
def fondo(semilla: int = typer.Option(2077, "--semilla")) -> None:
    """Regenera la ciudad cyberpunk y el fondo de bloqueo."""
    tema.actual().ok(str(regenerar(_ej(), semilla)))


@app.command()
def perfil() -> None:
    """Muestra la ficha y los logros del jugador."""
    t = tema.actual()
    datos = xp.leer()
    tabla = t.tabla("Logro", "Estado", titulo=f"Ficha del jugador · {rutas.home().name}")
    for id_, nombre in xp.LOGROS.items():
        tabla.add_row(nombre, "Desbloqueado" if id_ in datos["logros"] else "Pendiente")
    t.info(f"Nivel {xp.nivel(datos['xp'])} · {datos['xp']} XP")
    t.consola.print(tabla)
