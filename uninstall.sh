#!/usr/bin/env bash
set -euo pipefail

carpeta_bin="$(pipx environment --value PIPX_BIN_DIR)"
"$carpeta_bin/ultron" desinstalar
pipx uninstall ultron
