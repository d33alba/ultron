"""Capa plasma: en KDE Plasma (no GNOME) cambia fondo, pantalla de bloqueo y colores.

Se añade sola a cualquier modo que tenga capa `escritorio` y usa su misma configuración.
Fuera de KDE no está disponible y se salta. Restaura exactamente lo que había.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from ultron.capas.base import Capa, registrar_capa
from ultron.nucleo import rutas

BLOQUEO = ["--file", "kscreenlockerrc", "--group", "Greeter", "--group", "Wallpaper",
           "--group", "org.kde.image", "--group", "General", "--key", "Image"]
COLORES = ["--file", "kdeglobals", "--group", "General", "--key", "ColorScheme"]


def es_kde() -> bool:
    return "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper()


def fondo_actual(appletsrc: Path | None = None) -> str | None:
    """Imagen del primer escritorio, leída de la configuración de Plasma."""
    appletsrc = appletsrc or rutas.xdg_config_raiz() / "plasma-org.kde.plasma.desktop-appletsrc"
    try:
        texto = appletsrc.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    grupo = ""
    for linea in texto.splitlines():
        if linea.startswith("["):
            grupo = linea
        elif linea.startswith("Image=") and "[Wallpaper][org.kde.image][General]" in grupo \
                and grupo.startswith("[Containments]"):
            valor = linea[len("Image="):].strip()
            return valor.removeprefix("file://") or None
    return None


def esquema_actual(salida: str) -> str | None:
    for linea in salida.splitlines():
        if "(current color scheme)" in linea:
            return re.sub(r"^\s*\*?\s*|\s*\(current color scheme\)\s*$", "", linea) or None
    return None


@registrar_capa
class CapaPlasma(Capa):
    nombre = "plasma"
    orden = 21
    descripcion = "KDE Plasma: fondo, bloqueo y colores del modo"
    automatica = True
    cfg_de = "escritorio"

    def disponible(self) -> tuple[bool, str]:
        if not es_kde():
            return False, "no es KDE Plasma"
        if not self.ej.existe("plasma-apply-wallpaperimage") and not self.ej.simular:
            return False, "falta plasma-apply-wallpaperimage (Plasma 5.25 o posterior)"
        return True, ""

    def _leer(self, clave: list[str]) -> str | None:
        if not self.ej.existe("kreadconfig5"):
            return None
        r = self.ej.leer(["kreadconfig5", *clave])
        return r.salida.strip() or None if r.ok else None

    def _imagen(self, relativa: str | None) -> Path | None:
        if not relativa or str(relativa).startswith("#"):
            return None
        ruta = self.ctx.respaldo(relativa, self.ej)
        return ruta if ruta.is_file() else None

    def capturar(self, cfg: dict) -> dict:
        lista = self.ej.leer(["plasma-apply-colorscheme", "--list-schemes"])
        return {"fondo": fondo_actual(), "bloqueo": self._leer(BLOQUEO),
                "colores": esquema_actual(lista.salida) if lista.ok else self._leer(COLORES)}

    def aplicar(self, cfg: dict) -> None:
        if fondo := self._imagen(cfg.get("fondo")):
            self.ej.run(["plasma-apply-wallpaperimage", str(fondo)], check=False)
        bloqueo = self._imagen(cfg.get("fondo_bloqueo")) or self._imagen(cfg.get("fondo"))
        if bloqueo and self.ej.existe("kwriteconfig5"):
            self.ej.run(["kwriteconfig5", *BLOQUEO, bloqueo.as_uri()], check=False)
        if self.ej.existe("plasma-apply-colorscheme"):
            esquema = "BreezeLight" if cfg.get("esquema") == "claro" else "BreezeDark"
            self.ej.run(["plasma-apply-colorscheme", esquema], check=False)

    def restaurar(self, previo: dict) -> None:
        if previo.get("fondo"):
            self.ej.run(["plasma-apply-wallpaperimage", previo["fondo"]], check=False)
        elif self.ej.existe("qdbus"):
            # no había imagen propia: se vuelve al fondo por defecto de Plasma
            guion = ("var ds=desktops();for(var i=0;i<ds.length;i++){var d=ds[i];"
                     "d.wallpaperPlugin='org.kde.image';"
                     "d.currentConfigGroup=['Wallpaper','org.kde.image','General'];"
                     "d.deleteConfig('Image');}")
            self.ej.run(["qdbus", "org.kde.plasmashell", "/PlasmaShell",
                         "org.kde.PlasmaShell.evaluateScript", guion], check=False)
        if self.ej.existe("kwriteconfig5"):
            if previo.get("bloqueo"):
                self.ej.run(["kwriteconfig5", *BLOQUEO, previo["bloqueo"]], check=False)
            else:
                self.ej.run(["kwriteconfig5", *BLOQUEO[:-1], "--delete", "Image"], check=False)
        if self.ej.existe("plasma-apply-colorscheme"):
            self.ej.run(["plasma-apply-colorscheme", previo.get("colores") or "BreezeClassic"],
                        check=False)
