"""Capa extensiones: activa o desactiva extensiones de GNOME ya instaladas y las configura."""

from __future__ import annotations

from pathlib import Path

from ultron.capas import comun as C
from ultron.capas.base import Capa, registrar_capa
from ultron.nucleo import rutas

SHELL = "org.gnome.shell"
BMW = "burn-my-windows@schneegans.github.com"


def perfil_tv() -> Path:
    return rutas.xdg_config_raiz() / "burn-my-windows" / "profiles" / "ultron-netanyahu.conf"


def instalada(ej, uuid: str) -> bool:
    return ej.leer(["gnome-extensions", "info", uuid]).codigo == 0


@registrar_capa
class CapaExtensiones(Capa):
    nombre = "extensiones"
    orden = 40
    descripcion = "Animaciones y efectos: extensiones de GNOME del modo"

    def disponible(self) -> tuple[bool, str]:
        if not self.ej.existe("gnome-extensions"):
            return False, "no está gnome-extensions (sudo apt install gnome-shell-extensions)"
        return True, ""

    def capturar(self, cfg: dict) -> dict:
        ajustes = {ruta: C.dconf_leer(self.ej, ruta) for ruta in (cfg.get("ajustes") or {})}
        previo = {
            "claves": C.capturar_claves(self.ej, [(SHELL, "enabled-extensions"),
                                                  (SHELL, "disabled-extensions")]),
            "ajustes": ajustes,
        }
        if cfg.get("perfil_tv"):
            previo["crear_perfil_tv"] = not perfil_tv().exists()
        return previo

    def aplicar(self, cfg: dict) -> None:
        faltan = []
        for ruta, valor in (cfg.get("ajustes") or {}).items():
            C.dconf_escribir(self.ej, ruta, str(valor))
        if cfg.get("perfil_tv") and (self.ej.simular or instalada(self.ej, BMW)):
            if not perfil_tv().exists():
                self.ej.escribir(perfil_tv(), (
                    "[burn-my-windows-profile]\n"
                    "profile-high-priority=true\n"
                    "fire-enable-effect=false\n"
                    "tv-glitch-enable-effect=true\n"
                    "tv-glitch-color='rgb(56, 120, 255)'\n"
                ))
        for uuid in cfg.get("desactivar") or []:
            if instalada(self.ej, uuid):
                self.ej.run(["gnome-extensions", "disable", uuid], check=False)
        for uuid in cfg.get("activar") or []:
            if self.ej.simular or instalada(self.ej, uuid):
                self.ej.run(["gnome-extensions", "enable", uuid], check=False)
            else:
                faltan.append(uuid)
        if faltan and self.ctx.consola is not None:
            self.ctx.consola.print(
                f"[aviso]  faltan {len(faltan)} extensiones: {', '.join(faltan)}. "
                f"Ejecuta: ultron instalar --modo {self.ctx.modo.id}[/]"
            )

    def restaurar(self, previo: dict) -> None:
        if previo.get("crear_perfil_tv") and (perfil_tv().exists() or self.ej.simular):
            self.ej.borrar(perfil_tv())
        for ruta, valor in (previo.get("ajustes") or {}).items():
            C.dconf_restaurar(self.ej, ruta, valor)
        C.restaurar_claves(self.ej, previo.get("claves", {}))
