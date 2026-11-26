"""Capa escritorio: fondo, bloqueo, esquema, acento, temas GTK y de Shell generados, dock."""

from __future__ import annotations

from pathlib import Path

from ultron.capas import comun as C
from ultron.capas import estilos
from ultron.capas.base import Capa, registrar_capa
from ultron.nucleo import rutas
from ultron.ui.tema import cargar_tema

FONDO = "org.gnome.desktop.background"
BLOQUEO = "org.gnome.desktop.screensaver"
INTERFAZ = "org.gnome.desktop.interface"
DOCK = "org.gnome.shell.extensions.dash-to-dock"
USER_THEME = "/org/gnome/shell/extensions/user-theme/name"

CLAVES = [
    (FONDO, "picture-uri"), (FONDO, "picture-uri-dark"), (FONDO, "picture-options"),
    (FONDO, "primary-color"), (BLOQUEO, "picture-uri"), (BLOQUEO, "picture-options"),
    (INTERFAZ, "color-scheme"), (INTERFAZ, "gtk-theme"), (INTERFAZ, "accent-color"),
    (INTERFAZ, "font-name"), (INTERFAZ, "document-font-name"),
    (INTERFAZ, "monospace-font-name"), (INTERFAZ, "enable-animations"),
    (INTERFAZ, "clock-show-seconds"),
]
CLAVES_DOCK = ["dock-position", "dash-max-icon-size", "extend-height", "transparency-mode",
               "background-opacity", "custom-background-color", "background-color",
               "dock-fixed", "autohide", "intellihide"]
ACENTOS = {"blue", "teal", "green", "yellow", "orange", "red", "pink", "purple", "slate"}


def dir_tema(id_modo: str) -> Path:
    return rutas.xdg_datos_raiz() / "themes" / f"Ultron-{id_modo}"


def css_gtk4_usuario() -> Path:
    return rutas.xdg_config_raiz() / "gtk-4.0" / "gtk.css"


@registrar_capa
class CapaEscritorio(Capa):
    nombre = "escritorio"
    orden = 30
    descripcion = "Fondo, pantalla de bloqueo, temas de ventanas y de la barra, dock"

    def disponible(self) -> tuple[bool, str]:
        if not self.ej.existe("gsettings"):
            return False, "no hay gsettings (¿estás en GNOME?)"
        return True, ""

    def capturar(self, cfg: dict) -> dict:
        claves = list(CLAVES) + [(DOCK, k) for k in CLAVES_DOCK]
        gtk4 = css_gtk4_usuario()
        return {
            "claves": C.capturar_claves(self.ej, claves),
            "user_theme": C.dconf_leer(self.ej, USER_THEME),
            "gtk4_css": gtk4.read_text(encoding="utf-8") if gtk4.exists() else None,
        }

    # --- aplicar -------------------------------------------------------------
    def _fondo(self, relativa: str | None, nombre: str) -> Path:
        if relativa:
            ruta = self.ctx.recurso(relativa)
            if ruta.exists():
                return ruta
        destino = rutas.cache() / "fondos" / f"{self.ctx.modo.id}-{nombre}.png"
        if not destino.exists() and not self.ej.simular:
            p = cargar_tema(self.ctx.modo.id).paleta
            estilos.fondo_respaldo(p, destino, texto=f"ULTRON · {self.ctx.modo.nombre}")
        return destino

    def aplicar(self, cfg: dict) -> None:
        previo = self.capturar(cfg)["claves"]
        tema = cargar_tema(self.ctx.modo.id)
        p = tema.paleta
        oscuro = cfg.get("esquema", "oscuro") != "claro"
        fijar = lambda esq, k, v: C.fijar_si_existe(self.ej, previo, esq, k, v)  # noqa: E731

        fondo = self._fondo(cfg.get("fondo"), "fondo")
        fijar(FONDO, "picture-uri", C.gv_str(C.uri(fondo)))
        fijar(FONDO, "picture-uri-dark", C.gv_str(C.uri(fondo)))
        fijar(FONDO, "picture-options", C.gv_str(cfg.get("ajuste_fondo", "zoom")))
        fijar(FONDO, "primary-color", C.gv_str(p.get("fondo", "#000000")))
        bloqueo = self._fondo(cfg.get("fondo_bloqueo") or cfg.get("fondo"), "bloqueo")
        fijar(BLOQUEO, "picture-uri", C.gv_str(C.uri(bloqueo)))
        fijar(BLOQUEO, "picture-options", C.gv_str("zoom"))

        fijar(INTERFAZ, "color-scheme", C.gv_str("prefer-dark" if oscuro else "default"))
        acento = cfg.get("acento")
        if acento in ACENTOS:
            fijar(INTERFAZ, "accent-color", C.gv_str(acento))
        for clave_cfg, clave in (("fuente_ui", "font-name"), ("fuente_ui", "document-font-name"),
                                 ("fuente_mono", "monospace-font-name")):
            if cfg.get(clave_cfg):
                fijar(INTERFAZ, clave, C.gv_str(cfg[clave_cfg]))
        if "animaciones" in cfg:
            fijar(INTERFAZ, "enable-animations", C.gv_bool(cfg["animaciones"]))
        if "segundos" in cfg:
            fijar(INTERFAZ, "clock-show-seconds", C.gv_bool(cfg["segundos"]))

        nombre_tema = f"Ultron-{self.ctx.modo.id}"
        tema_gtk = cfg.get("tema_gtk", "generar")
        if tema_gtk == "generar":
            self._escribir_temas(p, oscuro, bool(cfg.get("brillo")))
            fijar(INTERFAZ, "gtk-theme", C.gv_str(nombre_tema))
            self.ej.escribir(css_gtk4_usuario(), estilos.css_gtk4(p, oscuro))
        elif tema_gtk:
            fijar(INTERFAZ, "gtk-theme", C.gv_str(tema_gtk))

        tema_shell = cfg.get("tema_shell", "generar")
        if tema_shell:
            nombre_shell = nombre_tema if tema_shell == "generar" else tema_shell
            C.dconf_escribir(self.ej, USER_THEME, C.gv_str(nombre_shell))

        for clave, valor in (cfg.get("dock") or {}).items():
            clave = clave.replace("_", "-")
            if isinstance(valor, bool):
                texto = C.gv_bool(valor)
            elif isinstance(valor, (int, float)):
                texto = str(valor)
            else:
                texto = C.gv_str(str(valor))
            fijar(DOCK, clave, texto)

    def _escribir_temas(self, p: dict, oscuro: bool, brillo: bool) -> None:
        d = dir_tema(self.ctx.modo.id)
        self.ej.escribir(d / "index.theme", estilos.index_theme(d.name))
        self.ej.escribir(d / "gtk-3.0" / "gtk.css", estilos.css_gtk3(p, oscuro))
        self.ej.escribir(d / "gtk-4.0" / "gtk.css", estilos.css_gtk4(p, oscuro))
        self.ej.escribir(d / "gnome-shell" / "gnome-shell.css",
                         estilos.css_shell(p, oscuro, brillo))

    # --- restaurar -------------------------------------------------------------
    def restaurar(self, previo: dict) -> None:
        C.restaurar_claves(self.ej, previo.get("claves", {}))
        C.dconf_restaurar(self.ej, USER_THEME, previo.get("user_theme"))
        if previo.get("gtk4_css") is not None:
            self.ej.escribir(css_gtk4_usuario(), previo["gtk4_css"])
        else:
            self.ej.borrar(css_gtk4_usuario())
