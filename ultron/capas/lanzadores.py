"""Capa lanzadores: las funciones del modo, visibles fuera de la terminal.

- Un icono por función en el menú de aplicaciones (y el NEXUS a pantalla completa).
- Las funciones principales en el escritorio y fijadas en el dock.
- Arrastrar un archivo sobre un lanzador lo procesa (p. ej. un PDF sobre «Resumir apuntes»).
- Clic derecho en Archivos → Scripts → Ultron → la función, con el archivo seleccionado.
Todo lo que crea lleva el prefijo `ultron-` y se borra al salir; los favoritos del dock vuelven
exactamente como estaban.
"""

from __future__ import annotations

import shlex
import shutil
from pathlib import Path

from ultron.capas import comun as C
from ultron.capas.base import Capa, registrar_capa
from ultron.nucleo import rutas
from ultron.ui.nexus import catalogo
from ultron.ui.tema import cargar_tema

SHELL = "org.gnome.shell"
FUENTES_GLIFO = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansSymbols2-Regular.ttf",
    "C:/Windows/Fonts/seguisym.ttf",
]


def dir_aplicaciones() -> Path:
    return rutas.xdg_datos_raiz() / "applications"


def dir_scripts() -> Path:
    return rutas.xdg_datos_raiz() / "nautilus" / "scripts" / "Ultron"


def dir_iconos(id_modo: str) -> Path:
    return rutas.datos() / "lanzadores" / id_modo


def dir_escritorio(ej) -> Path:
    if ej.existe("xdg-user-dir"):
        r = ej.leer(["xdg-user-dir", "DESKTOP"])
        if r.codigo == 0 and r.salida.strip():
            return Path(r.salida.strip())
    for nombre in ("Escritorio", "Desktop"):
        if (Path.home() / nombre).is_dir():
            return Path.home() / nombre
    return Path.home() / "Escritorio"


def ultron_bin() -> str:
    return shutil.which("ultron") or "ultron"


def terminal(titulo: str, pantalla_completa: bool = False) -> list[str]:
    """Orden para abrir una terminal con título (gnome-terminal, ptyxis o kgx)."""
    if shutil.which("gnome-terminal"):
        base = ["gnome-terminal", f"--title={titulo}"]
        return base + (["--full-screen"] if pantalla_completa else []) + ["--"]
    if shutil.which("ptyxis"):
        return ["ptyxis", "--title", titulo, "--"]
    if shutil.which("kgx"):
        return ["kgx", "--title", titulo, "-e"]
    return ["x-terminal-emulator", "-e"]


def linea_exec(argv: list[str], *, soltar: bool = False) -> str:
    texto = " ".join(shlex.quote(a) for a in argv)
    return texto + (" %F" if soltar else "")


def escritorio_entry(nombre: str, comentario: str, icono: Path, exec_: str,
                     soltar: bool = False) -> str:
    lineas = ["[Desktop Entry]", "Type=Application", f"Name={nombre}", f"Comment={comentario}",
              f"Icon={icono}", f"Exec={exec_}", "Terminal=false", "Categories=Utility;",
              "StartupNotify=true", "X-Ultron=true"]
    if soltar:
        lineas.append("MimeType=application/pdf;text/plain;text/markdown;image/jpeg;image/png;"
                      "inode/directory;application/octet-stream;")
    return "\n".join(lineas) + "\n"


def dibujar_icono(destino: Path, glifo: str, p: dict[str, str], tamano: int = 256) -> None:
    """Icono propio: losa redondeada con degradado del modo y el glifo en el centro."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    fondo, prim = p.get("fondo", "#101418"), p.get("primario", "#00D7FF")
    acento = p.get("acento", prim)
    img = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    capa = Image.new("RGBA", (tamano, tamano))
    d = ImageDraw.Draw(capa)
    for y in range(tamano):
        tono = C.mezclar(fondo, prim, 0.15 + y / tamano * 0.35)
        d.line([(0, y), (tamano, y)], fill=C.hex_a_rgb(tono))
    mascara = Image.new("L", (tamano, tamano), 0)
    m = int(tamano * 0.06)
    ImageDraw.Draw(mascara).rounded_rectangle([m, m, tamano - m, tamano - m],
                                              radius=int(tamano * 0.22), fill=255)
    img.paste(capa, (0, 0), mascara)
    borde = ImageDraw.Draw(img)
    borde.rounded_rectangle([m, m, tamano - m, tamano - m], radius=int(tamano * 0.22),
                            outline=C.hex_a_rgb(acento) + (255,), width=max(2, tamano // 48))
    fuente = None
    for ruta in FUENTES_GLIFO:
        if Path(ruta).exists():
            try:
                fuente = ImageFont.truetype(ruta, int(tamano * 0.5))
                break
            except OSError:
                continue
    if fuente is None:
        fuente = ImageFont.load_default()
    brillo = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    ImageDraw.Draw(brillo).text((tamano / 2, tamano / 2), glifo, font=fuente, anchor="mm",
                                fill=C.hex_a_rgb(prim) + (255,))
    img.alpha_composite(brillo.filter(ImageFilter.GaussianBlur(tamano // 24)))
    ImageDraw.Draw(img).text((tamano / 2, tamano / 2), glifo, font=fuente, anchor="mm",
                             fill=(255, 255, 255, 255))
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino)


@registrar_capa
class CapaLanzadores(Capa):
    nombre = "lanzadores"
    orden = 70
    descripcion = "Funciones del modo en el escritorio, el dock, el menú y Archivos"

    def disponible(self) -> tuple[bool, str]:
        return True, ""

    # --- qué se crea ----------------------------------------------------------
    def _fichas(self) -> list[catalogo.Ficha]:
        return catalogo.de_modo(self.ctx.modo.id)

    def _destacadas(self, cfg: dict) -> list[catalogo.Ficha]:
        maximo = int(cfg.get("maximo", 5))
        propias = [f for f in self._fichas() if f.escritorio][:maximo]
        comunes = [f for f in catalogo.comunes() if f.escritorio][:2]
        return propias + comunes

    def _plan(self, cfg: dict) -> dict[str, list[str]]:
        id_modo = self.ctx.modo.id
        apps = [dir_aplicaciones() / "ultron-nexus.desktop"]
        apps += [dir_aplicaciones() / f"ultron-{id_modo}-{f.id}.desktop"
                 for f in self._fichas() + catalogo.comunes()]
        escritorio: list[Path] = []
        if cfg.get("escritorio", True):
            base = dir_escritorio(self.ej)
            escritorio = [base / "ultron-nexus.desktop"]
            escritorio += [base / f"ultron-{id_modo}-{f.id}.desktop"
                           for f in self._destacadas(cfg)]
        scripts = []
        if cfg.get("archivos", True):
            scripts = [dir_scripts() / f.titulo for f in self._fichas() + catalogo.comunes()
                       if f.soltar]
        return {"apps": [str(r) for r in apps], "escritorio": [str(r) for r in escritorio],
                "scripts": [str(r) for r in scripts]}

    # --- capa -----------------------------------------------------------------
    def capturar(self, cfg: dict) -> dict:
        plan = self._plan(cfg)
        nuevos = [r for lista in plan.values() for r in lista if not Path(r).exists()]
        return {
            "claves": C.capturar_claves(self.ej, [(SHELL, "favorite-apps")]),
            "creados": nuevos,
            "dir_scripts": not dir_scripts().exists(),
            "iconos": str(dir_iconos(self.ctx.modo.id)),
        }

    def aplicar(self, cfg: dict) -> None:
        id_modo = self.ctx.modo.id
        p = cargar_tema(id_modo).paleta
        uu = ultron_bin()
        iconos = dir_iconos(id_modo)
        if not self.ej.simular:
            dibujar_icono(iconos / "nexus.png", cargar_tema(id_modo).glifo("marca") or "◆", p)
        nexus = escritorio_entry(
            "ULTRON NEXUS", "Centro de mando de Ultron", iconos / "nexus.png",
            linea_exec(terminal("ULTRON NEXUS", True) + [uu, "nexus"]))
        self.ej.escribir(dir_aplicaciones() / "ultron-nexus.desktop", nexus, modo=0o755)
        destacadas = {f.id for f in self._destacadas(cfg)}
        favoritos = ["ultron-nexus.desktop"]
        for f in self._fichas() + catalogo.comunes():
            icono = iconos / f"{f.id}.png"
            if not self.ej.simular:
                dibujar_icono(icono, f.icono, p)
            argv = terminal(f"ULTRON · {f.titulo}") + [uu, "lanzar", f.id]
            entrada = escritorio_entry(f.titulo, f.descripcion, icono,
                                       linea_exec(argv, soltar=bool(f.soltar)), bool(f.soltar))
            nombre = f"ultron-{id_modo}-{f.id}.desktop"
            self.ej.escribir(dir_aplicaciones() / nombre, entrada, modo=0o755)
            if f.id in destacadas and cfg.get("escritorio", True):
                destino = dir_escritorio(self.ej) / nombre
                self.ej.escribir(destino, entrada, modo=0o755)
                if self.ej.existe("gio"):
                    self.ej.run(["gio", "set", str(destino), "metadata::trusted", "true"],
                                check=False)
            if f.id in destacadas and f.modo == id_modo and len(favoritos) < 5:
                favoritos.append(nombre)
            if f.soltar and cfg.get("archivos", True):
                guion = ("#!/bin/sh\n# Ultron: script de Archivos (se borra al salir del modo)\n"
                         f"exec {linea_exec(argv)} \"$@\"\n")
                self.ej.escribir(dir_scripts() / f.titulo, guion, modo=0o755)
        if cfg.get("escritorio", True):
            destino = dir_escritorio(self.ej) / "ultron-nexus.desktop"
            self.ej.escribir(destino, nexus, modo=0o755)
            if self.ej.existe("gio"):
                self.ej.run(["gio", "set", str(destino), "metadata::trusted", "true"], check=False)
        if cfg.get("dock", True):
            actuales = C.leer_lista(self.ej.gsettings_get(SHELL, "favorite-apps"))
            if self.ej.gsettings_get(SHELL, "favorite-apps") is not None:
                resto = [a for a in actuales if not a.startswith("ultron-")]
                self.ej.gsettings_set(SHELL, "favorite-apps", C.gv_lista(favoritos + resto))
        if self.ej.existe("update-desktop-database"):
            self.ej.run(["update-desktop-database", str(dir_aplicaciones())], check=False)

    def restaurar(self, previo: dict) -> None:
        C.restaurar_claves(self.ej, previo.get("claves", {}))
        for ruta in previo.get("creados", []):
            if Path(ruta).exists() or self.ej.simular:
                self.ej.borrar(Path(ruta))
        if previo.get("dir_scripts") and dir_scripts().exists():
            try:
                dir_scripts().rmdir()
            except OSError:
                pass
