"""Qué instala `ultron instalar`: paquetes apt, extensiones de GNOME y fuentes."""

from __future__ import annotations

from dataclasses import dataclass, field

from ultron.nucleo import registro
from ultron.nucleo.doctor import Chequeo, OpcionesDoctor, comprobacion
from ultron.nucleo.ejecutor import Ejecutor

APT_COMUNES = [
    "mpv", "conky-all", "gnome-shell-extensions", "gnome-shell-extension-manager",
    "gnome-tweaks", "dconf-cli", "python3-gi", "gir1.2-gtk-4.0", "fonts-jetbrains-mono",
    "plymouth-themes", "yt-dlp", "ffmpeg", "chafa", "jq", "curl", "libgtk-3-bin",
]

EXTENSIONES_COMUNES = ["user-theme@gnome-shell-extensions.gcampax.github.com"]

FUENTES: dict[str, str] = {
    "Orbitron": "https://github.com/google/fonts/raw/main/ofl/orbitron/Orbitron%5Bwght%5D.ttf",
    "Rajdhani-Bold": "https://github.com/google/fonts/raw/main/ofl/rajdhani/Rajdhani-Bold.ttf",
    "Rajdhani-Medium": "https://github.com/google/fonts/raw/main/ofl/rajdhani/Rajdhani-Medium.ttf",
    "Inter": "https://github.com/google/fonts/raw/main/ofl/inter/Inter%5Bopsz,wght%5D.ttf",
    "JetBrainsMonoNerd": (
        "https://github.com/ryanoasis/nerd-fonts/raw/HEAD/patched-fonts/JetBrainsMono/"
        "Ligatures/Regular/JetBrainsMonoNerdFont-Regular.ttf"
    ),
}


@dataclass
class Plan:
    apt: list[str] = field(default_factory=list)
    extensiones: list[str] = field(default_factory=list)
    fuentes: list[str] = field(default_factory=list)


def plan(modos: list[str] | None = None) -> Plan:
    """Lo que hace falta para los modos indicados (todos si es None)."""
    p = Plan(apt=list(APT_COMUNES), extensiones=list(EXTENSIONES_COMUNES))
    for modo in registro.listar():
        if modos and modo.id not in modos:
            continue
        p.apt += modo.dependencias.get("apt", [])
        p.extensiones += modo.dependencias.get("extensiones", [])
        p.fuentes += modo.dependencias.get("fuentes", [])
    quitar_repetidos = lambda xs: list(dict.fromkeys(xs))  # noqa: E731
    return Plan(quitar_repetidos(p.apt), quitar_repetidos(p.extensiones),
                quitar_repetidos([f for f in p.fuentes if f in FUENTES]))


def apt_instalado(ej: Ejecutor, paquete: str) -> bool:
    r = ej.leer(["dpkg-query", "-W", "-f=${Status}", paquete])
    return r.codigo == 0 and "install ok installed" in r.salida


def apt_faltan(ej: Ejecutor, paquetes: list[str]) -> list[str]:
    if not ej.existe("dpkg-query"):
        return list(paquetes)
    return [p for p in paquetes if not apt_instalado(ej, p)]


@comprobacion("Dependencias", grupo="dependencias")
def _deps(ej: Ejecutor, op: OpcionesDoctor) -> list[Chequeo]:
    if not op.completo or not ej.existe("dpkg-query"):
        return []
    p = plan()
    faltan = apt_faltan(ej, p.apt)
    resultados = [Chequeo(
        "Paquetes apt", "ok" if not faltan else "aviso",
        "todos instalados" if not faltan else f"faltan {len(faltan)}: {', '.join(faltan[:8])}",
        "" if not faltan else "ultron instalar",
    )]
    no_ext = [u for u in p.extensiones
              if ej.leer(["gnome-extensions", "info", u]).codigo != 0]
    resultados.append(Chequeo(
        "Extensiones GNOME", "ok" if not no_ext else "aviso",
        "todas instaladas" if not no_ext else f"faltan {len(no_ext)}",
        "" if not no_ext else "ultron instalar (y cerrar sesión una vez)",
    ))
    return resultados
