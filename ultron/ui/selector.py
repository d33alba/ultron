"""Selector de modos a pantalla completa (Textual): `ultron` sin argumentos."""

from __future__ import annotations

from typing import Any

from rich.text import Text

from ultron.nucleo import estado, registro
from ultron.ui import tema as temas


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
    from textual.app import ComposeResult
    from textual.binding import Binding
    from textual.containers import HorizontalScroll
    from textual.widgets import Static

    from ultron.ui.escenas import titulo
    from ultron.ui.fondo import AppPixel, Fondo

    modos = registro.listar()

    class Selector(AppPixel):
        CSS = """
        Screen { align: center top; layers: paisaje base; overflow: hidden hidden; }
        #logo, #cartas, #barra, #ayuda { layer: base; }
        #logo { width: 100%; content-align: center middle; height: 3; margin-top: 6; }
        #cartas { height: 13; width: 100%; background: transparent; }
        .carta { width: 23; height: 12; border: round $panel;
                 padding: 0 1; margin: 0 1; }
        .carta.elegida { border: heavy $accent; }
        #barra, #ayuda { width: 100%; height: 1; padding: 0 2; }
        """
        BINDINGS = [
            Binding("left,h", "mover(-1)", "Anterior", priority=True),
            Binding("right,l", "mover(1)", "Siguiente", priority=True),
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
        def compose(self) -> ComposeResult:
            yield Fondo()
            yield Static(id="logo")
            with HorizontalScroll(id="cartas"):
                for i, _m in enumerate(modos):
                    yield Static(id=f"carta-{i}", classes="carta")
            yield Static(id="ayuda")
            yield Static(id="barra")

        def on_mount(self) -> None:
            self.pintar()

        def pintar(self) -> None:
            modo = modos[self.indice]
            tema = temas.cargar_tema(modo.id)
            p = tema.paleta
            fondo = p.get("fondo", "#101418")
            self.screen.styles.background = fondo
            self.query_one(Fondo).elegir(tema)
            logo = self.query_one("#logo", Static)
            logo.update(titulo("ULTRON", p.get("primario", "cyan"), ancho=self.size.width))
            for id_panel in ("#logo", "#barra", "#ayuda"):
                self.query_one(id_panel).styles.background = fondo
            for i, m in enumerate(modos):
                carta = self.query_one(f"#carta-{i}", Static)
                carta.update(tarjeta(m, i == self.indice, m.id == self.activo))
                carta.set_class(i == self.indice, "elegida")
                pm = temas.cargar_tema(m.id).paleta
                carta.styles.border = ("heavy" if i == self.indice else "round",
                                       pm.get("primario", "white"))
                carta.styles.background = pm.get("fondo", "#000000")
                if i == self.indice:
                    carta.scroll_visible(animate=False)
            ok, texto = estado_ia()
            self.query_one("#barra", Static).update(
                Text(texto, style=p.get("ok" if ok else "aviso", "")))
            self.query_one("#ayuda", Static).update(Text(
                "← → elegir · Enter entrar · s salir · d doctor · i chat · c IA · q cerrar",
                style=p.get("apagado", "grey")))

        def action_mover(self, delta: int) -> None:
            self.indice = (self.indice + delta) % len(modos)
            self.pintar()

        def action_entrar(self) -> None:
            self.exit(("entrar", modos[self.indice].id))

        def action_accion(self, accion: str | None) -> None:
            self.exit((accion, None) if accion else None)

    return Selector()


def abrir_selector() -> None:
    """Compatibilidad: el selector antiguo ahora es la pantalla HANGAR del NEXUS."""
    from ultron.ui.nexus import abrir

    abrir(pantalla="hangar")


def abrir_selector_clasico() -> None:
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
