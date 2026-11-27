"""Utilidades para modelos locales pequeños: troceado, map-reduce y JSON tolerante."""

from __future__ import annotations

import json
import re
from typing import Any

from ultron.ia import errores as E


def tokens_aprox(texto: str) -> int:
    return max(1, len(texto) // 4)


def trocear(texto: str, max_chars: int = 6000, solape: int = 300) -> list[str]:
    """Divide por párrafos sin pasar de max_chars, con un pequeño solape entre trozos."""
    texto = texto.strip()
    if not texto:
        return []
    if len(texto) <= max_chars:
        return [texto]
    parrafos: list[str] = []
    for p in re.split(r"\n\s*\n", texto):
        p = p.strip()
        while len(p) > max_chars:
            corte = p.rfind(" ", 0, max_chars)
            corte = corte if corte > max_chars // 2 else max_chars
            parrafos.append(p[:corte])
            p = p[corte:].strip()
        if p:
            parrafos.append(p)
    trozos: list[str] = []
    actual = ""
    for p in parrafos:
        if actual and len(actual) + len(p) + 2 > max_chars:
            trozos.append(actual)
            cola = actual[-solape:] if solape else ""
            actual = (cola + "\n\n" + p) if cola and len(cola) + len(p) + 2 <= max_chars else p
        else:
            actual = f"{actual}\n\n{p}" if actual else p
    if actual:
        trozos.append(actual)
    return trozos


_VALLA = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.S)
_COMA_FINAL = re.compile(r",\s*([}\]])")


def _equilibrado(texto: str) -> str | None:
    """Primer bloque {…} o […] equilibrado, respetando cadenas."""
    inicio = min((i for i in (texto.find("{"), texto.find("[")) if i >= 0), default=-1)
    if inicio < 0:
        return None
    pila: list[str] = []
    en_cadena: str | None = None
    escape = False
    pares = {"{": "}", "[": "]"}
    for i in range(inicio, len(texto)):
        c = texto[i]
        if en_cadena:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == en_cadena:
                en_cadena = None
            continue
        if c in "\"'":
            en_cadena = c
        elif c in pares:
            pila.append(pares[c])
        elif c in "}]":
            if not pila or pila.pop() != c:
                return None
            if not pila:
                return texto[inicio : i + 1]
    return texto[inicio:] if pila else None


def _intentos(candidato: str) -> list[str]:
    sin_comas = _COMA_FINAL.sub(r"\1", candidato)
    pythonico = re.sub(r"\bTrue\b", "true", sin_comas)
    pythonico = re.sub(r"\bFalse\b", "false", pythonico)
    pythonico = re.sub(r"\bNone\b", "null", pythonico)
    comillas = re.sub(r"(?<![\w\\])'([^'\\]*(?:\\.[^'\\]*)*)'", r'"\1"', pythonico)
    return [candidato, sin_comas, pythonico, comillas]


_PENSAMIENTO = re.compile(r"<(think|thinking|reasoning)>.*?(</\1>|$)", re.S | re.I)


def quitar_razonamiento(texto: str) -> str:
    """Quita el razonamiento de los modelos que «piensan» (Qwen 3, DeepSeek R1…)."""
    if not texto or "<" not in texto:
        return texto
    limpio = _PENSAMIENTO.sub("", texto)
    if "</think>" in limpio:  # bloque abierto antes del inicio de la respuesta
        limpio = limpio.split("</think>", 1)[1]
    return limpio.lstrip()


class FiltroRazonamiento:
    """Lo mismo, pero trozo a trozo mientras llega una respuesta en streaming."""

    def __init__(self) -> None:
        self.dentro = False
        self.pendiente = ""

    def __call__(self, trozo: str) -> str:
        texto, salida = self.pendiente + trozo, ""
        self.pendiente = ""
        while texto:
            if self.dentro:
                fin = re.search(r"</(think|thinking|reasoning)>", texto, re.I)
                if not fin:
                    self.pendiente = texto[-12:]
                    return salida
                texto, self.dentro = texto[fin.end():].lstrip("\n"), False
                continue
            ini = re.search(r"<(think|thinking|reasoning)>", texto, re.I)
            if ini:
                salida += texto[:ini.start()]
                texto, self.dentro = texto[ini.end():], True
                continue
            corte = texto.rfind("<")
            cola = texto[corte:].lower() if corte != -1 else ""
            if cola and any(e.startswith(cola) for e in ("<think>", "<thinking>",
                                                         "<reasoning>")):
                salida, self.pendiente = salida + texto[:corte], texto[corte:]
            else:
                salida += texto
            return salida
        return salida

    def final(self) -> str:
        """Lo que quedó retenido por si era el inicio de una etiqueta."""
        resto, self.pendiente = ("" if self.dentro else self.pendiente), ""
        return resto


def reparar_json(texto: str) -> Any:
    """Saca un JSON válido de lo que devuelva un modelo pequeño, o lanza RespuestaInvalida."""
    texto = quitar_razonamiento(texto) if isinstance(texto, str) else texto
    if not isinstance(texto, str) or not texto.strip():
        raise E.RespuestaInvalida("La IA ha devuelto una respuesta vacía.")
    fuentes = [m.group(1) for m in _VALLA.finditer(texto)] + [texto]
    for fuente in fuentes:
        fuente = fuente.strip()
        candidatos = [fuente]
        bloque = _equilibrado(fuente)
        if bloque:
            candidatos.insert(0, bloque)
        for cand in candidatos:
            for intento in _intentos(cand):
                try:
                    return json.loads(intento)
                except ValueError:
                    continue
            # JSON cortado: cerrar lo que falte
            cerrado = _cerrar(cand)
            if cerrado:
                try:
                    return json.loads(_COMA_FINAL.sub(r"\1", cerrado))
                except ValueError:
                    pass
    raise E.RespuestaInvalida("La IA no ha devuelto un JSON válido.",
                              "Prueba otra vez o con un modelo más grande.")


def _cerrar(texto: str) -> str | None:
    pila: list[str] = []
    en_cadena = False
    escape = False
    for c in texto:
        if en_cadena:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == '"':
                en_cadena = False
            continue
        if c == '"':
            en_cadena = True
        elif c in "{[":
            pila.append("}" if c == "{" else "]")
        elif c in "}]" and pila:
            pila.pop()
    if not pila:
        return None
    base = texto.rstrip().rstrip(",")
    if en_cadena:
        base += '"'
    return base + "".join(reversed(pila))


def pedir_json(
    prompt: str,
    esquema_ejemplo: Any,
    *,
    sistema: str | None = None,
    **kw: Any,
) -> Any:
    """Pide JSON a la IA; repara la respuesta y reintenta una vez si hace falta."""
    from ultron.ia.cliente import preguntar

    ejemplo = json.dumps(esquema_ejemplo, ensure_ascii=False)
    instruccion = f"{prompt}\n\nResponde únicamente con JSON con esta forma:\n{ejemplo}"
    respuesta = preguntar(instruccion, sistema=sistema, json=True, **kw)
    try:
        return reparar_json(respuesta)
    except E.RespuestaInvalida:
        respuesta = preguntar(
            instruccion + "\n\nIMPORTANTE: responde SOLO con JSON válido, sin texto alrededor.",
            sistema=sistema, json=True, **kw,
        )
        return reparar_json(respuesta)


def resumir_largo(
    texto: str,
    instruccion: str,
    *,
    max_chars: int = 6000,
    **kw: Any,
) -> str:
    """Map-reduce: resume cada trozo y después une los resúmenes."""
    from ultron.ia.cliente import preguntar

    trozos = trocear(texto, max_chars=max_chars)
    if not trozos:
        return ""
    if len(trozos) == 1:
        return preguntar(f"{instruccion}\n\nTEXTO:\n{trozos[0]}", **kw)
    parciales = [
        preguntar(f"Resume los puntos clave de este fragmento ({i}/{len(trozos)}). "
                  f"Sé breve.\n\nFRAGMENTO:\n{t}", **kw)
        for i, t in enumerate(trozos, 1)
    ]
    unido = "\n\n".join(parciales)
    if len(unido) > max_chars:
        return resumir_largo(unido, instruccion, max_chars=max_chars, **kw)
    return preguntar(f"{instruccion}\n\nRESÚMENES PARCIALES:\n{unido}", **kw)
