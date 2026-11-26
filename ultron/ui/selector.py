"""Selector de modos a pantalla completa (Textual): `ultron` sin argumentos."""

from __future__ import annotations

import random
from typing import Any

from rich.text import Text

from ultron.nucleo import estado, registro
from ultron.ui import tema as temas

LOGO = ["█ █ █   ▀█▀ █▀█ █▀█ █▄ █", "█▄█ █▄▄  █  █▀▄ █▄█ █ ▀█"]
RUIDO = "░▒▓█▀▄■◆"


def estado_ia() -> tuple[bool, str]:
    try:
        from ultron.ia.ajustes import resolver

        aj = resolver(autodetectar=False)
    except Exception:  # noqa: BLE001
        aj = None
    if aj is None:
        return False, "○ IA sin configurar · pulsa c"
    host = aj.url_base.split("//")[-1].split("/")[0]
    return True, f"● IA: {aj.modelo or '¿modelo?'} @ {host}"


def tarjeta(modo: Any, seleccionado: bool, activo: bool) -> Text:
    t = temas.cargar_tema(modo.id)
    p = t.paleta
    texto = Text()
    texto.append(f"{t.glifo('marca')}  {modo.nombre}\n", style=f"bold {p.get('primario')}")
    texto.append(f"{modo.lema}\n\n", style=p.get("acento", ""))
    for f in modo.funciones[:4]:
        texto.append(f"{t.glifo('vineta') or '·'} {f}\n", style=p.get("texto", ""))
    if activo:
        texto.append("\n● ACTIVO", style=f"bold {p.get('ok')}")
    if seleccionado:
        texto.append("\n\n▶ Enter para entrar", style=f"bold {p.get('primario')}")
    return texto


def crear_app():
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Horizontal
    from textual.widgets import Static

    modos = registro.listar()

    class Selector(App):
        CSS = """
        Screen { align: center middle; }
        #logo { width: 100%; content-align: center middle; height: 4; }
        #cartas { height: auto; width: 100%; align: center middle; }
        .carta { width: 1fr; min-width: 22; height: 16; border: round $panel;
                 padding: 1 2; margin: 0 1; }
        .carta.elegida { border: heavy $accent; }
        #barra { dock: bottom; height: 1; padding: 0 2; }
        #ayuda { dock: bottom; height: 1; padding: 0 2; }
        """
        BINDINGS = [
            Binding("left,h", "mover(-1)", "Anterior"), Binding("right,l", "mover(1)", "Siguiente"),
            Binding("enter", "entrar", "Entrar"), Binding("s", "accion('salir')", "Salir del modo"),
            Binding("d", "accion('doctor')", "Doctor"), Binding("i", "accion('chat')", "IA"),
            Binding("c", "accion('configurar')", "Configurar IA"),
            Binding("q,escape", "accion(None)", "Cerrar"),
        ]

        def __init__(self) -> None:
            super().__init__()
            activo = estado.modo_activo()
            ids = [m.id for m in modos]
            self.indice = ids.index(activo) if activo in ids else 0
            self.activo = activo
            self.paso_logo = 0

        def compose(self) -> ComposeResult:
            yield Static(id="logo")
            with Horizontal(id="cartas"):
                for i, _m in enumerate(modos):
                    yield Static(id=f"carta-{i}", classes="carta")
            yield Static(id="ayuda")
            yield Static(id="barra")

        def on_mount(self) -> None:
            self.pintar()
            self.set_interval(0.05, self.animar_logo)

        def animar_logo(self) -> None:
            if self.paso_logo > 12:
                return
            self.paso_logo += 1
            rng = random.Random(self.paso_logo)
            progreso = self.paso_logo / 12
            lineas = ["".join(c if c == " " or rng.random() < progreso else rng.choice(RUIDO)
                              for c in fila) for fila in LOGO]
            color = temas.cargar_tema(modos[self.indice].id).paleta.get("primario", "cyan")
            self.query_one("#logo", Static).update(Text("\n".join(lineas), style=f"bold {color}",
                                                        justify="center"))

        def pintar(self) -> None:
            modo = modos[self.indice]
            p = temas.cargar_tema(modo.id).paleta
            self.screen.styles.background = p.get("fondo", "#101418")
            self.screen.styles.animate("background", value=p.get("fondo", "#101418"),
                                       duration=0.3)
            for i, m in enumerate(modos):
                carta = self.query_one(f"#carta-{i}", Static)
                carta.update(tarjeta(m, i == self.indice, m.id == self.activo))
                carta.set_class(i == self.indice, "elegida")
                pm = temas.cargar_tema(m.id).paleta
                carta.styles.border = ("heavy" if i == self.indice else "round",
                                       pm.get("primario", "white"))
                carta.styles.background = pm.get("fondo", "#000000")
            ok, texto = estado_ia()
            self.query_one("#barra", Static).update(
                Text(texto, style=p.get("ok" if ok else "aviso", "")))
            self.query_one("#ayuda", Static).update(Text(
                "← → elegir · Enter entrar · s salir del modo · d doctor · i chat IA · q cerrar",
                style=p.get("apagado", "grey")))
            if self.paso_logo > 12:
                self.paso_logo = 6  # reanima el logo con el color nuevo

        def action_mover(self, delta: int) -> None:
            self.indice = (self.indice + delta) % len(modos)
            self.pintar()

        def action_entrar(self) -> None:
            self.exit(("entrar", modos[self.indice].id))

        def action_accion(self, accion: str | None) -> None:
            self.exit((accion, None) if accion else None)

    return Selector()


def abrir_selector() -> None:
    resultado = crear_app().run()
    if not resultado:
        return
    accion, id_modo = resultado
    from ultron.cli import app

    argumentos = {"entrar": ["entrar", str(id_modo)], "salir": ["salir"], "doctor": ["doctor"],
                  "chat": ["ia", "chat"], "configurar": ["ia", "configurar"]}[accion]
    try:
        app(argumentos, standalone_mode=False)
    except SystemExit:
        pass
