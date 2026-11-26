"""Qué instala `ultron instalar`: paquetes apt, extensiones de GNOME y fuentes."""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field

from ultron.nucleo import registro
from ultron.nucleo.doctor import Chequeo, OpcionesDoctor, comprobacion
from ultron.nucleo.ejecutor import Ejecutor, Resultado

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
    if not op.completo:
        return []
    from ultron.compartidas.instalacion import PROPIA
    from ultron.nucleo import rutas

    faltan_apt = set(apt_faltan(ej, plan().apt))
    extensiones = ej.existe("gnome-extensions")
    listadas = ej.leer(["gnome-extensions", "list"]) if extensiones else None
    disponibles = set(listadas.salida.splitlines()) if listadas and listadas.ok else set()
    datos = rutas.xdg_datos_raiz()
    destino = datos / "gnome-shell" / "extensions"
    fuentes = datos / "fonts" / "ultron"
    estados = {
        uuid: estado_extension(ej, uuid) for uuid in disponibles & {PROPIA, *plan().extensiones}
    }
    resultados = []
    for modo in registro.listar():
        p = plan([modo.id])
        faltan = [paquete for paquete in p.apt if paquete in faltan_apt]
        resultados.append(Chequeo(
            f"Paquetes apt · {modo.nombre}", "aviso" if faltan else "ok",
            ", ".join(faltan) if faltan else "Todos instalados",
            shlex.join(["sudo", "apt", "install", *faltan]) if faltan else "",
        ))
        instalar = f"ultron instalar --modo {modo.id}"
        for fuente in p.fuentes:
            existe = (fuentes / f"{fuente}.ttf").is_file()
            resultados.append(Chequeo(
                f"Fuente · {modo.nombre} · {fuente}", "ok" if existe else "aviso",
                "Instalada" if existe else "Falta instalarla", "" if existe else instalar,
            ))
        for uuid in [PROPIA, *p.extensiones]:
            nombre = f"GNOME · {modo.nombre} · {uuid}"
            estado_ext = estados.get(uuid)
            if estado_ext in {"OUT OF DATE", "OUT_OF_DATE"}:
                resultados.append(Chequeo(nombre, "aviso", "Versión incompatible", instalar))
            elif uuid in disponibles:
                if estado_ext in {None, "ERROR"}:
                    resultados.append(Chequeo(
                        nombre, "aviso", "GNOME no confirma que se pueda activar",
                        shlex.join(["gnome-extensions", "info", uuid]),
                    ))
                elif uuid == PROPIA and estado_ext not in {"ACTIVE", "ENABLED"}:
                    resultados.append(Chequeo(nombre, "aviso", "Indicador de Ultron inactivo",
                                              f"gnome-extensions enable {PROPIA}"))
                else:
                    resultados.append(Chequeo(nombre, "ok", "Instalada y reconocida por GNOME"))
            elif (destino / uuid / "metadata.json").is_file() or not listadas or not listadas.ok:
                resultados.append(Chequeo(
                    nombre, "aviso", "Activación sin verificar",
                    f"Tras volver a iniciar sesión: gnome-extensions info {uuid}",
                ))
            else:
                resultados.append(Chequeo(nombre, "aviso", "Falta instalarla", instalar))
    return resultados


def estado_extension(ej: Ejecutor, uuid: str) -> str | None:
    """Lee el estado que informa GNOME sin habilitar la extensión."""
    info = ej.leer(["env", "LC_ALL=C", "gnome-extensions", "info", uuid])
    return interpretar_estado_extension(info)


def interpretar_estado_extension(info: Resultado) -> str | None:
    """Extrae el estado de la información de GNOME en locale C."""
    if info.ok:
        for linea in info.salida.splitlines():
            clave, _, valor = linea.strip().partition(":")
            if clave == "State":
                return valor.strip().upper().replace("-", " ")
    return None
