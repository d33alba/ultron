"""Base de datos de estudio (SQLite): documentos, tarjetas, revisiones, sesiones, exámenes."""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

from ultron.nucleo import rutas

ESQUEMA = """
create table if not exists documentos(
  hash text primary key, ruta text, nombre text, paginas integer, creado text);
create table if not exists cache_ia(clave text primary key, valor text, creado text);
create table if not exists tarjetas(
  id integer primary key, mazo text, pregunta text, respuesta text, pagina integer,
  facilidad real default 2.5, intervalo integer default 0, repeticiones integer default 0,
  proxima text, creado text);
create table if not exists revisiones(
  id integer primary key, tarjeta integer, nota integer, fecha text);
create table if not exists sesiones(
  id integer primary key, asignatura text, inicio text, minutos real);
create table if not exists examenes(
  id integer primary key, asignatura text, fecha text, temas text, horas real,
  tipo text default 'examen');
"""


def ruta() -> Path:
    return rutas.datos() / "focus" / "focus.db"


def conectar() -> sqlite3.Connection:
    destino = ruta()
    destino.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(destino)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def hash_archivo(archivo: Path) -> str:
    h = hashlib.sha256()
    with open(archivo, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 16), b""):
            h.update(bloque)
    return h.hexdigest()[:20]


def cache_leer(clave: str) -> str | None:
    with conectar() as con:
        fila = con.execute("select valor from cache_ia where clave = ?", (clave,)).fetchone()
    return fila["valor"] if fila else None


def cache_guardar(clave: str, valor: str) -> None:
    with conectar() as con:
        con.execute("insert or replace into cache_ia values (?, ?, ?)", (clave, valor, ahora()))
