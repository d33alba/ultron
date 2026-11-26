#!/usr/bin/env bash
set -euo pipefail

main() {
    local origen="${BASH_SOURCE[0]:-}" proyecto sistema seleccion modo carpeta_bin
    local escritorio="${XDG_CURRENT_DESKTOP:-}"
    local repositorio="${ULTRON_REPO:-https://github.com/d33alba/ultron}"
    local -a modos=() opciones=()

    sistema="$(awk -F= '$1 == "ID" {gsub(/"/, "", $2); print $2}' /etc/os-release 2>/dev/null || true)"
    if [[ "$sistema" != ubuntu ]]; then
        printf '%s\n' 'Aviso: Ultron está pensado para Ubuntu 24.04 o posterior.'
    fi
    if [[ "${escritorio^^}" != *GNOME* ]]; then
        printf '%s\n' 'Aviso: no se detecta una sesión GNOME.'
    fi

    printf '%s\n' 'Se usará sudo para instalar pipx, GTK 4 y Git.'
    # La entrada viene de la terminal a propósito (instalación con curl | bash).
    # shellcheck disable=SC2024
    sudo apt install -y pipx python3-gi gir1.2-gtk-4.0 git </dev/tty

    if [[ -n "$origen" ]]; then
        proyecto="$(cd -- "$(dirname -- "$origen")" && pwd)"
    else
        proyecto="git+$repositorio"
    fi
    pipx install --system-site-packages "$proyecto" </dev/tty
    pipx ensurepath </dev/tty
    carpeta_bin="$(pipx environment --value PIPX_BIN_DIR)"
    export PATH="$carpeta_bin:$PATH"
    local ultron="$carpeta_bin/ultron"

    while true; do
        printf '%s\n' 'Modos disponibles: netanyahu focus gaming presentacion fantasma.'
        printf '%s' 'Pulsa Intro para todos o escribe los identificadores separados por espacios: '
        read -r seleccion </dev/tty
        read -r -a modos <<< "$seleccion"
        opciones=()
        for modo in "${modos[@]}"; do
            case "$modo" in
                netanyahu|focus|gaming|presentacion|fantasma) opciones+=(--modo "$modo") ;;
                *) printf 'Modo desconocido: %s\n' "$modo"; break ;;
            esac
        done
        if (( ${#opciones[@]} == 2 * ${#modos[@]} )); then
            break
        fi
    done
    "$ultron" instalar "${opciones[@]}" </dev/tty
    if ! "$ultron" ia configurar </dev/tty; then
        printf '%s\n' 'Configuración de IA pendiente. Puedes repetir ultron ia configurar.'
    fi
    if ! "$ultron" doctor --completo </dev/tty; then
        printf '%s\n' 'Revisa los requisitos pendientes que indica el diagnóstico.'
    fi
    printf '%s\n' 'Cierra sesión y vuelve a entrar una vez. Abre Ultron con ultron o Super+U.'
    printf '%s\n' 'En la nueva sesión, comprueba la entrega con ultron doctor --completo.'
}
main "$@"
