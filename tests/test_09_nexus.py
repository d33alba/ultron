"""NEXUS: catálogo de funciones, búsqueda, lanzadores del escritorio y la interfaz Textual."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
import typer.main

from tests.falsos import EjecutorFalso
from ultron.capas.base import Contexto
from ultron.capas.lanzadores import CapaLanzadores, dir_aplicaciones
from ultron.cli import app
from ultron.nucleo import registro
from ultron.ui.nexus import catalogo

SHELL = "org.gnome.shell"


def _comandos() -> dict[str, object]:
    salida: dict[str, object] = {}

    def recorrer(grupo, ruta):
        for nombre, sub in grupo.commands.items():
            if hasattr(sub, "commands"):
                salida[" ".join(ruta + [nombre])] = sub
                recorrer(sub, ruta + [nombre])
            else:
                salida[" ".join(ruta + [nombre])] = sub

    recorrer(typer.main.get_command(app), [])
    return salida


def test_todas_las_fichas_existen_en_el_cli():
    comandos = _comandos()
    for f in catalogo.FICHAS:
        assert f.comando in comandos, f.comando
        cmd = comandos[f.comando]
        opciones = {o for p in getattr(cmd, "params", []) for o in getattr(p, "opts", [])}
        for c in f.campos:
            if c.opcion:
                assert c.opcion in opciones, (f.comando, c.opcion)


def test_modos_tienen_fichas_y_ids_unicos():
    for m in registro.listar():
        assert catalogo.de_modo(m.id), m.id
    ids = [(f.modo, f.id) for f in catalogo.FICHAS]
    assert len(ids) == len(set(ids))


def test_argv_y_campos_obligatorios():
    f = catalogo.buscar_comando("osint dominio")
    assert f.argv({"objetivo": "ubuntu.com"}) == ["osint", "dominio", "ubuntu.com"]
    assert f.faltan({}) and not f.faltan({"objetivo": "x"})
    r = catalogo.buscar_comando("radar")
    assert r.argv({"puertos": "1"}) == ["radar", "--puertos"]
    e = catalogo.buscar_comando("examen")
    assert e.argv({"archivo": "a.pdf"}) == ["examen", "a.pdf", "--n", "10"]


@pytest.mark.parametrize("consulta,esperado", [
    ("escanea mi red", "radar"), ("resume mis apuntes", "resumen"),
    ("ordenar descargas", "ordenar"), ("jugar", "juegos"), ("borrar historial", "rastros"),
])
def test_lenguaje_natural(consulta, esperado):
    assert catalogo.ordenar_por_consulta(list(catalogo.FICHAS), consulta)[0].comando == esperado


def test_lanzadores_crean_y_restauran(tmp_home):
    favoritos = "['firefox_firefox.desktop', 'org.gnome.Nautilus.desktop']"
    ej = EjecutorFalso(gsettings={(SHELL, "favorite-apps"): favoritos},
                       programas={"gsettings"})
    m = registro.obtener("focus")
    capa = CapaLanzadores(ej, Contexto(modo=m, dir_modo=m.dir))
    previo = capa.capturar({})
    capa.aplicar({})
    apps = dir_aplicaciones()
    assert (apps / "ultron-nexus.desktop").exists()
    resumen = (apps / "ultron-focus-resumen.desktop").read_text(encoding="utf-8")
    assert "lanzar resumen %F" in resumen and "MimeType=" in resumen
    assert (Path.home() / "Escritorio" / "ultron-focus-pomodoro.desktop").exists()
    nuevos = ej.gsettings[(SHELL, "favorite-apps")]
    assert nuevos.startswith("['ultron-nexus.desktop'") and "firefox_firefox" in nuevos
    capa.restaurar(previo)
    assert not (apps / "ultron-focus-resumen.desktop").exists()
    assert not (Path.home() / "Escritorio" / "ultron-nexus.desktop").exists()
    assert ej.gsettings[(SHELL, "favorite-apps")] == favoritos


def test_nexus_puente_y_hangar(tmp_home):
    from textual.widgets import Input

    from ultron.nucleo import estado
    from ultron.ui.nexus.app import Formulario, Nexus

    async def puente():
        estado.actualizar(modo_activo="netanyahu")
        nexus = Nexus(arranque=False)
        async with nexus.run_test(size=(150, 45)) as piloto:
            await piloto.pause(0.2)
            for c in "investiga ubuntu.com":
                await piloto.press("space" if c == " " else c)
            assert nexus.screen.query_one("#mando", Input).value == "investiga ubuntu.com"
            await piloto.press("enter")
            await piloto.pause(0.2)
            assert isinstance(nexus.screen, Formulario)
            await piloto.press("enter")
        return nexus.return_value

    assert asyncio.run(puente()) == ("ejecutar", ["osint", "operacion", "ubuntu.com"])

    async def hangar():
        estado.actualizar(modo_activo=None)
        nexus = Nexus(arranque=True)
        async with nexus.run_test(size=(150, 45)) as piloto:
            await piloto.pause(0.1)
            await piloto.press("x")  # salta el arranque
            await piloto.pause(0.2)
            await piloto.press("down", "enter")
        return nexus.return_value

    assert asyncio.run(hangar())[0] == "entrar"


def test_lanzadores_colocan_iconos_en_columna(tmp_home):
    ej = EjecutorFalso(gsettings={(SHELL, "favorite-apps"): "@as []"},
                       programas={"gsettings", "gio"})
    m = registro.obtener("netanyahu")  # sin gnome-extensions: no reinicia el escritorio
    capa = CapaLanzadores(ej, Contexto(modo=m, dir_modo=m.dir))
    capa.aplicar({})
    posiciones = [c[-1] for c in ej.historial if "metadata::nautilus-icon-position" in c]
    assert posiciones[0] == "150,70" and posiciones[1] == "150,188"
    assert (Path.home() / "Escritorio" / "ultron-nexus.desktop").exists()
    assert ["gnome-extensions", "enable", "ding@rastersoft.com"] not in ej.historial
