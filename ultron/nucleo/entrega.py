"""Creación de modos personales y recorrido de demostración."""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import typer

from ultron.nucleo import motor, registro, rutas
from ultron.nucleo.esquema import validar_id
from ultron.ui import banner, tema
from ultron.ui.teclas import leer_tecla

DEMOSTRACIONES = {
    "netanyahu": (("radar", "--demo"), ("osint", "ip", "8.8.8.8", "--demo")),
    "focus": (("stats", "--demo"), ("repasar", "--demo", "--sin-pausa")),
    "gaming": (("juegos", "--demo"), ("hud", "--demo", "--una-vez")),
    "presentacion": (("diapos", "--demo"), ("cronometro", "--demo")),
    "fantasma": (("mac", "--demo"), ("dns-seguro", "--demo")),
}


def crear_modo(id_modo: str, *, simular: bool = False) -> None:
    """Crea un modo activable a partir del tema de Ultron."""
    validar_id(id_modo)
    destino = rutas.modos_usuario() / id_modo
    if id_modo in registro.ids() or destino.exists():
        raise motor.ErrorMotor(f"Ya existe el modo o su carpeta: {destino}")
    t = tema.actual()
    if simular:
        t.info(f"Se crearía el modo en {destino}")
        return
    definicion = (
        f'id: "{id_modo}"\nnombre: "{id_modo.upper()}"\nlema: "Modo personal"\n'
        'descripcion: "Mi modo de Ultron"\nia:\n  personalidad: "Responde en español."\n'
        'capas:\n  shell: {}\nfunciones: []\n'
    )
    plantilla = Path(tema.__file__).with_name("tema_defecto.toml").read_text(encoding="utf-8")
    plantilla = plantilla.replace('id = "ultron"', f'id = "{id_modo}"', 1)
    plantilla = plantilla.replace('nombre = "ULTRON"', f'nombre = "{id_modo.upper()}"', 1)
    try:
        destino.mkdir(parents=True)
        try:
            (destino / "tema").mkdir()
            (destino / "tema.toml").write_text(plantilla, encoding="utf-8")
            (destino / "modo.yaml").write_text(definicion, encoding="utf-8")
        except OSError:
            (destino / "modo.yaml").unlink(missing_ok=True)
            (destino / "tema.toml").unlink(missing_ok=True)
            if (destino / "tema").is_dir():
                (destino / "tema").rmdir()
            destino.rmdir()
            raise
    except OSError as e:
        raise motor.ErrorMotor(f"No se pudo crear el modo en {destino}: {e}") from e
    registro.invalidar()
    tema.invalidar()
    t.ok(f"Modo creado en {destino}. Pruébalo con: ultron entrar {id_modo}")


def recorrer(
    ejecutar: Callable[[tuple[str, ...]], None], *, rapida: bool, simular: bool,
) -> None:
    """Presenta los cinco modos y restaura los cambios incluso al cancelar."""
    interactivo = sys.stdin.isatty() and sys.stdout.isatty()
    tema.actual().info("Ultron transforma el escritorio y la terminal con cinco modos.")
    activado = False
    try:
        for id_modo, comandos in DEMOSTRACIONES.items():
            modo = registro.obtener(id_modo)
            t = tema.cargar_tema(id_modo)
            banner.mostrar_banner(t, animado=False)
            t.info(modo.descripcion)
            if interactivo and not simular and not rapida:
                if typer.confirm(f"¿Entrar en {modo.nombre}?", default=False):
                    activado = True
                    motor.entrar(
                        id_modo, sin_sudo=True, excepto=["sistema"], consola=t.consola,
                    )
            for args in comandos[:1] if rapida else comandos:
                t.info("ultron " + " ".join(args))
                ejecutar(args)
            if interactivo and not rapida:
                t.info("Pulsa una tecla para continuar o Q para terminar.")
                if leer_tecla().lower() == "q":
                    break
    finally:
        if activado and any(r.estado == "fallida" for r in motor.salir()):
            raise motor.ErrorMotor("La restauración quedó pendiente. Ejecuta: ultron salir")
    tema.actual().ok("Todo restaurado" if activado else "Demostración terminada.")
