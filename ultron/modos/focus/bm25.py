"""Búsqueda BM25 sin embeddings, con un stemming muy básico para español."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter

PARADAS = set("""
a al algo algunas algunos ante antes como con contra cual cuando de del desde donde durante e
el ella ellas ellos en entre era es esa esas ese eso esos esta estas este esto estos fue ha
hay la las le les lo los mas me mi mis muy ni no nos o os para pero por que se ser si sin
sobre su sus tambien te tiene tu un una uno unos y ya the of and to in is it that for on
""".split())

SUFIJOS = sorted("""
amientos imientos aciones iciones amiento imiento mente acion icion ancia encia idades idad
ismos ismo istas ista ables ibles able ible adoras adores adora ador ando iendo ados idos
adas idas ado ido ada ida es as os s
""".split(), key=len, reverse=True)


def normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in sin_tildes if not unicodedata.combining(c) or c == "̃")


def raiz(palabra: str) -> str:
    for sufijo in SUFIJOS:
        if palabra.endswith(sufijo) and len(palabra) - len(sufijo) >= 3:
            return palabra[: -len(sufijo)]
    return palabra


def tokens(texto: str) -> list[str]:
    palabras = re.findall(r"[a-z0-9ñ]+", normalizar(texto))
    return [raiz(p) for p in palabras if p not in PARADAS and len(p) > 1]


class BM25:
    def __init__(self, documentos: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b = k1, b
        self.docs = [Counter(tokens(d)) for d in documentos]
        self.largos = [sum(c.values()) for c in self.docs]
        self.media = (sum(self.largos) / len(self.largos)) if self.largos else 0
        df: Counter[str] = Counter()
        for c in self.docs:
            df.update(c.keys())
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def puntuar(self, consulta: str) -> list[tuple[int, float]]:
        terminos = tokens(consulta)
        resultados = []
        for i, c in enumerate(self.docs):
            puntos = 0.0
            for t in terminos:
                if t not in c:
                    continue
                f = c[t]
                norma = 1 - self.b + self.b * self.largos[i] / (self.media or 1)
                puntos += self.idf[t] * f * (self.k1 + 1) / (f + self.k1 * norma)
            if puntos > 0:
                resultados.append((i, puntos))
        return sorted(resultados, key=lambda x: -x[1])


def trozos(paginas: list[tuple[int, str]], tam: int = 800) -> list[tuple[int, str]]:
    """Divide cada página en trozos de ~tam caracteres, conservando el número de página."""
    salida = []
    for numero, texto in paginas:
        texto = re.sub(r"\s+", " ", texto).strip()
        for i in range(0, len(texto), tam):
            trozo = texto[i : i + tam]
            if trozo.strip():
                salida.append((numero, trozo))
    return salida


def mejores(paginas: list[tuple[int, str]], consulta: str, n: int = 4) -> list[tuple[int, str]]:
    partes = trozos(paginas)
    if not partes:
        return []
    indice = BM25([t for _, t in partes])
    return [partes[i] for i, _ in indice.puntuar(consulta)[:n]]
