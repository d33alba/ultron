"""NEXUS: abre el centro de mando y ejecuta lo que se elija, volviendo después al panel."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from ultron.nucleo import rutas

AVISO_ENTRADA = ("✔ Sistema transformado. Cierra o minimiza esta terminal y mira tu escritorio: "
                 "fondo, iconos, dock, widgets y funciones nuevas.")


def _ruta_marca() -> Path:
    return rutas.cache() / "nexus-arranque"


def _toca_arranque() -> bool:
    """La animación de arranque solo se ve si hace más de 10 minutos de la última."""
    if os.environ.get("ULTRON_SIN_ANIMACIONES"):
        return False
    marca = _ruta_marca()
    try:
        reciente = marca.exists() and time.time() - marca.stat().st_mtime < 600
        rutas.asegurar(marca.parent)
        marca.touch()
    except OSError:
        return True
    return not reciente


def ejecutar_ultron(argv: list[str]) -> int:
    """Lanza `ultron <argv>` en esta misma terminal (con todo su color y animación)."""
    from ultron.ui.tema import OPCIONES

    entorno = dict(os.environ, ULTRON_DESDE_NEXUS="1")
    opciones = []
    if OPCIONES.sin_animaciones:
        opciones.append("--sin-animaciones")
    if OPCIONES.sin_color:
        opciones.append("--sin-color")
    try:
        return subprocess.run([sys.executable, "-m", "ultron", *opciones, *argv], env=entorno,
                              check=False).returncode
    except KeyboardInterrupt:
        return 130


def _pausa(codigo: int) -> bool:
    """Espera una tecla. Devuelve False si el usuario quiere cerrar el NEXUS."""
    from ultron.ui import tema
    from ultron.ui.teclas import leer_tecla

    t = tema.actual()
    estado = "[ok]✔ hecho[/]" if codigo == 0 else f"[aviso]terminó con código {codigo}[/]"
    t.consola.print(f"\n[apagado]──[/] {estado} [apagado]· Enter vuelve al NEXUS · q cierra ──[/]")
    try:
        tecla = leer_tecla()
    except (OSError, EOFError, KeyboardInterrupt):
        return False
    return str(tecla).lower() not in {"q", "escape", "\x1b"}


def pausa_final(codigo: int) -> None:
    """Al lanzar desde un icono: deja ver el resultado antes de cerrar la ventana."""
    from ultron.ui import tema
    from ultron.ui.teclas import leer_tecla

    estado = "[ok]✔ hecho[/]" if codigo == 0 else f"[aviso]terminó con código {codigo}[/]"
    tema.actual().consola.print(f"\n[apagado]──[/] {estado} [apagado]· pulsa una tecla para "
                                "cerrar · n abre el NEXUS ──[/]")
    try:
        tecla = str(leer_tecla()).lower()
    except (OSError, EOFError, KeyboardInterrupt):
        return
    if tecla == "n":
        abrir()


def abrir(pantalla: str | None = None, funcion: str | None = None) -> None:
    from ultron.ui import tema

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        tema.actual().consola.print("NEXUS se abre en una terminal interactiva. "
                                    "Consulta los modos con ultron modos.")
        return
    from ultron.ui.nexus.app import Nexus

    arranque, aviso = _toca_arranque(), ""
    while True:
        resultado = Nexus(arranque=arranque, pantalla=pantalla, aviso=aviso,
                          funcion=funcion).run()
        arranque, aviso, funcion, pantalla = False, "", None, None
        if not resultado:
            return
        tipo, dato = resultado
        if tipo == "entrar":
            codigo = ejecutar_ultron(["entrar", str(dato), "--si"])
            if codigo == 0:
                aviso, pantalla = AVISO_ENTRADA, "puente"
            elif not _pausa(codigo):
                return
            continue
        codigo = ejecutar_ultron(list(dato))
        if dato and dato[0] == "salir":
            pantalla = "hangar"
            continue
        if not _pausa(codigo):
            return
