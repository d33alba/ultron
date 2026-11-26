#!/usr/bin/env bash
# Construye Ultron bloque a bloque con Codex: implementa → tests → arreglos → commit.
# Uso: bash scripts/construir.sh [bloque_inicial]   (p. ej. 03 para reanudar)
set -uo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
cd "$RAIZ"
mkdir -p logs
PY=".venv/Scripts/python"; [ -x "$PY" ] || PY=".venv/bin/python"
INICIO="${1:-01}"
REINTENTOS=2

limite_agotado() { grep -qiE "usage limit|rate limit|quota|exceeded your|try again (in|at)" "$1"; }

ejecutar_codex() {  # $1 = prompt, $2 = log
  codex exec --approve-for-me --skip-git-repo-check -C "$RAIZ" \
    --color never -o "${2%.log}.final.md" - <<<"$1" >"$2" 2>&1
  local codigo=$?
  if limite_agotado "$2"; then
    echo "LIMITE_GPT log=$2" | tee logs/ESTADO; exit 3
  fi
  if [ $codigo -ne 0 ]; then
    echo "ERROR_CODEX codigo=$codigo log=$2" | tee logs/ESTADO; tail -n 20 "$2"; exit 4
  fi
}

pasar_tests() {  # $1 = archivo de salida
  { "$PY" -m ruff check ultron tests && "$PY" -m pytest -q -x --no-header; } >"$1" 2>&1
}

for SPEC in specs/0[1-8]-*.md; do
  NUM="$(basename "$SPEC" | cut -c1-2)"
  [[ "$NUM" < "$INICIO" ]] && continue
  echo "=== Bloque $NUM: $SPEC ($(date +%H:%M)) ===" | tee -a logs/progreso.txt

  PROMPT="Trabaja de forma autónoma y sin hacer preguntas.
Implementa POR COMPLETO el bloque descrito en $SPEC.
Antes de empezar lee AGENTS.md (contrato obligatorio), PLAN.md y specs/diseno-terminal.md,
y revisa el código de los bloques anteriores para integrarte sin romperlo.
No dejes TODOs, stubs ni funciones vacías: todo lo de la spec tiene que funcionar.
Añade los tests que pide la spec. Ejecuta '$PY -m ruff check ultron tests' y
'$PY -m pytest -q' y arregla hasta que pase TODO (también los tests de bloques anteriores).
No ejecutes pip install (no hay red; las dependencias ya están en .venv). No hagas git commit.
Al terminar, resume en 10 líneas: qué hiciste, qué no pudiste hacer y por qué."

  ejecutar_codex "$PROMPT" "logs/$NUM.log"
  if limite_agotado "logs/$NUM.log"; then
    echo "LIMITE_GPT bloque=$NUM" | tee logs/ESTADO; exit 3
  fi

  OK=0
  for i in $(seq 1 $REINTENTOS); do
    if pasar_tests "logs/$NUM.tests.txt"; then OK=1; break; fi
    echo "  tests fallan, arreglo $i" | tee -a logs/progreso.txt
    FALLO="$(tail -n 80 "logs/$NUM.tests.txt")"
    ejecutar_codex "Trabaja de forma autónoma. Los tests o ruff fallan tras implementar $SPEC.
Arregla el código (no borres ni debilites tests salvo que estén mal según la spec).
Salida del fallo:
$FALLO
No hagas git commit." "logs/$NUM.arreglo$i.log"
    if limite_agotado "logs/$NUM.arreglo$i.log"; then
      echo "LIMITE_GPT bloque=$NUM (arreglando)" | tee logs/ESTADO; exit 3
    fi
  done
  [ $OK -eq 1 ] || pasar_tests "logs/$NUM.tests.txt" && OK=1

  ESTADO_TESTS="tests OK"; [ $OK -eq 1 ] || ESTADO_TESTS="TESTS FALLANDO"
  git add -A
  git commit -q -m "Bloque $NUM: $(basename "$SPEC" .md) ($ESTADO_TESTS)

Implementado por Codex a partir de $SPEC.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" || true
  echo "  bloque $NUM terminado: $ESTADO_TESTS" | tee -a logs/progreso.txt
done

echo "COMPLETADO" | tee logs/ESTADO
