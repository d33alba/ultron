#!/usr/bin/env bash
# Prepara Ultron en la máquina virtual de pruebas. Se ejecuta UNA vez dentro de Ubuntu:
#   bash /media/sf_ultron/scripts/vm-preparar.sh
# Copia el proyecto desde la carpeta compartida de VirtualBox, instala todo sin preguntas
# y deja Ultron listo. Pide la contraseña de sudo una sola vez.
set -euo pipefail

origen=/media/sf_ultron
if [[ ! -d "$origen" ]]; then
    origen="$(find /media -maxdepth 1 -name 'sf_*' -print -quit 2>/dev/null || true)"
fi
if [[ -z "$origen" || ! -d "$origen" ]]; then
    printf '%s\n' 'No encuentro la carpeta compartida (Dispositivos → Carpetas compartidas).' >&2
    exit 1
fi

printf '%s\n' '== Ultron: preparando la máquina virtual de pruebas =='
sudo -v
sudo usermod -aG vboxsf "$USER" || true
sudo apt-get update -q
sudo apt-get install -y -q pipx python3-gi gir1.2-gtk-4.0 git rsync curl

sudo rsync -a --delete --exclude '.venv' --exclude '.worktrees' --exclude 'logs' \
    --exclude '__pycache__' --exclude '.git' "$origen"/ "$HOME/ultron/"
sudo chown -R "$USER:$USER" "$HOME/ultron"

pipx install --force --system-site-packages "$HOME/ultron"
pipx ensurepath
export PATH="$HOME/.local/bin:$PATH"

ultron instalar --si
ultron doctor --completo --sin-ia || true

printf '\n%s\n' '== Listo. Cierra sesión y vuelve a entrar una vez (para las extensiones). =='
