"""Capa terminal: perfil propio en GNOME Terminal (y Ptyxis en Ubuntu 25.04+)."""

from __future__ import annotations

from ultron.capas import comun as C
from ultron.capas.base import Capa, registrar_capa
from ultron.ui.tema import cargar_tema

BASE_GT = "/org/gnome/terminal/legacy/profiles:/"
BASE_PTYXIS = "/org/gnome/Ptyxis/"


def _ajustes(cfg: dict, id_modo: str) -> dict:
    tema = cargar_tema(id_modo)
    p = tema.paleta
    return {
        "paleta": cfg.get("paleta") or C.paleta_terminal(p),
        "fondo": cfg.get("fondo") or p.get("fondo", "#101010"),
        "texto": cfg.get("texto") or p.get("texto", "#dddddd"),
        "cursor_color": cfg.get("cursor_color") or p.get("primario", "#ffffff"),
        "fuente": cfg.get("fuente", "JetBrains Mono 12"),
        "transparencia": int(cfg.get("transparencia", 0)),
        "cursor": cfg.get("cursor", "block"),
    }


@registrar_capa
class CapaTerminal(Capa):
    nombre = "terminal"
    orden = 20
    descripcion = "Perfil de colores, fuente y transparencia de la terminal"

    def disponible(self) -> tuple[bool, str]:
        if not self.ej.existe("dconf"):
            return False, "no está dconf (sudo apt install dconf-cli)"
        return True, ""

    @property
    def uuid(self) -> str:
        return C.uuid_modo(self.ctx.modo.id)

    def capturar(self, cfg: dict) -> dict:
        return {
            "gt_default": C.dconf_leer(self.ej, BASE_GT + "default"),
            "gt_list": C.dconf_leer(self.ej, BASE_GT + "list"),
            "px_default": C.dconf_leer(self.ej, BASE_PTYXIS + "default-profile-uuid"),
            "px_list": C.dconf_leer(self.ej, BASE_PTYXIS + "profile-uuids"),
            "uuid": self.uuid,
        }

    def aplicar(self, cfg: dict) -> None:
        a = _ajustes(cfg, self.ctx.modo.id)
        nombre = f"Ultron-{self.ctx.modo.id}"
        if self.ej.existe("gnome-terminal") or not self.ej.existe("ptyxis"):
            self._gnome_terminal(a, nombre)
        if self.ej.existe("ptyxis"):
            self._ptyxis(a, nombre)

    def _gnome_terminal(self, a: dict, nombre: str) -> None:
        perfil = f"{BASE_GT}:{self.uuid}/"
        claves = {
            "visible-name": C.gv_str(nombre),
            "palette": C.gv_lista(a["paleta"]),
            "background-color": C.gv_str(a["fondo"]),
            "foreground-color": C.gv_str(a["texto"]),
            "cursor-colors-set": "true",
            "cursor-background-color": C.gv_str(a["cursor_color"]),
            "cursor-foreground-color": C.gv_str(a["fondo"]),
            "use-theme-colors": "false",
            "use-system-font": "false",
            "font": C.gv_str(a["fuente"]),
            "cursor-shape": C.gv_str(a["cursor"]),
            "use-transparent-background": C.gv_bool(a["transparencia"] > 0),
            "background-transparency-percent": str(a["transparencia"]),
            "bold-is-bright": "true",
            "audible-bell": "false",
        }
        for clave, valor in claves.items():
            C.dconf_escribir(self.ej, perfil + clave, valor)
        lista = C.leer_lista(C.dconf_leer(self.ej, BASE_GT + "list"))
        if self.uuid not in lista:
            lista.append(self.uuid)
        C.dconf_escribir(self.ej, BASE_GT + "list", C.gv_lista(lista))
        C.dconf_escribir(self.ej, BASE_GT + "default", C.gv_str(self.uuid))

    def _ptyxis(self, a: dict, nombre: str) -> None:
        from ultron.nucleo import rutas

        ident = f"ultron-{self.ctx.modo.id}"
        colores = "\n".join(f"Color{i}={c}" for i, c in enumerate(a["paleta"]))
        contenido = (
            f"[Palette]\nName={nombre}\n\n[Dark]\nBackground={a['fondo']}\n"
            f"Foreground={a['texto']}\nCursor={a['cursor_color']}\n{colores}\n\n"
            f"[Light]\nBackground={a['fondo']}\nForeground={a['texto']}\n{colores}\n"
        )
        destino = rutas.xdg_datos_raiz() / "org.gnome.Ptyxis" / "palettes" / f"{ident}.palette"
        self.ej.escribir(destino, contenido)
        perfil = f"{BASE_PTYXIS}Profiles/{self.uuid}/"
        C.dconf_escribir(self.ej, perfil + "label", C.gv_str(nombre))
        C.dconf_escribir(self.ej, perfil + "palette", C.gv_str(ident))
        opacidad = max(0.0, 1 - a["transparencia"] / 100)
        C.dconf_escribir(self.ej, perfil + "opacity", f"{opacidad:.2f}")
        lista = C.leer_lista(C.dconf_leer(self.ej, BASE_PTYXIS + "profile-uuids"))
        if self.uuid not in lista:
            lista.append(self.uuid)
        C.dconf_escribir(self.ej, BASE_PTYXIS + "profile-uuids", C.gv_lista(lista))
        C.dconf_escribir(self.ej, BASE_PTYXIS + "default-profile-uuid", C.gv_str(self.uuid))
        C.dconf_escribir(self.ej, BASE_PTYXIS + "font-name", C.gv_str(a["fuente"]))
        C.dconf_escribir(self.ej, BASE_PTYXIS + "use-system-font", "false")

    def restaurar(self, previo: dict) -> None:
        uuid = previo.get("uuid") or self.uuid
        C.dconf_restaurar(self.ej, BASE_GT + "default", previo.get("gt_default"))
        C.dconf_restaurar(self.ej, BASE_GT + "list", previo.get("gt_list"))
        self.ej.run(["dconf", "reset", "-f", f"{BASE_GT}:{uuid}/"], check=False)
        if self.ej.existe("ptyxis"):
            C.dconf_restaurar(self.ej, BASE_PTYXIS + "default-profile-uuid",
                              previo.get("px_default"))
            C.dconf_restaurar(self.ej, BASE_PTYXIS + "profile-uuids", previo.get("px_list"))
            self.ej.run(["dconf", "reset", "-f", f"{BASE_PTYXIS}Profiles/{uuid}/"], check=False)
