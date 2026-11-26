"""`ultron notas` (Markdown con etiquetas) y `ultron tareas` (con fecha y prioridad)."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

import typer
import yaml
from rich.markdown import Markdown
from rich.text import Text

from ultron.nucleo import jsonio, panel, rutas
from ultron.ui import tema

app = typer.Typer()
notas = typer.Typer(help="Notas rápidas en Markdown.", no_args_is_help=True)
tareas = typer.Typer(help="Tareas con fecha y prioridad.", invoke_without_command=True)
app.add_typer(notas, name="notas")
app.add_typer(tareas, name="tareas")


# --- notas -----------------------------------------------------------------------------


def dir_notas() -> Path:
    return rutas.datos() / "notas"


def _slug(texto: str) -> str:
    sin = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", sin).strip("-")[:40] or "nota"


def crear_nota(texto: str, etiquetas: list[str] | None = None) -> Path:
    d = rutas.asegurar(dir_notas())
    ahora = datetime.now()
    titulo = texto.strip().splitlines()[0] if texto.strip() else "nota"
    ruta = d / f"{ahora:%Y%m%d-%H%M%S}-{_slug(titulo)}.md"
    cabecera = yaml.safe_dump({"fecha": ahora.isoformat(timespec="seconds"),
                               "etiquetas": etiquetas or []}, allow_unicode=True).strip()
    ruta.write_text(f"---\n{cabecera}\n---\n\n{texto.strip()}\n", encoding="utf-8")
    return ruta


def leer_nota(ruta: Path) -> tuple[dict, str]:
    texto = ruta.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n\n?(.*)$", texto, re.S)
    if not m:
        return {}, texto
    return yaml.safe_load(m.group(1)) or {}, m.group(2)


def lista_notas() -> list[Path]:
    return sorted(dir_notas().glob("*.md"), reverse=True) if dir_notas().exists() else []


def buscar_nota(ref: str) -> Path:
    todas = lista_notas()
    if ref.isdigit() and 1 <= int(ref) <= len(todas):
        return todas[int(ref) - 1]
    for n in todas:
        if ref in n.stem:
            return n
    raise typer.BadParameter(f"No encuentro la nota «{ref}». Mira: ultron notas lista")


def _editor(inicial: str = "") -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(inicial)
        ruta = f.name
    editor = os.environ.get("EDITOR") or ("notepad" if os.name == "nt" else "nano")
    subprocess.call([editor, ruta])
    texto = Path(ruta).read_text(encoding="utf-8")
    Path(ruta).unlink(missing_ok=True)
    return texto


@notas.command("nueva")
def cmd_nueva(
    texto: list[str] = typer.Argument(None, help="Texto de la nota (vacío: abre el editor)."),
    etiqueta: list[str] = typer.Option(None, "--etiqueta", "-e", help="Etiquetas."),
) -> None:
    """Crea una nota."""
    contenido = " ".join(texto) if texto else _editor()
    if not contenido.strip():
        tema.actual().aviso("Nota vacía: no se guarda.")
        raise typer.Exit(1)
    ruta = crear_nota(contenido, list(etiqueta or []))
    tema.actual().ok(f"Nota guardada: {ruta.name}")


@notas.command("lista")
def cmd_lista_notas() -> None:
    """Lista las notas (las más recientes primero)."""
    t = tema.actual()
    tabla = t.tabla("#", "Fecha", "Nota", "Etiquetas")
    for i, ruta in enumerate(lista_notas(), 1):
        meta, cuerpo = leer_nota(ruta)
        primera = cuerpo.strip().splitlines()[0][:60] if cuerpo.strip() else ""
        tabla.add_row(str(i), str(meta.get("fecha", ""))[:16].replace("T", " "), primera,
                      ", ".join(meta.get("etiquetas") or []))
    t.consola.print(tabla)


@notas.command("ver")
def cmd_ver(ref: str) -> None:
    """Muestra una nota (por número o nombre)."""
    t = tema.actual()
    ruta = buscar_nota(ref)
    meta, cuerpo = leer_nota(ruta)
    t.consola.print(t.panel(Markdown(cuerpo), titulo=ruta.stem))


@notas.command("buscar")
def cmd_buscar_notas(texto: str) -> None:
    """Busca en el texto de las notas."""
    t = tema.actual()
    encontradas = 0
    for i, ruta in enumerate(lista_notas(), 1):
        meta, cuerpo = leer_nota(ruta)
        etiquetas = " ".join(meta.get("etiquetas") or [])
        if texto.lower() in (cuerpo + " " + etiquetas).lower():
            encontradas += 1
            linea = next((ln for ln in cuerpo.splitlines() if texto.lower() in ln.lower()),
                         cuerpo.strip()[:80])
            t.consola.print(f"[acento]{i}[/] {ruta.stem}  [apagado]{linea.strip()[:90]}[/]")
    if not encontradas:
        t.info("Nada.")


@notas.command("borrar")
def cmd_borrar_nota(ref: str) -> None:
    """Borra una nota."""
    ruta = buscar_nota(ref)
    ruta.unlink()
    tema.actual().ok(f"Borrada: {ruta.name}")


# --- tareas -----------------------------------------------------------------------------

DIAS = {"lunes": 0, "martes": 1, "miercoles": 2, "miércoles": 2, "jueves": 3, "viernes": 4,
        "sabado": 5, "sábado": 5, "domingo": 6}
PRIORIDADES = {"alta": 0, "media": 1, "baja": 2}


def ruta_tareas() -> Path:
    return rutas.datos() / "tareas.json"


def cargar() -> list[dict]:
    datos = jsonio.leer(ruta_tareas(), [])
    return datos if isinstance(datos, list) else []


def guardar(lista: list[dict]) -> None:
    jsonio.escribir(ruta_tareas(), lista)
    actualizar_panel(lista)


def interpretar_fecha(texto: str | None, hoy: date | None = None) -> str | None:
    if not texto:
        return None
    hoy = hoy or date.today()
    t = texto.strip().lower()
    if t == "hoy":
        return hoy.isoformat()
    if t in ("mañana", "manana"):
        return (hoy + timedelta(days=1)).isoformat()
    if t in DIAS:
        dias = (DIAS[t] - hoy.weekday()) % 7 or 7
        return (hoy + timedelta(days=dias)).isoformat()
    m = re.match(r"^\+?(\d+)d$", t)
    if m:
        return (hoy + timedelta(days=int(m.group(1)))).isoformat()
    try:
        return date.fromisoformat(t).isoformat()
    except ValueError as e:
        raise typer.BadParameter("Fecha: hoy, mañana, viernes, +3d o AAAA-MM-DD") from e


def grupo(tarea: dict, hoy: date) -> str:
    if not tarea.get("fecha"):
        return "sin fecha"
    f = date.fromisoformat(tarea["fecha"])
    if f <= hoy:
        return "hoy"
    if f <= hoy + timedelta(days=7 - hoy.weekday()):
        return "esta semana"
    return "después"


def actualizar_panel(lista: list[dict], hoy: date | None = None) -> None:
    hoy = hoy or date.today()
    de_hoy = [x for x in lista if grupo(x, hoy) == "hoy" and
              (not x.get("hecha") or x.get("hecha_el", "")[:10] == hoy.isoformat())]
    panel.escribir(tareas={"total": len(de_hoy), "hechas": sum(bool(x.get("hecha"))
                                                                for x in de_hoy)}
                   if de_hoy else None)


@tareas.callback()
def cmd_tareas(ctx: typer.Context) -> None:
    """Sin subcomando: lista de tareas pendientes."""
    if ctx.invoked_subcommand is None:
        cmd_lista(todas=False)


@tareas.command("añadir")
def cmd_anadir(
    texto: list[str] = typer.Argument(...),
    para: str = typer.Option(None, "--para", "-p", help="hoy, mañana, viernes, +3d, AAAA-MM-DD"),
    prioridad: str = typer.Option("media", "--prioridad", help="alta, media o baja."),
    etiqueta: str = typer.Option(None, "--etiqueta", "-e"),
) -> None:
    """Añade una tarea."""
    lista = cargar()
    siguiente = max((x["id"] for x in lista), default=0) + 1
    lista.append({"id": siguiente, "texto": " ".join(texto), "fecha": interpretar_fecha(para),
                  "prioridad": prioridad if prioridad in PRIORIDADES else "media",
                  "etiqueta": etiqueta, "hecha": False,
                  "creada": datetime.now().isoformat(timespec="seconds")})
    guardar(lista)
    tema.actual().ok(f"Tarea {siguiente} añadida.")


@tareas.command("lista")
def cmd_lista(todas: bool = typer.Option(False, "--todas", help="Incluye las hechas.")) -> None:
    """Tareas por hoy, esta semana, después y sin fecha."""
    t = tema.actual()
    hoy = date.today()
    lista = [x for x in cargar() if todas or not x.get("hecha")]
    if not lista:
        t.ok("No hay tareas pendientes.")
        return
    estilos = {"alta": "error", "media": "aviso", "baja": "apagado"}
    for nombre in ("hoy", "esta semana", "después", "sin fecha"):
        del_grupo = sorted((x for x in lista if grupo(x, hoy) == nombre),
                           key=lambda x: (PRIORIDADES.get(x["prioridad"], 1), x.get("fecha") or ""))
        if not del_grupo:
            continue
        t.consola.print(f"\n[bold primario]{nombre}[/]")
        for x in del_grupo:
            marca = t.glifo("ok") if x.get("hecha") else "○"
            linea = Text(f"  {marca} ", style="ok" if x.get("hecha") else "texto")
            linea.append(f"{x['id']:>3} ", style="apagado")
            linea.append(x["texto"], style="apagado" if x.get("hecha") else "texto")
            if x.get("fecha") and nombre != "hoy":
                linea.append(f"  {x['fecha']}", style="acento")
            linea.append(f"  {x['prioridad']}", style=estilos.get(x["prioridad"], "texto"))
            if x.get("etiqueta"):
                linea.append(f"  #{x['etiqueta']}", style="apagado")
            t.consola.print(linea)


def _marcar(id_tarea: int, hecha: bool) -> dict:
    lista = cargar()
    for x in lista:
        if x["id"] == id_tarea:
            x["hecha"] = hecha
            x["hecha_el"] = datetime.now().isoformat(timespec="seconds") if hecha else None
            guardar(lista)
            return x
    raise typer.BadParameter(f"No existe la tarea {id_tarea}.")


@tareas.command("hecha")
def cmd_hecha(id_tarea: int) -> None:
    """Marca una tarea como hecha."""
    x = _marcar(id_tarea, True)
    tema.actual().ok(f"Hecha: {x['texto']}")


@tareas.command("borrar")
def cmd_borrar(id_tarea: int) -> None:
    """Borra una tarea."""
    lista = cargar()
    nueva = [x for x in lista if x["id"] != id_tarea]
    if len(nueva) == len(lista):
        raise typer.BadParameter(f"No existe la tarea {id_tarea}.")
    guardar(nueva)
    tema.actual().ok("Borrada.")
