"""Pomodoro con reloj inyectable, bloqueo de webs y dígitos grandes en ASCII."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from ultron.nucleo import config, hosts, panel
from ultron.nucleo.ejecutor import Ejecutor

WEBS_DEFECTO = ["youtube.com", "tiktok.com", "instagram.com", "x.com", "twitter.com",
                "reddit.com", "twitch.tv", "netflix.com", "facebook.com"]
ETIQUETA = "pomodoro"

DIGITOS = {
    "0": ["█▀▀█", "█  █", "█  █", "█  █", "█▄▄█"],
    "1": ["  ▄█", "   █", "   █", "   █", "   █"],
    "2": ["█▀▀█", "   █", "█▀▀▀", "█   ", "█▄▄▄"],
    "3": ["█▀▀█", "   █", " ▀▀█", "   █", "█▄▄█"],
    "4": ["█  █", "█  █", "▀▀▀█", "   █", "   █"],
    "5": ["█▀▀▀", "█   ", "▀▀▀█", "   █", "▄▄▄█"],
    "6": ["█▀▀▀", "█   ", "█▀▀█", "█  █", "█▄▄█"],
    "7": ["▀▀▀█", "   █", "  █ ", " █  ", " █  "],
    "8": ["█▀▀█", "█  █", "█▀▀█", "█  █", "█▄▄█"],
    "9": ["█▀▀█", "█  █", "▀▀▀█", "   █", "▄▄▄█"],
    ":": [" ", "▀", " ", "▀", " "],
}


def digitos_grandes(texto: str) -> list[str]:
    filas = ["", "", "", "", ""]
    for c in texto:
        patron = DIGITOS.get(c, ["    "] * 5)
        for i in range(5):
            filas[i] += patron[i] + " "
    return [f.rstrip() for f in filas]


def webs() -> list[str]:
    return list(config.obtener("focus", "webs", WEBS_DEFECTO))


def guardar_webs(lista: list[str]) -> None:
    config.fijar("focus", "webs", sorted(set(lista)))


class Reloj:
    def ahora(self) -> float:
        return time.time()

    def dormir(self, segundos: float) -> None:
        time.sleep(segundos)


@dataclass
class Fase:
    nombre: str        # trabajo | descanso
    ciclo: int
    total: float
    restante: float


def ejecutar(
    *,
    minutos: float = 25,
    descanso: float = 5,
    ciclos: int = 4,
    ej: Ejecutor,
    reloj: Reloj | None = None,
    al_tick: Callable[[Fase], None] | None = None,
    al_terminar_fase: Callable[[Fase], None] | None = None,
    bloquear: bool = True,
    lista_webs: list[str] | None = None,
) -> float:
    """Ejecuta los ciclos. Devuelve los minutos de trabajo completados."""
    reloj = reloj or Reloj()
    lista = lista_webs if lista_webs is not None else webs()
    trabajados = 0.0
    try:
        for ciclo in range(1, ciclos + 1):
            fases = [("trabajo", minutos)]
            if ciclo < ciclos:
                fases.append(("descanso", descanso))
            for nombre, duracion in fases:
                if nombre == "trabajo" and bloquear and lista:
                    bloquear = _intentar(hosts.bloquear, ej, lista, ETIQUETA)
                elif bloquear:
                    _intentar(hosts.desbloquear, ej, ETIQUETA)
                total = duracion * 60
                fin = reloj.ahora() + total
                panel.escribir(pomodoro={"fin": fin, "total": total, "fase": nombre,
                                         "ciclo": ciclo, "ciclos": ciclos})
                while (restante := fin - reloj.ahora()) > 0:
                    if al_tick:
                        al_tick(Fase(nombre, ciclo, total, restante))
                    reloj.dormir(min(1.0, restante))
                if nombre == "trabajo":
                    trabajados += duracion
                if al_terminar_fase:
                    al_terminar_fase(Fase(nombre, ciclo, total, 0))
    finally:
        if bloquear:
            _intentar(hosts.desbloquear, ej, ETIQUETA)
        panel.escribir(pomodoro=None)
    return trabajados


def _intentar(funcion: Callable[..., object], *args: object) -> bool:
    """El bloqueo de webs necesita sudo: si no se puede, el pomodoro sigue sin él."""
    from ultron.nucleo.ejecutor import ErrorEjecucion

    try:
        funcion(*args)
        return True
    except ErrorEjecucion:
        from ultron.ui import tema

        tema.actual().aviso("No he podido bloquear las webs (hacen falta permisos). "
                            "El pomodoro sigue sin bloqueo.")
        return False
