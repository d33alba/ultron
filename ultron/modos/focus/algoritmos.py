"""Algoritmos sin IA: repetición espaciada SM-2, plan de estudio, rachas y mapa de calor."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

# --- SM-2 ---------------------------------------------------------------------------

NOTAS = {1: 1, 2: 3, 3: 4, 4: 5}  # otra vez, difícil, bien, fácil → calidad SM-2


@dataclass
class EstadoTarjeta:
    facilidad: float = 2.5
    intervalo: int = 0
    repeticiones: int = 0


def sm2(estado: EstadoTarjeta, nota: int) -> EstadoTarjeta:
    """Nueva programación de una tarjeta tras puntuarla de 1 a 4."""
    q = NOTAS.get(nota, 4)
    facilidad = max(1.3, estado.facilidad + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
    if q < 3:
        return EstadoTarjeta(facilidad, 1, 0)
    repeticiones = estado.repeticiones + 1
    if repeticiones == 1:
        intervalo = 1
    elif repeticiones == 2:
        intervalo = 6
    else:
        intervalo = round(estado.intervalo * facilidad)
    if nota == 4:
        intervalo = max(intervalo + 1, round(intervalo * 1.3))
    return EstadoTarjeta(facilidad, intervalo, repeticiones)


# --- plan de estudio ---------------------------------------------------------------


@dataclass
class Evento:
    asignatura: str
    fecha: date
    temas: list[str] = field(default_factory=list)
    horas: float = 4.0
    tipo: str = "examen"


@dataclass
class Bloque:
    asignatura: str
    horas: float
    tipo: str      # estudio | repaso | repaso final
    tema: str


def generar_plan(eventos: list[Evento], desde: date) -> dict[date, list[Bloque]]:
    """Reparte las horas de cada examen hasta su fecha.

    - Los temas nuevos se estudian en la primera parte del periodo.
    - Cada tema se repasa a 1, 3 y 7 días de estudiarlo (si da tiempo).
    - Los dos días anteriores al examen tienen el doble de carga y son repaso final.
    """
    plan: dict[date, list[Bloque]] = defaultdict(list)
    for ev in sorted(eventos, key=lambda e: e.fecha):
        dias = (ev.fecha - desde).days
        if dias <= 0:
            continue
        pesos = [2.0 if dias - d <= 2 else 1.0 for d in range(dias)]
        total = sum(pesos)
        temas = ev.temas or ["temario"]
        dias_estudio = max(1, dias - 2) if dias > 2 else dias
        estudio_de: dict[int, list[str]] = defaultdict(list)
        for i, tema in enumerate(temas):
            estudio_de[min(dias_estudio - 1, i * dias_estudio // len(temas))].append(tema)
        repaso_de: dict[int, list[str]] = defaultdict(list)
        for d, ts in estudio_de.items():
            for salto in (1, 3, 7):
                if d + salto < dias - 2:
                    repaso_de[d + salto].extend(ts)
        for d in range(dias):
            dia = desde + timedelta(days=d)
            horas = round(ev.horas * pesos[d] / total, 2)
            if dias - d <= 2:
                plan[dia].append(Bloque(ev.asignatura, horas, "repaso final", ", ".join(temas)))
            elif estudio_de.get(d):
                plan[dia].append(Bloque(ev.asignatura, horas, "estudio",
                                        ", ".join(estudio_de[d])))
            elif repaso_de.get(d):
                plan[dia].append(Bloque(ev.asignatura, horas, "repaso",
                                        ", ".join(dict.fromkeys(repaso_de[d]))))
            else:
                plan[dia].append(Bloque(ev.asignatura, horas, "repaso", ", ".join(temas)))
    return dict(sorted(plan.items()))


# --- estadísticas -------------------------------------------------------------------


def rachas(dias: set[date], hoy: date) -> tuple[int, int]:
    """(racha actual, racha máxima) de días seguidos con estudio."""
    actual = 0
    d = hoy if hoy in dias else hoy - timedelta(days=1)
    while d in dias:
        actual += 1
        d -= timedelta(days=1)
    maxima = seguidos = 0
    previo: date | None = None
    for d in sorted(dias):
        seguidos = seguidos + 1 if previo and (d - previo).days == 1 else 1
        maxima = max(maxima, seguidos)
        previo = d
    return actual, maxima


def nivel_intensidad(minutos: float) -> int:
    if minutos <= 0:
        return 0
    if minutos < 30:
        return 1
    if minutos < 60:
        return 2
    if minutos < 120:
        return 3
    return 4


def mapa_calor(minutos: dict[date, float], hoy: date, semanas: int = 20) -> list[list[int]]:
    """Matriz 7 × semanas (lunes arriba) con niveles 0–4; -1 para días futuros."""
    inicio = hoy - timedelta(days=hoy.weekday()) - timedelta(weeks=semanas - 1)
    filas = [[0] * semanas for _ in range(7)]
    for s in range(semanas):
        for d in range(7):
            dia = inicio + timedelta(weeks=s, days=d)
            filas[d][s] = -1 if dia > hoy else nivel_intensidad(minutos.get(dia, 0))
    return filas
