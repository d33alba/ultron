"""Pruebas de las transformaciones de escritorio sin depender de una sesión gráfica."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET

import pytest
from falsos import EjecutorFalso

from ultron.capas._plasma_radical import SERVICIO
from ultron.capas.base import Contexto
from ultron.capas.sesion_grafica import CapaSesionGrafica
from ultron.nucleo import registro, rutas
from ultron.nucleo.ejecutor import Resultado


def capa(modo, ej):
    definicion = registro.obtener(modo)
    return CapaSesionGrafica(ej, Contexto(definicion, definicion.dir)), (
        definicion.capas["sesion_grafica"]
    )


@pytest.mark.parametrize(("version", "bus"), [("5", "qdbus"), ("6", "qdbus6")])
def test_plasma_disposicion_y_restauracion_exacta(monkeypatch, version, bus):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    monkeypatch.setenv("KDE_SESSION_VERSION", version)
    config, datos = rutas.xdg_config_raiz(), rutas.xdg_datos_raiz()
    applets = config / "plasma-org.kde.plasma.desktop-appletsrc"
    shell = config / "plasmashellrc"
    kwin = config / "kwinrc"
    xbel = datos / "user-places.xbel"
    originales = {
        applets: b"[Containments][4]\r\nplugin=org.kde.panel\r\n",
        shell: b"[PlasmaViews]\n# comentario\n",
        kwin: b"[Plugins]\nblurEnabled=false",
        xbel: b"<xbel><bookmark href='file:///mis-cosas'><title>Antes</title></bookmark></xbel>",
    }
    for ruta, contenido in originales.items():
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(contenido)
    ej = EjecutorFalso(programas={bus, f"kwriteconfig{version}", "systemctl",
                                  "plasma-apply-colorscheme", "plasma-apply-desktoptheme"},
                       respuestas=({("kwriteconfig6", "--help"): "--notify"}
                                   if version == "6" else {}))
    escritorio, cfg = capa("gaming", ej)
    assert escritorio.disponible()[0]
    previo = json.loads(json.dumps(escritorio.capturar(cfg)))
    escritorio.aplicar(cfg)

    paquete = datos / "plasma/look-and-feel/ultron-gaming/contents"
    guion = (paquete / "layouts/org.kde.plasma.desktop-layout.js").read_text(encoding="utf-8")
    assert '"top", 28' in guion and '"bottom", 62' in guion and "appmenu" in guion
    assert "systemmonitor.cpu" in guion and "panel.alignment" in guion
    assert "NumberAnimation" in (paquete / "splash/Splash.qml").read_text(encoding="utf-8")
    assert any(c[0] == bus and c[-1] == guion for c in ej.historial)
    perfil = next(c for c in ej.historial if "DefaultProfile" in c)
    assert perfil[0] == f"kwriteconfig{version}"
    assert ("--notify" in perfil) == (version == "6")
    assert ej.comandos("plasma-apply-desktoptheme ultron-gaming")
    assert bool(ej.comandos("systemctl --user restart")) == (version == "5")
    ventana = datos / "aurorae/themes/ultron-gaming/decoration.svg"
    assert ET.parse(ventana).getroot().find(".//*[@id='decoration-topleft']") is not None
    assert "file:///mis-cosas" in xbel.read_text(encoding="utf-8")
    for ruta in (applets, shell, kwin):
        ruta.write_bytes(b"cambios aplicados por KDE")
    salir, _ = capa("gaming", ej)
    salir.restaurar(previo)
    assert not ventana.exists()
    assert all(ruta.read_bytes() == contenido for ruta, contenido in originales.items())
    assert ej.historial.index(["systemctl", "--user", "stop", SERVICIO]) < (
        ej.historial.index(["systemctl", "--user", "start", SERVICIO])
    )
    assert not ej.comandos("sudo") and not ej.comandos("pkexec")


def test_plasma_sin_servicio_y_simulado(monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    ej = EjecutorFalso(simular=True, programas={"kwriteconfig6", "qdbus6", "systemctl"},
                       respuestas={"systemctl --user is-active": Resultado(3, "", "")})
    escritorio, cfg = capa("fantasma", ej)
    previo = escritorio.capturar(cfg)
    assert not previo["paneles"]
    escritorio.aplicar(cfg)
    assert any("PreviewsShown" in c and c[-1] == "false" for c in ej.historial)
    assert not any("org.kde.PlasmaShell.evaluateScript" in c for c in ej.historial)
    assert all(not rutas.xdg_datos_raiz().joinpath(p).exists() for p in ("plasma", "aurorae"))
    escritorio.restaurar(previo)
    assert not ej.comandos("systemctl")


def test_gnome_priva_recientes_y_restaura_marcadores(monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "ubuntu:GNOME")
    clave = ("org.gnome.desktop.privacy", "remember-recent-files")
    ej = EjecutorFalso(gsettings={clave: "true"})
    marcador = rutas.xdg_config_raiz() / "gtk-3.0/bookmarks"
    marcador.parent.mkdir(parents=True)
    marcador.write_bytes(b"file:///apuntes Mis notas\r\n")
    escritorio, cfg = capa("fantasma", ej)
    previo = escritorio.capturar(cfg)
    escritorio.aplicar(cfg)
    assert ej.gsettings[clave] == "false"
    assert b"Carpeta personal" in marcador.read_bytes()
    escritorio.restaurar(previo)
    assert ej.gsettings[clave] == "true"
    assert marcador.read_bytes() == b"file:///apuntes Mis notas\r\n"
    assert ej.comandos("gsettings reset org.gnome.desktop.privacy remember-recent-files")


@pytest.mark.parametrize(("sesion", "esquema", "clave"), [
    ("X-Cinnamon", "org.cinnamon", "desktop-effects"),
    ("MATE", "org.mate.NotificationDaemon", "do-not-disturb"),
])
def test_esquemas_opcionales(monkeypatch, sesion, esquema, clave):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", sesion)
    anterior = "true" if sesion == "X-Cinnamon" else "false"
    ej = EjecutorFalso(gsettings={(esquema, clave): anterior})
    escritorio, cfg = capa("focus", ej)
    previo = escritorio.capturar(cfg)
    escritorio.aplicar(cfg)
    assert ej.gsettings[esquema, clave] != anterior
    escritorio.restaurar(previo)
    assert ej.gsettings[esquema, clave] == anterior


def test_xfce_omite_propiedades_inexistentes(monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "XFCE")
    cmd = "xfconf-query -c xfce4-notifyd -p /do-not-disturb"
    ej = EjecutorFalso(respuestas={cmd: "false\n"})
    escritorio, cfg = capa("presentacion", ej)
    previo = escritorio.capturar(cfg)
    escritorio.aplicar(cfg)
    escritorio.restaurar(previo)
    assert ej.comandos("xfconf-query") == [cmd + " -s true", cmd + " -s false"]


def test_fantasma_oculta_recientes_sin_borrar_marcadores(monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    xbel = rutas.xdg_datos_raiz() / "user-places.xbel"
    xbel.parent.mkdir(parents=True)
    original = b'<xbel><bookmark href="recentlyused:/files"><title>Recientes</title></bookmark></xbel>'
    xbel.write_bytes(original)
    escritorio, cfg = capa("fantasma", EjecutorFalso(programas={"kwriteconfig5"}))
    previo = escritorio.capturar(cfg)
    escritorio.aplicar(cfg)
    assert ET.parse(xbel).findtext("./bookmark/info/metadata/IsHidden") == "true"
    escritorio.restaurar(previo)
    assert xbel.read_bytes() == original
