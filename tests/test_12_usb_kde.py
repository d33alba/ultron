"""PC del centro: KDE Plasma, sin sudo y sin internet (instalación desde USB)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.falsos import EjecutorFalso
from ultron.capas import plasma, sonido
from ultron.capas.base import Contexto
from ultron.nucleo import motor, registro, rutas
from ultron.nucleo.ejecutor import Ejecutor, ErrorEjecucion

LISTA = """You have the following color schemes on your system:
 * BreezeClassic
 * BreezeDark
 * BreezeLight (current color scheme)
"""

APPLETSRC = """[Containments][1]
plugin=org.kde.panel

[Containments][7][Wallpaper][org.kde.image][General]
Image=file:///usr/share/wallpapers/Next/contents/images/1920x1080.png
"""


def _ctx(id_modo: str) -> Contexto:
    m = registro.obtener(id_modo)
    return Contexto(modo=m, dir_modo=m.dir)


def test_fondo_y_esquema_actuales_de_plasma(tmp_path):
    archivo = tmp_path / "appletsrc"
    archivo.write_text(APPLETSRC, encoding="utf-8")
    assert plasma.fondo_actual(archivo) == "/usr/share/wallpapers/Next/contents/images/1920x1080.png"
    assert plasma.fondo_actual(tmp_path / "no") is None
    assert plasma.esquema_actual(LISTA) == "BreezeLight"


def test_capa_plasma_solo_en_kde(monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "ubuntu:GNOME")
    assert not plasma.CapaPlasma(EjecutorFalso(), _ctx("netanyahu")).disponible()[0]
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    assert plasma.CapaPlasma(EjecutorFalso(), _ctx("netanyahu")).disponible()[0]


def test_capa_plasma_aplica_y_restaura(monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    actual = {"esquema": "BreezeLight"}

    def aplicar_esquema(cmd: list[str]) -> str:
        actual["esquema"] = cmd[-1]
        return ""

    ej = EjecutorFalso(respuestas={
        ("kreadconfig5", *plasma.COLORES): lambda _cmd: actual["esquema"] + "\n",
        "plasma-apply-colorscheme": aplicar_esquema,
    })
    capa = plasma.CapaPlasma(ej, _ctx("netanyahu"))
    cfg = registro.obtener("netanyahu").capas["escritorio"]
    previo = capa.capturar(cfg)
    capa.aplicar(cfg)
    assert any("fondo.png" in c for c in ej.comandos("plasma-apply-wallpaperimage"))
    assert ej.comandos("plasma-apply-colorscheme BreezeDark")
    assert any("bloqueo.png" in c for c in ej.comandos("kwriteconfig5"))
    capa.restaurar(previo)
    assert ej.comandos("plasma-apply-colorscheme BreezeLight")
    assert ej.comandos("qdbus org.kde.plasmashell")  # no había fondo propio: el de Plasma
    # sin bloqueo previo se borra la clave (kwriteconfig5 … --key Image --delete)
    assert any(c.endswith("--key Image --delete") for c in ej.comandos("kwriteconfig5"))


def test_motor_anade_plasma_a_los_modos_con_escritorio():
    clases, _ = motor.capas_del_modo(registro.obtener("focus"))
    assert plasma.CapaPlasma in clases
    clases, _ = motor.capas_del_modo(registro.obtener("focus"), excepto=["escritorio"])
    assert plasma.CapaPlasma not in clases


def test_musica_sin_mpv_usa_vlc_ffplay_o_paplay(tmp_path):
    mp3 = tmp_path / "musica.mp3"
    mp3.write_bytes(b"x")
    cfg = {"volumen": 50, "bucle": True}
    assert sonido.orden_musica(EjecutorFalso(programas={"cvlc"}), mp3, cfg)[0] == "cvlc"
    assert sonido.orden_musica(EjecutorFalso(programas={"ffplay"}), mp3, cfg)[0] == "ffplay"
    assert sonido.orden_musica(EjecutorFalso(programas={"paplay"}), mp3, cfg) is None
    mp3.with_suffix(".ogg").write_bytes(b"x")
    orden = sonido.orden_musica(EjecutorFalso(programas={"paplay"}), mp3, cfg)
    assert orden[:2] == ["bash", "-c"] and orden[-1].endswith("musica.ogg")


def test_netanyahu_trae_copia_ogg_para_paplay():
    assert (registro.obtener("netanyahu").dir / "tema" / "musica.ogg").is_file()


def test_instalacion_usa_la_carpeta_offline(tmp_path, monkeypatch):
    from ultron.compartidas.instalacion import descargar_extension

    zip_ = tmp_path / "extensiones" / "46" / "blur-my-shell@aunetx.zip"
    zip_.parent.mkdir(parents=True)
    zip_.write_bytes(b"PK")
    monkeypatch.setenv("ULTRON_OFFLINE", str(tmp_path))
    assert rutas.offline() == tmp_path

    class SinRed:
        def get(self, *a, **k):
            raise AssertionError("no debe usar la red")

    assert descargar_extension("blur-my-shell@aunetx", "46", tmp_path / "c", SinRed()) == zip_


def test_sin_sudo_no_pide_contrasena(monkeypatch):
    monkeypatch.setenv("ULTRON_SIN_SUDO", "1")
    monkeypatch.delenv("ULTRON_SUDO", raising=False)
    from ultron.nucleo.entorno import puede_sudo

    assert not puede_sudo()
    with pytest.raises(ErrorEjecucion, match="administrador"):
        Ejecutor().run(["true"], sudo=True)


def test_atajo_crea_entrada_de_menu(monkeypatch):
    from ultron.nucleo import atajo

    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    ej = EjecutorFalso()
    assert atajo.instalar(ej)
    menu = rutas.xdg_datos_raiz() / "applications" / "ultron-nexus.desktop"
    assert "X-KDE-Shortcuts=Meta+U" in menu.read_text(encoding="utf-8")
    assert any("Meta+U" in c for c in ej.comandos("kwriteconfig5"))
    atajo.quitar(ej)
    assert not menu.exists()


def test_instalador_usb_sin_sudo():
    texto = (Path(__file__).parent.parent / "instalar-usb.sh").read_text(encoding="utf-8")
    ordenes = "\n".join(x for x in texto.splitlines() if not x.lstrip().startswith("#"))
    import re

    assert not re.search(r"(^|[;&|]\s*)sudo\s", ordenes, re.M) and "apt-get" not in ordenes
    assert "--no-index" in texto and "--sin-apt" in texto


def test_voz_quita_fonemas_que_piper_2023_no_admite(tmp_path):
    import json

    from ultron.nucleo import voz

    ruta = tmp_path / "voz.onnx.json"
    ruta.write_text(json.dumps({"phoneme_id_map": {"a": [14], "aɪ": [161], "ɔɪ": [163]},
                                "espeak": {"voice": "es"}}), encoding="utf-8")
    assert voz.reparar_config(ruta)
    assert json.loads(ruta.read_text(encoding="utf-8"))["phoneme_id_map"] == {"a": [14]}
    assert not voz.reparar_config(ruta)  # ya estaba bien


def test_salir_borra_lanzadores_de_una_sesion_cortada():
    from ultron.capas import lanzadores

    ej = EjecutorFalso()
    escritorio = lanzadores.dir_escritorio(ej)
    escritorio.mkdir(parents=True, exist_ok=True)
    resto = escritorio / "ultron-gaming-hud.desktop"
    ajeno = escritorio / "mi-documento.desktop"
    resto.write_text("x", encoding="utf-8")
    ajeno.write_text("x", encoding="utf-8")
    capa = lanzadores.CapaLanzadores(ej, _ctx("netanyahu"))
    capa.restaurar({"creados": []})
    assert not resto.exists() and ajeno.exists()


def test_sin_admin_no_toca_el_perfil_de_energia(monkeypatch):
    from ultron.capas import sistema

    monkeypatch.setenv("ULTRON_SIN_SUDO", "1")
    ej = EjecutorFalso(respuestas={"powerprofilesctl get": "balanced\n"})
    capa = sistema.CapaSistema(ej, _ctx("gaming"))
    cfg = {"perfil_energia": "performance"}
    capa.restaurar(capa.capturar(cfg) | {"perfil": "balanced"})
    capa.aplicar(cfg)
    assert not ej.comandos("powerprofilesctl set")


def test_plasma_no_pide_el_esquema_que_ya_esta(monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    ej = EjecutorFalso(respuestas={("kreadconfig5", *plasma.COLORES): "BreezeDark\n"})
    capa = plasma.CapaPlasma(ej, _ctx("netanyahu"))
    capa.aplicar(registro.obtener("netanyahu").capas["escritorio"])
    capa.restaurar({"colores": "BreezeDark"})
    assert not ej.comandos("plasma-apply-colorscheme")
