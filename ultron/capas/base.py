"""Clase base de las capas y su registro."""

from __future__ import annotations

import importlib
import pkgutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from ultron.nucleo import rutas
from ultron.nucleo.ejecutor import Ejecutor
from ultron.nucleo.esquema import ModoDef


@dataclass
class Contexto:
    modo: ModoDef
    dir_modo: Path
    consola: Any = None
    rutas: Any = rutas

    def recurso(self, relativa: str | Path) -> Path:
        return self.modo.recurso(relativa)

    def respaldo(self, relativa: str | Path, ej: Ejecutor) -> Path:
        ruta = self.recurso(relativa)
        if self.modo.id == "netanyahu" and not ruta.exists():
            from ultron.modos.netanyahu.generar_recursos import recurso_generado

            return recurso_generado(relativa, ej) or ruta
        if self.modo.id == "gaming" and not ruta.exists():
            from ultron.modos.gaming.generar_recursos import recurso_generado

            return recurso_generado(relativa, ej) or ruta
        return ruta


class Capa(ABC):
    nombre: ClassVar[str] = ""
    requiere_sudo: ClassVar[bool] = False
    orden: ClassVar[int] = 50
    descripcion: ClassVar[str] = ""

    def __init__(self, ej: Ejecutor, ctx: Contexto):
        self.ej = ej
        self.ctx = ctx

    def disponible(self) -> tuple[bool, str]:
        return True, ""

    @abstractmethod
    def capturar(self, cfg: dict) -> dict:
        """Estado actual de todo lo que se va a tocar (serializable a JSON)."""

    @abstractmethod
    def aplicar(self, cfg: dict) -> None:
        """Aplica la configuración del modo."""

    @abstractmethod
    def restaurar(self, previo: dict) -> None:
        """Deja exactamente lo capturado."""


REGISTRO_CAPAS: dict[str, type[Capa]] = {}


def registrar_capa(cls: type[Capa]) -> type[Capa]:
    if not cls.nombre:
        raise ValueError(f"{cls.__name__} no tiene nombre")
    REGISTRO_CAPAS[cls.nombre] = cls
    return cls


_cargadas = False


def cargar_capas() -> dict[str, type[Capa]]:
    """Importa todos los módulos de ultron.capas para rellenar el registro."""
    global _cargadas
    if not _cargadas:
        import ultron.capas as paquete

        for info in pkgutil.iter_modules(paquete.__path__):
            if info.name not in {"base"} and not info.name.startswith("_"):
                importlib.import_module(f"ultron.capas.{info.name}")
        _cargadas = True
    return REGISTRO_CAPAS
