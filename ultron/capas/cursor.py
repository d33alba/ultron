"""Capas cursor y fuentes."""

from __future__ import annotations

import shutil
from pathlib import Path

from ultron.capas import comun as C
from ultron.capas import iconos_gen, xcursor
from ultron.capas.base import Capa, registrar_capa
from ultron.nucleo import rutas
from ultron.ui.tema import cargar_tema

INTERFAZ = "org.gnome.desktop.interface"
BASES_CURSOR = [Path("/usr/share/icons/Yaru"), Path("/usr/share/icons/DMZ-White"),
                Path("/usr/share/icons/Adwaita")]


def generar_cursor(base: Path, destino: Path, aj: iconos_gen.Ajustes) -> int:
    """Copia el tema de cursores de `base` recoloreando cada imagen."""
    origen = base / "cursors"
    if destino.exists():
        shutil.rmtree(destino)
    (destino / "cursors").mkdir(parents=True)
    n = 0
    for f in origen.iterdir():
        objetivo = destino / "cursors" / f.name
        if f.is_symlink():
            try:
                objetivo.symlink_to(f.readlink())
            except OSError:
                shutil.copy2(f.resolve(), objetivo)
            continue
        datos = f.read_bytes()
        if not xcursor.es_xcursor(datos):
            continue
        objetivo.write_bytes(xcursor.recolorear(
            datos, lambda img: iconos_gen.recolorear_imagen(img, aj, aj.objetivo)))
        n += 1
    (destino / "index.theme").write_text(
        f"[Icon Theme]\nName={destino.name}\nComment=Cursor de Ultron\nInherits={base.name}\n",
        encoding="utf-8",
    )
    return n


@registrar_capa
class CapaCursor(Capa):
    nombre = "cursor"
    orden = 36
    descripcion = "Tema y tamaño del cursor"

    def disponible(self) -> tuple[bool, str]:
        return (True, "") if self.ej.existe("gsettings") else (False, "no hay gsettings")

    def capturar(self, cfg: dict) -> dict:
        return {"claves": C.capturar_claves(
            self.ej, [(INTERFAZ, "cursor-theme"), (INTERFAZ, "cursor-size")])}

    def aplicar(self, cfg: dict) -> None:
        previo = C.capturar_claves(self.ej, [(INTERFAZ, "cursor-theme"),
                                             (INTERFAZ, "cursor-size")])
        nombre = cfg.get("tema")
        if cfg.get("generar"):
            destino = rutas.xdg_datos_raiz() / "icons" / f"Ultron-cursor-{self.ctx.modo.id}"
            base = next((b for b in BASES_CURSOR if (b / "cursors").is_dir()), None)
            if base is not None and not self.ej.simular:
                p = cargar_tema(self.ctx.modo.id).paleta
                aj = iconos_gen.Ajustes(
                    objetivo=cfg.get("color") or p.get("bandera") or p.get("primario", "#ffffff"),
                    intensidad=0.9, umbral=0.0, monocromo=bool(cfg.get("monocromo")),
                )
                generar_cursor(base, destino, aj)
                nombre = destino.name
            elif base is not None:
                nombre = destino.name
            else:
                nombre = cfg.get("respaldo") or nombre
        if nombre:
            C.fijar_si_existe(self.ej, previo, INTERFAZ, "cursor-theme", C.gv_str(nombre))
        if cfg.get("tamano"):
            C.fijar_si_existe(self.ej, previo, INTERFAZ, "cursor-size", str(int(cfg["tamano"])))

    def restaurar(self, previo: dict) -> None:
        C.restaurar_claves(self.ej, previo.get("claves", {}))


@registrar_capa
class CapaFuentes(Capa):
    nombre = "fuentes"
    orden = 10
    descripcion = "Fuentes del modo (Orbitron, JetBrains Mono…)"

    def _destino(self) -> Path:
        return rutas.xdg_datos_raiz() / "fonts" / "ultron" / self.ctx.modo.id

    def capturar(self, cfg: dict) -> dict:
        return {"existia": self._destino().exists()}

    def aplicar(self, cfg: dict) -> None:
        origen = self.ctx.recurso(cfg.get("carpeta", "tema/fuentes"))
        copiadas = 0
        if origen.is_dir():
            for f in origen.iterdir():
                if f.suffix.lower() in (".ttf", ".otf"):
                    self.ej.copiar(f, self._destino() / f.name)
                    copiadas += 1
        if copiadas and self.ej.existe("fc-cache"):
            # solo esta carpeta y en segundo plano: «fc-cache -f» de todo el sistema puede
            # tardar minutos (PC del centro) y nunca debe frenar ni cancelar el modo
            self.ej.run(["fc-cache", str(self._destino())], check=False, fondo=True)

    def restaurar(self, previo: dict) -> None:
        if not previo.get("existia"):
            self.ej.borrar(self._destino())
