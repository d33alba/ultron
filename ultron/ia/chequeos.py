"""Comprobaciones de IA para doctor."""

from __future__ import annotations

from ultron.ia import errores as E
from ultron.ia.ajustes import resolver
from ultron.ia.cliente import crear
from ultron.nucleo.doctor import Chequeo, OpcionesDoctor, comprobacion
from ultron.nucleo.ejecutor import Ejecutor


@comprobacion("IA", grupo="ia")
def _ia(_ej: Ejecutor, op: OpcionesDoctor) -> list[Chequeo]:
    aj = resolver()
    if aj is None:
        return [Chequeo("IA configurada", "aviso", "No hay IA configurada",
                        "ultron ia configurar  (todo lo que no es IA funciona igual)")]
    resultados = [Chequeo("IA configurada", "ok",
                          f"{aj.proveedor} · {aj.url_base} · {aj.modelo or 'sin modelo'}")]
    if op.sin_ia:
        return resultados
    cliente = crear(aj)
    try:
        disponibles = cliente.modelos()
    except E.IAError as e:
        resultados.append(Chequeo("IA responde", "error", e.mensaje, e.sugerencia))
        return resultados
    if aj.modelo and disponibles and aj.modelo not in disponibles:
        resultados.append(Chequeo(
            "Modelo existe", "error", f"«{aj.modelo}» no está en el servidor",
            "Disponibles: " + ", ".join(disponibles[:8]),
        ))
        return resultados
    if not aj.modelo:
        resultados.append(Chequeo("Modelo existe", "aviso", "No hay modelo elegido",
                                  "ultron ia modelo <nombre>"))
        return resultados
    resultados.append(Chequeo("Modelo existe", "ok", aj.modelo))
    diag = cliente.probar()
    if diag.ok:
        resultados.append(Chequeo("IA responde", "ok", diag.mensaje))
    else:
        err = diag.error
        resultados.append(Chequeo("IA responde", "error", diag.mensaje,
                                  err.sugerencia if err else ""))
    return resultados
