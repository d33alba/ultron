"""Prompt de sistema según el modo activo."""

from __future__ import annotations

COMUN = (
    "Responde siempre en español. Sé conciso. Usa Markdown simple que se vea bien en una "
    "terminal (listas, negritas, bloques de código); nada de tablas HTML."
)

NEUTRO = "Eres ULTRON, un asistente de terminal para Ubuntu, directo y útil."


def sistema(extra: str | None = None) -> str:
    from ultron.nucleo import estado, registro

    base = NEUTRO
    activo = estado.modo_activo()
    if activo:
        try:
            base = registro.obtener(activo).ia.personalidad or NEUTRO
        except registro.ModoNoEncontrado:
            pass
    partes = [base.strip(), COMUN]
    if extra:
        partes.append(extra.strip())
    return "\n\n".join(partes)


def temperatura() -> float:
    from ultron.nucleo import estado, registro

    activo = estado.modo_activo()
    if activo:
        try:
            return registro.obtener(activo).ia.temperatura
        except registro.ModoNoEncontrado:
            pass
    return 0.7
