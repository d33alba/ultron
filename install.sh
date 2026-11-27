#!/usr/bin/env bash
# Instalador de Ultron.
#   bash install.sh          instala preguntando (modos e IA)
#   bash install.sh --si     instala todo sin preguntas (la IA se conecta después)
set -euo pipefail

main() {
    local origen="${BASH_SOURCE[0]:-}" proyecto sistema seleccion modo carpeta_bin
    local escritorio="${XDG_CURRENT_DESKTOP:-}"
    local repositorio="${ULTRON_REPO:-https://github.com/d33alba/ultron}"
    local si=0 entrada=/dev/null
    local -a modos=() opciones=()

    for argumento in "$@"; do
        case "$argumento" in
            --si|-y) si=1 ;;
            -h|--help) sed -n '2,4p' "$0"; return 0 ;;
        esac
    done
    if [[ $si == 0 ]] && { : </dev/tty; } 2>/dev/null; then
        entrada=/dev/tty
    else
        si=1
    fi

    sistema="$(awk -F= '$1 == "ID" {gsub(/"/, "", $2); print $2}' /etc/os-release 2>/dev/null || true)"
    if [[ "$sistema" != ubuntu ]]; then
        printf '%s\n' 'Aviso: Ultron está pensado para Ubuntu 24.04 o posterior.'
    fi
    if [[ "${escritorio^^}" != *GNOME* ]]; then
        printf '%s\n' 'Aviso: no se detecta una sesión GNOME (se puede instalar igualmente).'
    fi

    printf '%s\n' '== Ultron: paquetes base (pipx, GTK 4, Git) con sudo =='
    # shellcheck disable=SC2024
    sudo apt-get install -y pipx python3-gi gir1.2-gtk-4.0 git <"$entrada"

    if [[ -n "$origen" && -f "$(dirname -- "$origen")/pyproject.toml" ]]; then
        proyecto="$(cd -- "$(dirname -- "$origen")" && pwd)"
    else
        proyecto="git+$repositorio"
    fi
    printf '%s\n' '== Ultron: instalando el programa =='
    pipx install --force --system-site-packages "$proyecto" <"$entrada"
    pipx ensurepath <"$entrada" >/dev/null 2>&1 || true
    carpeta_bin="$(pipx environment --value PIPX_BIN_DIR)"
    export PATH="$carpeta_bin:$PATH"
    local ultron="$carpeta_bin/ultron"

    if [[ $si == 0 ]]; then
        while true; do
            printf '%s\n' 'Modos disponibles: netanyahu focus gaming presentacion fantasma.'
            printf '%s' 'Pulsa Intro para todos o escribe los identificadores separados por espacios: '
            read -r seleccion <"$entrada"
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
    fi
    printf '%s\n' '== Ultron: dependencias, extensiones, fuentes y recursos de los modos =='
    "$ultron" instalar --si "${opciones[@]}" <"$entrada"

    if [[ $si == 0 ]]; then
        if ! "$ultron" ia configurar <"$entrada"; then
            printf '%s\n' 'Configuración de IA pendiente. Puedes repetir: ultron ia configurar'
        fi
    fi
    "$ultron" doctor --completo <"$entrada" || true
    printf '\n%s\n' '== Listo =='
    printf '%s\n' '1. Cierra sesión y vuelve a entrar una vez (GNOME carga las extensiones).'
    printf '%s\n' '2. Conecta tu IA:  ultron ia configurar --url https://TU-SERVIDOR/v1 --modelo MODELO'
    printf '%s\n' '3. Abre Ultron con: ultron   (o Super+U)'
}
main "$@"
