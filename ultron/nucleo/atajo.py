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
    for terminal, sep in (("gnome-terminal", "--"), ("ptyxis", "--"), ("kgx", "-e")):
        if shutil.which(terminal):
            return f"{terminal} {sep} {ultron}"
    return f"x-terminal-emulator -e {ultron}"


def instalar(ej: Ejecutor) -> bool:
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
    actual = C.leer_lista(ej.gsettings_get(ESQUEMA, "custom-keybindings"))
    if RUTA in actual:
        ej.gsettings_set(ESQUEMA, "custom-keybindings",
                         C.gv_lista([r for r in actual if r != RUTA]))
    ej.run(["dconf", "reset", "-f", RUTA], check=False)
