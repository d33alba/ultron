"""Herramientas del sistema sin sudo: paquetes .deb del USB desempaquetados en el usuario.

En el PC del centro no hay administrador ni internet. `scripts/preparar_herramientas.py`
deja en el USB los .deb que faltan (con sus dependencias) y aquí se desempaquetan con
`dpkg-deb -x` en ~/.local/share/ultron/sistema. Cada programa recibe un lanzador en
~/.local/share/ultron/sistema/bin (y en ~/.local/bin) que prepara las rutas de sus
bibliotecas, de modo que `nmap`, `exiftool`, `tesseract`… funcionan como si estuvieran
instalados con apt.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from ultron.nucleo import rutas
from ultron.nucleo.ejecutor import Ejecutor

# no se empaquetan, con el motivo que se enseña si faltan
SOLO_GNOME = {"gnome-shell-extensions", "gnome-shell-extension-manager", "gnome-tweaks",
              "xdg-desktop-portal-gnome"}
MOTIVO = {
    "plymouth-themes": "la pantalla de arranque solo la cambia un administrador",
    "gamemode": "su servicio del sistema solo lo instala un administrador",
    "wf-recorder": "solo graba en Wayland (se usa ffmpeg en su lugar)",
} | {p: "solo sirve en GNOME" for p in SOLO_GNOME}
NO_EMPAQUETAR = set(MOTIVO) | {"nodejs", "npm"}  # Node 24 va en datos-linux.tar.gz
# programas que apt crea con update-alternatives (en el .deb tienen otro nombre)
ALIAS = {"traceroute": "traceroute.db", "traceroute6": "traceroute6.db"}
# rutas fijadas dentro de scripts y archivos de datos que hay que apuntar a lo desempaquetado
PARCHES = {
    "usr/bin/torsocks": [(r"(?m)^libdir=.*$", 'libdir="{P}/usr/lib/x86_64-linux-gnu"')],
}
# paquetes que cuentan como presentes si ya existe su programa (aunque no sean de apt)
PROGRAMA = {"nodejs": "node", "npm": "npm", "yt-dlp": "yt-dlp", "curl": "curl", "git": "git"}

LANZADOR = """#!/bin/sh
# Lanzador de Ultron: {nombre} desempaquetado sin sudo desde el USB
P="{prefijo}"
export LD_LIBRARY_PATH="$P/usr/lib/x86_64-linux-gnu:$P/lib/x86_64-linux-gnu:$P/usr/lib\
${{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}}"
export PERL5LIB="$P/usr/share/perl5:$P/usr/lib/x86_64-linux-gnu/perl5/5.34:\
$P/usr/share/perl/5.34:$P/usr/lib/x86_64-linux-gnu/perl/5.34${{PERL5LIB:+:$PERL5LIB}}"
export PYTHONPATH="$P/usr/lib/python3/dist-packages${{PYTHONPATH:+:$PYTHONPATH}}"
export RUBYLIB="$P/usr/lib/ruby/vendor_ruby:$P/usr/lib/ruby/3.0.0:\
$P/usr/lib/x86_64-linux-gnu/ruby/3.0.0${{RUBYLIB:+:$RUBYLIB}}"
export GEM_PATH="$P/usr/share/rubygems-integration/all:$P/usr/share/rubygems-integration/3.0.0:\
$P/usr/lib/x86_64-linux-gnu/rubygems-integration/3.0.0${{GEM_PATH:+:$GEM_PATH}}"
export GI_TYPELIB_PATH="$P/usr/lib/x86_64-linux-gnu/girepository-1.0\
${{GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}}"
export XDG_DATA_DIRS="${{XDG_DATA_DIRS:-/usr/local/share:/usr/share}}:$P/usr/share"
export GST_PLUGIN_PATH="$P/usr/lib/x86_64-linux-gnu/gstreamer-1.0\
${{GST_PLUGIN_PATH:+:$GST_PLUGIN_PATH}}"
[ -d "$P/usr/share/nmap" ] && export NMAPDIR="${{NMAPDIR:-$P/usr/share/nmap}}"
[ -d "$P/usr/share/tesseract-ocr/4.00/tessdata" ] && \
export TESSDATA_PREFIX="${{TESSDATA_PREFIX:-$P/usr/share/tesseract-ocr/4.00/tessdata}}"
[ -d "$P/usr/share/pandoc/data" ] && export pandoc_datadir="$P/usr/share/pandoc"
[ -d "$P/usr/lib/x86_64-linux-gnu/espeak-ng-data" ] && \
export ESPEAK_DATA_PATH="${{ESPEAK_DATA_PATH:-$P/usr/lib/x86_64-linux-gnu}}"
export PATH="$P/bin:$PATH"
exec {orden} "$@"
"""


def prefijo() -> Path:
    return rutas.datos() / "sistema"


def dir_bin() -> Path:
    return prefijo() / "bin"


def activar_path() -> None:
    """Pone los lanzadores en el PATH de este proceso (y de lo que lance)."""
    carpeta = str(dir_bin())
    partes = os.environ.get("PATH", "").split(os.pathsep)
    if carpeta not in partes and Path(carpeta).is_dir():
        os.environ["PATH"] = os.pathsep.join([carpeta, *partes])


def empaquetables(modos: list[str] | None = None) -> list[str]:
    from ultron.nucleo import dependencias

    return [p for p in dependencias.plan(modos).apt if p not in NO_EMPAQUETAR]


def registro_local() -> dict[str, list[str]]:
    try:
        return json.loads((prefijo() / "instalados.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def presente(ej: Ejecutor, paquete: str) -> bool:
    """¿El paquete está (apt, desempaquetado por Ultron o su programa ya existe)?"""
    from ultron.nucleo import dependencias

    if paquete in registro_local():
        return True
    if paquete in PROGRAMA and ej.existe(PROGRAMA[paquete]):
        return True
    if paquete in {"nodejs", "npm"} and (rutas.datos() / "node" / "bin" / "node").is_file():
        return True  # Node 24 portátil del Ojo de Dios
    return ej.existe("dpkg-query") and dependencias.apt_instalado(ej, paquete)


def faltan(ej: Ejecutor, paquetes: list[str]) -> list[str]:
    return [p for p in paquetes if not presente(ej, p)]


def lista_usb(offline: Path | None) -> dict[str, list[str]]:
    if offline is None:
        return {}
    try:
        return json.loads((offline / "debs" / "lista.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def instalar_desde_usb(ej: Ejecutor, offline: Path, paquetes: list[str]) -> tuple[list, list]:
    """Desempaqueta los .deb de cada paquete. Devuelve (instalados, sin_paquete_en_usb)."""
    lista = lista_usb(offline)
    hechos, sin = [], []
    registro = registro_local()
    ya = {deb for debs in registro.values() for deb in debs}
    for paquete in paquetes:
        debs = lista.get(paquete)
        if debs is None:
            sin.append(paquete)
            continue
        for deb in debs:
            if deb not in ya:
                ej.run(["dpkg-deb", "-x", str(offline / "debs" / deb), str(prefijo())],
                       timeout=300)
                ya.add(deb)
        registro[paquete] = debs
        hechos.append(paquete)
    if hechos and not ej.simular:
        rutas.asegurar(prefijo())
        (prefijo() / "instalados.json").write_text(json.dumps(registro, indent=1),
                                                    encoding="utf-8")
        crear_lanzadores(ej)
        _fuentes(ej)
    return hechos, sin


def crear_lanzadores(ej: Ejecutor) -> list[str]:
    """Un lanzador por programa de usr/bin y usr/sbin, también en ~/.local/bin."""
    p = prefijo()
    rutas.asegurar(dir_bin())
    local_bin = rutas.asegurar(rutas.home() / ".local" / "bin")
    nombres = []
    for carpeta in (p / "usr" / "bin", p / "usr" / "sbin", p / "usr" / "games"):
        if not carpeta.is_dir():
            continue
        for programa in sorted(carpeta.iterdir()):
            if programa.is_dir() or not os.access(programa, os.X_OK) and not programa.is_symlink():
                continue
            _recolocar(programa)
            lanzador = dir_bin() / programa.name
            lanzador.write_text(LANZADOR.format(nombre=programa.name, prefijo=p,
                                                orden=_orden(programa)), encoding="utf-8")
            lanzador.chmod(0o755)
            enlace = local_bin / programa.name
            if not enlace.exists() or enlace.is_symlink():
                enlace.unlink(missing_ok=True)
                enlace.symlink_to(lanzador)
            nombres.append(programa.name)
    for alias, real in ALIAS.items():
        for carpeta in ("bin", "sbin"):
            if (dir_bin() / real).exists() and (p / "usr" / carpeta / real).exists():
                (dir_bin() / alias).write_text(
                    (dir_bin() / real).read_text(encoding="utf-8"), encoding="utf-8")
                (dir_bin() / alias).chmod(0o755)
                enlace = local_bin / alias
                if not enlace.exists() or enlace.is_symlink():
                    enlace.unlink(missing_ok=True)
                    enlace.symlink_to(dir_bin() / alias)
                nombres.append(alias)
    for capa in (p / "usr" / "share" / "vulkan" / "implicit_layer.d").glob("*.json"):
        _recolocar(capa)  # MangoHud: "library_path": "/usr/$LIB/mangohud/…"
    _john()
    return nombres


def _john() -> None:
    """john busca john.conf en /usr/share/john o en ~/.john: se deja en ~/.john apuntando aquí."""
    origen = prefijo() / "etc" / "john" / "john.conf"
    destino = rutas.home() / ".john" / "john.conf"
    if not origen.is_file() or destino.exists():
        return
    texto = origen.read_text(encoding="utf-8", errors="ignore")
    texto = texto.replace("$JOHN/", f"{prefijo()}/usr/share/john/")
    rutas.asegurar(destino.parent)
    destino.write_text(texto, encoding="utf-8")


def _orden(programa: Path) -> str:
    """exec directo, o con el intérprete desempaquetado si el del #! no está en el sistema."""
    destino = f'"{programa}"'
    try:
        primera = programa.read_bytes()[:200].split(b"\n", 1)[0].decode()
    except (OSError, UnicodeDecodeError):
        return destino
    if not primera.startswith("#!"):
        return destino
    partes = primera[2:].strip().split()
    if not partes or Path(partes[0]).exists():
        return destino
    propio = prefijo() / partes[0].lstrip("/")
    if propio.exists():
        return " ".join([f'"{propio}"', *partes[1:], destino])
    return destino


def _recolocar(programa: Path) -> None:
    """En los scripts, cambia rutas /usr/... que solo existen desempaquetadas."""
    try:
        if programa.is_symlink() or programa.stat().st_size > 2_000_000:
            return
        texto = programa.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    p = prefijo()

    def cambiar(m: re.Match) -> str:
        ruta = m.group(0)
        real = re.sub(r"\\?\$LIB", "lib/x86_64-linux-gnu", ruta)
        propia = p / real.lstrip("/")
        return str(propia) if not Path(real).exists() and propia.exists() else ruta

    nuevo = re.sub(r"(?<![\w./-])/usr/(?:lib|share|libexec|\\?\$LIB)/[\w.+/-]+", cambiar, texto)
    relativa = programa.relative_to(p).as_posix() if programa.is_relative_to(p) else ""
    for patron, cambio in PARCHES.get(relativa, []):
        nuevo = re.sub(patron, cambio.replace("{P}", str(p)), nuevo)
    if nuevo != texto:
        modo = programa.stat().st_mode
        programa.write_text(nuevo, encoding="utf-8")
        programa.chmod(modo)


def _fuentes(ej: Ejecutor) -> None:
    origen = prefijo() / "usr" / "share" / "fonts"
    if not origen.is_dir():
        return
    destino = rutas.asegurar(rutas.xdg_datos_raiz() / "fonts" / "ultron-sistema")
    for f in origen.rglob("*"):
        if f.suffix.lower() in {".ttf", ".otf"} and not (destino / f.name).exists():
            shutil.copy2(f, destino / f.name)
    if ej.existe("fc-cache"):
        ej.run(["fc-cache", str(destino)], check=False, fondo=True)


def desinstalar(ej: Ejecutor) -> None:
    """Quita los lanzadores de ~/.local/bin y la carpeta sistema/."""
    local_bin = rutas.home() / ".local" / "bin"
    if dir_bin().is_dir():
        for lanzador in dir_bin().iterdir():
            enlace = local_bin / lanzador.name
            if enlace.is_symlink() and Path(os.readlink(enlace)) == lanzador:
                ej.borrar(enlace)
    if prefijo().is_dir() and not ej.simular:
        shutil.rmtree(prefijo(), ignore_errors=True)
