"""Carga y validación de modo.yaml."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ultron.nucleo import rutas

_ID = re.compile(r"^[a-z][a-z0-9_-]{1,30}$")


class ErrorEsquema(Exception):
    """modo.yaml no es válido."""


@dataclass
class IADef:
    personalidad: str = ""
    temperatura: float = 0.7


@dataclass
class Recurso:
    ruta: str
    descripcion: str = ""


@dataclass
class ModoDef:
    id: str
    nombre: str
    lema: str
    descripcion: str
    dir: Path
    ia: IADef = field(default_factory=IADef)
    capas: dict[str, dict[str, Any]] = field(default_factory=dict)
    funciones: list[str] = field(default_factory=list)
    recursos_opcionales: list[Recurso] = field(default_factory=list)
    dependencias: dict[str, list[str]] = field(default_factory=dict)
    orden: int = 100

    def dir_usuario(self) -> Path:
        return rutas.modos_usuario() / self.id

    def recurso(self, relativa: str | Path) -> Path:
        """Ruta de un recurso: primero los datos del usuario y luego el paquete."""
        rel = Path(relativa)
        if rel.is_absolute():
            return rel
        propia = self.dir_usuario() / rel
        return propia if propia.exists() else self.dir / rel

    def tiene_recurso(self, relativa: str | Path) -> bool:
        return self.recurso(relativa).exists()


def _exigir(datos: dict, clave: str, tipo: type, archivo: Path) -> Any:
    if clave not in datos:
        raise ErrorEsquema(f"{archivo}: falta la clave obligatoria «{clave}».")
    valor = datos[clave]
    if not isinstance(valor, tipo):
        raise ErrorEsquema(
            f"{archivo}: «{clave}» debe ser {tipo.__name__}, no {type(valor).__name__}."
        )
    return valor


def cargar(archivo: Path) -> ModoDef:
    archivo = Path(archivo)
    try:
        datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ErrorEsquema(f"No existe {archivo}.") from e
    except yaml.YAMLError as e:
        linea = getattr(getattr(e, "problem_mark", None), "line", None)
        donde = f" (línea {linea + 1})" if linea is not None else ""
        raise ErrorEsquema(f"{archivo}: YAML inválido{donde}.") from e
    if not isinstance(datos, dict):
        raise ErrorEsquema(f"{archivo}: el contenido debe ser un diccionario.")

    id_ = _exigir(datos, "id", str, archivo)
    if not _ID.match(id_):
        raise ErrorEsquema(f"{archivo}: id «{id_}» inválido (minúsculas, números, - y _).")
    nombre = _exigir(datos, "nombre", str, archivo)

    ia_raw = datos.get("ia") or {}
    if not isinstance(ia_raw, dict):
        raise ErrorEsquema(f"{archivo}: «ia» debe ser un diccionario.")
    ia = IADef(
        personalidad=str(ia_raw.get("personalidad", "")).strip(),
        temperatura=float(ia_raw.get("temperatura", 0.7)),
    )

    capas_raw = datos.get("capas") or {}
    if not isinstance(capas_raw, dict):
        raise ErrorEsquema(f"{archivo}: «capas» debe ser un diccionario capa → configuración.")
    capas: dict[str, dict[str, Any]] = {}
    for nombre_capa, cfg in capas_raw.items():
        if cfg is None:
            cfg = {}
        if not isinstance(cfg, dict):
            raise ErrorEsquema(f"{archivo}: la capa «{nombre_capa}» debe ser un diccionario.")
        capas[str(nombre_capa)] = cfg

    funciones = datos.get("funciones") or []
    if not isinstance(funciones, list):
        raise ErrorEsquema(f"{archivo}: «funciones» debe ser una lista.")

    recursos = []
    for r in datos.get("recursos_opcionales") or []:
        if not isinstance(r, dict) or "ruta" not in r:
            raise ErrorEsquema(f"{archivo}: cada recurso opcional necesita «ruta».")
        recursos.append(Recurso(ruta=str(r["ruta"]), descripcion=str(r.get("descripcion", ""))))

    deps = datos.get("dependencias") or {}
    if not isinstance(deps, dict):
        raise ErrorEsquema(f"{archivo}: «dependencias» debe ser un diccionario.")

    return ModoDef(
        id=id_,
        nombre=nombre,
        lema=str(datos.get("lema", "")),
        descripcion=str(datos.get("descripcion", "")),
        dir=archivo.parent,
        ia=ia,
        capas=capas,
        funciones=[str(f) for f in funciones],
        recursos_opcionales=recursos,
        dependencias={k: list(v or []) for k, v in deps.items()},
        orden=int(datos.get("orden", 100)),
    )
