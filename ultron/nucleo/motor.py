"""Entrar y salir de modos: orquesta capas, instantánea y rollback."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ultron.capas.base import REGISTRO_CAPAS, Capa, Contexto, cargar_capas
from ultron.nucleo import estado, jsonio, panel, registro, rutas
from ultron.nucleo.ejecutor import Ejecutor
from ultron.nucleo.esquema import ModoDef

Progreso = Callable[[str, str], None]
"""progreso(capa, estado) con estado: aplicando|aplicada|saltada|fallida|restaurando|restaurada."""


class ErrorMotor(Exception):
    """Un modo no se ha podido aplicar o restaurar."""


@dataclass
class ResultadoCapa:
    nombre: str
    estado: str
    motivo: str = ""


def ruta_instantanea() -> Path:
    return rutas.estado() / "instantanea.json"


def leer_instantanea() -> dict[str, Any] | None:
    datos = jsonio.leer(ruta_instantanea())
    return datos if isinstance(datos, dict) and datos.get("modo") else None


def _guardar_instantanea(datos: dict[str, Any]) -> None:
    jsonio.escribir(ruta_instantanea(), datos)


def _nada(_capa: str, _estado: str) -> None:
    return None


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def capas_del_modo(
    modo: ModoDef,
    solo: Iterable[str] | None = None,
    excepto: Iterable[str] | None = None,
) -> tuple[list[type[Capa]], list[str]]:
    """Clases de capa del modo ordenadas, y nombres de capas desconocidas."""
    cargar_capas()
    solo_s = {s.strip() for s in solo or [] if s.strip()}
    excepto_s = {s.strip() for s in excepto or [] if s.strip()}
    clases, desconocidas = [], []
    for nombre in modo.capas:
        if solo_s and nombre not in solo_s:
            continue
        if nombre in excepto_s:
            continue
        cls = REGISTRO_CAPAS.get(nombre)
        if cls is None:
            desconocidas.append(nombre)
        else:
            clases.append(cls)
    clases.sort(key=lambda c: (c.orden, c.nombre))
    return clases, desconocidas


def _contexto(modo: ModoDef, consola: Any = None) -> Contexto:
    return Contexto(modo=modo, dir_modo=modo.dir, consola=consola)


def _restaurar_lista(
    entradas: list[dict[str, Any]], ej: Ejecutor, ctx: Contexto | None, progreso: Progreso
) -> list[ResultadoCapa]:
    resultados = []
    for entrada in reversed(entradas):
        nombre = entrada.get("nombre", "?")
        cls = REGISTRO_CAPAS.get(nombre)
        if cls is None or ctx is None:
            resultados.append(ResultadoCapa(nombre, "fallida", "capa desconocida"))
            continue
        progreso(nombre, "restaurando")
        try:
            cls(ej, ctx).restaurar(entrada.get("previo") or {})
        except Exception as e:  # noqa: BLE001 - se sigue restaurando el resto
            resultados.append(ResultadoCapa(nombre, "fallida", str(e)))
            progreso(nombre, "fallida")
            continue
        resultados.append(ResultadoCapa(nombre, "restaurada"))
        progreso(nombre, "restaurada")
    return resultados


def _panel_modo(modo: ModoDef | None) -> None:
    import shutil

    modos = [{"id": m.id, "nombre": m.nombre} for m in registro.listar()]
    comando = shutil.which("ultron") or "ultron"
    if modo is None:
        panel.escribir(
            modo=None, nombre=None, glifo=None, acento=None, musica_sonando=False, modos=modos,
            comando=comando,
        )
        return
    from ultron.ui.tema import cargar_tema

    tema = cargar_tema(modo.id)
    panel.escribir(
        modo=modo.id,
        nombre=modo.nombre,
        glifo=tema.glifos.get("marca", "●"),
        acento=tema.paleta.get("primario", "#00F0FF"),
        musica_silenciada=False,
        modos=modos,
        comando=comando,
    )


def entrar(
    id_modo: str,
    *,
    ej: Ejecutor | None = None,
    simular: bool = False,
    solo: Iterable[str] | None = None,
    excepto: Iterable[str] | None = None,
    sin_sudo: bool = False,
    confirmar_sudo: Callable[[list[str]], bool] | None = None,
    progreso: Progreso | None = None,
    consola: Any = None,
) -> list[ResultadoCapa]:
    """Aplica un modo. Si algo falla, restaura lo aplicado y lanza ErrorMotor."""
    progreso = progreso or _nada
    modo = registro.obtener(id_modo)
    ej = ej or Ejecutor(simular=simular, consola=consola)
    simular = ej.simular
    resultados: list[ResultadoCapa] = []

    if not simular and leer_instantanea():
        restauradas = salir(ej=ej, progreso=progreso, consola=consola)
        if any(r.estado == "fallida" for r in restauradas):
            raise ErrorMotor("Restaura primero las capas pendientes con: ultron salir")

    clases, desconocidas = capas_del_modo(modo, solo, excepto)
    for nombre in desconocidas:
        resultados.append(ResultadoCapa(nombre, "saltada", "capa no disponible en esta versión"))

    con_sudo = [c.nombre for c in clases if c.requiere_sudo]
    saltar_sudo = False
    if con_sudo and not simular:
        if sin_sudo:
            saltar_sudo = True
        elif confirmar_sudo is not None and not confirmar_sudo(con_sudo):
            saltar_sudo = True

    ctx = _contexto(modo, consola)
    inst: dict[str, Any] = {"modo": modo.id, "inicio": _ahora(), "capas": []}
    if not simular:
        _guardar_instantanea(inst)

    for cls in clases:
        nombre = cls.nombre
        if saltar_sudo and cls.requiere_sudo:
            resultados.append(ResultadoCapa(nombre, "saltada", "necesita sudo"))
            progreso(nombre, "saltada")
            continue
        capa = cls(ej, ctx)
        cfg = modo.capas.get(nombre) or {}
        progreso(nombre, "aplicando")
        ok, motivo = capa.disponible()
        if not ok:
            resultados.append(ResultadoCapa(nombre, "saltada", motivo))
            progreso(nombre, "saltada")
            continue
        try:
            previo = capa.capturar(cfg)
            inst["capas"].append({"nombre": nombre, "previo": previo})
            if not simular:
                _guardar_instantanea(inst)
            capa.aplicar(cfg)
        except Exception as e:  # noqa: BLE001 - cualquier fallo provoca rollback
            progreso(nombre, "fallida")
            mensaje = ""
            if not simular:
                restauradas = salir(ej=ej, progreso=progreso, consola=consola)
                mensaje = (
                    " Restaura las capas pendientes con: ultron salir"
                    if any(r.estado == "fallida" for r in restauradas)
                    else " Se ha restaurado todo lo aplicado."
                )
            raise ErrorMotor(f"La capa «{nombre}» ha fallado: {e}.{mensaje}") from e
        resultados.append(ResultadoCapa(nombre, "aplicada"))
        progreso(nombre, "aplicada")

    if not simular:
        estado.actualizar(
            modo_activo=modo.id,
            desde=_ahora(),
            capas=[r.__dict__ for r in resultados],
        )
        _panel_modo(modo)
        _invalidar_tema()
    return resultados


def salir(
    *,
    ej: Ejecutor | None = None,
    simular: bool = False,
    progreso: Progreso | None = None,
    consola: Any = None,
) -> list[ResultadoCapa]:
    """Restaura el sistema a partir de la instantánea, en orden inverso."""
    progreso = progreso or _nada
    ej = ej or Ejecutor(simular=simular, consola=consola)
    cargar_capas()
    inst = leer_instantanea()
    if not inst:
        if not ej.simular:
            estado.actualizar(modo_activo=None, capas=None)
        return []
    try:
        ctx: Contexto | None = _contexto(registro.obtener(inst["modo"]), consola)
    except registro.ModoNoEncontrado:
        ctx = None
    resultados = _restaurar_lista(inst.get("capas", []), ej, ctx, progreso)
    if not ej.simular:
        pendientes = {r.nombre for r in resultados if r.estado == "fallida"}
        if pendientes:
            inst["capas"] = [c for c in inst.get("capas", []) if c.get("nombre") in pendientes]
            _guardar_instantanea(inst)
            return resultados
        ruta_instantanea().unlink(missing_ok=True)
        estado.actualizar(modo_activo=None, desde=None, capas=None)
        _panel_modo(None)
        _invalidar_tema()
    return resultados


def _invalidar_tema() -> None:
    from ultron.ui import tema

    tema.invalidar()
