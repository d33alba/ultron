# Bloque 05: modo FOCUS (estudio) + `ultron ordenar` (compartida)

## Objetivo
Un modo de estudio **útil de verdad**, con una estética limpia y de concentración. La IA
trabaja con PDF y apuntes, y funciona bien con **modelos locales pequeños** (map-reduce,
prompts cortos, JSON reparado).

## `modo.yaml` (estética)
- **terminal:** fondo `#1E1F22`, texto `#C8C8C8`, paleta suave, Inter/JetBrains Mono y sin
  transparencia.
- **escritorio:** fondo **generado** (`generar_recursos.py`) gris cálido liso con una línea
  fina y la frase del día en tipografía ligera; esquema oscuro suave, acento `slate` o
  `teal`, animaciones desactivadas y tema GTK y del shell generados con poco contraste.
- **iconos:** `monocromo: true` (escala de grises con un ligero tono salvia `#8FBC8F` en las
  carpetas).
- **sistema:** notificaciones desactivadas, luz nocturna y escala de texto de 1,05.
- **extensiones:** desactivar las de animación (si estaban activas por gaming); `user-theme`.
- **widgets:** Conky mínimo con la hora grande, el pomodoro y el siguiente examen con su
  cuenta atrás.
- **sonido:** sonido de campana suave al acabar el pomodoro (generado). Sin música.
- **dependencias:** `pandoc` (opcional), `poppler-utils` (`pdftotext` como respaldo) y
  `tesseract-ocr` + `tesseract-ocr-spa` (opcional para PDF escaneados).

## Biblioteca de estudio
Todo se guarda en `~/.local/share/ultron/focus/` (una base de datos SQLite
`focus.db` con las tablas `documentos`, `tarjetas`, `revisiones`, `sesiones`, `examenes` y
`tareas`). Los documentos procesados se cachean por hash, así que no se repiten las
llamadas a la IA.

## Extracción de texto (`modos/focus/extraer.py`)
PDF con pypdf (página a página, conservando el número de página), con `pdftotext -layout`
como respaldo. Si una página tiene menos de 30 caracteres y existe `tesseract`, se hace OCR
(convirtiendo con `pdftoppm`). También admite `.txt`, `.md` y `.docx` (descomprimiendo
`word/document.xml`, sin dependencias nuevas). Devuelve `[(pagina, texto)]`.

## Comandos
- **`ultron resumen <archivo> [--nivel corto|medio|esquema] [--guardar]`:**
  - map-reduce por trozos (`ia.util.resumir_largo`);
  - el nivel `esquema` saca títulos, viñetas y conceptos clave en **negrita**;
  - se muestra en un panel con el tema; `--guardar` crea `<archivo>.resumen.md` al lado.
- **`ultron flashcards <archivo> [--n 20] [--anki salida.apkg]`:**
  - la IA genera `[{pregunta, respuesta, pagina}]` por trozo, se deduplican por similitud
    simple (difflib) y se guardan en la base de datos con el mazo = nombre del archivo;
  - `--anki` exporta con genanki (modelo básico y una etiqueta por documento);
  - `ultron flashcards lista`, `borrar <mazo>` y `exportar <mazo>`.
- **`ultron repasar [mazo]`:**
  - repaso en la terminal con **SM-2**: enseña la pregunta, `espacio` muestra la respuesta,
    se puntúa con `1-4` (otra vez, difícil, bien, fácil);
  - interfaz limpia centrada y barra de progreso de la sesión;
  - al acabar: estadísticas, siguiente repaso y racha. Funciona **sin IA**.
- **`ultron examen <archivo> [--n 10] [--tipo test|corta|mixto]`:**
  - la IA genera las preguntas (test con 4 opciones y la correcta, o respuesta corta con
    la respuesta modelo);
  - se responde en la terminal; en las cortas, la IA corrige con una nota de 0 a 10 y un
    comentario;
  - nota final, preguntas falladas con la página del PDF, y las falladas pasan a tarjetas.
- **`ultron pregunta <archivo> "<duda>"`:**
  - recuperación sin embeddings: BM25 sencillo implementado a mano sobre trozos de unos
    800 caracteres, con stemming muy básico en español (quitar sufijos frecuentes);
  - se pasan los 4 mejores trozos a la IA, que responde citando `[p. 12]`.
- **`ultron esquema <archivo> [--png salida.png]`:**
  - la IA devuelve un árbol JSON de conceptos (máximo 3 niveles);
  - se pinta como árbol de Rich con el estilo del modo;
  - `--png` lo dibuja con Pillow (cajas y líneas, layout de árbol horizontal) y `--mermaid`
    saca el diagrama en Mermaid.
- **`ultron explica "<concepto>" [--nivel 1|2|3|todos]`:** explicación simple (para un niño
  de 12 años), normal y experta, con un ejemplo y una pregunta de comprobación.
- **`ultron plan`:**
  - añadir o quitar exámenes y entregas (`ultron plan añadir "Matemáticas" 2026-12-10
    --temas "derivadas, integrales" --horas 6`);
  - genera un **plan día a día** hasta cada fecha con un algoritmo propio (no hace falta
    IA): reparte las horas, con repasos espaciados a 1, 3 y 7 días y más carga los dos días
    anteriores;
  - `ultron plan hoy` dice lo que toca hoy;
  - `ultron plan ver` enseña un calendario en la terminal con colores por asignatura y una
    cuenta atrás;
  - `--ia` ajusta o explica el plan.
- **`ultron pomodoro [--min 25 --descanso 5 --ciclos 4] [--asignatura X]`:**
  - temporizador grande en ASCII (dígitos de 5 líneas) centrado y anillo de progreso con
    `○◔◑◕●`;
  - actualiza `panel.json`, de modo que se ve en la barra superior y en el prompt;
  - bloquea webs durante el trabajo (la lista se puede editar con `ultron pomodoro webs
    añadir|quitar`; por defecto youtube, tiktok, instagram, x, twitter, reddit, twitch y
    netflix) usando la capa `sistema` (bloque de hosts), y las desbloquea en el descanso
    y al final (también con Ctrl+C);
  - sonido de campana;
  - registra la sesión en la base de datos.
- **`ultron stats`:**
  - horas por asignatura (barras), racha actual y máxima, tarjetas repasadas y precisión;
  - **mapa de calor de las últimas 20 semanas** estilo GitHub con `■` en 5 intensidades
    del color del modo.
- **`ultron tareas`:** compartida, pero con vista de "hoy / esta semana / después" en focus.

## `ultron ordenar <carpeta>` (compartida, en `ultron/compartidas/ordenar.py`)
- **Inventario:** nombre, extensión, tamaño, fecha, tipo MIME, y para PDF, docx, txt y md
  los primeros 500 caracteres. Las imágenes se ordenan por EXIF y fecha.
- **Reglas sin IA** (siempre disponibles, `--sin-ia`): por tipo (Documentos, Imágenes,
  Vídeos, Música, Comprimidos, Código, Instaladores) y por fecha (`--por-fecha`).
- **Con IA:**
  - se manda el inventario por lotes de unos 40 archivos (nombre + extracto corto) y la
    **estructura existente** de la carpeta;
  - la IA devuelve JSON `{archivo: "Carpeta/Subcarpeta"}`; puede reutilizar las carpetas
    que ya hay o crear nuevas (por ejemplo `Universidad/Matemáticas/Apuntes`), con un
    máximo de 3 niveles;
  - se valida que no haya rutas absolutas ni `..`.
- **Vista previa obligatoria:** un árbol antes y después con colores (nuevo, se mueve, se
  queda), un resumen y la confirmación `s/n/editar` (editar abre el plan en `$EDITOR` como
  YAML).
- Mueve con `shutil.move`, resuelve conflictos de nombre con ` (2)` y escribe un **diario**
  `~/.local/state/ultron/ordenar/<fecha>.json`.
- `ultron ordenar --deshacer [id]` devuelve todo a su sitio y borra las carpetas que se
  quedaron vacías y que creó Ultron.
- Opciones `--simular` y `--recursivo`; ignora los archivos ocultos y `.git`.

## IA del modo
"Eres ULTRON en modo FOCUS, un tutor paciente y claro. Explicas paso a paso con ejemplos,
compruebas que se ha entendido con una pregunta y animas sin exagerar. Respuestas breves y
ordenadas."

## Criterios de aceptación
- Tests:
  - extracción de un PDF generado en el test (con pypdf o un PDF mínimo escrito a mano);
  - SM-2 (intervalos tras secuencias de notas);
  - el algoritmo de `plan` (reparto de horas y repasos);
  - BM25 (devuelve el trozo correcto);
  - flashcards con la IA falseada y JSON roto que se repara;
  - exportación a `.apkg` (el archivo existe y es un zip válido);
  - el mapa de calor de stats;
  - el pomodoro con el reloj inyectable (sin `sleep` real) y el bloqueo y desbloqueo de
    hosts en el historial;
  - ordenar: sin IA, con IA falseada, la vista previa, los conflictos de nombre, deshacer
    completo y la validación de rutas maliciosas.
- `ultron repasar --demo` y `ultron stats --demo` muestran datos de ejemplo.
