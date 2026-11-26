"""Capa iconos: tema de iconos completo del modo (apps, carpetas, archivos…)."""

from __future__ import annotations

import re
from pathlib import Path

from ultron.capas import comun as C
from ultron.capas import iconos_gen
from ultron.capas.base import Capa, registrar_capa
from ultron.nucleo import rutas
from ultron.ui.tema import cargar_tema

INTERFAZ = "org.gnome.desktop.interface"
FLATPAK_APPS = [Path("/var/lib/flatpak/exports/share/applications"),
                rutas.home() / ".local/share/flatpak/exports/share/applications"]


def dir_iconos(id_modo: str) -> Path:
    return rutas.xdg_datos_raiz() / "icons" / f"Ultron-{id_modo}"


@registrar_capa
class CapaIconos(Capa):
    nombre = "iconos"
    orden = 35
    descripcion = "Todos los iconos recoloreados: apps, carpetas, archivos y dispositivos"

    def disponible(self) -> tuple[bool, str]:
        if not self.ej.existe("gsettings"):
            return False, "no hay gsettings"
        base = iconos_gen.base_disponible()
        if base is None and not self.ej.simular:
            return False, "no encuentro el tema de iconos Yaru ni Adwaita"
        return True, ""

    def capturar(self, cfg: dict) -> dict:
        return {"claves": C.capturar_claves(self.ej, [(INTERFAZ, "icon-theme")]),
                "desktop": []}

    def aplicar(self, cfg: dict) -> None:
        destino = dir_iconos(self.ctx.modo.id)
        if not self.ej.simular:
            emblema = self.ctx.respaldo(cfg["emblema"], self.ej) if cfg.get("emblema") else None
            aj = iconos_gen.ajustes_desde_cfg(cfg, cargar_tema(self.ctx.modo.id).paleta, emblema)
            propios = self.ctx.recurso(cfg.get("personalizados", "tema/iconos"))
            base = Path(cfg["base"]) if cfg.get("base") else None
            iconos_gen.generar(self.ctx.modo.id, aj, destino, base=base,
                               dir_personalizados=propios)
        else:
            self.ej.historial.append(["#generar-iconos", str(destino)])
        if self.ej.existe("gtk-update-icon-cache"):
            self.ej.run(["gtk-update-icon-cache", "-f", "-t", "-q", str(destino)], check=False)
        previo = C.capturar_claves(self.ej, [(INTERFAZ, "icon-theme")])
        C.fijar_si_existe(self.ej, previo, INTERFAZ, "icon-theme", C.gv_str(destino.name))
        self._overrides_flatpak(cfg)

    def _overrides_flatpak(self, cfg: dict) -> None:
        """Las apps Flatpak traen su icono: se crea un .desktop propio que apunta al nuestro."""
        propios = self.ctx.recurso(cfg.get("personalizados", "tema/iconos"))
        if not propios.is_dir():
            return
        creados = []
        destino_apps = rutas.xdg_datos_raiz() / "applications"
        for icono in propios.iterdir():
            for carpeta in FLATPAK_APPS:
                original = carpeta / f"{icono.stem}.desktop"
                if not original.exists():
                    continue
                texto = original.read_text(encoding="utf-8", errors="ignore")
                texto = re.sub(r"(?m)^Icon=.*$", f"Icon={icono.stem}", texto)
                destino = destino_apps / f"{icono.stem}.desktop"
                if destino.exists():
                    continue
                self.ej.escribir(destino, texto + "\nX-Ultron=1\n")
                creados.append(str(destino))
        if creados:
            from ultron.nucleo import estado

            estado.actualizar(iconos_desktop=creados)

    def restaurar(self, previo: dict) -> None:
        C.restaurar_claves(self.ej, previo.get("claves", {}))
        from ultron.nucleo import estado

        for ruta in estado.obtener("iconos_desktop", []) or []:
            self.ej.borrar(Path(ruta))
        if not self.ej.simular:
            estado.actualizar(iconos_desktop=None)
