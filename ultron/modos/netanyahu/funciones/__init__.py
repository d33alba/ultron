"""Comandos propios del modo netanyahu."""

import typer

from ultron.modos.netanyahu.generar_recursos import generar

from . import ctf, defensa, hackia, ojo, osint
from .comun import ejecutor, interfaz

app = typer.Typer()
app.registered_commands.extend(defensa.app.registered_commands)
app.registered_commands.extend(hackia.app.registered_commands)
app.add_typer(osint.app, name="osint")
app.add_typer(ctf.app, name="ctf")
app.add_typer(ojo.app, name="ojo")
recursos = typer.Typer(hidden=True)
app.add_typer(recursos, name="netanyahu")


@recursos.command("generar-recursos")
def generar_recursos(ctx: typer.Context) -> None:
    """Genera los recursos originales del aspecto Netanyahu."""
    ej = ejecutor(ctx)
    if ej.simular:
        interfaz().info("Se generarían los recursos originales.")
        return
    with interfaz().spinner_ctx("GENERANDO RECURSOS"):
        generar(ej)
    interfaz().ok("Recursos de Netanyahu listos.")
