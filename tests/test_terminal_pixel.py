"""Escenas, degradación y coste del framebuffer de Ultron."""

from __future__ import annotations

import asyncio
import base64
from hashlib import sha256
from io import StringIO
from statistics import quantiles
from time import perf_counter_ns

import pytest
from rich.color import ColorSystem
from rich.console import Console

from ultron.ui import escenas, pantalla_pixel, pixel, tema

HUELLAS = {
    "gaming": "f58b823d7d8ec4b804c7962fef037b4190c131be91b21bbd150e5ff19b54b88d",
    "netanyahu": "6233b51f4d360ab9d5e7ba50dc1c07268069d87cd26ab453a67ac81ad85e626d",
    "focus": "c0c475aa3c40a1563298af11081a6ffb0e503d63b120bd0c69d58472d68f1f95",
    "presentacion": "c1c889bd4f5b64aead66c25790e43f756445c7cc5eee5961328dd1a1980c1288",
    "fantasma": "06d011981ed2d7b5407c5e7c86265f136a2d5056a0f27daeddf08e2870e2c8cf",
}


@pytest.mark.parametrize("modo", HUELLAS)
def test_secuencia_de_spans(modo):
    render = pixel.Diferencial()
    paleta = tema.cargar_tema(modo).paleta
    cuadros = [render.spans(escenas.fotograma(modo, paleta, 80, 24, t, reloj="18:42"))
               for t in (0.137, 0.673, 2.677, 2.863)]
    assert sha256(repr(cuadros).encode()).hexdigest() == HUELLAS[modo]


@pytest.mark.parametrize(("env", "tty", "color", "unicode", "esperado"), [
    ({"KITTY_WINDOW_ID": "3"}, True, True, True, "kitty"),
    ({"TERM": "xterm-sixel"}, True, True, True, "sixel"),
    ({"TERM_PROGRAM": "iTerm.app"}, True, True, True, "iterm"),
    ({"TERM": "xterm-256color", "VTE_VERSION": "7600"}, True, True, True, "bloques"),
    ({"TERM": "xterm-256color", "KONSOLE_VERSION": "230800"}, True, True, True, "bloques"),
    ({"TERM": "xterm-kitty", "TMUX": "1"}, True, True, True, "bloques"),
    ({"TERM": "xterm-kitty", "SSH_CONNECTION": "enlace"}, True, True, True, "bloques"),
    ({"TERM": "xterm-kitty", "NO_COLOR": ""}, True, True, True, "simple"),
    ({"TERM": "xterm-kitty"}, False, True, True, "simple"),
    ({"TERM": "xterm-kitty"}, True, False, True, "simple"),
    ({"TERM": "xterm-kitty"}, True, True, False, "simple"),
    ({"TERM": "dumb"}, True, True, True, "simple"),
])
def test_protocolo(env, tty, color, unicode, esperado):
    assert pixel.protocolo(env, tty=tty, color=color, unicode=unicode) == esperado


def test_braille_spans_y_256_colores():
    lienzo = pixel.Lienzo(4, 2, ((0, 0, 0), (255, 255, 255)))
    render = pixel.Diferencial()
    render.spans(lienzo)
    lienzo.fino(2, 0, 1)
    lienzo.fino(3, 3, 1)
    lienzo.punto(3, 2, 1)
    assert render.spans(lienzo) == [(0, 1, (("⢁", 1, 0),)), (1, 3, (("▀", 1, 0),))]
    assert render.spans(lienzo) == []
    lienzo.velar(2)
    datos = render.ansi(lienzo, ColorSystem.EIGHT_BIT)
    assert datos.startswith("\x1b[1;2H\x1b[38;5;")
    assert ";48;5;" in datos and ";2;" not in datos
    assert render.ansi(lienzo, ColorSystem.EIGHT_BIT) == ""


def test_codificadores_nativos(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "numpy", None)
    lienzo = pixel.Lienzo(2, 1, ((0, 0, 0), (250, 130, 5)))
    lienzo.punto(1, 1, 1)
    kitty = pixel.imagen(lienzo, "kitty")
    assert kitty.startswith("\x1b_Ga=T,")
    assert base64.b64decode(kitty.partition(";")[2][:-2]) == bytes(9) + bytes((250, 130, 5))
    sixel = pixel.imagen(lienzo, "sixel")
    assert '"1;1;2;2' in sixel and "#1;2;98;51;2" in sixel
    iterm = pixel.imagen(lienzo, "iterm")
    assert base64.b64decode(iterm.partition(":")[2][:-1]).startswith(b"\x89PNG")


def test_ritmo_con_latencia(monkeypatch):
    monkeypatch.setenv("SSH_CONNECTION", "enlace")
    ritmo = pantalla_pixel.Ritmo(60)
    assert ritmo.intervalo == 1 / 15
    ritmo.medir(0.04)
    assert ritmo.intervalo == 0.12
    for _ in range(60):
        ritmo.medir(0.001)
    assert ritmo.intervalo == 1 / 15


def test_portada_restaura_terminal_si_se_interrumpe(monkeypatch):
    archivo = StringIO()
    consola = Console(file=archivo, force_terminal=True, color_system="truecolor",
                      legacy_windows=False, width=80, height=24)
    modo = tema.Tema("gaming", "Gaming", {}, _consola=consola)
    monkeypatch.setattr(tema, "animaciones_activas", lambda: True)
    monkeypatch.setattr(pantalla_pixel, "salida", lambda _tema: "bloques")

    def interrumpir(_segundos):
        raise KeyboardInterrupt

    monkeypatch.setattr(pantalla_pixel.time, "sleep", interrumpir)
    with pytest.raises(KeyboardInterrupt):
        pantalla_pixel.avance(modo)
    datos = archivo.getvalue()
    assert "\x1b[?1049h" in datos and "\x1b[?1049l" in datos
    assert "\x1b[?25h" in datos


@pytest.mark.parametrize("modo", HUELLAS)
def test_presupuesto_de_8_ms_en_python_puro(modo):
    render = pixel.Diferencial()
    paleta = tema.cargar_tema(modo).paleta
    muestras = []
    for i in range(110):
        inicio = perf_counter_ns()
        cuadro = escenas.fotograma(modo, paleta, 120, 40, i / 60, reloj="18:42")
        render.ansi(cuadro, ColorSystem.TRUECOLOR)
        if i >= 10:
            muestras.append((perf_counter_ns() - inicio) / 1e6)
    assert quantiles(muestras, n=20)[-1] < 8


def test_hangar_y_selector_a_80_columnas(monkeypatch):
    from ultron.ui.fondo import Fondo
    from ultron.ui.nexus.app import Hangar, Nexus
    from ultron.ui.selector import crear_app

    monkeypatch.setattr(pantalla_pixel, "habilitada", lambda _tema: True)
    monkeypatch.setattr(Hangar, "_precalentar", lambda _pantalla: None)
    monkeypatch.setenv("ULTRON_SIN_ANIMACIONES", "1")

    async def comprobar():
        hangar = Nexus(arranque=False, pantalla="hangar")
        async with hangar.run_test(size=(80, 24)) as piloto:
            await piloto.pause()
            fondo = hangar.screen.query_one(Fondo)
            assert fondo.region.width == 80 and fondo.region.y == 0
            assert hangar.screen.query_one("#cuerpo").region.y >= 7
            assert hangar.screen.query_one("#activar").region.right <= 80
            antes = fondo.tema.id
            await piloto.press("down")
            assert fondo.tema.id != antes and fondo.ultimo is not None
            await piloto.press("enter")
        assert hangar.return_value[0] == "entrar"
        selector = crear_app()
        async with selector.run_test(size=(80, 24)) as piloto:
            await piloto.pause()
            fondo = selector.screen.query_one(Fondo)
            assert fondo.region.width == 80 and fondo.region.y == 0
            assert selector.screen.query_one("#logo").region.y >= 5
            antes = fondo.tema.id
            await piloto.press("left")
            assert fondo.tema.id != antes
            await piloto.press("enter")
        assert selector.return_value[0] == "entrar"

    asyncio.run(comprobar())
