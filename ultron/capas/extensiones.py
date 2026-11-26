"""Capa extensiones: activa o desactiva extensiones de GNOME ya instaladas y las configura."""

from __future__ import annotations

from pathlib import Path

from ultron.capas import comun as C
from ultron.capas.base import Capa, registrar_capa
from ultron.nucleo import rutas

SHELL = "org.gnome.shell"
BMW = "burn-my-windows@schneegans.github.com"
HANABI = "hanabi-extension@jeffshee.github.io"
RUTA_VIDEO = "/io/github/jeffshee/hanabi-extension/video-path"


def perfil_neon() -> Path:
    return rutas.xdg_config_raiz() / "burn-my-windows/profiles/ultron-gaming.conf"


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
        if cfg.get("perfil_neon"):
            previo["crear_perfil_neon"] = not perfil_neon().exists()
        if cfg.get("video") and self.ej.existe("dconf"):
            ajustes[RUTA_VIDEO] = C.dconf_leer(self.ej, RUTA_VIDEO)
        return previo

    def aplicar(self, cfg: dict) -> None:
        faltan = []
        for ruta, valor in (cfg.get("ajustes") or {}).items():
            texto = C.gv_bool(valor) if isinstance(valor, bool) else str(valor)
            C.dconf_escribir(self.ej, ruta, texto)
        if cfg.get("perfil_tv") and (self.ej.simular or instalada(self.ej, BMW)):
            if not perfil_tv().exists():
                self.ej.escribir(perfil_tv(), (
                    "[burn-my-windows-profile]\n"
                    "profile-high-priority=true\n"
                    "fire-enable-effect=false\n"
                    "tv-glitch-enable-effect=true\n"
                    "tv-glitch-color='rgb(56, 120, 255)'\n"
                ))
        if cfg.get("perfil_neon") and not perfil_neon().exists():
            if self.ej.simular or instalada(self.ej, BMW):
                self.ej.escribir(perfil_neon(), (
                    "[burn-my-windows-profile]\nprofile-high-priority=true\n"
                    "fire-enable-effect=false\n"
                    "glitch-enable-effect=true\nglitch-color='rgb(0, 240, 255)'\n"
                    "tv-enable-effect=true\ntv-effect-color='rgb(255, 0, 230)'\n"
                    "energize-a-enable-effect=true\npixelate-enable-effect=true\n"
                ))
        if cfg.get("video") and (self.ej.simular or instalada(self.ej, HANABI)):
            video = self.ctx.recurso(cfg["video"])
            if video.is_file() and self.ej.existe("dconf"):
                C.dconf_escribir(self.ej, RUTA_VIDEO, C.gv_str(str(video.resolve())))
                self.ej.run(["gnome-extensions", "enable", HANABI], check=False)
            else:
                self.ej.run(["gnome-extensions", "disable", HANABI], check=False)
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
        if previo.get("crear_perfil_neon"):
            self.ej.borrar(perfil_neon())
        for ruta, valor in (previo.get("ajustes") or {}).items():
            C.dconf_restaurar(self.ej, ruta, valor)
        C.restaurar_claves(self.ej, previo.get("claves", {}))
