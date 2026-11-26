"""Lecturas breves para el widget de Conky."""

import ipaddress
import socket
import sys

import httpx

from ultron.nucleo import rutas
from ultron.ui.tema import consola


def publica() -> str:
    try:
        respuesta = httpx.get("https://api.ipify.org", timeout=4, trust_env=False)
        respuesta.raise_for_status()
        return str(ipaddress.ip_address(respuesta.text.strip()))
    except (httpx.HTTPError, ValueError):
        return "—"


def local() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as conexion:
            conexion.connect(("192.0.2.1", 9))
            return conexion.getsockname()[0]
    except OSError:
        return "—"


def total() -> str:
    try:
        return str(int((rutas.estado() / "radar.total").read_text(encoding="ascii")))
    except (OSError, ValueError):
        return "—"


def main() -> None:
    c = consola()
    if sys.argv[1:] == ["publica"]:
        c.print(f"IP pública  {publica()}")
    else:
        c.print(f"IP local  {local()}\nDispositivos de la última lectura  {total()}")


if __name__ == "__main__":
    main()
