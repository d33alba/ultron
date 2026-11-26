# Bloque 08: entrega, GitHub organizado, CI, instalador y documentación

## Objetivo
Que el profesor clone el repo, lo instale en un paso, configure su IA local y lo pruebe todo
sin atascarse. Que el repo se vea profesional y creativo.

## Instalador
- `install.sh` en la raíz (ejecutable y compatible con `shellcheck`):
  1. comprueba Ubuntu y GNOME (si no lo son, avisa y deja continuar);
  2. `sudo apt install -y pipx python3-gi gir1.2-gtk-4.0 git` (con aviso previo);
  3. `pipx install .`, o `pipx install git+https://github.com/<repo>` si se ejecuta con
     `curl | bash`;
  4. `pipx ensurepath`;
  5. ejecuta `ultron instalar` (pregunta si instala todos los modos o elige);
  6. lanza `ultron ia configurar`;
  7. imprime los pasos finales: cerrar sesión una vez, luego `ultron` o Super+U.
- `uninstall.sh`: `ultron desinstalar` seguido de `pipx uninstall ultron`.
- **Comprobación final** `ultron doctor --completo`: dependencias de cada modo, extensiones
  instaladas y activables, recursos y la IA. Al final, "Listo para corregir ✔" o la lista de
  lo que falta, con el comando exacto para arreglar cada cosa.

## Guía para el profesor: `ultron demo`
Recorrido guiado e interactivo: explica qué es Ultron y luego, para cada modo, ofrece
entrar, enseña 2 o 3 funciones con `--demo` (sin red ni IA si no hay) y espera a que se
pulse una tecla para pasar al siguiente. Al final, `salir` y "todo restaurado ✔". Opción
`--rapida` (3 minutos).

## README.md (en español; es lo primero que ve el profesor)
- Cabecera con un banner ASCII de ULTRON (en un bloque de código), un lema y badges (CI,
  Python, licencia, Ubuntu 24.04).
- **Capturas y GIFs** en `docs/media/` (las genera el script del punto siguiente; deja
  apuntados en el README los nombres esperados).
- "¿Qué es?" en 3 frases y una tabla de modos (glifo, nombre, estética, funciones
  estrella).
- **Instalación en 3 comandos**, "Configurar tu IA" (ejemplos para Ollama, LM Studio,
  vLLM y OpenAI, con una sección de "Problemas frecuentes" que remite a `ultron doctor`),
  "Primeros pasos" y "Deshacer todo".
- Arquitectura con un diagrama Mermaid (CLI → motor → capas → GNOME; IA modular).
- Seguridad y ética (OSINT y hacking ético, reversibilidad, sudo), créditos (God's Eye View,
  Yaru, las extensiones de GNOME con sus autores y licencias) y licencia MIT.

## `docs/`
- `docs/modos/<modo>.md`: un manual por modo (cada comando con un ejemplo y su salida).
- `docs/ia.md`: configuración detallada y tabla de errores.
- `docs/arquitectura.md`: capas, instantáneas, extensión y cómo crear un modo nuevo
  (`ultron modos nuevo <id>`: genera el esqueleto de un modo en
  `~/.local/share/ultron/modos/<id>` a partir de una plantilla; impleméntalo).
- `docs/desarrollo.md`: tests, CI y estructura.
- `specs/prompts-imagenes.md`: prompts listos para GPT Images. El fondo de Netanyahu
  (3840×2160, con estética de cartel de ciberinteligencia israelí, azul y blanco) y los 15
  iconos estrella (Firefox, Archivos, Terminal, Ajustes, Calculadora, Software, Editor de
  texto, Visor de imágenes, Música, Vídeos, Papelera, Correo, Calendario, Capturas y
  Tienda), con el estilo común "icono plano redondeado, azul `#0038B8` y blanco, estrella
  de David sutil, 512×512 y fondo transparente", y el nombre de archivo exacto de cada uno
  (el nombre de icono de freedesktop, por ejemplo `firefox.png` y
  `org.gnome.Calculator.png`).

## Capturas automáticas: `scripts/capturas.py`
Usa la grabación de Rich (`Console(record=True)`) para generar **SVG** de los comandos
`--demo` de cada modo (`modos`, `radar --demo`, `osint ip --demo`, `hud --demo --una-vez`,
`stats --demo`, `repasar --demo` y banners) en `docs/media/*.svg`, que GitHub muestra en el
README. Se ejecuta sin red ni IA. Genera también `docs/media/fondos/` a partir de los
generadores de fondos (a 1280×720).

## CI: `.github/workflows/ci.yml`
- **Job `tests`:** `ubuntu-24.04`, Python 3.10 y 3.12 en matriz, `pip install -e .[dev]`,
  `ruff check` y `pytest --cov`.
- **Job `simular`:** instala, `ultron modos`, `ultron entrar <m> --simular --si` y `ultron
  salir --simular` para cada modo, y `ultron doctor --sin-ia`.
- **Job `extension`:** valida `metadata.json` y hace `node --check` de `extension.js`.
- **Job `shellcheck`:** `install.sh` y `uninstall.sh`.
- **Job `capturas`:** ejecuta `scripts/capturas.py` y sube `docs/media` como artefacto.

## Organización del repo
`LICENSE` (MIT; los recursos de terceros con sus licencias en `docs/creditos.md`),
`CHANGELOG.md`, `.github/ISSUE_TEMPLATE/` (opcional) y `pyproject.toml` con metadatos
(descripción, keywords y URLs). Repasa que `.gitignore` está bien, que no haya archivos
grandes y que todo sigue la estructura de `AGENTS.md`.

## Revisión final del bloque
- Pasa todos los tests y ruff.
- Ejecuta `python -m ultron --help` y la ayuda de cada grupo, y repasa que **todos** los
  textos estén en español y sin faltas.
- Comprueba que los comandos documentados en el README existen de verdad (añade un test
  que procese el README y compare con los comandos registrados en Typer).
