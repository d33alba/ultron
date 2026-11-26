"""Leer una tecla sin esperar a Enter (Linux y Windows)."""

from __future__ import annotations

import sys


def leer_tecla() -> str:
    if sys.platform == "win32":
        import msvcrt

        tecla = msvcrt.getwch()
        if tecla in ("\x00", "\xe0"):  # flechas y teclas especiales
            return {"H": "arriba", "P": "abajo", "K": "izquierda", "M": "derecha"}.get(
                msvcrt.getwch(), "")
        return "\n" if tecla == "\r" else tecla
    import termios
    import tty

    fd = sys.stdin.fileno()
    previo = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        tecla = sys.stdin.read(1)
        if tecla == "\x1b":
            resto = sys.stdin.read(2)
            return {"[A": "arriba", "[B": "abajo", "[D": "izquierda", "[C": "derecha"}.get(
                resto, "escape")
        if tecla == "\x03":
            raise KeyboardInterrupt
        return "\n" if tecla == "\r" else tecla
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, previo)
