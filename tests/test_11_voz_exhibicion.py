"""Voz de ULTRON, enlace del Ojo de Dios con capas, ayuda en español."""

from __future__ import annotations

from ultron.modos.netanyahu.funciones.ojo import url_vista
from ultron.nucleo import voz


def test_limpiar_texto_para_voz():
    texto = voz.limpiar("## Hola **mundo** `codigo` https://x.y/z ✨ fin.")
    assert "#" not in texto and "*" not in texto and "enlace" in texto and "✨" not in texto


def test_comando_espeak_por_modo(monkeypatch):
    monkeypatch.setattr(voz, "motor", lambda: "espeak-ng")
    grave = voz.comando("hola", "netanyahu")[0]
    rapida = voz.comando("hola", "gaming")[0]
    assert grave[0] == "espeak-ng" and "es+m7" in grave
    assert int(rapida[rapida.index("-s") + 1]) > int(grave[grave.index("-s") + 1])


def test_voz_callada_en_tests():
    assert voz.hablar("hola") is False


def test_url_ojo_con_capas():
    url = url_vista(40.4, -3.7, 80000, "vuelos,satelites")
    assert "welcome=0" in url and "l=f.s" in url and "lat=40.4000" in url
    assert "&l=" not in url_vista(capas="ninguna")


def test_ayuda_en_espanol():
    from typer.testing import CliRunner

    from ultron.cli import app

    salida = CliRunner().invoke(app, ["voz", "--help"]).output
    assert "Uso:" in salida and "Muestra esta ayuda" in salida and "Usage" not in salida
