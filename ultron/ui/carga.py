"""Pantalla de carga mientras se aplican las capas."""

from __future__ import annotations

import math
import os
import threading
import time
from collections.abc import Callable
from typing import Any, TypeVar

from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ultron.ui import pantalla_pixel
from ultron.ui.tema import Tema, animaciones_activas

T = TypeVar("T")
Progreso = Callable[[str, str], None]
Trabajo = Callable[[Progreso], T]

ESTADOS = {
    "aplicando": ("info", "acento"), "restaurando": ("info", "acento"),
    "aplicada": ("ok", "ok"), "restaurada": ("ok", "ok"),
    "saltada": ("aviso", "aviso"), "fallida": ("error", "error"),
}


def gtk_disponible() -> bool:
    if os.environ.get("ULTRON_SIN_CARGA"):
        return False
    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        return False
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk  # noqa: F401
    except (ImportError, ValueError):
        return False
    return True


def ejecutar(
    tema: Tema,
    titulo: str,
    capas: list[str],
    trabajo: Trabajo,
    *,
    usar_gtk: bool = True,
    mostrar: bool = True,
) -> Any:
    """Ejecuta `trabajo(progreso)` mostrando la pantalla de carga adecuada."""
    if not mostrar or not animaciones_activas():
        return _simple(tema, trabajo)
    if pantalla_pixel.habilitada(tema):
        return _con_rich(tema, titulo, capas, trabajo)
    if usar_gtk and tema.consola.color_system and gtk_disponible():
        try:
            return _con_gtk(tema, titulo, capas, trabajo)
        except _ErrorGtk:
            pass
    return _simple(tema, trabajo)


# --- terminal ---------------------------------------------------------------------


def _simple(tema: Tema, trabajo: Trabajo) -> Any:
    def progreso(capa: str, estado: str) -> None:
        if estado in ("aplicando", "restaurando"):
            return
        glifo, estilo = ESTADOS.get(estado, ("info", "texto"))
        tema.consola.print(f"  [acento]{tema.glifo('info')}[/] {capa:<12} "
                           f"[{estilo}]{tema.glifo(glifo)} {estado}[/]")

    return trabajo(progreso)


def _tabla(tema: Tema, titulo: str, capas: list[str], estados: dict[str, str]) -> Table:
    t = Table.grid(padding=(0, 2))
    t.add_column()
    t.add_column()
    t.add_column()
    giro = tema.spinner[int(time.monotonic() * 10) % len(tema.spinner)]
    hechas = sum(estados.get(c) in ("aplicada", "restaurada", "saltada", "fallida") for c in capas)
    t.add_row(Text(titulo, style="bold primario"), "",
              Text(f"{hechas}/{len(capas)}", style="apagado"))
    for capa in capas:
        estado = estados.get(capa)
        if estado in ("aplicando", "restaurando"):
            marca = Text(giro, style="acento")
        elif estado:
            glifo, estilo = ESTADOS.get(estado, ("info", "texto"))
            marca = Text(tema.glifo(glifo), style=estilo)
        else:
            marca = Text("·", style="apagado")
        t.add_row(Text(f"  {tema.glifo('info')} {capa}", style="texto"), marca,
                  Text(estado or "", style="apagado"))
    t.add_row("", "", "")
    t.add_row(tema.barra(hechas / max(1, len(capas)), 32), "", "")
    return t


def _con_rich(tema: Tema, titulo: str, capas: list[str], trabajo: Trabajo) -> Any:
    estados: dict[str, str] = {}
    vistas = list(capas)
    inicio = time.monotonic()
    siguiente = 0.0
    imagen = Text()
    ritmo = pantalla_pixel.Ritmo(30)

    def progreso(capa: str, estado: str) -> None:
        if capa not in vistas:
            vistas.append(capa)
        estados[capa] = estado

    class _Vista:
        def __rich__(self_inner) -> Group:  # noqa: N805
            nonlocal imagen, siguiente
            ahora = time.monotonic()
            ancho = min(120, tema.consola.width)
            alto = max(4, min(14, tema.consola.height - len(vistas) - 7))
            if ahora >= siguiente:
                imagen = pantalla_pixel.vista(tema, ancho, alto, ahora - inicio,
                                              round(1 / ritmo.intervalo))
                ritmo.medir(time.monotonic() - ahora)
                siguiente = ahora + ritmo.intervalo
            tabla = _tabla(tema, titulo, list(vistas), estados.copy())
            fondo = tema.paleta.get("fondo", "#101418")
            return Group(imagen, Panel(tabla, border_style="primario", style=f"on {fondo}"))

    with Live(_Vista(), console=tema.consola, refresh_per_second=ritmo.maximo, transient=True):
        return trabajo(progreso)


# --- GTK 4 ---------------------------------------------------------------------------


class _ErrorGtk(Exception):
    pass


def _rgb(color: str) -> tuple[float, float, float]:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def dibujar_animacion(cr: Any, ancho: int, alto: int, t: float, id_modo: str,
                      paleta: dict[str, str]) -> None:
    """Dibuja un fotograma con cairo. Una animación distinta para cada modo."""
    cx, cy = ancho / 2, alto / 2
    r = min(ancho, alto) * 0.18
    pr = _rgb(paleta.get("primario", "#00d7ff"))
    ac = _rgb(paleta.get("acento", "#ffffff"))
    cr.set_line_width(max(2.0, r * 0.04))
    if id_modo == "netanyahu":
        angulo = t * 0.6
        for desfase in (0, math.pi):
            cr.set_source_rgb(*pr if desfase == 0 else ac)
            for k in range(4):
                a = angulo + desfase + k * 2 * math.pi / 3
                x, y = cx + r * math.sin(a), cy - r * math.cos(a)
                (cr.move_to if k == 0 else cr.line_to)(x, y)
            cr.stroke()
    elif id_modo == "focus":
        pulso = 0.75 + 0.25 * math.sin(t * 1.2)
        cr.set_source_rgba(*pr, 0.35)
        cr.arc(cx, cy, r * pulso, 0, 2 * math.pi)
        cr.fill()
        cr.set_source_rgb(*ac)
        cr.arc(cx, cy, r * pulso, 0, 2 * math.pi)
        cr.stroke()
    elif id_modo == "gaming":
        for i in range(0, alto, 6):
            cr.set_source_rgba(*pr, 0.05 + 0.05 * math.sin(i * 0.05 + t * 4))
            cr.rectangle(0, i, ancho, 2)
            cr.fill()
        cr.set_source_rgb(*ac)
        for k in range(7):
            a = t * 1.5 + k * math.pi / 3
            x, y = cx + r * math.cos(a), cy + r * math.sin(a)
            (cr.move_to if k == 0 else cr.line_to)(x, y)
        cr.stroke()
        y = (t * 300) % alto
        cr.set_source_rgba(*pr, 0.6)
        cr.rectangle(0, y, ancho, 3)
        cr.fill()
    elif id_modo == "presentacion":
        abierto = min(1.0, (t % 4) / 2)
        cr.set_source_rgb(0.55, 0.1, 0.15)
        cr.rectangle(0, 0, cx * (1 - abierto), alto)
        cr.rectangle(ancho - cx * (1 - abierto), 0, cx * (1 - abierto), alto)
        cr.fill()
        cr.set_source_rgba(*pr, 0.4)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.fill()
    elif id_modo == "fantasma":
        for k in range(12):
            a = t * 0.3 + k
            cr.set_source_rgba(0.9, 0.9, 0.9, 0.04)
            cr.arc(cx + math.cos(a) * r * 1.5, cy + math.sin(a * 1.3) * r, r * 1.2, 0, 2 * math.pi)
            cr.fill()
    else:
        cr.set_source_rgb(*pr)
        cr.arc(cx, cy, r, t * 2, t * 2 + math.pi * 1.5)
        cr.stroke()


def _con_gtk(tema: Tema, titulo: str, capas: list[str], trabajo: Trabajo) -> Any:
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gio, GLib, Gtk
    except (ImportError, ValueError) as e:
        raise _ErrorGtk() from e

    resultado: dict[str, Any] = {}
    estados: dict[str, str] = {}
    inicio = time.monotonic()
    app = Gtk.Application(application_id="io.github.ultron.carga",
                          flags=Gio.ApplicationFlags.NON_UNIQUE)

    def activar(aplicacion: Any) -> None:
        win = Gtk.ApplicationWindow(application=aplicacion, title="Ultron")
        win.set_decorated(False)
        css = Gtk.CssProvider()
        fondo = tema.paleta.get("fondo", "#000000")
        texto = tema.paleta.get("texto", "#ffffff")
        acento = tema.paleta.get("primario", "#00d7ff")
        css.load_from_data(
            f"window {{ background: {fondo}; color: {texto}; }}"
            f".titulo {{ font-size: 42px; font-weight: 800; letter-spacing: 6px; "
            f"color: {acento}; }}"
            f".capa {{ font-size: 18px; opacity: 0.8; }}"
            f"progressbar trough {{ min-height: 6px; }}"
            f"progressbar progress {{ background: {acento}; min-height: 6px; }}", -1)
        Gtk.StyleContext.add_provider_for_display(win.get_display(), css, 800)
        caja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        caja.set_margin_bottom(80)
        area = Gtk.DrawingArea()
        area.set_vexpand(True)
        area.set_draw_func(lambda _a, cr, w, h: dibujar_animacion(
            cr, w, h, time.monotonic() - inicio, tema.id, tema.paleta))
        etiqueta = Gtk.Label(label=titulo)
        etiqueta.add_css_class("titulo")
        capa_lbl = Gtk.Label(label="preparando…")
        capa_lbl.add_css_class("capa")
        barra = Gtk.ProgressBar()
        barra.set_margin_start(300)
        barra.set_margin_end(300)
        for w in (area, etiqueta, capa_lbl, barra):
            caja.append(w)
        win.set_child(caja)
        win.fullscreen()
        win.present()
        GLib.timeout_add(33, lambda: area.queue_draw() or True)

        def actualizar(capa: str, estado: str) -> bool:
            estados[capa] = estado
            hechas = sum(e in ("aplicada", "restaurada", "saltada", "fallida")
                         for e in estados.values())
            capa_lbl.set_label(f"{capa} · {estado}")
            barra.set_fraction(hechas / max(1, len(capas), len(estados)))
            return False

        def progreso(capa: str, estado: str) -> None:
            GLib.idle_add(actualizar, capa, estado)

        def hilo() -> None:
            try:
                resultado["valor"] = trabajo(progreso)
            except BaseException as e:  # noqa: BLE001 - se relanza en el hilo principal
                resultado["error"] = e
            finally:
                GLib.timeout_add(400, lambda: aplicacion.quit() or False)

        threading.Thread(target=hilo, daemon=True).start()

    app.connect("activate", activar)
    app.run([])
    if "error" in resultado:
        raise resultado["error"]
    return resultado.get("valor")
