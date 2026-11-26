"""Comprobaciones de `ultron doctor`. Cada módulo registra las suyas con @comprobacion."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ultron.nucleo.ejecutor import Ejecutor


@dataclass
class Chequeo:
    nombre: str
    estado: str  # ok | aviso | error
    detalle: str = ""
    solucion: str = ""


@dataclass
class OpcionesDoctor:
    sin_ia: bool = False
    completo: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


Funcion = Callable[[Ejecutor, OpcionesDoctor], "Chequeo | list[Chequeo]"]


@dataclass
class _Registro:
    nombre: str
    grupo: str
    funcion: Funcion


COMPROBACIONES: list[_Registro] = []


def comprobacion(nombre: str, grupo: str = "sistema") -> Callable[[Funcion], Funcion]:
    def decorador(f: Funcion) -> Funcion:
        COMPROBACIONES[:] = [c for c in COMPROBACIONES if c.nombre != nombre]
        COMPROBACIONES.append(_Registro(nombre, grupo, f))
        return f

    return decorador


def ejecutar(ej: Ejecutor | None = None, opciones: OpcionesDoctor | None = None) -> list[Chequeo]:
    _cargar_comprobaciones()
    ej = ej or Ejecutor()
    opciones = opciones or OpcionesDoctor()
    resultados: list[Chequeo] = []
    for c in COMPROBACIONES:
        try:
            r = c.funcion(ej, opciones)
        except Exception as e:  # noqa: BLE001 - doctor nunca se cae
            r = Chequeo(c.nombre, "error", f"La comprobación falló: {e}")
        resultados.extend(r if isinstance(r, list) else [r])
    return resultados


def _cargar_comprobaciones() -> None:
    """Importa los módulos que registran comprobaciones (si existen)."""
    import importlib

    for modulo in (
        "ultron.nucleo.chequeos",
        "ultron.ia.chequeos",
        "ultron.nucleo.dependencias",
    ):
        try:
            importlib.import_module(modulo)
        except ImportError:
            continue
