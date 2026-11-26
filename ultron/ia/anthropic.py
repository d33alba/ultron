"""Adaptador para la API de mensajes de Anthropic (Claude)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx

from ultron.ia import errores as E
from ultron.ia.ajustes import AjustesIA
from ultron.ia.base import ClienteHTTP, lineas_sse, traducir_excepcion


class ClienteAnthropic(ClienteHTTP):
    def __init__(self, aj: AjustesIA, transport: httpx.BaseTransport | None = None):
        super().__init__(aj, transport)
        self.base = (aj.url_base or "https://api.anthropic.com").rstrip("/")
        if self.base.endswith("/v1"):
            self.base = self.base[:-3]

    def _cabeceras(self) -> dict[str, str]:
        h = {"content-type": "application/json", "anthropic-version": "2023-06-01"}
        if self.aj.clave:
            h["x-api-key"] = self.aj.clave
        return h

    def _cuerpo(self, mensajes: list[dict], temperatura: float | None, max_tokens: int | None,
                json: bool, stream: bool) -> dict[str, Any]:
        sistema = "\n\n".join(m["content"] for m in mensajes if m.get("role") == "system")
        if json:
            sistema = (sistema + "\n\nResponde SOLO con JSON válido.").strip()
        resto = [m for m in mensajes if m.get("role") != "system"]
        cuerpo: dict[str, Any] = {
            "model": self.modelo, "messages": resto, "max_tokens": max_tokens or 1024,
            "stream": stream,
        }
        if sistema:
            cuerpo["system"] = sistema
        if temperatura is not None:
            cuerpo["temperature"] = temperatura
        return cuerpo

    def _post(self, cuerpo: dict[str, Any]) -> httpx.Response:
        try:
            r = self._http.post(self.base + "/v1/messages", headers=self._cabeceras(), json=cuerpo)
        except httpx.HTTPError as e:
            raise traducir_excepcion(e, self.aj) from e
        return self._comprobar(r)

    def chat(
        self,
        mensajes: list[dict],
        *,
        temperatura: float | None = None,
        max_tokens: int | None = None,
        json: bool = False,
    ) -> str:
        r = self._post(self._cuerpo(mensajes, temperatura, max_tokens, json, False))
        try:
            bloques = r.json()["content"]
            return "".join(b.get("text", "") for b in bloques if b.get("type") == "text")
        except (ValueError, KeyError, TypeError) as e:
            raise E.RespuestaInvalida("La respuesta no tiene el formato de Anthropic.") from e

    def chat_stream(
        self,
        mensajes: list[dict],
        *,
        temperatura: float | None = None,
        max_tokens: int | None = None,
        json: bool = False,
    ) -> Iterator[str]:
        cuerpo = self._cuerpo(mensajes, temperatura, max_tokens, json, True)
        try:
            with self._http.stream("POST", self.base + "/v1/messages",
                                   headers=self._cabeceras(), json=cuerpo) as r:
                self._comprobar(r)
                for evento in lineas_sse(r.iter_lines()):
                    if evento.get("type") == "content_block_delta":
                        trozo = evento.get("delta", {}).get("text")
                        if trozo:
                            yield trozo
        except httpx.HTTPError as e:
            raise traducir_excepcion(e, self.aj) from e

    def modelos(self) -> list[str]:
        try:
            r = self._http.get(self.base + "/v1/models", headers=self._cabeceras())
        except httpx.HTTPError as e:
            raise traducir_excepcion(e, self.aj) from e
        self._comprobar(r)
        try:
            return sorted(m["id"] for m in r.json().get("data", []))
        except (ValueError, KeyError, TypeError) as e:
            raise E.RespuestaInvalida() from e
