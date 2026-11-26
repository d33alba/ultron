"""Genera capturas reproducibles con los ejemplos sin red de Ultron."""

from __future__ import annotations

import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from rich.console import Console
from typer.main import get_command

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ultron.cli import app  # noqa: E402
from ultron.modos.fantasma.generar_recursos import fondo as fondo_fantasma  # noqa: E402
from ultron.modos.focus.generar_recursos import fondo as fondo_focus  # noqa: E402
from ultron.modos.gaming.generar_recursos import fondo as fondo_gaming  # noqa: E402
from ultron.modos.netanyahu.generar_fondo import fondo as fondo_netanyahu  # noqa: E402
from ultron.modos.presentacion.generar_recursos import fondo as fondo_presentacion  # noqa: E402
from ultron.nucleo.entrega import DEMOSTRACIONES  # noqa: E402
from ultron.ui import banner, tema  # noqa: E402


def captura(destino: Path, modo: str | None, args: tuple[str, ...] = ()) -> None:
    """Graba un banner o un comando con la paleta seleccionada."""
    base = tema.cargar_tema(modo)
    consola = Console(
        record=True, file=StringIO(), width=112, theme=base.theme(),
        force_terminal=True, color_system="truecolor", highlight=False, legacy_windows=False,
    )
    with (
        patch.object(tema, "actual", return_value=base),
        patch.object(base, "_consola", consola),
    ):
        if args:
            consola.print("ultron " + " ".join(args), style="acento")
            raiz = get_command(app)
            with raiz.context_class(raiz) as ctx:
                ctx.meta["ultron_simulado"] = True
                comando = raiz.get_command(ctx, args[0])
                with comando.make_context(args[0], list(args[1:]), parent=ctx) as sub:
                    comando.invoke(sub)
        else:
            banner.mostrar_banner(base, animado=False)
    consola.save_svg(str(destino), title="Ultron", unique_id=f"ultron-{destino.stem}")


def fondos(destino: Path) -> None:
    """Guarda los fondos a 1280×720 y una vista animada reducida."""
    from PIL import Image

    destino.mkdir(parents=True, exist_ok=True)
    fondo_gaming(ancho=1280, alto=720).save(destino / "gaming.png")
    fondo_netanyahu(1280, 720).save(destino / "netanyahu.png")
    fondo_focus(destino / "focus.png", 1280, 720, frase="haz espacio para concentrarte")
    fondo_presentacion(destino / "presentacion.png", 1280, 720)
    fondo_fantasma(destino / "fantasma.png", 1280, 720)
    fotogramas = []
    for modo in DEMOSTRACIONES:
        with Image.open(destino / f"{modo}.png") as imagen:
            reducida = imagen.resize((640, 360))
            fotogramas.append(reducida.convert("P", palette=Image.Palette.ADAPTIVE))
    fotogramas[0].save(
        destino.parent / "fondos.gif", save_all=True, append_images=fotogramas[1:],
        duration=1800, loop=0, optimize=True,
    )


def generar(destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    tema.configurar(sin_animaciones=True)
    captura(destino / "modos.svg", None, ("modos",))
    for modo, comandos in DEMOSTRACIONES.items():
        captura(destino / f"banner-{modo}.svg", modo)
        for args in comandos:
            nombre = "osint-ip" if args[0] == "osint" else args[0]
            captura(destino / f"{nombre}.svg", modo, args)
    fondos(destino / "fondos")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    generar(Path(__file__).resolve().parents[1] / "docs" / "media")
