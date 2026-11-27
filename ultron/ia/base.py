"""Base común de los adaptadores HTTP: errores traducidos, SSE y diagnóstico."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx

from ultron.ia import errores as E
from ultron.ia.ajustes import AjustesIA


@dataclass
class Diagnostico:
    ok: bool
    mensaje: str
    latencia_ms: int = 0
    ejemplo: str = ""
    error: E.IAError | None = None


def _texto_cuerpo(r: httpx.Response) -> str:
    try:
        return r.text[:2000].lower()
    except (httpx.ResponseNotRead, UnicodeDecodeError):
        return ""


def traducir_respuesta(r: httpx.Response, aj: AjustesIA) -> E.IAError:
    """Convierte una respuesta HTTP fallida en el IAError adecuado."""
    cuerpo = _texto_cuerpo(r)
    codigo = r.status_code
    if codigo in (401, 403):
        return E.ClaveInvalida(
            f"El servidor rechaza la clave ({codigo}).",
            "Revisa ULTRON_API_KEY o ejecuta: ultron ia configurar",
        )
    if codigo == 402 or (codigo == 429 and any(
            p in cuerpo for p in ("quota", "insufficient", "billing", "credit"))):
        return E.SinSaldo(sugerencia="Revisa el saldo de la cuenta o usa una IA local (Ollama).")
    if codigo == 413 or (codigo == 400 and any(
            p in cuerpo for p in ("context", "too long", "maximum", "token limit"))):
        return E.ContextoExcedido(
            sugerencia="Prueba con un texto más corto o un modelo con más contexto."
        )
    if codigo in (400, 404) and "model" in cuerpo:
        return E.ModeloNoExiste(
            f"El modelo «{aj.modelo}» no existe en {aj.url_base}.",
            "Mira los modelos disponibles con: ultron ia modelo",
        )
    if codigo == 404:
        return E.URLIncorrecta(
            f"{aj.url_base} no responde en esa ruta (404).",
            "La URL base suele acabar en /v1 (p. ej. http://localhost:11434/v1).",
        )
    if codigo == 429:
        return E.IAError("Demasiadas peticiones seguidas (429).", "Espera unos segundos.")
    if codigo >= 500:
        return E.IAError(f"El servidor de IA ha fallado ({codigo}).",
                         "Mira los registros del servidor o reinícialo.")
    return E.IAError(f"Error {codigo} del servidor de IA: {cuerpo[:200]}")


def traducir_excepcion(e: Exception, aj: AjustesIA) -> E.IAError:
    if isinstance(e, E.IAError):
        return e
    if isinstance(e, (httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
        return E.TiempoAgotado(
            sugerencia="Los modelos locales pueden tardar; sube «timeout» en config.toml."
        )
    if isinstance(e, (httpx.ConnectError, httpx.ConnectTimeout)):
        return E.SinConexion(
            f"No puedo conectar con {aj.url_base}.",
            f"¿Está arrancado el servidor? Prueba: curl {aj.url_base}/models",
        )
    if isinstance(e, httpx.UnsupportedProtocol):
        return E.URLIncorrecta(f"La URL «{aj.url_base}» no es válida.",
                               "Debe empezar por http:// o https://")
    if isinstance(e, httpx.TimeoutException):
        return E.TiempoAgotado()
    if isinstance(e, (ValueError, KeyError, IndexError, TypeError)):
        return E.RespuestaInvalida()
    if isinstance(e, httpx.HTTPError):
        return E.SinConexion(f"Error de red: {e}")
    return E.IAError(str(e))


def lineas_sse(lineas: Iterator[str]) -> Iterator[dict[str, Any]]:
    """Eventos JSON de un flujo SSE (`data: {...}`), parando en [DONE]."""
    for linea in lineas:
        linea = linea.strip()
        if not linea.startswith("data:"):
            continue
        datos = linea[5:].strip()
        if datos == "[DONE]":
            return
        try:
            yield json.loads(datos)
        except ValueError:
            continue


class ClienteHTTP:
    """Lógica común: cliente httpx, errores y diagnóstico."""

    proveedor: str
    modelo: str

    def __init__(self, aj: AjustesIA, transport: httpx.BaseTransport | None = None):
        self.aj = aj
        self.proveedor = aj.proveedor
        self.modelo = aj.modelo
        espera = aj.timeout
        if es_url_local(aj.url_base) and espera < 300:
            espera = 300.0  # un modelo local en CPU puede tardar en dar la primera palabra
        self._http = httpx.Client(timeout=httpx.Timeout(espera, connect=10.0),
                                  transport=transport)

    def _cabeceras(self) -> dict[str, str]:
        return {}

    def _comprobar(self, r: httpx.Response) -> httpx.Response:
        if r.status_code >= 400:
            try:
                r.read()
            except httpx.HTTPError:
                pass
            raise traducir_respuesta(r, self.aj)
        return r

    def chat(self, mensajes: list[dict], **kw: Any) -> str:  # pragma: no cover - abstracto
        raise NotImplementedError

    def modelos(self) -> list[str]:  # pragma: no cover - abstracto
        raise NotImplementedError

    def probar(self) -> Diagnostico:
        inicio = time.monotonic()
        try:
            texto = self.chat(
                [{"role": "user", "content": "Responde solo: OK"}], max_tokens=8, temperatura=0
            )
        except Exception as e:  # noqa: BLE001 - probar nunca lanza
            err = traducir_excepcion(e, self.aj)
            return Diagnostico(False, err.mensaje, error=err)
        ms = int((time.monotonic() - inicio) * 1000)
        return Diagnostico(True, f"{self.modelo} responde en {ms} ms", ms, texto.strip()[:80])


def es_url_local(url: str) -> bool:
    from urllib.parse import urlparse

    host = (urlparse(url).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local")
