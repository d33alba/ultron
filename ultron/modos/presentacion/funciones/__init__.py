"""Comandos del modo PRESENTACIÓN: diapos, ensayo, cronómetro, teleprompter."""

from __future__ import annotations

import time
from pathlib import Path

import typer
from rich.align import Align
from rich.console import Group
from rich.live import Live
from rich.text import Text

from ultron.modos.presentacion import diapos as D
from ultron.modos.presentacion import letras
from ultron.nucleo import jsonio, rutas
from ultron.ui import tema

app = typer.Typer()
ArchivoMd = typer.Argument(..., exists=True, dir_okay=False, help="Presentación en Markdown.")


def _t() -> tema.Tema:
    return tema.cargar_tema("presentacion")


def ruta_sincro() -> Path:
    return rutas.estado() / "diapos.json"


# --- diapos ------------------------------------------------------------------------------


def app_diapos(diapos: list[D.Diapo], titulo: str, t: tema.Tema):
    """Aplicación Textual de diapositivas (se crea aquí para no importar Textual al inicio)."""
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.widgets import Static

    paleta = t.paleta
    estilos = {"titulo": f"bold {paleta.get('acento', 'yellow')}",
               "vineta": paleta.get("acento", "yellow")}

    class Diapos(App):
        CSS = f"""
        Screen {{ background: {paleta.get('fondo', '#2B2B2E')}; color: {paleta.get('texto', 'white')}; }}
        #diapo {{ padding: 2 6; height: 1fr; }}
        #pie {{ dock: bottom; height: 1; color: {paleta.get('apagado', 'grey')}; padding: 0 2; }}
        """
        BINDINGS = [
            Binding("right,space,enter,pagedown", "siguiente", "Siguiente"),
            Binding("left,pageup,backspace", "anterior", "Anterior"),
            Binding("q,escape", "quit", "Salir"),
        ]

        def __init__(self) -> None:
            super().__init__()
            self.indice, self.paso, self.inicio = 0, 0, time.monotonic()
            self.cortina = 0

        def compose(self) -> ComposeResult:
            yield Static(id="diapo")
            yield Static(id="pie")

        def on_mount(self) -> None:
            self.pintar()
            self.set_interval(1, self.pintar_pie)
            self.set_interval(0.04, self.animar)

        def sincronizar(self) -> None:
            d = diapos[self.indice]
            siguiente = diapos[self.indice + 1].titulo if self.indice + 1 < len(diapos) else "—"
            jsonio.escribir(ruta_sincro(), {"indice": self.indice, "total": len(diapos),
                                            "titulo": d.titulo, "notas": d.notas,
                                            "siguiente": siguiente, "inicio": self.inicio,
                                            "archivo": titulo})

        def pintar(self) -> None:
            d = diapos[self.indice]
            ancho = max(20, self.size.width - 12)
            if self.cortina:
                relleno = "▓▒░"[min(2, self.cortina // 3)] * ancho
                contenido = Text("\n".join([relleno] * max(1, self.size.height - 6)),
                                 style=paleta.get("error", "red"))
            else:
                contenido = D.render(d, self.paso, ancho, estilos)
            self.query_one("#diapo", Static).update(contenido)
            self.pintar_pie()
            self.sincronizar()

        def pintar_pie(self) -> None:
            seg = int(time.monotonic() - self.inicio)
            self.query_one("#pie", Static).update(
                f"★ {titulo}   {self.indice + 1}/{len(diapos)}   ⏱ {seg // 60:02d}:{seg % 60:02d}"
                "   ← → para moverte · q para salir")

        def animar(self) -> None:
            if self.cortina:
                self.cortina -= 1
                self.pintar()

        def action_siguiente(self) -> None:
            if self.paso + 1 < diapos[self.indice].pasos:
                self.paso += 1
            elif self.indice + 1 < len(diapos):
                self.indice, self.paso, self.cortina = self.indice + 1, 0, 8
            self.pintar()

        def action_anterior(self) -> None:
            if self.paso > 0:
                self.paso -= 1
            elif self.indice > 0:
                self.indice -= 1
                self.paso = diapos[self.indice].pasos - 1
            self.pintar()

    return Diapos()


def app_notas(t: tema.Tema):
    from textual.app import App, ComposeResult
    from textual.widgets import Static

    paleta = t.paleta

    class Notas(App):
        CSS = f"Screen {{ background: #111; color: {paleta.get('texto', 'white')}; padding: 1 3; }}"
        BINDINGS = [("q", "quit", "Salir")]

        def compose(self) -> ComposeResult:
            yield Static(id="notas")

        def on_mount(self) -> None:
            self.set_interval(0.5, self.refrescar)
            self.refrescar()

        def refrescar(self) -> None:
            datos = jsonio.leer(ruta_sincro(), {}) or {}
            seg = int(time.monotonic() - datos.get("inicio", time.monotonic()))
            texto = Text()
            texto.append(f"{datos.get('indice', 0) + 1}/{datos.get('total', '?')}  ",
                         style=f"bold {paleta.get('acento', 'yellow')}")
            texto.append(f"{datos.get('titulo', 'esperando la presentación…')}\n\n", style="bold")
            texto.append(datos.get("notas") or "(sin notas)")
            texto.append(f"\n\nsiguiente: {datos.get('siguiente', '—')}", style="dim")
            texto.append(f"\n⏱ {seg // 60:02d}:{seg % 60:02d}", style="dim")
            self.query_one("#notas", Static).update(texto)

    return Notas()


@app.command("diapos")
def cmd_diapos(
    archivo: Path = typer.Argument(None, help="Presentación en Markdown (separa con ---)."),
    notas: bool = typer.Option(False, "--notas", help="Abre la vista del orador (otra ventana)."),
    exportar: str = typer.Option(None, "--exportar", help="html: exporta la presentación."),
) -> None:
    """Presentación a pantalla completa en la terminal, con notas del orador después de ???."""
    t = _t()
    if notas:
        app_notas(t).run()
        return
    if archivo is None or not archivo.exists():
        t.error("Indica el archivo .md: ultron diapos charla.md")
        raise typer.Exit(1)
    lista = D.cargar(archivo)
    if not lista:
        t.error("No hay diapositivas (sepáralas con una línea ---).")
        raise typer.Exit(1)
    if exportar:
        if exportar.lower() != "html":
            t.error("Solo se puede exportar a html.")
            raise typer.Exit(1)
        destino = archivo.with_suffix(".html")
        destino.write_text(D.a_html(lista, archivo.stem, t.paleta), encoding="utf-8")
        t.ok(f"Exportado a {destino}")
        return
    app_diapos(lista, archivo.stem, t).run()


# --- ensayo -------------------------------------------------------------------------------


@app.command("ensayo")
def cmd_ensayo(
    archivo: Path = ArchivoMd,
    tiempo: float = typer.Option(None, "--tiempo", help="Minutos totales de la charla."),
) -> None:
    """La IA hace de público: 3 preguntas difíciles por diapositiva y una nota de claridad."""
    t = _t()
    lista = D.cargar(archivo)
    tiempos = D.repartir_tiempo(lista, tiempo) if tiempo else [None] * len(lista)
    from ultron.ia.util import pedir_json

    for i, (d, minutos) in enumerate(zip(lista, tiempos, strict=True), 1):
        contenido = "\n".join(b.contenido for b in d.bloques)
        with t.spinner_ctx(f"el público lee la diapositiva {i}"):
            r = pedir_json(
                "Eres el público exigente de una presentación. Para esta diapositiva haz 3 "
                "preguntas difíciles, da una nota de claridad de 1 a 10 y un consejo concreto."
                f"\n\nTÍTULO: {d.titulo}\nCONTENIDO:\n{contenido}\nNOTAS: {d.notas}",
                {"preguntas": ["…", "…", "…"], "claridad": 7, "consejo": "…"})
        r = r if isinstance(r, dict) else {}
        cuerpo = Text()
        if minutos:
            cuerpo.append(f"⏱ {minutos:g} min\n", style="acento")
        for p in (r.get("preguntas") or [])[:3]:
            cuerpo.append(f"? {p}\n", style="texto")
        cuerpo.append(f"\nclaridad {r.get('claridad', '?')}/10 · ", style="bold acento")
        cuerpo.append(str(r.get("consejo", "")), style="apagado")
        t.consola.print(t.panel(cuerpo, titulo=f"{i}. {d.titulo or 'sin título'}"))
    if tiempo:
        t.info(f"Reparto para {tiempo:g} minutos según el contenido de cada diapositiva.")


# --- cronómetro -------------------------------------------------------------------------------


def color_cronometro(restante: float, paleta: dict[str, str]) -> str:
    if restante <= 30:
        return paleta.get("error", "red")
    if restante <= 120:
        return paleta.get("aviso", "yellow")
    return paleta.get("ok", "green")


def vista_cronometro(restante: float, total: float, paleta: dict[str, str]) -> Group:
    m, s = divmod(max(0, int(restante)), 60)
    color = color_cronometro(restante, paleta)
    filas = [Text(f, style=f"bold {color}") for f in letras.grandes(f"{m:02d}:{s:02d}")]
    estado = "¡TIEMPO!" if restante <= 0 else "quedan"
    return Group(Text(estado, style=paleta.get("apagado", "grey")), Text(""), *filas,
                 Text(""), Text("▰" * round(30 * restante / total if total else 0)
                                + "▱" * (30 - round(30 * restante / total if total else 0)),
                                style=color))


@app.command("cronometro")
def cmd_cronometro(
    minutos: float = typer.Option(10, "--min", help="Minutos de la charla."),
) -> None:
    """Cuenta atrás gigante: verde, ámbar a los 2 minutos y rojo a los 30 segundos."""
    t = _t()
    total = minutos * 60
    fin = time.monotonic() + total
    try:
        with Live(console=t.consola, screen=True, refresh_per_second=4) as live:
            while True:
                restante = fin - time.monotonic()
                live.update(Align.center(vista_cronometro(restante, total, t.paleta),
                                         vertical="middle"))
                if restante <= -5:
                    break
                time.sleep(0.25)
    except KeyboardInterrupt:
        pass


# --- teleprompter -------------------------------------------------------------------------------


def espejo(linea: str) -> str:
    return linea[::-1]


@app.command("teleprompter")
def cmd_teleprompter(
    archivo: Path = typer.Argument(..., exists=True, dir_okay=False),
    velocidad: float = typer.Option(1.0, "--velocidad", help="Líneas por segundo."),
    con_espejo: bool = typer.Option(False, "--espejo", help="Texto en espejo (para cristal)."),
) -> None:
    """Texto grande que se desplaza solo: ↑↓ velocidad, espacio pausa, e espejo, q salir."""
    from textual.app import App, ComposeResult
    from textual.containers import VerticalScroll
    from textual.widgets import Static

    t = _t()
    texto = archivo.read_text(encoding="utf-8")
    paleta = t.paleta

    class Teleprompter(App):
        CSS = f"""
        Screen {{ background: black; }}
        #texto {{ color: {paleta.get('texto', 'white')}; text-style: bold; padding: 4 10;
                  text-align: center; }}
        #pie {{ dock: bottom; height: 1; color: {paleta.get('apagado', 'grey')}; }}
        """
        BINDINGS = [("up", "mas", "Más rápido"), ("down", "menos", "Más lento"),
                    ("space", "pausa", "Pausa"), ("e", "espejo", "Espejo"), ("q", "quit", "Salir")]

        def __init__(self) -> None:
            super().__init__()
            self.vel, self.pausado, self.espejado = velocidad, False, con_espejo

        def compose(self) -> ComposeResult:
            with VerticalScroll(id="rollo"):
                yield Static(id="texto")
            yield Static(id="pie")

        def on_mount(self) -> None:
            self.pintar()
            self.set_interval(0.1, self.avanzar)

        def pintar(self) -> None:
            lineas = texto.splitlines()
            if self.espejado:
                lineas = [espejo(x) for x in lineas]
            self.query_one("#texto", Static).update("\n\n".join(lineas) + "\n" * 30)
            self.query_one("#pie", Static).update(
                f" velocidad {self.vel:.1f} · {'pausa' if self.pausado else 'avanzando'}"
                f"{' · espejo' if self.espejado else ''}   ↑↓ espacio e q")

        def avanzar(self) -> None:
            if not self.pausado:
                rollo = self.query_one("#rollo", VerticalScroll)
                rollo.scroll_to(y=rollo.scroll_y + self.vel * 0.2, animate=False)

        def action_mas(self) -> None:
            self.vel = min(10, self.vel + 0.25)
            self.pintar()

        def action_menos(self) -> None:
            self.vel = max(0.25, self.vel - 0.25)
            self.pintar()

        def action_pausa(self) -> None:
            self.pausado = not self.pausado
            self.pintar()

        def action_espejo(self) -> None:
            self.espejado = not self.espejado
            self.pintar()

    Teleprompter().run()
