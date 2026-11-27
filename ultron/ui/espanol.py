"""Traduce al español los textos de ayuda y de error que trae Typer (y su click interno).

Se aplica una vez al importar `ultron.cli`. Si una versión futura de Typer cambia algo,
simplemente se queda el texto en inglés: nunca rompe la ayuda.
"""

from __future__ import annotations

import re
from typing import Any

FRASES = [
    (r"No such option: ", "No existe la opción: "),
    (r"\(Possible options: ", "(Opciones posibles: "),
    (r"Did you mean (.+)\?", r"¿Querías decir \1?"),
    (r"No such command '([^']+)'\.", r"No existe el comando «\1»."),
    (r"Missing command\.", "Falta el comando."),
    (r"Missing argument '([^']+)'\.", r"Falta el dato «\1»."),
    (r"Missing option '([^']+)'\.", r"Falta la opción «\1»."),
    (r"Missing parameter: ", "Falta el parámetro: "),
    (r"Invalid value for ([^:]+): ", r"Valor no válido para \1: "),
    (r"Invalid value: ", "Valor no válido: "),
    (r"Got unexpected extra arguments? \(([^)]*)\)", r"Sobran datos: \1"),
    (r"is not a valid (integer|float|boolean)", r"no es un número válido"),
    (r"Option '([^']+)' requires an argument\.", r"La opción «\1» necesita un valor."),
]


def traducir(texto: str) -> str:
    for patron, cambio in FRASES:
        texto = re.sub(patron, cambio, texto)
    return texto


def aplicar() -> None:
    try:
        import typer.rich_utils as ru
        from typer._click import decorators, exceptions, formatting
    except ImportError:
        return
    for nombre, valor in {
        "ARGUMENTS_PANEL_TITLE": "Datos", "OPTIONS_PANEL_TITLE": "Opciones",
        "COMMANDS_PANEL_TITLE": "Comandos", "ERRORS_PANEL_TITLE": "Error",
        "ABORTED_TEXT": "Cancelado.", "DEFAULT_STRING": "[por defecto: {}]",
        "REQUIRED_LONG_STRING": "[obligatorio]", "ENVVAR_STRING": "[variable: {}]",
        "RICH_HELP": "Prueba [blue]'{command_path} {help_option}'[/] para ver la ayuda.",
    }.items():
        if hasattr(ru, nombre):
            setattr(ru, nombre, valor)

    escribir = formatting.HelpFormatter.write_usage

    def write_usage(self: Any, prog: str, args: str = "", prefix: str | None = None) -> None:
        for ingles, castellano in (("[OPTIONS]", "[OPCIONES]"), ("COMMAND", "COMANDO"),
                                   ("[ARGS]...", "[DATOS]...")):
            args = args.replace(ingles, castellano)
        escribir(self, prog, args, "Uso: " if prefix is None else prefix)

    formatting.HelpFormatter.write_usage = write_usage  # type: ignore[method-assign]
    if hasattr(ru, "highlighter") and hasattr(ru.highlighter, "highlights"):
        ru.highlighter.highlights = [h.replace("Usage: ", "Uso: ")
                                     for h in ru.highlighter.highlights]

    try:
        from typer._click import core

        piezas = core.Command.collect_usage_pieces

        def collect_usage_pieces(self: Any, ctx: Any) -> list[str]:
            cambios = {"[OPTIONS]": "[OPCIONES]", "COMMAND [ARGS]...": "COMANDO [DATOS]...",
                       "COMMAND": "COMANDO", "[ARGS]...": "[DATOS]..."}
            return [cambios.get(p, p) for p in piezas(self, ctx)]

        core.Command.collect_usage_pieces = collect_usage_pieces  # type: ignore[method-assign]
        for clase in (core.Command, *core.Command.__subclasses__()):
            if getattr(clase, "options_metavar", None) == "[OPTIONS]":
                clase.options_metavar = "[OPCIONES]"
    except (ImportError, AttributeError):
        pass

    ayuda = decorators.help_option

    def help_option(*args: Any, **kw: Any) -> Any:
        decorador = ayuda(*args, **kw)

        def aplicar_a(f: Any) -> Any:
            resultado = decorador(f)
            params = getattr(resultado, "params", None)
            if params:
                ultimo = params[-1]
                if getattr(ultimo, "help", "") == "Show this message and exit.":
                    ultimo.help = "Muestra esta ayuda."
            return resultado
        return aplicar_a

    decorators.help_option = help_option

    for clase in (exceptions.ClickException, exceptions.UsageError, exceptions.BadParameter,
                  exceptions.MissingParameter, exceptions.NoSuchOption,
                  exceptions.BadOptionUsage, exceptions.BadArgumentUsage):
        original = clase.__dict__.get("format_message")
        if original is None:
            continue

        def formatear(self: Any, _original: Any = original) -> str:
            return traducir(_original(self))

        clase.format_message = formatear  # type: ignore[method-assign]
