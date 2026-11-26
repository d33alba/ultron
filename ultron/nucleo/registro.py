"""Descubre los modos del paquete y los del usuario."""

from __future__ import annotations

import difflib
from pathlib import Path

from ultron.nucleo import rutas
from ultron.nucleo.esquema import ModoDef, cargar


class ModoNoEncontrado(Exception):
    """No existe un modo con ese id."""


_cache: dict[str, ModoDef] | None = None


def invalidar() -> None:
    global _cache
    _cache = None


def _buscar(base: Path) -> list[Path]:
    if not base.is_dir():
        return []
    return sorted(p / "modo.yaml" for p in base.iterdir() if (p / "modo.yaml").is_file())


def _todos() -> dict[str, ModoDef]:
    global _cache
    if _cache is None:
        modos: dict[str, ModoDef] = {}
        for archivo in _buscar(rutas.modos_paquete()) + _buscar(rutas.modos_usuario()):
            modo = cargar(archivo)
            modos[modo.id] = modo
        _cache = modos
    return _cache


def listar() -> list[ModoDef]:
    return sorted(_todos().values(), key=lambda m: (m.orden, m.id))


def ids() -> list[str]:
    return [m.id for m in listar()]


def obtener(id_: str) -> ModoDef:
    id_ = id_.strip().lower()
    modos = _todos()
    if id_ in modos:
        return modos[id_]
    for modo in modos.values():
        if modo.nombre.lower() == id_:
            return modo
    parecidos = difflib.get_close_matches(id_, list(modos), n=2, cutoff=0.5)
    pista = f" ¿Querías decir {' o '.join(parecidos)}?" if parecidos else ""
    raise ModoNoEncontrado(f"No existe el modo «{id_}».{pista} Mira la lista con: ultron modos")
