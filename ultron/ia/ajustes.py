"""Resolución de la configuración de IA: argumentos > entorno > config.toml > autodetección."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import httpx

from ultron.nucleo import config

PROVEEDORES: dict[str, dict[str, str]] = {
    "local": {"tipo": "openai", "url": "http://localhost:11434/v1",
              "nombre": "Local / OpenAI-compatible"},
    "ollama": {"tipo": "openai", "url": "http://localhost:11434/v1", "nombre": "Ollama"},
    "lmstudio": {"tipo": "openai", "url": "http://localhost:1234/v1", "nombre": "LM Studio"},
    "openai": {"tipo": "openai", "url": "https://api.openai.com/v1", "nombre": "OpenAI"},
    "groq": {"tipo": "openai", "url": "https://api.groq.com/openai/v1", "nombre": "Groq"},
    "openrouter": {"tipo": "openai", "url": "https://openrouter.ai/api/v1",
                   "nombre": "OpenRouter"},
    "gemini": {"tipo": "openai",
               "url": "https://generativelanguage.googleapis.com/v1beta/openai",
               "nombre": "Gemini (OpenAI-compatible)"},
    "anthropic": {"tipo": "anthropic", "url": "https://api.anthropic.com", "nombre": "Anthropic"},
}

LOCALES = [("ollama", "http://localhost:11434/v1"), ("lmstudio", "http://localhost:1234/v1")]


@dataclass
class AjustesIA:
    proveedor: str = "local"
    url_base: str = ""
    modelo: str = ""
    clave: str | None = None
    timeout: float = 120.0
    origen: dict[str, str] = field(default_factory=dict)

    @property
    def tipo(self) -> str:
        return PROVEEDORES.get(self.proveedor, {}).get("tipo", "openai")

    @property
    def es_local(self) -> bool:
        url = self.url_base.lower()
        return any(h in url for h in ("localhost", "127.0.0.1", "0.0.0.0", "[::1]")) or (
            url.startswith("http://192.168.") or url.startswith("http://10.")
        )

    def clave_enmascarada(self) -> str:
        if not self.clave:
            return "—"
        if len(self.clave) <= 8:
            return "•" * len(self.clave)
        return f"{self.clave[:3]}…{self.clave[-4:]}"


def detectar_locales(timeout: float = 0.6) -> list[tuple[str, str, list[str]]]:
    """Servidores locales que responden: (proveedor, url, modelos)."""
    if os.environ.get("ULTRON_SIN_AUTODETECCION"):
        return []
    encontrados = []
    for proveedor, url in LOCALES:
        try:
            r = httpx.get(f"{url}/models", timeout=timeout)
            if r.status_code == 200:
                datos = r.json().get("data", [])
                encontrados.append((proveedor, url, [m.get("id", "") for m in datos]))
        except (httpx.HTTPError, ValueError):
            continue
    return encontrados


def resolver(
    *,
    proveedor: str | None = None,
    url: str | None = None,
    modelo: str | None = None,
    clave: str | None = None,
    autodetectar: bool = True,
) -> AjustesIA | None:
    """Combina las fuentes por prioridad. None si no hay nada configurado ni detectado."""
    archivo = config.leer().get("ia", {})
    entorno = {
        "proveedor": os.environ.get("ULTRON_PROVEEDOR"),
        "url_base": os.environ.get("ULTRON_URL_BASE"),
        "modelo": os.environ.get("ULTRON_MODELO"),
        "clave": os.environ.get("ULTRON_API_KEY"),
    }
    argumentos = {"proveedor": proveedor, "url_base": url, "modelo": modelo, "clave": clave}
    valores: dict[str, str | None] = {}
    origen: dict[str, str] = {}
    for campo in ("proveedor", "url_base", "modelo", "clave"):
        for fuente, datos in (("argumento", argumentos), ("entorno", entorno),
                              ("config", archivo)):
            valor = datos.get(campo)
            if valor:
                valores[campo] = str(valor)
                origen[campo] = fuente
                break

    if not valores.get("url_base") and valores.get("proveedor") in PROVEEDORES:
        valores["url_base"] = PROVEEDORES[valores["proveedor"]]["url"]
        origen["url_base"] = "proveedor"

    if not valores.get("url_base") and autodetectar:
        locales = detectar_locales()
        if locales:
            prov, url_local, modelos = locales[0]
            valores.setdefault("proveedor", prov)
            valores["url_base"] = url_local
            origen.setdefault("proveedor", "detectado")
            origen["url_base"] = "detectado"
            if not valores.get("modelo") and modelos:
                valores["modelo"] = modelos[0]
                origen["modelo"] = "detectado"

    if not valores.get("url_base"):
        return None
    timeout = float(archivo.get("timeout", 120))
    return AjustesIA(
        proveedor=valores.get("proveedor") or "local",
        url_base=valores["url_base"],
        modelo=valores.get("modelo") or "",
        clave=valores.get("clave"),
        timeout=timeout,
        origen=origen,
    )


def guardar(aj: AjustesIA) -> None:
    datos = config.leer()
    datos["ia"] = {
        "proveedor": aj.proveedor,
        "url_base": aj.url_base,
        "modelo": aj.modelo,
        "clave": aj.clave,
        "timeout": aj.timeout,
    }
    config.guardar(datos)
