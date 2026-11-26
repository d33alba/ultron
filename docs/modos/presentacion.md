# Presentación

Activa el modo con `ultron entrar presentacion`. Escribe una presentación Markdown con
una línea `---` entre diapositivas. En cada una, sitúa las notas del orador después de `???`.

| Ejemplo | Salida |
|---|---|
| `ultron diapos --demo` | Diapositiva de muestra. |
| `ultron diapos charla.md` | Presentación a pantalla completa. |
| `ultron diapos --notas` | Diapositiva actual, notas, siguiente título y tiempo. |
| `ultron diapos charla.md --exportar html` | Archivo `charla.html` en la carpeta de origen. |
| `ultron ensayo charla.md --tiempo 12` | Preguntas de la IA, valoración de claridad y reparto de los 12 minutos. |
| `ultron cronometro --demo` | Cuenta atrás de ejemplo con dígitos grandes. |
| `ultron teleprompter guion.txt --velocidad 0.8` | Guion desplazándose a 0,8 líneas por segundo. |

Termina con `ultron salir` para recuperar el escritorio anterior.
