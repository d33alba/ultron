"""Adaptador OpenAI-compatible: Ollama, LM Studio, vLLM, llama.cpp, OpenAI, Groq, OpenRouter…"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from urllib.parse import urlparse

import httpx

from ultron.ia import errores as E
from ultron.ia.ajustes import AjustesIA
from ultron.ia.base import ClienteHTTP, lineas_sse, traducir_excepcion


def normalizar_url(url: str) -> str:
    """Quita la barra final y añade /v1 si la URL es solo host:puerto."""
    url = url.strip().rstrip("/")
    if not urlparse(url).path:
        url += "/v1"
    return url


class ClienteOpenAI(ClienteHTTP):
    def __init__(self, aj: AjustesIA, transport: httpx.BaseTransport | None = None):
        super().__init__(aj, transport)
        self.base = normalizar_url(aj.url_base)
        self._probado_v1 = self.base.endswith("/v1")

    def _cabeceras(self) -> dict[str, str]:
        h = {"Content-Type": "application/json"}
        if self.aj.clave:
            h["Authorization"] = f"Bearer {self.aj.clave}"
        return h

    def _peticion(self, metodo: str, ruta: str, **kw: Any) -> httpx.Response:
        try:
            r = self._http.request(metodo, self.base + ruta, headers=self._cabeceras(), **kw)
            if r.status_code == 404 and not self._probado_v1 and "model" not in r.text.lower():
                self._probado_v1 = True
                self.base += "/v1"
                r = self._http.request(metodo, self.base + ruta, headers=self._cabeceras(), **kw)
        except httpx.HTTPError as e:
            raise traducir_excepcion(e, self.aj) from e
        return self._comprobar(r)

    def _cuerpo(self, mensajes: list[dict], temperatura: float | None, max_tokens: int | None,
                json: bool, stream: bool) -> dict[str, Any]:
        cuerpo: dict[str, Any] = {"model": self.modelo, "messages": mensajes, "stream": stream}
        if temperatura is not None:
            cuerpo["temperature"] = temperatura
        if max_tokens is None and self._es_local():
            # tope de seguridad: los modelos pequeños en modo JSON a veces no paran nunca
            max_tokens = 1200 if json else 1600
        if max_tokens is not None:
            cuerpo["max_tokens"] = max_tokens
        if json:
            cuerpo["response_format"] = {"type": "json_object"}
        return cuerpo

    def chat(
        self,
        mensajes: list[dict],
        *,
        temperatura: float | None = None,
        max_tokens: int | None = None,
        json: bool = False,
    ) -> str:
        if self._es_local():
            # Los modelos locales en CPU pueden tardar minutos: en streaming el límite de
            # tiempo cuenta entre trozo y trozo, no para la respuesta entera.
            try:
                return "".join(self.chat_stream(mensajes, temperatura=temperatura,
                                                max_tokens=max_tokens, json=json))
            except E.IAError as e:
                if not json or isinstance(e, (E.SinConexion, E.ClaveInvalida, E.SinSaldo,
                                              E.TiempoAgotado, E.ModeloNoExiste)):
                    raise
                return "".join(self.chat_stream(mensajes, temperatura=temperatura,
                                                max_tokens=max_tokens, json=False))
        cuerpo = self._cuerpo(mensajes, temperatura, max_tokens, json, False)
        try:
            r = self._peticion("POST", "/chat/completions", json=cuerpo)
        except E.IAError as e:
            if not json or isinstance(e, (E.SinConexion, E.ClaveInvalida, E.SinSaldo)):
                raise
            cuerpo.pop("response_format", None)  # el servidor no soporta modo JSON
            r = self._peticion("POST", "/chat/completions", json=cuerpo)
        try:
            datos = r.json()
            return datos["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as e:
            raise E.RespuestaInvalida(
                "La respuesta no tiene el formato de OpenAI (sin «choices»).",
                "¿La URL apunta a una API compatible con OpenAI?",
            ) from e

    def _es_local(self) -> bool:
        from urllib.parse import urlparse

        host = (urlparse(self.base).hostname or "").lower()
        return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local")

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
            with self._http.stream("POST", self.base + "/chat/completions",
                                   headers=self._cabeceras(), json=cuerpo) as r:
                self._comprobar(r)
                for evento in lineas_sse(r.iter_lines()):
                    try:
                        trozo = evento["choices"][0].get("delta", {}).get("content")
                    except (KeyError, IndexError, AttributeError):
                        continue
                    if trozo:
                        yield trozo
        except httpx.HTTPError as e:
            raise traducir_excepcion(e, self.aj) from e

    def modelos(self) -> list[str]:
        r = self._peticion("GET", "/models")
        try:
            return sorted(m["id"] for m in r.json().get("data", []))
        except (ValueError, KeyError, TypeError) as e:
            raise E.RespuestaInvalida() from e
