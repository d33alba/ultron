"""`ultron exhibicion`: Ultron se presenta solo, sin tocar nada (unos 3 minutos).

Recorre los cinco modos de verdad: transforma el escritorio, lo anuncia con voz, abre una
función de cada modo en su propia ventana (el Ojo de Dios con vuelos y satélites en
Netanyahu), y al final restaura Ubuntu. Ctrl+C la para en cualquier momento y deja el
sistema como estaba.
"""

from __future__ import annotations

import subprocess
import sys
import time

import typer

from ultron.nucleo import voz
from ultron.ui import tema

app = typer.Typer()

GUION: list[tuple[str, str, list[str] | None, int]] = [
    # (modo, narración, función que se abre en su ventana, segundos en pantalla)
    ("netanyahu", "Unidad de inteligencia: OSINT y el Ojo de Dios con vuelos y satélites en "
                  "directo.", ["ojo", "abrir", "--si"], 35),
    ("gaming", "Escritorio cyberpunk, dock vertical neón y un HUD de rendimiento.",
     ["hud", "--demo"], 18),
    ("focus", "Modo túnel: webs que distraen bloqueadas, lluvia de fondo y estadísticas de "
              "estudio.", ["stats", "--demo"], 18),
    ("presentacion", "Escenario: diapositivas a pantalla completa desde un Markdown.",
     ["diapos", "--demo"], 18),
    ("fantasma", "Privacidad: MAC aleatoria, DNS cifrado y rastros fuera.",
     ["mac", "--demo"], 14),
]


def _ultron(*args: str, espera: bool = True) -> subprocess.Popen | int:
    orden = [sys.executable, "-m", "ultron", *args]
    if espera:
        return subprocess.run(orden, check=False, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL).returncode
    return subprocess.Popen(orden, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)


def _ventana(titulo: str, argv: list[str], segundos: int) -> subprocess.Popen | None:
    """Abre la función en una terminal propia que se cierra sola."""
    from ultron.capas.lanzadores import terminal

    guion = f"{sys.executable} -m ultron {' '.join(argv)}; sleep {segundos}"
    try:
        return subprocess.Popen([*terminal(titulo), "bash", "-c", f"timeout {segundos} "
                                 f"bash -c '{guion}'"], stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return None


@app.command("exhibicion")
def cmd_exhibicion(
    rapida: bool = typer.Option(False, "--rapida", help="La mitad de tiempo por modo."),
    sin_ventanas: bool = typer.Option(False, "--sin-ventanas",
                                      help="Solo cambia los escritorios."),
) -> None:
    """Ultron se presenta solo: recorre los cinco modos de verdad y restaura Ubuntu."""
    t = tema.actual()
    c = t.consola
    c.print(t.panel("Ultron va a transformar este escritorio cinco veces y volver a dejarlo "
                    "como estaba. Puedes minimizar esta terminal y mirar.\n"
                    "Ctrl+C para en cualquier momento y restaura todo.",
                    titulo="EXHIBICIÓN"))
    voz.hablar("Iniciando demostración. Observa el escritorio.", None, esperar=True)
    try:
        for i, (id_modo, narracion, funcion, segundos) in enumerate(GUION, 1):
            segundos = max(8, segundos // 2) if rapida else segundos
            c.print(f"\n[bold primario]{i}/5 · {id_modo.upper()}[/] [apagado]{narracion}[/]")
            if _ultron("entrar", id_modo, "--si", "--sin-sudo", "--sin-carga"):
                t.aviso(f"No se pudo entrar en {id_modo}; sigo con el siguiente.")
                continue
            time.sleep(5)  # deja ver el rótulo y el escritorio nuevo
            ventana = None
            if funcion and not sin_ventanas:
                ventana = _ventana(f"ULTRON · {id_modo.upper()}", funcion, segundos)
            voz.hablar(narracion, id_modo)
            time.sleep(segundos)
            if ventana and ventana.poll() is None:
                ventana.terminate()
            if id_modo == "netanyahu":
                _ultron("ojo", "parar")
    except KeyboardInterrupt:
        c.print("\n[aviso]Exhibición interrumpida.[/]")
    finally:
        c.print("\n[bold primario]FIN · restaurando Ubuntu[/]")
        _ultron("salir")
        voz.hablar("Demostración completada. Ubuntu ha vuelto a su estado original.", None)
    t.ok("Exhibición terminada. Todo está como al principio.")
