"""Asistente de diagnóstico local con comandos de solo lectura."""

import json
import shlex

import typer
from rich.text import Text

from ultron.ia.cliente import preguntar
from ultron.ia.util import reparar_json

from .comun import ejecutor, fallo, interfaz, permiso, requerir

app = typer.Typer()
CATALOGO = {
    ("uname", "-r"): "Versión del núcleo.",
    ("uptime",): "Tiempo de actividad y carga.",
    ("free", "-h"): "Uso de memoria.",
    ("df", "-h"): "Espacio disponible.",
    ("ip", "addr", "show"): "Direcciones de las interfaces locales.",
    ("ip", "route", "show"): "Rutas del equipo local.",
    ("ss", "-tuln"): "Sockets TCP y UDP en escucha.",
    ("systemctl", "--failed", "--no-pager"): "Unidades que han fallado.",
}


def comando_permitido(comando: str) -> tuple[str, ...] | None:
    try:
        argumentos = tuple(shlex.split(comando))
    except ValueError:
        return None
    return argumentos if argumentos in CATALOGO else None


@app.command("hackia")
def hackia(ctx: typer.Context, solicitud: str) -> None:
    """Propone diagnósticos locales y pide aprobación para cada comando."""
    ej = ejecutor(ctx)
    t = interfaz()
    if ej.simular:
        t.info("Se pediría a la IA un plan de diagnóstico local.")
        return
    permiso(ej)
    respuesta = preguntar(
        "Eres un analista defensivo de Ubuntu. Elige hasta 5 comandos exactos del catálogo "
        'de solo lectura. Devuelve solo JSON: {"explicacion":"", "pasos":[{"comando":"", '
        '"que_hace":"", "peligro":"bajo"}]}. Catálogo: '
        + json.dumps([" ".join(cmd) for cmd in CATALOGO])
        + "\nSolicitud: " + solicitud[:2000], json=True,
    )
    try:
        plan = reparar_json(respuesta)
        pasos = plan["pasos"]
        if not isinstance(pasos, list):
            raise ValueError
    except (ValueError, TypeError, KeyError):
        fallo("La IA no devolvió un plan válido.")
    t.consola.print(Text(str(plan.get("explicacion", ""))))
    tabla = t.tabla("Comando", "Qué hace", "Riesgo")
    elegidos = []
    for paso in pasos[:5]:
        if not isinstance(paso, dict) or not isinstance(paso.get("comando"), str):
            continue
        argumentos = comando_permitido(paso["comando"])
        if argumentos is None:
            t.aviso("Se bloqueó un comando fuera del catálogo de diagnóstico.")
            continue
        elegidos.append(argumentos)
        tabla.add_row(shlex.join(argumentos), CATALOGO[argumentos], "bajo")
    t.consola.print(tabla)
    todos = False
    for argumentos in elegidos:
        decision = "s" if todos else typer.prompt(
            f"¿Ejecutar {shlex.join(argumentos)}? (s/n/todos/editar)", default="n",
            show_default=False,
        ).strip().lower()
        if decision == "editar":
            editado = typer.prompt("Comando", default=shlex.join(argumentos))
            argumentos = comando_permitido(editado)
            if argumentos is None:
                t.aviso("Se bloqueó un comando fuera del catálogo de diagnóstico.")
                continue
            decision = typer.prompt(
                f"¿Ejecutar {shlex.join(argumentos)}? (s/n)", default="n", show_default=False,
            ).strip().lower()
        if decision not in {"s", "sí", "todos"}:
            continue
        todos = todos or decision == "todos"
        requerir(ej, argumentos[0], {"ip": "iproute2", "ss": "iproute2"}.get(argumentos[0]))
        resultado = ej.run(list(argumentos), check=False)
        t.consola.print(Text(resultado.salida or resultado.error))
