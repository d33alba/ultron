"""Atajo global Super+U que abre Ultron (selector de modos) en una terminal."""

from __future__ import annotations

import shutil

from ultron.capas import comun as C
from ultron.nucleo.ejecutor import Ejecutor

ESQUEMA = "org.gnome.settings-daemon.plugins.media-keys"
RUTA = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/ultron/"
TECLA = "<Super>u"


def comando_terminal() -> str:
    ultron = shutil.which("ultron") or "ultron"
    for terminal, sep in (("gnome-terminal", "--full-screen --title=ULTRON --"),
                          ("ptyxis", "--"), ("kgx", "-e"),
                          ("konsole", "--fullscreen --hide-menubar -e")):
        if shutil.which(terminal):
            return f"{terminal} {sep} {ultron} nexus"
    return f"x-terminal-emulator -e {ultron} nexus"


def entrada_menu() -> str:
    """Lanzador «Ultron NEXUS» del menú de aplicaciones (y Meta+U en KDE Plasma)."""
    lineas = ["[Desktop Entry]", "Type=Application", "Name=Ultron NEXUS",
              "Comment=Centro de mando de Ultron", "Icon=utilities-terminal",
              f"Exec={comando_terminal()}", "Terminal=false", "Categories=Utility;System;",
              "X-KDE-Shortcuts=Meta+U"]
    return "\n".join(lineas) + "\n"


def _instalar_kde(ej: Ejecutor) -> bool:
    from ultron.capas.plasma import es_kde
    from ultron.nucleo import rutas

    apps = rutas.xdg_datos_raiz() / "applications" / "ultron-nexus.desktop"
    ej.escribir(apps, entrada_menu(), modo=0o755)
    if not es_kde() or not ej.existe("kwriteconfig5"):
        return False
    ej.run(["kwriteconfig5", "--file", "kglobalshortcutsrc", "--group", "ultron-nexus.desktop",
            "--key", "_launch", "Meta+U,none,Ultron NEXUS"], check=False)
    ej.run(["kwriteconfig5", "--file", "kglobalshortcutsrc", "--group", "ultron-nexus.desktop",
            "--key", "_k_friendly_name", "Ultron NEXUS"], check=False)
    return True


def instalar(ej: Ejecutor) -> bool:
    if _instalar_kde(ej):
        return True
    actual = C.leer_lista(ej.gsettings_get(ESQUEMA, "custom-keybindings"))
    if ej.gsettings_get(ESQUEMA, "custom-keybindings") is None:
        return False
    if RUTA not in actual:
        ej.gsettings_set(ESQUEMA, "custom-keybindings", C.gv_lista([*actual, RUTA]))
    C.dconf_escribir(ej, RUTA + "name", C.gv_str("Ultron"))
    C.dconf_escribir(ej, RUTA + "command", C.gv_str(comando_terminal()))
    C.dconf_escribir(ej, RUTA + "binding", C.gv_str(TECLA))
    return True


def quitar(ej: Ejecutor) -> None:
    from ultron.nucleo import rutas

    menu = rutas.xdg_datos_raiz() / "applications" / "ultron-nexus.desktop"
    if menu.exists():
        ej.borrar(menu)
    if ej.existe("kwriteconfig5"):
        ej.run(["kwriteconfig5", "--file", "kglobalshortcutsrc", "--group",
                "ultron-nexus.desktop", "--key", "_launch", "--delete"], check=False)
    actual = C.leer_lista(ej.gsettings_get(ESQUEMA, "custom-keybindings"))
    if RUTA in actual:
        ej.gsettings_set(ESQUEMA, "custom-keybindings",
                         C.gv_lista([r for r in actual if r != RUTA]))
    ej.run(["dconf", "reset", "-f", RUTA], check=False)
