"""`ultron explica-cmd`, `ultron error` y `ultron sistema`."""

from __future__ import annotations

import platform
import shlex
import socket
import time
from pathlib import Path

import typer
from rich.table import Table
from rich.text import Text

from ultron.compartidas.agente_cmd import evaluar
from ultron.nucleo import rutas
from ultron.nucleo.ejecutor import Ejecutor
from ultron.ui import tema

app = typer.Typer()
COLORES_PARTES = ["primario", "acento", "aviso", "ok", "secundario"]


# --- explica-cmd -----------------------------------------------------------------------


def dividir(comando: str) -> list[dict]:
    """Divide un comando en partes: programa, opciones, argumentos y operadores."""
    lexer = shlex.shlex(comando, posix=True, punctuation_chars="|&;<>")
    lexer.whitespace_split = True
    partes, esperando_programa = [], True
    for token in lexer:
        if token in ("|", "||", "&&", ";", "&", ">", ">>", "<", "2>"):
            partes.append({"texto": token, "tipo": "operador"})
            esperando_programa = token in ("|", "||", "&&", ";", "&")
        elif esperando_programa:
            partes.append({"texto": token, "tipo": "programa"})
            esperando_programa = token == "sudo"
        elif token.startswith("-"):
            partes.append({"texto": token, "tipo": "opcion"})
        else:
            partes.append({"texto": token, "tipo": "argumento"})
    return partes


def explicacion_local(ej: Ejecutor, partes: list[dict]) -> list[str]:
    """Explicación sin IA: `whatis` para programas y la línea de --help para opciones."""
    ayudas: dict[str, str] = {}
    salida = []
    programa = ""
    for p in partes:
        if p["tipo"] == "programa":
            programa = p["texto"]
            r = ej.leer(["whatis", programa]) if ej.existe("whatis") else None
            linea = (r.salida.splitlines() or [""])[0] if r and r.codigo == 0 else ""
            salida.append(linea.split(" - ", 1)[-1].strip() or "programa")
        elif p["tipo"] == "opcion" and programa:
            if programa not in ayudas:
                r = ej.leer([programa, "--help"]) if ej.existe(programa) else None
                ayudas[programa] = (r.salida + r.error) if r else ""
            clave = p["texto"].split("=")[0]
            linea = next((ln.strip() for ln in ayudas[programa].splitlines()
                          if clave in ln.split()), "")
            salida.append(linea[:120] or "opción")
        elif p["tipo"] == "operador":
            salida.append({"|": "pasa la salida al siguiente comando",
                           "&&": "sigue solo si el anterior fue bien",
                           "||": "sigue solo si el anterior falló", ";": "y después",
                           ">": "escribe la salida en un archivo (lo sobrescribe)",
                           ">>": "añade la salida al final de un archivo",
                           "<": "lee la entrada de un archivo", "&": "en segundo plano",
                           }.get(p["texto"], "operador"))
        else:
            salida.append("argumento")
    return salida


@app.command("explica-cmd")
def cmd_explica(
    comando: str = typer.Argument(..., help="El comando entre comillas."),
    sin_ia: bool = typer.Option(False, "--sin-ia", help="Solo con man y --help."),
) -> None:
    """Explica un comando trozo a trozo, con colores y nivel de peligro."""
    t = tema.actual()
    partes = dividir(comando)
    explicaciones: list[str] = []
    resumen = ""
    from ultron.ia.cliente import hay_ia

    if not sin_ia and hay_ia():
        from ultron.ia.util import pedir_json

        with t.spinner_ctx("analizando"):
            r = pedir_json(
                "Explica cada parte de este comando de Linux en una frase corta, en el mismo "
                f"orden. Partes: {[p['texto'] for p in partes]}\nComando: {comando}",
                {"partes": ["explicación de la parte 1", "…"], "resumen": "qué hace en total"})
        if isinstance(r, dict):
            explicaciones = [str(x) for x in r.get("partes") or []]
            resumen = str(r.get("resumen", ""))
    if len(explicaciones) != len(partes):
        explicaciones = explicacion_local(Ejecutor(), partes)
    linea = Text()
    for i, p in enumerate(partes):
        linea.append(p["texto"] + " ", style=f"bold {COLORES_PARTES[i % len(COLORES_PARTES)]}")
    t.consola.print(t.panel(linea, titulo="comando"))
    tabla = Table.grid(padding=(0, 2))
    for i, (p, e) in enumerate(zip(partes, explicaciones, strict=False)):
        tabla.add_row(Text(p["texto"], style=COLORES_PARTES[i % len(COLORES_PARTES)]),
                      Text(p["tipo"], style="apagado"), Text(e))
    t.consola.print(tabla)
    ev = evaluar(comando)
    estilo = {"bajo": "ok", "medio": "aviso", "alto": "error"}[ev.peligro]
    t.consola.print(f"\n[{estilo}]peligro: {ev.peligro}[/] {ev.motivo}")
    if resumen:
        t.info(resumen)


# --- error ---------------------------------------------------------------------------


def ruta_ultimo() -> Path:
    return rutas.estado() / "ultimo_cmd"


def leer_ultimo() -> tuple[int, str] | None:
    try:
        codigo, comando = ruta_ultimo().read_text(encoding="utf-8").rstrip("\n").split("\t", 1)
        return int(codigo), comando.strip()
    except (OSError, ValueError):
        return None


@app.command("error")
def cmd_error(
    sin_ejecutar: bool = typer.Option(False, "--sin-ejecutar",
                                      help="No vuelvas a ejecutar el comando."),
) -> None:
    """La IA lee el último comando que falló, su salida, y te dice cómo arreglarlo."""
    t = tema.actual()
    ultimo = leer_ultimo()
    if not ultimo:
        t.info("No tengo registrado ningún comando (abre una terminal nueva con el modo activo).")
        raise typer.Exit(1)
    codigo, comando = ultimo
    if comando.startswith(("ultron error", "uerr")):
        t.info("El último comando fue este mismo.")
        return
    if codigo == 0:
        t.ok(f"«{comando}» terminó bien (código 0).")
        return
    salida = ""
    if not sin_ejecutar and evaluar(comando).permitido and typer.confirm(
            f"¿Vuelvo a ejecutar «{comando}» para ver el error?", default=True):
        r = Ejecutor().run(["bash", "-c", comando], check=False, timeout=60)
        salida = (r.salida + r.error)[-3000:]
    from ultron.ia.cliente import preguntar_stream

    t.consola.print(t.panel(Text(f"$ {comando}\ncódigo {codigo}\n{salida[-800:]}"),
                            titulo="último error"))
    prompt = (f"Este comando de Ubuntu ha fallado con código {codigo}.\nCOMANDO: {comando}\n"
              f"SALIDA:\n{salida or '(no disponible)'}\n\nExplica la causa en dos frases y da "
              "el comando exacto para arreglarlo.")
    for trozo in preguntar_stream(prompt):
        t.consola.print(trozo, end="", markup=False, highlight=False)
    t.consola.print()


# --- sistema -------------------------------------------------------------------------------


def _bytes(n: float) -> str:
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unidad}"
        n /= 1024
    return f"{n:.1f} PB"


def resumen_sistema() -> list[tuple[str, str, float | None]]:
    import psutil

    from ultron.nucleo.entorno import detectar

    ent = detectar()
    filas: list[tuple[str, str, float | None]] = [
        ("Sistema", f"{ent.distro} {ent.version} · GNOME {ent.gnome or '—'} · "
                    f"{ent.sesion or '—'}", None),
        ("Núcleo", platform.release(), None),
        ("Equipo", socket.gethostname(), None),
    ]
    cpu = psutil.cpu_percent(interval=0.3)
    filas.append(("CPU", f"{psutil.cpu_count()} núcleos · {cpu:.0f}%", cpu / 100))
    mem = psutil.virtual_memory()
    filas.append(("RAM", f"{_bytes(mem.used)} / {_bytes(mem.total)}", mem.percent / 100))
    disco = psutil.disk_usage(str(Path.home().anchor or "/"))
    filas.append(("Disco", f"{_bytes(disco.used)} / {_bytes(disco.total)}", disco.percent / 100))
    ips = [a.address for dirs in psutil.net_if_addrs().values() for a in dirs
           if a.family == socket.AF_INET and not a.address.startswith("127.")]
    filas.append(("Red", ", ".join(ips) or "sin conexión", None))
    bateria = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    if bateria:
        filas.append(("Batería", f"{bateria.percent:.0f}%"
                      f"{' (cargando)' if bateria.power_plugged else ''}", bateria.percent / 100))
    horas = (time.time() - psutil.boot_time()) / 3600
    filas.append(("Encendido", f"{int(horas)} h {int(horas % 1 * 60)} min", None))
    return filas


@app.command("sistema")
def cmd_sistema() -> None:
    """Resumen del sistema con la estética del modo activo."""
    t = tema.actual()
    tabla = Table.grid(padding=(0, 2))
    for nombre, valor, fraccion in resumen_sistema():
        tabla.add_row(Text(nombre, style="acento"), Text(valor),
                      t.barra(fraccion, 20) if fraccion is not None else Text(""))
    t.consola.print(t.panel(tabla, titulo="sistema"))
