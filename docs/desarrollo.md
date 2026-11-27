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

## Banco de pruebas con funciones reales

Desde la raíz del repositorio, usa un Python que pueda ejecutar `python -m ultron`. El [banco de pruebas](../scripts/probar_funciones.py) lanza comandos reales de los cinco modos. Prepara apuntes, un PDF, una foto con GPS, un correo y otros materiales en una carpeta temporal cuya ruta imprime al terminar.

```bash
python3 scripts/probar_funciones.py
python3 scripts/probar_funciones.py --solo "osint imagen"
python3 scripts/probar_funciones.py --ia
```

`--solo` filtra por texto de la orden. `--ia` indica que ya hay un modelo configurado y se espera una respuesta normal. Sin esa opción también se acepta el aviso de configuración pendiente. Usa una cuenta de prueba en Ubuntu para la pasada completa. Algunos casos consultan servicios externos, examinan el equipo o escriben datos de usuario, como eventos del plan de estudio.

Cada fila muestra el comando, la duración y el resultado. Una traza de Python o un código inesperado dan **FALLO**. Agotar el tiempo da **LENTO**, salvo en las funciones interactivas, donde el corte previsto permite comprobar el arranque. El proceso termina con código 1 si algún caso queda sin aprobar.
