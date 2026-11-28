"""Personalización progresiva de la sesión gráfica, sin privilegios."""

from __future__ import annotations

import os
import re
from pathlib import Path

from ultron.capas import comun as C
from ultron.capas._plasma_radical import Plasma, capturar_archivo, restaurar_archivo
from ultron.capas._recursos_plasma import PANELES
from ultron.capas.base import Capa, registrar_capa
from ultron.nucleo.ejecutor import ErrorEjecucion
from ultron.ui.tema import consola

SESIONES = {"KDE", "PLASMA", "GNOME", "CINNAMON", "XFCE", "MATE"}
SILENCIOSOS = {"focus", "presentacion", "fantasma"}
TAMANOS_PANEL = {"gaming": 52, "focus": 28, "netanyahu": 40, "presentacion": 44, "fantasma": 26}
PATRON_PANEL_XFCE = re.compile(r"/panels/panel-\d+/(?:size|autohide-behavior)")
ATAJOS = {
    "gaming": (("Juegos", ("Juegos", "Games")), ("Descargas", ("Descargas", "Downloads"))),
    "focus": (("Apuntes", ("Apuntes", "apuntes", "Documentos", "Documents")),),
    "netanyahu": (("Operaciones", ("Operaciones", "Documentos", "Documents")),),
    "presentacion": (("Presentaciones", ("Presentaciones", "Documentos", "Documents")),),
    "fantasma": (("Carpeta personal", ()),),
}


def sesion() -> str | None:
    for variable in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION"):
        for nombre in os.environ.get(variable, "").upper().split(":"):
            nombre = nombre.removeprefix("X-")
            if nombre in SESIONES:
                return "KDE" if nombre == "PLASMA" else nombre
            if nombre in {"UBUNTU", "UBUNTU-WAYLAND", "GNOME-CLASSIC"}:
                return "GNOME"
    return None


def _lugares(modo: str) -> list[tuple[Path, str]]:
    home = Path.home()
    return [(next((home / n for n in opciones if (home / n).is_dir()), home), titulo)
            for titulo, opciones in ATAJOS[modo]]


@registrar_capa
class CapaSesionGrafica(Capa):
    nombre = "sesion_grafica"
    orden = 35
    descripcion = "Paneles, ventanas, terminal y gestor de archivos según el escritorio"

    def disponible(self) -> tuple[bool, str]:
        escritorio = sesion()
        if self.ctx.modo.id not in PANELES:
            return False, "el modo carece de un perfil de sesión gráfica"
        if escritorio is None:
            return False, "sesión gráfica no reconocida"
        if escritorio == "XFCE" and not self.ej.existe("xfconf-query"):
            return False, "falta el paquete xfconf (xfconf-query)"
        if escritorio in {"GNOME", "CINNAMON", "MATE"} and not self.ej.existe("gsettings"):
            return False, "falta el paquete libglib2.0-bin (gsettings)"
        return True, ""

    def _aviso(self, mensaje: str) -> None:
        (self.ctx.consola or consola()).print(f"Aviso de escritorio: {mensaje}", markup=False)

    def _gsettings(self, escritorio: str) -> dict[tuple[str, str], str]:
        modo = self.ctx.modo.id
        tranquilo = modo in SILENCIOSOS
        if escritorio == "GNOME":
            interfaz = "org.gnome.desktop.interface"
            valores = {
                (interfaz, "clock-show-weekday"): C.gv_bool(modo in {"focus", "presentacion"}),
                (interfaz, "clock-show-date"): C.gv_bool(modo != "fantasma"),
                (interfaz, "show-battery-percentage"): C.gv_bool(modo in {"gaming", "netanyahu"}),
                ("org.gnome.desktop.a11y.interface", "locate-pointer"):
                    C.gv_bool(modo == "presentacion"),
                ("org.gnome.desktop.notifications", "show-banners"): C.gv_bool(not tranquilo),
            }
            if modo == "fantasma":
                valores["org.gnome.desktop.privacy", "remember-recent-files"] = "false"
                valores["org.gnome.nautilus.preferences", "show-image-thumbnails"] = "'never'"
            return valores
        base = "org.cinnamon" if escritorio == "CINNAMON" else "org.mate"
        interfaz = f"{base}.desktop.interface" if escritorio == "CINNAMON" else f"{base}.interface"
        archivos = ("org.nemo.preferences" if escritorio == "CINNAMON"
                    else "org.mate.caja.preferences")
        vista = "list-view" if modo in {"focus", "netanyahu", "fantasma"} else "icon-view"
        valores = {
            (interfaz, "font-name"): C.gv_str({
                "gaming": "Sans 11", "focus": "Serif 11", "netanyahu": "Sans 10",
                "presentacion": "Sans 12", "fantasma": "Sans 9",
            }[modo]),
            (interfaz, "gtk-theme"): C.gv_str(self._gtk(escritorio)),
            (archivos, "default-folder-viewer"): C.gv_str(vista),
            (f"{base}.desktop.background" if escritorio == "CINNAMON" else f"{base}.background",
             "primary-color"): C.gv_str({
                "gaming": "#0b0b16", "focus": "#657568", "netanyahu": "#0a1a3f",
                "presentacion": "#2b2b2e", "fantasma": "#000000",
            }[modo]),
        }
        if modo == "fantasma":
            valores[archivos, "show-image-thumbnails"] = "'never'"
        if escritorio == "CINNAMON":
            valores[base, "desktop-effects"] = C.gv_bool(not tranquilo)
            valores[f"{base}.desktop.notifications", "display-notifications"] = C.gv_bool(
                not tranquilo
            )
        elif tranquilo:
            valores["org.mate.NotificationDaemon", "do-not-disturb"] = "true"
        if modo == "presentacion":
            mouse = "org.cinnamon.desktop.peripherals.mouse" if escritorio == "CINNAMON" else (
                "org.mate.peripherals-mouse"
            )
            valores[mouse, "locate-pointer"] = "true"
            valores[mouse, "cursor-size"] = "40"
        valores.update(self._paneles_gsettings(escritorio))
        return valores

    def _paneles_gsettings(self, escritorio: str) -> dict[tuple[str, str], str]:
        modo = self.ctx.modo.id
        ocultar = C.gv_bool(modo in SILENCIOSOS)
        tamano = str(TAMANOS_PANEL[modo])
        if escritorio == "CINNAMON":
            paneles = C.leer_lista(self.ej.gsettings_get("org.cinnamon", "panels-enabled"))
            ids = [p.split(":", 1)[0] for p in paneles if p.split(":", 1)[0].isdigit()]
            if not ids:
                return {}
            return {
                ("org.cinnamon", clave): C.gv_lista([f"{i}:{valor}" for i in ids])
                for clave, valor in (("panels-autohide", ocultar), ("panels-height", tamano))
            }
        ids = C.leer_lista(self.ej.gsettings_get("org.mate.panel", "toplevel-id-list"))
        return {
            (f"org.mate.panel.toplevel:/org/mate/panel/toplevels/{i}/", clave): valor
            for i in ids if re.fullmatch(r"[a-zA-Z0-9_-]+", i)
            for clave, valor in (("auto-hide", ocultar), ("size", tamano))
        }

    def _gtk(self, escritorio: str) -> str:
        oscuro = self.ctx.modo.id in {"gaming", "netanyahu", "fantasma"}
        return ("Mint-Y-Dark" if oscuro else "Mint-Y") if escritorio == "CINNAMON" else (
            "Adwaita-dark" if oscuro else "Adwaita"
        )

    def _xfce(self) -> dict[tuple[str, str], str]:
        modo = self.ctx.modo.id
        valores = {
            ("xsettings", "/Net/ThemeName"): self._gtk("XFCE"),
            ("xsettings", "/Gtk/FontName"): {
                "focus": "Serif 11", "presentacion": "Sans 12", "fantasma": "Sans 9",
            }.get(modo, "Sans 10"),
            ("xfwm4", "/general/use_compositing"): C.gv_bool(modo in {"gaming", "netanyahu"}),
            ("xfce4-notifyd", "/do-not-disturb"): C.gv_bool(modo in SILENCIOSOS),
            ("thunar", "/last-view"): (
                "ThunarDetailsView" if modo in SILENCIOSOS else "ThunarIconView"
            ),
            ("thunar", "/misc-thumbnail-mode"): "THUNAR_THUMBNAIL_MODE_NEVER" if modo == "fantasma"
            else "THUNAR_THUMBNAIL_MODE_ONLY_LOCAL",
        }
        if modo == "presentacion":
            valores["xsettings", "/Gtk/CursorThemeSize"] = "40"
        paneles = self.ej.leer(["xfconf-query", "-c", "xfce4-panel", "-l"], timeout=2)
        for clave in paneles.salida.splitlines() if paneles.ok else ():
            if PATRON_PANEL_XFCE.fullmatch(clave):
                valores["xfce4-panel", clave] = (
                    str(TAMANOS_PANEL[modo]) if clave.endswith("/size")
                    else ("2" if modo in SILENCIOSOS else "0")
                )
        return valores

    def _capturar_gsettings(self, escritorio: str) -> list[list]:
        resultado = []
        for (esquema, clave), nuevo in self._gsettings(escritorio).items():
            actual = self.ej.gsettings_get(esquema, clave)
            if actual is None:
                continue
            if escritorio == "GNOME" and self.ej.existe("dconf"):
                actual = C.dconf_leer(self.ej, "/" + esquema.replace(".", "/") + "/" + clave)
            resultado.append([esquema, clave, actual, nuevo])
        return resultado

    def _capturar_xfce(self) -> list[list]:
        resultado = []
        for (canal, clave), nuevo in self._xfce().items():
            r = self.ej.leer(["xfconf-query", "-c", canal, "-p", clave], timeout=2)
            if r.ok and r.salida.strip():
                resultado.append([canal, clave, r.salida.rstrip("\r\n"), nuevo])
        return resultado

    def _marcadores(self) -> dict:
        ruta = self.ctx.rutas.xdg_config_raiz() / "gtk-3.0" / "bookmarks"
        if ruta.is_symlink():
            self._aviso("se omiten los marcadores GTK porque el archivo es un enlace.")
            return {}
        anterior = capturar_archivo(ruta)
        datos = ruta.read_bytes() if anterior is not None else b""
        existentes = {linea.split(b" ", 1)[0] for linea in datos.splitlines()}
        lineas = [f"{p.as_uri()} {titulo}".encode() for p, titulo in _lugares(self.ctx.modo.id)
                  if p.as_uri().encode() not in existentes]
        if lineas:
            separador = b"\n" if datos and not datos.endswith(b"\n") else b""
            self._marcadores_nuevos = (ruta, datos + separador + b"\n".join(lineas) + b"\n")
            return {str(ruta): anterior}
        return {}

    def capturar(self, cfg: dict) -> dict:
        escritorio = sesion()
        self._marcadores_nuevos = None
        if escritorio == "KDE":
            self._plasma = Plasma(self, _lugares(self.ctx.modo.id))
            return {"escritorio": escritorio, **self._plasma.preparar(cfg)}
        self._plasma = None
        valores = self._capturar_xfce() if escritorio == "XFCE" else (
            self._capturar_gsettings(escritorio)
        )
        self._previo = {"escritorio": escritorio, "valores": valores,
                        "archivos": self._marcadores()}
        return self._previo

    def _fijar(self, escritorio: str, origen: str, clave: str, valor: str | None) -> None:
        if escritorio == "XFCE":
            cmd = ["xfconf-query", "-c", origen, "-p", clave, "-s", valor]
        elif valor is None:
            cmd = ["gsettings", "reset", origen, clave]
        else:
            cmd = ["gsettings", "set", origen, clave, valor]
        self.ej.run(cmd, timeout=2)

    def aplicar(self, cfg: dict) -> None:
        if not hasattr(self, "_plasma"):
            self.capturar(cfg)
        if self._plasma:
            self._plasma.aplicar()
            return
        escritorio = self._previo["escritorio"]
        if escritorio in {"CINNAMON", "MATE", "XFCE"}:
            self._aviso(f"{escritorio}: se ajustan las propiedades disponibles de los paneles "
                        "existentes. Los widgets y las decoraciones dependen del escritorio.")
        if escritorio == "GNOME" and self.ctx.modo.id in {"gaming", "netanyahu"}:
            dock = "org.gnome.shell.extensions.dash-to-dock"
            if self.ej.gsettings_get(dock, "dock-position") is None:
                self._aviso("el dock requiere Dash to Dock o Ubuntu Dock instalado.")
            extension = ("gnome-shell/extensions/"
                         "user-theme@gnome-shell-extensions.gcampax.github.com")
            if not any((raiz / extension).is_dir()
                       for raiz in (self.ctx.rutas.xdg_datos_raiz(), Path("/usr/share"))):
                self._aviso("el estilo de barra superior requiere la extensión Temas de usuario.")
        for origen, clave, anterior, nuevo in self._previo["valores"]:
            if anterior == nuevo:
                continue
            try:
                self._fijar(escritorio, origen, clave, nuevo)
            except ErrorEjecucion:
                self._aviso(f"no se pudo aplicar {origen} / {clave}.")
        if self._marcadores_nuevos:
            self.ej.escribir(*self._marcadores_nuevos)

    def restaurar(self, previo: dict) -> None:
        escritorio = previo["escritorio"]
        if escritorio == "KDE":
            Plasma(self, []).restaurar(previo)
            return
        errores = []
        for origen, clave, anterior, nuevo in reversed(previo["valores"]):
            if anterior != nuevo:
                try:
                    self._fijar(escritorio, origen, clave, anterior)
                except ErrorEjecucion:
                    errores.append(f"{origen}/{clave}")
        for ruta, original in previo["archivos"].items():
            restaurar_archivo(self.ej, Path(ruta), original)
        if errores:
            raise ErrorEjecucion("No se pudieron restaurar estos ajustes: " + ", ".join(errores))
