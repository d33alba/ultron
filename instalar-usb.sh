#!/usr/bin/env bash
# Instala Ultron desde un USB preparado con scripts/preparar_usb.py:
#   - sin sudo (no hace falta ser administrador)
#   - sin internet (todo viene en la carpeta offline/ del USB)
#   - en Ubuntu 22.04 o posterior, con GNOME o KDE Plasma
# Uso: bash instalar-usb.sh
set -euo pipefail

aqui="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
offline="${ULTRON_OFFLINE:-$aqui/offline}"
datos="${XDG_DATA_HOME:-$HOME/.local/share}/ultron"
entorno="$datos/venv"
bin="$HOME/.local/bin"

paso() { printf '\n\033[1;36m== %s ==\033[0m\n' "$*"; }
falla() { printf '\033[1;31m%s\033[0m\n' "$*" >&2; exit 1; }

[[ -d "$offline/ruedas" ]] || falla "No encuentro $offline/ruedas. ¿Es el USB preparado?"
command -v python3 >/dev/null || falla "Falta python3 en este equipo."
python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' \
    || falla "Ultron necesita Python 3.10 o posterior."

paso "Ultron · instalación sin sudo y sin internet ($(python3 --version))"
mkdir -p "$datos" "$bin"
rm -rf "$entorno"
python3 -m venv --without-pip --system-site-packages "$entorno"

paso "Instalando el programa (desde el USB)"
pip_rueda="$(ls "$offline"/ruedas/pip-*.whl | head -1)"
"$entorno/bin/python" "$pip_rueda/pip" install --quiet --no-index --ignore-installed \
    --disable-pip-version-check --find-links "$offline/ruedas" "$offline"/ruedas/ultron-*.whl
ln -sf "$entorno/bin/ultron" "$bin/ultron"
export PATH="$bin:$PATH"
if ! grep -q 'ULTRON-PATH' "$HOME/.bashrc" 2>/dev/null; then
    printf '\nexport PATH="$HOME/.local/bin:$PATH"  # ULTRON-PATH\n' >> "$HOME/.bashrc"
fi

paso "Voz de ULTRON, Node 24 y Ojo de Dios (ya preparados en el USB)"
for paquete in "$offline"/datos/*.tar.gz; do
    [[ -e "$paquete" ]] || continue
    tar -xzf "$paquete" -C "$datos"
done

paso "Temas, iconos, fuentes, lanzadores y atajo"
ULTRON_OFFLINE="$offline" ultron instalar --si --sin-apt

paso "Comprobación"
ultron doctor || true

printf '\n\033[1;32m== Ultron instalado ==\033[0m\n'
printf '%s\n' "1. Abre una terminal nueva (o escribe: export PATH=\"\$HOME/.local/bin:\$PATH\")."
printf '%s\n' "2. Escribe: ultron     (o busca «Ultron NEXUS» en el menú; en KDE, Meta+U tras reiniciar sesión)"
printf '%s\n' "3. Prueba un modo:  ultron entrar netanyahu     y para volver:  ultron salir"
printf '%s\n' "4. IA del centro:   ultron ia configurar --url https://SERVIDOR/v1 --modelo MODELO"
