"""Cliente de grabación de GNOME, ejecutado con el Python del sistema."""

import os
import sys
import time


def grabar(destino: str, segundos: int) -> None:
    """Mantiene la conexión al bus durante todo el segmento."""
    from gi.repository import Gio, GLib

    interfaz = "org.gnome.Shell.Screencast"
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    def llamar(metodo: str, argumentos=None):
        return bus.call_sync(interfaz, "/org/gnome/Shell/Screencast", interfaz, metodo,
                             argumentos, None, Gio.DBusCallFlags.NONE, 10000, None).unpack()

    exito, ruta = llamar("Screencast", GLib.Variant("(sa{sv})", (
        destino, {"framerate": GLib.Variant("i", 30)},
    )))
    if not exito:
        raise RuntimeError("GNOME no pudo iniciar la grabación.")
    try:
        time.sleep(segundos)
    finally:
        (detenido,) = llamar("StopScreencast")
    if not detenido:
        raise RuntimeError("GNOME no pudo cerrar el segmento.")
    if ruta != destino:
        os.replace(ruta, destino)


if __name__ == "__main__":
    try:
        grabar(sys.argv[1], int(sys.argv[2]))
    except Exception as error:
        sys.stderr.write(f"No se pudo grabar con GNOME: {error}\n")
        raise SystemExit(1) from None

