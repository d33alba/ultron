"""`ultron voz`: la voz de ULTRON (activar, desactivar, probar, hacerle decir algo)."""

from __future__ import annotations

import typer

from ultron.nucleo import config, voz
from ultron.ui import tema

app = typer.Typer()
grupo = typer.Typer(help="La voz de ULTRON: anuncia los modos y lee respuestas.",
                    invoke_without_command=True)
app.add_typer(grupo, name="voz")


@grupo.callback()
def cmd_voz(ctx: typer.Context) -> None:
    """Estado de la voz."""
    if ctx.invoked_subcommand:
        return
    t = tema.actual()
    m = voz.motor()
    nombres = {"piper": "Piper (neuronal)", "espeak-ng": "espeak-ng", "spd-say": "spd-say"}
    estado = "activada" if voz.activa() else "desactivada"
    t.info(f"Voz {estado} · motor: {nombres.get(m or '', 'ninguno')}")
    if m != "piper":
        t.info("Para la voz neuronal: ultron voz instalar")


@grupo.command("on")
def cmd_on() -> None:
    """Activa la voz."""
    config.fijar("voz", "activa", True)
    tema.actual().ok("Voz activada.")
    voz.hablar("Voz activada.")


@grupo.command("off")
def cmd_off() -> None:
    """Silencia la voz."""
    config.fijar("voz", "activa", False)
    tema.actual().ok("Voz desactivada.")


@grupo.command("di")
def cmd_di(texto: str = typer.Argument(..., help="Lo que ULTRON debe decir.")) -> None:
    """ULTRON dice el texto con la voz del modo activo."""
    if not voz.hablar(texto, esperar=True):
        tema.actual().aviso("No hay voz disponible (ultron voz instalar o apt install espeak-ng).")


@grupo.command("probar")
def cmd_probar() -> None:
    """Presenta cada voz de modo."""
    for id_modo, frase in voz.FRASES_ENTRADA.items():
        tema.actual().info(f"{id_modo}: {frase}")
        if not voz.hablar(frase, id_modo, esperar=True):
            tema.actual().aviso("No hay voz disponible.")
            return


@grupo.command("instalar")
def cmd_instalar() -> None:
    """Descarga la voz neuronal (Piper, unos 80 MB, funciona sin internet después)."""
    t = tema.actual()
    with t.spinner_ctx("Descargando la voz de ULTRON"):
        destino = voz.instalar()
    t.ok(f"Voz instalada en {destino}")
    voz.hablar("Hola. Soy Ultron. Sistemas de voz en línea.", esperar=True)
