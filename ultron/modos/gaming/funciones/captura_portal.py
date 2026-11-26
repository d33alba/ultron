"""Grabación Wayland con selección de pantalla mediante el portal de GNOME."""

import os
import signal
import sys
import time
import uuid
from pathlib import Path

PORTAL = "org.freedesktop.portal.Desktop"
OBJETO = "/org/freedesktop/portal/desktop"
PANTALLA = "org.freedesktop.portal.ScreenCast"


class Portal:
    def __init__(self, gio, glib):
        self.gio, self.glib = gio, glib
        self.bus = gio.bus_get_sync(gio.BusType.SESSION, None)
        self.emisor = self.bus.get_unique_name()[1:].replace(".", "_")

    def pedir(self, metodo: str, firma: str, *argumentos, **opciones) -> dict:
        token = "ultron" + uuid.uuid4().hex
        opciones["handle_token"] = self.glib.Variant("s", token)
        bucle = self.glib.MainLoop()
        resultado = []

        def recibir(_bus, _emisor, _ruta, _interfaz, _senal, parametros):
            resultado.extend(parametros.unpack())
            bucle.quit()

        solicitud = f"{OBJETO}/request/{self.emisor}/{token}"
        suscripcion = self.bus.signal_subscribe(
            PORTAL, "org.freedesktop.portal.Request", "Response", solicitud, None,
            self.gio.DBusSignalFlags.NONE, recibir,
        )

        def vencer():
            bucle.quit()
            return self.glib.SOURCE_CONTINUE

        tiempo = self.glib.timeout_add_seconds(120, vencer)
        try:
            self.bus.call_sync(
                PORTAL, OBJETO, PANTALLA, metodo,
                self.glib.Variant(firma, (*argumentos, opciones)), None,
                self.gio.DBusCallFlags.NONE, 10000, None,
            )
            bucle.run()
        finally:
            self.glib.source_remove(tiempo)
            self.bus.signal_unsubscribe(suscripcion)
        if not resultado or resultado[0] != 0:
            raise RuntimeError("La selección de pantalla se canceló o agotó el tiempo.")
        return resultado[1]

    def abrir(self, sesion: str) -> int:
        respuesta, descriptores = self.bus.call_with_unix_fd_list_sync(
            PORTAL, OBJETO, PANTALLA, "OpenPipeWireRemote",
            self.glib.Variant("(oa{sv})", (sesion, {})), None,
            self.gio.DBusCallFlags.NONE, 10000, None, None,
        )
        return descriptores.get(respuesta.unpack()[0])


def guardar_tramos(gst, glib, fd: int, nodo: int, carpeta: Path, conservar: int) -> None:
    pipeline = gst.parse_launch(
        "pipewiresrc name=origen do-timestamp=true ! queue ! videoconvert ! "
        "videorate ! video/x-raw,framerate=30/1 ! "
        "x264enc tune=zerolatency speed-preset=ultrafast key-int-max=30 ! "
        "h264parse ! splitmuxsink name=salida max-size-time=5000000000"
    )
    origen = pipeline.get_by_name("origen")
    origen.set_property("fd", fd)
    origen.set_property("path", str(nodo))
    salida = pipeline.get_by_name("salida")
    salida.set_property("location", str(carpeta / "portal-%09d.mkv"))
    salida.set_property("muxer", gst.ElementFactory.make("matroskamux"))
    bucle = glib.MainLoop()
    fallos = []

    def mensaje(_bus, evento):
        if evento.type == gst.MessageType.ERROR:
            fallos.append(str(evento.parse_error()[0]))
            bucle.quit()
        elif evento.type == gst.MessageType.EOS:
            bucle.quit()
        elif evento.type == gst.MessageType.ELEMENT:
            estructura = evento.get_structure()
            if estructura and estructura.get_name() == "splitmuxsink-fragment-closed":
                parcial = Path(estructura.get_string("location"))
                os.replace(parcial, carpeta / f"tramo-{time.time_ns()}.mkv")
                for antiguo in sorted(carpeta.glob("tramo-*.mkv"))[:-conservar]:
                    antiguo.unlink(missing_ok=True)

    def detener():
        pipeline.send_event(gst.Event.new_eos())
        return glib.SOURCE_CONTINUE

    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", mensaje)
    pid_senal = glib.unix_signal_add(glib.PRIORITY_DEFAULT, signal.SIGINT, detener)
    try:
        if pipeline.set_state(gst.State.PLAYING) == gst.StateChangeReturn.FAILURE:
            raise RuntimeError("GStreamer no pudo abrir el flujo de pantalla.")
        bucle.run()
    finally:
        glib.source_remove(pid_senal)
        pipeline.set_state(gst.State.NULL)
        bus.remove_signal_watch()
        for parcial in carpeta.glob("portal-*.mkv"):
            parcial.unlink(missing_ok=True)
    if fallos:
        raise RuntimeError(fallos[0])


def grabar(carpeta: Path, conservar: int) -> None:
    import gi

    gi.require_version("Gst", "1.0")
    from gi.repository import Gio, GLib, Gst

    Gst.init(None)
    portal = Portal(Gio, GLib)
    sesion = portal.pedir("CreateSession", "(a{sv})",
                         session_handle_token=GLib.Variant("s", "ultron" + uuid.uuid4().hex))
    ruta = sesion["session_handle"]
    portal.pedir("SelectSources", "(oa{sv})", ruta, types=GLib.Variant("u", 1))
    fuentes = portal.pedir("Start", "(osa{sv})", ruta, "")
    nodo, _propiedades = fuentes["streams"][0]
    fd = portal.abrir(ruta)
    try:
        guardar_tramos(Gst, GLib, fd, nodo, carpeta, conservar)
    finally:
        os.close(fd)


if __name__ == "__main__":
    try:
        grabar(Path(sys.argv[1]), int(sys.argv[2]))
    except Exception as error:
        sys.stderr.write(f"No se pudo grabar con el portal de pantalla: {error}\n")
        raise SystemExit(1) from None

