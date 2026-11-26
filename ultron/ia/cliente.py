"""Punto de entrada de la IA para el resto de Ultron."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Protocol

import httpx

from ultron.ia import errores as E
from ultron.ia.ajustes import AjustesIA, resolver
from ultron.ia.base import Diagnostico

# Los tests inyectan aquí un httpx.MockTransport.
TRANSPORTE: httpx.BaseTransport | None = None


class ClienteIA(Protocol):
    proveedor: str
    modelo: str
    aj: AjustesIA

    def chat(self, mensajes: list[dict], *, temperatura: float | None = None,
             max_tokens: int | None = None, json: bool = False) -> str: ...

    def chat_stream(self, mensajes: list[dict], **kw: Any) -> Iterator[str]: ...

    def modelos(self) -> list[str]: ...

    def probar(self) -> Diagnostico: ...


def crear(aj: AjustesIA) -> ClienteIA:
    if aj.tipo == "anthropic":
        from ultron.ia.anthropic import ClienteAnthropic

        return ClienteAnthropic(aj, TRANSPORTE)
    from ultron.ia.openai_compat import ClienteOpenAI

    return ClienteOpenAI(aj, TRANSPORTE)


def obtener_cliente(modelo: str | None = None, **kw: Any) -> ClienteIA:
    aj = resolver(modelo=modelo, **kw)
    if aj is None:
        raise E.IANoConfigurada()
    cliente = crear(aj)
    if not cliente.modelo:
        try:
            disponibles = cliente.modelos()
        except E.IAError:
            disponibles = []
        if not disponibles:
            raise E.IANoConfigurada(
                "Hay servidor de IA pero no hay ningún modelo elegido.",
                "Elige uno con: ultron ia modelo <nombre>",
            )
        cliente.modelo = aj.modelo = disponibles[0]
    return cliente


def _mensajes(prompt: str, sistema: str | None, historial: list[dict] | None) -> list[dict]:
    from ultron.ia.personalidad import sistema as sistema_modo

    return [
        {"role": "system", "content": sistema_modo(sistema)},
        *(historial or []),
        {"role": "user", "content": prompt},
    ]


def preguntar(
    prompt: str,
    *,
    sistema: str | None = None,
    json: bool = False,
    modelo: str | None = None,
    historial: list[dict] | None = None,
    **kw: Any,
) -> str:
    """Pregunta a la IA con la personalidad del modo activo."""
    cliente = obtener_cliente(modelo)
    return cliente.chat(_mensajes(prompt, sistema, historial), json=json, **kw)


def preguntar_stream(
    prompt: str,
    *,
    sistema: str | None = None,
    modelo: str | None = None,
    historial: list[dict] | None = None,
    **kw: Any,
) -> Iterator[str]:
    cliente = obtener_cliente(modelo)
    yield from cliente.chat_stream(_mensajes(prompt, sistema, historial), **kw)


def hay_ia() -> bool:
    try:
        return resolver(autodetectar=False) is not None
    except Exception:  # noqa: BLE001
        return False
