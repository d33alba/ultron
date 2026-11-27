"""Prepara un USB para instalar Ultron sin sudo y sin internet (p. ej. en el PC del centro).

Uso (en un equipo con internet):
    python scripts/preparar_usb.py E:/Ultron --datos datos-linux.tar.gz

`--datos` es el paquete de Linux con la voz Piper, Node 24 y el Ojo de Dios ya compilado
(se construye en cualquier Ubuntu con scripts/construir_datos.sh).
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

PYTHONS = ["3.10", "3.11", "3.12", "3.13"]
GNOME = ["42", "46"]


def _pip(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "pip", *args], check=True)


def rueda_ultron(destino: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        _pip("install", "--quiet", "--target", tmp, "hatchling")
        codigo = (f"import sys; sys.path.insert(0, {tmp!r}); import os; "
                  f"os.chdir({str(RAIZ)!r}); from hatchling.build import build_wheel; "
                  f"print(build_wheel({str(destino)!r}))")
        subprocess.run([sys.executable, "-c", codigo], check=True)


def dependencias(destino: Path) -> None:
    rueda = next(destino.glob("ultron-*.whl"))
    for version in PYTHONS:
        # pip evalúa los marcadores con el Python de este equipo: tomli (solo 3.10) va aparte
        extra = ["tomli>=2"] if version == "3.10" else []
        _pip("download", "--quiet", "--dest", str(destino), "--only-binary=:all:",
             "--platform", "manylinux2014_x86_64", "--platform", "manylinux_2_28_x86_64",
             "--python-version", version, "--implementation", "cp", str(rueda), *extra)
    _pip("download", "--quiet", "--dest", str(destino), "--only-binary=:all:", "--no-deps",
         "pip")
    podar(destino)


def podar(destino: Path) -> list[str]:
    """Quita las versiones nuevas que exigen Python > 3.10 cuando hay otra que vale para
    todos: con --find-links, pip elige la más alta y luego la rechaza (Ubuntu 22.04)."""
    import re
    import zipfile

    def requiere(rueda: Path) -> str:
        with zipfile.ZipFile(rueda) as z:
            meta = next(n for n in z.namelist() if n.endswith(".dist-info/METADATA"))
            texto = z.read(meta).decode("utf-8", "replace")
        m = re.search(r"^Requires-Python:\s*(.+)$", texto, re.M)
        return m.group(1).strip() if m else ""

    por_proyecto: dict[str, list[Path]] = {}
    for rueda in destino.glob("*-none-any.whl"):
        por_proyecto.setdefault(rueda.name.split("-")[0].lower(), []).append(rueda)
    quitadas = []
    for ruedas in por_proyecto.values():
        validas = [r for r in ruedas if not re.search(r">=\s*3\.1[1-9]", requiere(r))]
        if validas and len(validas) < len(ruedas):
            for r in set(ruedas) - set(validas):
                r.unlink()
                quitadas.append(r.name)
    return quitadas


def extensiones(destino: Path) -> None:
    import httpx

    from ultron.compartidas.instalacion import descargar_extension
    from ultron.nucleo import dependencias as deps

    with httpx.Client(timeout=60, follow_redirects=True) as cliente:
        for version in GNOME:
            for uuid in deps.plan().extensiones:
                try:
                    descargar_extension(uuid, version, destino / version, cliente)
                except Exception as e:  # noqa: BLE001
                    print(f"  (sin {uuid} para GNOME {version}: {e})")


def fuentes(destino: Path) -> None:
    import httpx

    from ultron.nucleo import dependencias as deps

    destino.mkdir(parents=True, exist_ok=True)
    for nombre, url in deps.FUENTES.items():
        r = httpx.get(url, timeout=60, follow_redirects=True)
        r.raise_for_status()
        (destino / f"{nombre}.ttf").write_bytes(r.content)


def copiar_lf(origen: Path, destino: Path) -> None:
    destino.write_bytes(origen.read_bytes().replace(b"\r\n", b"\n"))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("destino", type=Path)
    p.add_argument("--datos", type=Path, help="datos-linux.tar.gz (voz, Node y Ojo)")
    a = p.parse_args()
    offline = a.destino / "offline"
    ruedas = offline / "ruedas"
    if ruedas.exists():
        shutil.rmtree(ruedas)
    ruedas.mkdir(parents=True)
    print("· programa");      rueda_ultron(ruedas)  # noqa: E702
    print("· dependencias");  dependencias(ruedas)  # noqa: E702
    print("· extensiones");   extensiones(offline / "extensiones")  # noqa: E702
    print("· fuentes");       fuentes(offline / "fuentes")  # noqa: E702
    if a.datos:
        (offline / "datos").mkdir(exist_ok=True)
        shutil.copy2(a.datos, offline / "datos" / a.datos.name)
    copiar_lf(RAIZ / "instalar-usb.sh", a.destino / "instalar-usb.sh")
    copiar_lf(RAIZ / "scripts" / "LEEME-USB.txt", a.destino / "LEEME.txt")
    print(f"USB listo en {a.destino}")


if __name__ == "__main__":
    main()
