"""Empaqueta en el USB las herramientas apt que Ultron necesita, para instalarlas SIN sudo.

En un PC sin administrador ni internet no se puede usar apt. Este script (se ejecuta en un
equipo con internet) resuelve las dependencias de cada paquete contra lo que ya trae la
instalación de referencia (el manifiesto de la ISO de Kubuntu/Ubuntu 22.04) y descarga los
.deb que faltan desde archive.ubuntu.com, comprobando su SHA256. En el PC del centro,
`ultron instalar` los desempaqueta en ~/.local/share/ultron/sistema con `dpkg-deb -x`.

Uso: python scripts/preparar_herramientas.py DESTINO --manifiesto filesystem.manifest
"""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import re
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

ESPEJO = "http://archive.ubuntu.com/ubuntu"
SERIE = "jammy"
BOLSILLOS = [f"{SERIE}-security", f"{SERIE}-updates", SERIE]  # el primero que lo tenga gana
COMPONENTES = ["main", "universe", "restricted", "multiverse"]


def _bajar(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as r:  # noqa: S310 (URL fija de Ubuntu)
        return r.read()


def _orden_letra(c: str) -> int:
    """Orden de dpkg: ~ antes que el final, letras antes que el resto de signos."""
    if c == "~":
        return -1
    if c.isalpha():
        return ord(c)
    return ord(c) + 256


def _clave_version(v: str) -> list:
    """Clave de orden de versiones Debian (época, partes alternas de texto y números)."""
    epoca, _, resto = v.rpartition(":") if ":" in v else ("0", "", v)
    clave: list = [int(epoca or 0)]
    for trozo in re.findall(r"\d+|\D+", resto):
        if trozo.isdigit():
            clave.append((1, int(trozo)))
        else:
            clave.append((0, [_orden_letra(c) for c in trozo] + [0]))
    clave.append((0, [0]))  # final: mayor que "~", menor que cualquier letra
    return clave


def indices(cache: Path) -> dict[str, dict]:
    """Paquetes disponibles (amd64 + all): nombre -> campos del más reciente."""
    paquetes: dict[str, dict] = {}
    for bolsillo in BOLSILLOS:
        for comp in COMPONENTES:
            archivo = cache / f"{bolsillo}-{comp}.Packages"
            if not archivo.exists():
                url = f"{ESPEJO}/dists/{bolsillo}/{comp}/binary-amd64/Packages.xz"
                archivo.write_bytes(lzma.decompress(_bajar(url)))
            for bloque in archivo.read_text(encoding="utf-8", errors="ignore").split("\n\n"):
                campos = _campos(bloque)
                nombre = campos.get("Package")
                if not nombre:
                    continue
                previo = paquetes.get(nombre)
                if previo is None or _clave_version(campos["Version"]) > \
                        _clave_version(previo["Version"]):
                    paquetes[nombre] = campos
    return paquetes


def _campos(bloque: str) -> dict[str, str]:
    campos: dict[str, str] = {}
    clave = ""
    for linea in bloque.splitlines():
        if linea.startswith((" ", "\t")) and clave:
            campos[clave] += "\n" + linea.strip()
        elif ":" in linea:
            clave, _, valor = linea.partition(":")
            campos[clave] = valor.strip()
    return campos


def proveedores(paquetes: dict[str, dict]) -> dict[str, list[str]]:
    prov: dict[str, list[str]] = {}
    for nombre, c in paquetes.items():
        for p in c.get("Provides", "").split(","):
            p = p.strip().split(" ")[0]
            if p:
                prov.setdefault(p, []).append(nombre)
    return prov


def instalados(manifiesto: Path, quitar: Path | None) -> set[str]:
    nombres = {ln.split()[0].split(":")[0] for ln in manifiesto.read_text().splitlines()
               if ln.strip()}
    if quitar and quitar.exists():
        nombres -= {ln.split()[0].split(":")[0] for ln in quitar.read_text().splitlines()
                    if ln.strip()}
    return nombres


def resolver(pedidos: list[str], paquetes: dict, prov: dict, base: set[str]) -> dict:
    """Para cada paquete pedido, el conjunto de .deb que falta en el sistema base."""
    satisfechos = set(base)
    for nombre in list(base):  # lo que proveen los instalados también cuenta
        for p in paquetes.get(nombre, {}).get("Provides", "").split(","):
            if p.strip():
                satisfechos.add(p.strip().split(" ")[0])

    def cierre(raiz: str) -> list[str]:
        pendientes, vistos = [raiz], []
        while pendientes:
            nombre = pendientes.pop()
            if nombre in satisfechos or nombre in vistos:
                continue
            if nombre not in paquetes:
                reales = [p for p in prov.get(nombre, []) if p in paquetes]
                if not reales:
                    raise KeyError(f"{raiz}: no encuentro {nombre}")
                if any(r in satisfechos or r in vistos for r in reales):
                    continue
                nombre = reales[0]
                if nombre in vistos:
                    continue
            vistos.append(nombre)
            c = paquetes[nombre]
            deps = ",".join(filter(None, [c.get("Pre-Depends", ""), c.get("Depends", "")]))
            for dep in deps.split(","):
                opciones = [o.strip().split(" ")[0].split(":")[0] for o in dep.split("|")]
                opciones = [o for o in opciones if o]
                if not opciones:
                    continue
                if any(o in satisfechos or o in vistos for o in opciones):
                    continue
                elegida = next((o for o in opciones if o in paquetes or o in prov), opciones[0])
                pendientes.append(elegida)
        return vistos

    return {p: cierre(p) for p in pedidos}


def descargar(nombres: set[str], paquetes: dict, destino: Path) -> int:
    total = 0
    for nombre in sorted(nombres):
        c = paquetes[nombre]
        archivo = destino / Path(c["Filename"]).name
        if not archivo.exists() or hashlib.sha256(archivo.read_bytes()).hexdigest() != c["SHA256"]:
            datos = _bajar(f"{ESPEJO}/{c['Filename']}")
            if hashlib.sha256(datos).hexdigest() != c["SHA256"]:
                raise ValueError(f"SHA256 incorrecto: {nombre}")
            archivo.write_bytes(datos)
        total += archivo.stat().st_size
    return total


def main() -> None:
    from ultron.nucleo.herramientas import empaquetables

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("destino", type=Path, help="Carpeta offline/ del USB")
    ap.add_argument("--manifiesto", type=Path, required=True)
    ap.add_argument("--quitar", type=Path, help="filesystem.manifest-remove de la ISO")
    ap.add_argument("--cache", type=Path, default=Path.home() / ".cache" / "ultron-debs")
    a = ap.parse_args()
    a.cache.mkdir(parents=True, exist_ok=True)
    destino = a.destino / "debs"
    destino.mkdir(parents=True, exist_ok=True)

    paquetes = indices(a.cache)
    base = instalados(a.manifiesto, a.quitar)
    pedidos = [p for p in empaquetables() if p not in base]
    cierres = resolver(pedidos, paquetes, proveedores(paquetes), base)
    todos = {n for lista in cierres.values() for n in lista}
    tam = descargar(todos, paquetes, destino)
    lista = {p: [Path(paquetes[n]["Filename"]).name for n in ns] for p, ns in cierres.items()}
    (destino / "lista.json").write_text(json.dumps(lista, indent=1, ensure_ascii=False),
                                        encoding="utf-8")
    sobran = {f.name for f in destino.glob("*.deb")} - \
        {Path(paquetes[n]["Filename"]).name for n in todos}
    for nombre in sobran:
        (destino / nombre).unlink()
    print(f"{len(pedidos)} paquetes, {len(todos)} .deb, {tam / 1e6:.0f} MB en {destino}")
    for p, ns in sorted(cierres.items(), key=lambda x: -len(x[1])):
        print(f"  {p}: {len(ns)}")


if __name__ == "__main__":
    main()
