# Desarrollo

El proyecto requiere Python 3.10 o posterior. Las pruebas de lógica se ejecutan en Windows
y Ubuntu. Las capas de escritorio requieren una sesión Ubuntu con GNOME.

```bash
python -m pip install -e '.[dev]'
python -m ruff check ultron tests scripts/capturas.py
python -m pytest --cov=ultron
python scripts/capturas.py
```

En Windows, con las dependencias disponibles, usa `.venv/Scripts/python` en lugar de
`python`. Si la consola usa una página de códigos antigua, activa `PYTHONUTF8=1`.
Los tests usan un directorio XDG temporal y un ejecutor falso para las operaciones de sistema.

- `ultron/nucleo/` contiene el motor, el registro y los diagnósticos.
- `ultron/capas/`, `ultron/ia/`, `ultron/ui/` y `ultron/modos/` contienen la
  integración con GNOME, la IA, la terminal y las funciones de cada modo.
- `extension/` contiene el código de GNOME Shell y `specs/` los contratos de cada bloque.
- `tests/` contiene pruebas de lógica, CLI, diagnóstico y reversibilidad.

GitHub Actions ejecuta la matriz de Python en Ubuntu 24.04, prueba las simulaciones,
valida la extensión y los scripts Bash, y publica `docs/media/` como artefacto.
Para revisar las capas visuales y el retorno al escritorio inicial, usa una sesión
Ubuntu GNOME y ejecuta `ultron demo` y `ultron doctor --completo`.
