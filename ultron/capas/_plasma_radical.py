"""Transformación de Plasma por usuario con instantánea de los archivos modificados."""

from __future__ import annotations

import base64
import os
import stat
import xml.etree.ElementTree as ET
from pathlib import Path

from ultron.capas import _recursos_plasma as R
from ultron.capas.base import Capa
from ultron.nucleo.ejecutor import Ejecutor, ErrorEjecucion
from ultron.ui.tema import animaciones_activas, cargar_tema, consola

SERVICIO = "plasma-plasmashell.service"
PANELES = ("plasma-org.kde.plasma.desktop-appletsrc", "plasmashellrc")
MODOS_VISTA = {"gaming": "0", "focus": "1", "netanyahu": "1",
               "presentacion": "0", "fantasma": "2"}
OPACIDADES = {"gaming": .72, "focus": 1, "netanyahu": .82, "presentacion": 1, "fantasma": .95}


def capturar_archivo(ruta: Path) -> dict | None:
    try:
        return {"bytes": base64.b64encode(ruta.read_bytes()).decode("ascii"),
                "permisos": stat.S_IMODE(ruta.stat().st_mode)}
    except FileNotFoundError:
        return None


def restaurar_archivo(ej: Ejecutor, ruta: Path, previo: dict | None) -> None:
    if ruta.is_symlink():
        return
    if previo is None:
        if ruta.is_file() or ej.simular:
            ej.borrar(ruta)
    else:
        ej.escribir(ruta, base64.b64decode(previo["bytes"]), modo=previo["permisos"])


def lugares_xbel(ruta: Path, lugares: list[tuple[Path, str]], discreto: bool) -> str:
    contenido = ruta.read_bytes() if ruta.is_file() else b"<xbel/>"
    raiz = ET.fromstring(contenido)
    if raiz.tag != "xbel":
        raise ValueError("el archivo no contiene marcadores XBEL")
    for lugar, titulo in lugares:
        uri = lugar.as_uri()
        if not any(n.get("href") == uri for n in raiz.findall("bookmark")):
            nodo = ET.SubElement(raiz, "bookmark", href=uri)
            ET.SubElement(nodo, "title").text = titulo
    if discreto:
        for nodo in raiz.findall("bookmark"):
            if nodo.get("href", "").split(":", 1)[0] in {"recentlyused", "timeline", "activities"}:
                meta = nodo.find("./info/metadata[@owner='http://www.kde.org']")
                if meta is None:
                    info = nodo.find("info")
                    if info is None:
                        info = ET.SubElement(nodo, "info")
                    meta = ET.SubElement(info, "metadata", owner="http://www.kde.org")
                oculto = meta.find("IsHidden")
                if oculto is None:
                    oculto = ET.SubElement(meta, "IsHidden")
                oculto.text = "true"
    return '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xbel>\n' + ET.tostring(
        raiz, encoding="unicode"
    )


class Plasma:
    """Adapta las herramientas de Frameworks 5 y 6."""

    def __init__(self, capa: Capa, lugares: list[tuple[Path, str]]):
        self.ej = capa.ej
        self.ctx = capa.ctx
        self.modo = capa.ctx.modo.id
        self.id = f"ultron-{self.modo}"
        self.config = self.ctx.rutas.xdg_config_raiz()
        self.datos = self.ctx.rutas.xdg_datos_raiz()
        self.lugares = lugares
        version = os.environ.get("KDE_SESSION_VERSION")
        if version not in {"5", "6"}:
            version = "6" if self.ej.existe("kwriteconfig6") else "5"
        self.version = version
        self.escribir = self.programa(f"kwriteconfig{version}")
        self.dbus = self.programa(f"qdbus{version}", f"qdbus-qt{version}",
                                  f"/usr/lib/qt{version}/bin/qdbus", "qdbus")
        self.archivos: dict[Path, str] = {}
        self.claves: dict[Path, dict[str, dict[str, str]]] = {}
        self.paneles = False
        self.fondo: str | None = None
        self.guion = R.layout(self.modo)

    def programa(self, *nombres: str) -> str | None:
        return next((n for n in nombres if self.ej.existe(n)), None)

    def avisar(self, mensaje: str) -> None:
        (self.ctx.consola or consola()).print(f"Aviso de Plasma: {mensaje}", markup=False)

    def ejecutar(self, cmd: list[str], accion: str, *, fondo: bool = False) -> bool:
        try:
            bien = self.ej.run(cmd, timeout=3, check=False, fondo=fondo).ok
        except ErrorEjecucion:
            bien = False
        if not bien:
            self.avisar(accion)
        return bien

    def servicio_activo(self) -> bool:
        return bool(self.dbus and self.programa("systemctl") and self.ej.leer(
            ["systemctl", "--user", "is-active", "--quiet", SERVICIO], timeout=2
        ).ok)

    def _recursos(self, p: dict, cfg: dict) -> None:
        tema = self.datos / "plasma" / "look-and-feel" / self.id
        estilo = self.datos / "plasma" / "desktoptheme" / self.id
        aurora = self.datos / "aurorae" / "themes" / self.id
        radio = cfg.get("radio", 8)
        opacidad = OPACIDADES[self.modo]
        metadatos = ("[Desktop Entry]\n"
                     f"Name={self.id}\nX-KDE-PluginInfo-Name={self.id}\n"
                     "X-KDE-PluginInfo-Version=1.0\n")
        self.archivos.update({
            tema / "metadata.json": R.metadatos(self.id),
            tema / "metadata.desktop": metadatos + "X-KDE-ServiceTypes=Plasma/LookAndFeel\n",
            tema / "contents/layouts/org.kde.plasma.desktop-layout.js": self.guion,
            tema / "contents/splash/Splash.qml": R.splash(
                self.ctx.modo.nombre, self.ctx.modo.lema, p, cfg.get("splash_ms", 500)
            ),
            estilo / "metadata.json": R.metadatos(self.id),
            estilo / "metadata.desktop": metadatos,
            estilo / "plasmarc": "[Settings]\nFallbackTheme=breeze\n",
            estilo / "colors": R.ini(R.colores(p)),
            aurora / "metadata.desktop": metadatos,
            aurora / f"{self.id}rc": R.ini({
                "Layout": {"TitleHeight": str(cfg.get("titulo_px", 27)), "ButtonWidth": "18",
                           "ButtonHeight": "18", "BorderLeft": "4", "BorderRight": "4",
                           "BorderBottom": "5"},
                "General": {"ActiveTextColor": p["texto"], "InactiveTextColor": p["texto"]},
            }),
            aurora / "decoration.svg": R.svg(
                R.marco("decoration-", p["fondo"], p["acento"], max(.8, opacidad), radio)
                + R.marco("decoration-inactive-", p["fondo"], p["apagado"], 1, radio)
                + R.marco("mask-", "#ffffff", "#ffffff", 1, radio)
            ),
            self.datos / "color-schemes" / f"{self.id}.colors": R.ini({
                "General": {"Name": self.id}, **R.colores(p),
            }),
        })
        for variante, alfa in (("widgets", max(.67, opacidad - .10)), ("opaque/widgets", 1),
                               ("translucent/widgets", max(.55, opacidad - .20))):
            self.archivos[estilo / variante / "panel-background.svg"] = R.svg(
                R.marco("", p["fondo"], p["acento"], alfa, radio)
                + R.marco("mask-", "#ffffff", "#ffffff", 1, radio)
                + '<rect id="hint-stretch-borders" width="1" height="1"/>'
            )
        for archivo, contenido in R.botones(p).items():
            self.archivos[aurora / archivo] = contenido
        for archivo, contenido in R.konsole(self.id, p, cfg.get("fuente_konsole", "Monospace"),
                                          opacidad).items():
            self.archivos[self.datos / "konsole" / archivo] = contenido

    def _preferencias(self, cfg: dict) -> None:
        self.claves = {
            self.config / "ksplashrc": {"KSplash": {"Theme": self.id, "Engine": "KSplashQML"}},
            self.config / "plasmarc": {"Theme": {"name": self.id}},
            self.config / "kwinrc": {
                "org.kde.kdecoration2": {
                    "library": "org.kde.kwin.aurorae",
                    "theme": f"__aurorae__svg__{self.id}",
                    "ButtonsOnLeft": "XIA" if self.modo == "gaming" else "M",
                    "ButtonsOnRight": "M" if self.modo == "gaming" else "IAX",
                    "BorderSizeAuto": "false", "BorderSize": "Tiny",
                },
                "Plugins": {
                    "blurEnabled": str(self.modo in {"gaming", "netanyahu"}).lower(),
                    "wobblywindowsEnabled": str(self.modo == "gaming").lower(),
                },
                "Effect-Blur": {"BlurStrength": "7", "NoiseStrength": "2"},
            },
            self.config / "kdeglobals": {"General": {
                "font": cfg.get("fuente_kde", "Sans Serif,10"),
                "fixed": cfg.get("fuente_konsole", "Monospace,11"),
            }},
            self.config / "dolphinrc": {"General": {
                "GlobalViewProps": "true",
                "ShowToolTips": "false",
                "RememberOpenedTabs": str(self.modo != "fantasma").lower(),
            }},
            self.config / "konsolerc": {"Desktop Entry": {"DefaultProfile": self.id + ".profile"}},
            self.datos / "dolphin/view_properties/global/.directory": {"Dolphin": {
                "ViewMode": MODOS_VISTA[self.modo],
                "PreviewsShown": str(self.modo == "gaming").lower(),
                "HiddenFilesShown": "false", "Version": "4",
            }},
        }
        if self.modo in {"focus", "presentacion", "fantasma"}:
            self.claves[self.config / "plasmanotifyrc"] = {
                "DoNotDisturb": {"Until": "2099,1,1,0,0,0.0"},
            }
        if self.modo == "presentacion":
            self.claves[self.config / "kcminputrc"] = {"Mouse": {"cursorSize": "44"}}
        if self.modo == "fantasma":
            self.claves[self.config / "kactivitymanagerdrc"] = {
                "Plugins": {"org.kde.ActivityManager.Resources.ScoringEnabled": "false"},
            }

    def preparar(self, cfg: dict) -> dict:
        p = cargar_tema(self.modo).paleta
        self._recursos(p, cfg)
        self._preferencias(cfg)
        apariencia = self.ctx.modo.capas.get("escritorio", {})
        self.paneles = self.servicio_activo()
        wallpaper = apariencia.get("fondo")
        if self.paneles and self.programa("plasma-apply-wallpaperimage"):
            self.fondo = wallpaper
        bloqueo = self.ctx.recurso(apariencia.get("fondo_bloqueo") or wallpaper or ".")
        if bloqueo.is_file():
            grupos = self.claves.setdefault(self.config / "kscreenlockerrc", {})
            grupos["Greeter/Wallpaper/org.kde.image/General"] = {"Image": bloqueo.as_uri()}
        xbel = self.datos / "user-places.xbel"
        try:
            if not xbel.is_symlink():
                self.archivos[xbel] = lugares_xbel(xbel, self.lugares, self.modo == "fantasma")
        except (ValueError, ET.ParseError, OSError):
            self.avisar("se conservan los Lugares originales de Dolphin porque no se pueden leer.")
        archivos = set(self.claves) | self.archivos.keys()
        if self.paneles and any((self.config / nombre).is_symlink() for nombre in PANELES):
            self.paneles = False
        if self.paneles:
            archivos.update(self.config / nombre for nombre in PANELES)
        return {"archivos": {str(r): capturar_archivo(r) for r in sorted(archivos)
                             if not r.is_symlink()},
                "paneles": self.paneles}

    def reconfigurar(self) -> None:
        if self.dbus:
            self.ejecutar([self.dbus, "org.kde.KWin", "/KWin", "reconfigure"],
                          "KWin no respondió a la recarga de la decoración.")

    def aplicar(self) -> None:
        for ruta, contenido in self.archivos.items():
            if not ruta.is_symlink():
                self.ej.escribir(ruta, contenido)
        if self.programa("ksplashqml") and self.programa("timeout") and animaciones_activas():
            paquete = self.datos / "plasma" / "look-and-feel" / self.id
            self.ejecutar(["timeout", "4s", "ksplashqml", "--nofork", "--test", str(paquete)],
                          "no se pudo mostrar la pantalla de carga.", fondo=True)
        plasmarc = self.config / "plasmarc"
        tema_aplicado = (
            self.programa("plasma-apply-desktoptheme") and not plasmarc.is_symlink()
            and self.ejecutar(["plasma-apply-desktoptheme", self.id],
                              "se intentará activar el estilo desde plasmarc.")
        )
        if self.escribir:
            ayuda = self.ej.leer([self.escribir, "--help"], timeout=2).salida
            notificar = ["--notify"] if "--notify" in ayuda else []
            for ruta, grupos in self.claves.items():
                if tema_aplicado and ruta == plasmarc:
                    continue
                if ruta.is_symlink():
                    self.avisar(f"se omite el archivo enlazado {ruta.name}.")
                    continue
                if not ruta.parent.is_dir() and not self.ej.simular:
                    ruta.parent.mkdir(parents=True, exist_ok=True)
                for grupo, valores in grupos.items():
                    opciones = [parte for g in grupo.split("/") for parte in ("--group", g)]
                    for clave, valor in valores.items():
                        if not self.ejecutar(
                            [self.escribir, "--file", str(ruta), *opciones, "--key", clave,
                             *notificar, valor], f"no se pudo modificar {ruta.name}."
                        ):
                            break
        else:
            self.avisar("faltan kwriteconfig5/6 (paquete libkf5config-bin o libkf6config-bin).")
        if (self.programa("plasma-apply-colorscheme")
                and not (self.config / "kdeglobals").is_symlink()):
            self.ejecutar(["plasma-apply-colorscheme", self.id],
                          "no se pudo aplicar el esquema de colores.")
        self.reconfigurar()
        if self.paneles:
            self._aplicar_paneles()
        else:
            self.avisar("se omiten los paneles en vivo: se necesitan qdbus y plasmashell "
                       "gestionado por systemd de usuario con archivos de configuración propios.")

    def _aplicar_paneles(self) -> None:
        if not self.ejecutar([self.dbus, "org.kde.plasmashell", "/PlasmaShell",
                              "org.kde.PlasmaShell.evaluateScript", self.guion],
                             "no se pudo aplicar la disposición de paneles."):
            return
        if self.fondo:
            from ultron.capas.escritorio import CapaEscritorio

            imagen = CapaEscritorio(self.ej, self.ctx)._fondo(self.fondo, "fondo")
            if imagen.is_file() or self.ej.simular:
                self.ejecutar(["plasma-apply-wallpaperimage", str(imagen)],
                              "no se pudo aplicar la imagen de fondo.")
        if self.version == "5":
            self.ejecutar(["systemctl", "--user", "restart", SERVICIO],
                          "Plasma no pudo recargar sus preferencias visuales.")

    def restaurar(self, previo: dict) -> None:
        paneles = previo["paneles"]
        if paneles:
            self.ej.run(["systemctl", "--user", "stop", SERVICIO], timeout=5)
        try:
            for ruta, original in previo["archivos"].items():
                restaurar_archivo(self.ej, Path(ruta), original)
        finally:
            if paneles:
                self.ej.run(["systemctl", "--user", "start", SERVICIO], timeout=5)
        self.reconfigurar()
        if self.programa("dbus-send"):
            self.ejecutar(["dbus-send", "--session", "--type=signal", "/KGlobalSettings",
                           "org.kde.KGlobalSettings.notifyChange", "int32:0", "int32:0"],
                          "las aplicaciones abiertas podrían conservar la paleta anterior.")
