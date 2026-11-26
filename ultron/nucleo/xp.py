"""Experiencia y logros persistentes del jugador."""

import math
import sys
import time
from contextlib import contextmanager
from datetime import datetime

from ultron.nucleo import estado, jsonio, panel, rutas

PUNTOS = {"entrar": 50, "salir": 10, "juegos": 15, "turbo": 20, "hud": 10,
          "fps": 10, "clip": 20, "visualizador": 10, "osint": 25, "pomodoro": 25,
          "ia": 15, "repasar": 20}
LOGROS = {
    "estreno": "Primer contacto", "noctambulo": "Noctámbulo", "poliglota": "Políglota",
    "analista": "Analista", "empollon": "Empollón", "speedrun": "Speedrun",
    "arcade": "Habitual del arcade", "turbo": "Sobremarcha", "hud": "Ojo de piloto",
    "fps": "Fluidez neón", "clip": "Momento estelar", "cava": "Pulso sintético",
    "veterano": "Veterano", "nivel5": "Nivel cinco", "comando": "Cien comandos",
}


def nivel(xp: int) -> int:
    return math.isqrt(max(0, xp) // 50)


@contextmanager
def _bloquear():
    """Serializa las asignaciones de XP de varias invocaciones de Ultron."""
    archivo = rutas.estado() / "xp.lock"
    archivo.parent.mkdir(parents=True, exist_ok=True)
    with archivo.open("ab") as flujo:
        if sys.platform == "win32":
            import msvcrt

            flujo.seek(0)
            msvcrt.locking(flujo.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(flujo.fileno(), fcntl.LOCK_EX)
        yield


def leer() -> dict:
    return jsonio.leer(rutas.estado() / "xp.json",
                       {"xp": 0, "usos": {}, "modos": [], "logros": []})


def sumar(datos: dict, comando: str, modo: str | None, ahora: datetime,
          reloj: float) -> list[str]:
    """Actualiza la ficha y devuelve los logros recién desbloqueados."""
    usos = datos["usos"]
    usos[comando] = usos.get(comando, 0) + 1
    datos["xp"] += PUNTOS.get(comando, 5)
    if comando == "entrar" and modo:
        if modo not in datos["modos"]:
            datos["modos"].append(modo)
        datos["entrada"] = reloj
    inicio = datos.pop("entrada", None) if comando == "salir" else None
    reglas = {
        "estreno": True,
        "noctambulo": 2 <= ahora.hour < 5,
        "poliglota": len(datos["modos"]) >= 5,
        "analista": usos.get("osint", 0) >= 10,
        "empollon": usos.get("pomodoro_completado", 0) >= 10,
        "speedrun": inicio is not None and 0 <= reloj - inicio < 30,
        "arcade": usos.get("juegos", 0) >= 5,
        "turbo": usos.get("turbo", 0) >= 1,
        "hud": usos.get("hud", 0) >= 1,
        "fps": usos.get("fps", 0) >= 1,
        "clip": usos.get("clip", 0) >= 1,
        "cava": usos.get("visualizador", 0) >= 1,
        "veterano": datos["xp"] >= 500,
        "nivel5": nivel(datos["xp"]) >= 5,
        "comando": sum(usos.values()) >= 100,
    }
    nuevos = [id_ for id_, conseguido in reglas.items()
              if conseguido and id_ not in datos["logros"]]
    datos["logros"].extend(nuevos)
    return nuevos


def registrar(comando: str, *, modo_previo: str | None = None) -> None:
    from rich.text import Text

    from ultron.ui import animaciones, tema

    modo = estado.modo_activo()
    visible = modo == "gaming" or modo_previo == "gaming"
    with _bloquear():
        datos = leer()
        anterior = nivel(datos["xp"])
        nuevos = sumar(datos, comando, modo, datetime.now(), time.time())
        actual = nivel(datos["xp"])
        jsonio.escribir(rutas.estado() / "xp.json", datos)
        if visible:
            panel.escribir(nivel=actual)
    if visible:
        t = tema.cargar_tema("gaming")
        mensajes = [f"LOGRO DESBLOQUEADO · {LOGROS[id_]}" for id_ in nuevos]
        if actual > anterior:
            mensajes.insert(0, f"¡SUBES AL NIVEL {actual}!")
        if mensajes and animaciones.activas():
            animaciones.glitch(t.consola, [Text(m, style="aviso") for m in mensajes], duracion=0.4)
        else:
            for mensaje in mensajes:
                t.ok(mensaje)
        if mensajes:
            from ultron.capas.sonido import reproductor_efecto
            from ultron.modos.gaming.generar_recursos import recurso_generado
            from ultron.nucleo.ejecutor import Ejecutor

            ej = Ejecutor()
            if reproductor := reproductor_efecto(ej):
                archivo = recurso_generado("tema/sonidos/logro.wav", ej)
                ej.run([*reproductor, str(archivo)], fondo=True, check=False)


