# Diseño de la interfaz de terminal por modo

Al entrar en un modo, Ultron cambia por completo su forma de hablar en la terminal: el banner,
la paleta, los bordes, el prompt, los iconos de texto, las animaciones y la forma de mostrar
resultados. Todo se hace con caracteres (Unicode y colores ANSI), usando Rich.

Los bocetos de abajo usan solo caracteres. Los colores se indican entre corchetes: `[azul]`.

---

## Motor de temas (común a todos)

Cada modo define un `tema.toml` con estas piezas, y toda la interfaz de Ultron las usa:

| Pieza | Qué es | Ejemplo |
|---|---|---|
| `paleta` | colores primario, secundario, acento, aviso, error, apagado | `#0038B8` |
| `bordes` | estilo de caja de Rich | `DOUBLE`, `ROUNDED`, `HEAVY` |
| `banner` | arte de texto que aparece al entrar | ver cada modo |
| `glifos` | iconos de texto para ok, error, info, cargando y viñeta | `✡ ✔ ✖ ▸` |
| `prompt` | plantilla del prompt de bash | `✡ {usuario} ▸ {op} ❯` |
| `spinner` | animación de "cargando" | fotogramas propios |
| `entrada` | animación al entrar en el modo | escritura, glitch, fundido |
| `voz` | cómo se redactan los mensajes | "OPERACIÓN COMPLETADA" o "Hecho." |

**Fallbacks obligatorios:**
- Sin color verdadero se usan 256 colores, y sin eso, 16.
- Sin Unicode (`LANG=C`) se cambian los glifos por ASCII puro (`*`, `+`, `-`, `|`).
- Si la salida no es una terminal (por ejemplo, con `| grep`), o con `ULTRON_SIN_ANIMACIONES=1`
  o `--sin-animaciones`, no hay animaciones ni colores.
- Con menos de 80 columnas se usa un banner compacto.

**Transición entre modos (`ultron entrar X`):** la interfaz del modo anterior se "deshace"
con un glitch de 0,5 s, luego se ve una barra con las capas que se van aplicando y por último
aparece el banner del modo nuevo con su animación de entrada.

```
 ultron entrar creativo
 ░▒▓ desmontando modo foco ▓▒░
 ▸ shell       ✔
 ▸ terminal    ✔
 ▸ escritorio  ✔
 ▸ iconos      ⠹
```

---

## Modo Netanyahu

**Concepto:** terminal de operaciones de inteligencia israelí. Sobria, oficial, "clasificada".

- **Paleta:** azul `#0038B8` (primario), blanco `#FFFFFF`, azul claro `#6EA8FE` (acento),
  rojo `#E63946` (alertas), gris `#8A94A6`.
- **Bordes:** `DOUBLE` (`╔═╗`), como un documento oficial.
- **Glifos:** `✡` marca, `▸` viñeta, `◉` objetivo, `✔` ok, `✖` error, `⚠` aviso.
- **Voz:** mayúsculas en los títulos, frases cortas, en tono de informe:
  "OBJETIVO ANALIZADO", "OPERACIÓN EN CURSO".
- **Animación de entrada:** texto que se escribe letra a letra con sonido de teletipo
  (si hay audio), seguido de la estrella de David que se dibuja línea a línea.
- **Spinner:** `◜ ◝ ◞ ◟` en azul claro.

**Banner (al entrar):**
```
[azul]╔══════════════════════════════════════════════════════════╗
[azul]║[blanco]                         /\                               [azul]║
[azul]║[blanco]                    ____/__\____                          [azul]║
[azul]║[blanco]                    \  /    \  /       █ █ █   ▀█▀ █▀█ █▀█ █▄ █[azul]║
[azul]║[blanco]                     \/      \/        █▄█ █▄▄  █  █▀▄ █▄█ █ ▀█[azul]║
[azul]║[blanco]                     /\      /\                           [azul]║
[azul]║[blanco]                    /__\____/__\       MODO NETANYAHU      [azul]║
[azul]║[blanco]                        \  /           שלום · ACCESO CONCEDIDO[azul]║
[azul]║[blanco]                         \/                               [azul]║
[azul]╠══════════════════════════════════════════════════════════╣
[azul]║ [gris]CLASIFICACIÓN: ALTO SECRETO   SESIÓN: 0x7F3A   26-11-2026 [azul]║
[azul]╚══════════════════════════════════════════════════════════╝
```
> Ojo: el hebreo se escribe de derecha a izquierda y en algunas terminales descuadra los
> bordes. Se usa solo en una línea del banner y se mide con `wcwidth`; si descuadra, se
> sustituye por "SHALOM".

**Prompt:**
```
[azul]✡ [blanco]david[azul]@[blanco]netanyahu [azul]▸ [gris]op:osint [azul]❯ 
```

**Resultado de una función (OSINT de un dominio):**
```
[azul]╔═ ✡ INFORME OSINT ══════════════════════════════════╗
[azul]║ [blanco]◉ OBJETIVO    [azul]ejemplo.com                         ║
[azul]║ [blanco]▸ IP          [blanco]93.184.216.34                       ║
[azul]║ [blanco]▸ REGISTRADOR [blanco]IANA                                ║
[azul]║ [blanco]▸ SUBDOMINIOS [blanco]4 encontrados                       ║
[azul]║ [rojo]⚠ PUERTOS     [blanco]22 · 80 · 443                       ║
[azul]╠════════════════════════════════════════════════════╣
[azul]║ [gris]ANÁLISIS IA: superficie de ataque reducida...      [azul]║
[azul]╚═════════════════════════════════ OPERACIÓN COMPLETA ═╝
```

---

## Modo foco

**Concepto:** papel y tinta. Minimalista, silencioso, mucho espacio en blanco. Nada distrae.

- **Paleta:** gris claro `#C8C8C8` (texto), gris `#6B6B6B` (apagado), verde salvia `#8FBC8F`
  (progreso), ámbar suave `#D9A441` (aviso). Sin negritas chillonas.
- **Bordes:** `ROUNDED` fino (`╭─╮`) o directamente sin caja.
- **Glifos:** `·` viñeta, `○ ◔ ◑ ◕ ●` progreso, `✓` hecho, `›` acción.
- **Voz:** minúsculas, en calma, frases mínimas: "hecho.", "25 minutos. empieza cuando quieras."
- **Animación de entrada:** fundido lento de oscuro a claro (3 pasos) y una frase de
  concentración aleatoria.
- **Spinner:** `·  ·· ··· ·· ·` respirando despacio.

**Banner (al entrar):**
```
[gris]

[gris]        u l t r o n
[apagado]        ─────────────
[gris]        modo foco

[apagado]        "lo que haces cada día importa más
[apagado]         que lo que haces de vez en cuando."


```

**Prompt** (con el pomodoro y las tareas en vivo):
```
[salvia]◑ 18:42 [apagado]· 3/8 · [gris]~/apuntes [apagado]› 
```

**Pomodoro en curso:**
```
[apagado]  ╭──────────────────────────────────────╮
[gris]  │   sesión 2 de 4 · matemáticas        │
[gris]  │                                      │
[salvia]  │   ━━━━━━━━━━━━━━━━━━━━━[apagado]──────────   │
[gris]  │   18:42                  restan 6:18 │
[apagado]  ╰──────────────────────────────────────╯
[apagado]   webs bloqueadas: 6 · notificaciones: no
```

**Tareas:**
```
[gris]  hoy
[salvia]  ✓ [apagado]repasar tema 3
[gris]  ○ ejercicios de derivadas          [ámbar]mañana
[gris]  ○ entrega de historia              [ámbar]viernes
```

---

## Modo creativo (gaming)

**Concepto:** HUD de videojuego. Neón, degradados, barras de vida, glitch. Mucha energía.

- **Paleta:** degradado magenta `#FF00E6` → violeta `#8A2BE2` → cian `#00F0FF`,
  verde lima `#39FF14` (ok), amarillo `#FFE600` (aviso), fondo negro.
- **Bordes:** `HEAVY` (`┏━┓`) con esquinas de color distinto, como un HUD.
- **Glifos:** `⚡` energía, `▰▱` barras, `◆` viñeta, `★` logro, `☠` error, `▶` acción.
- **Voz:** de videojuego: "¡MODO ACTIVADO!", "+50 XP", "LOGRO DESBLOQUEADO".
- **Animación de entrada:** el banner aparece con glitch (caracteres aleatorios
  `░▒▓█` que se resuelven en el texto) y un degradado de color que recorre las letras.
- **Spinner:** `▰▱▱▱ ▰▰▱▱ ▰▰▰▱ ▰▰▰▰` con degradado.
- **Extra:** sistema de **XP y niveles**. Cada comando usado da puntos, y con algunas
  acciones se desbloquean logros.

**Banner (al entrar), con degradado de magenta a cian de izquierda a derecha:**
```
[magenta]░▒▓█[violeta] ██╗   ██╗██╗  ████████╗██████╗  ██████╗ ███╗   ██╗[cian]█▓▒░
[magenta]░▒▓█[violeta] ██║   ██║██║  ╚══██╔══╝██╔══██╗██╔═══██╗████╗  ██║[cian]█▓▒░
[magenta]░▒▓█[violeta] ██║   ██║██║     ██║   ██████╔╝██║   ██║██╔██╗ ██║[cian]█▓▒░
[magenta]░▒▓█[violeta] ╚██████╔╝███████╗██║   ██║  ██║╚██████╔╝██║ ╚████║[cian]█▓▒░
[magenta]░▒▓█[violeta]  ╚═════╝ ╚══════╝╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝[cian]█▓▒░
[amarillo]           ⚡ MODO CREATIVO ⚡  PLAYER: DAVID  LVL 7 ⚡
```

**Prompt:**
```
[magenta]▰▰▰▰[violeta]▰▰[apagado]▱▱ [cian]LVL 7 [amarillo]⚡ [magenta]david [cian]❯❯❯ 
```

**HUD del sistema (`ultron hud`, en vivo):**
```
[magenta]┏━━━━━━━━━━━━━━━━━━━━━ ◆ SYSTEM HUD ◆ ━━━━━━━━━━━━━━━━━━━━━┓
[magenta]┃ [lima]HP  CPU  [lima]▰▰▰▰▰▰▰[apagado]▱▱▱  [blanco]68%   [cian]TEMP  61°C        [magenta]┃
[magenta]┃ [cian]MP  RAM  [cian]▰▰▰▰▰[apagado]▱▱▱▱▱  [blanco]52%   [cian]GPU   44%          [magenta]┃
[magenta]┃ [amarillo]XP       [amarillo]▰▰▰▰▰▰▰▰[apagado]▱▱  [blanco]820/1000           [cian]FPS 144 [magenta]┃
[magenta]┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
[amarillo]  ★ LOGRO DESBLOQUEADO: "Noctámbulo" (usar Ultron después de las 2:00)
```

**Error:**
```
[magenta]☠ GAME OVER [blanco]· no encuentro el juego "minecraf" · [cian]▶ ¿querías decir minecraft?
```

---

## Qué se implementa y cuándo

- **Fase 0:** motor de temas (`tema.toml`, paleta, bordes, glifos, fallbacks), los tres banners
  sin animar y `ultron modos` usando el tema de cada modo como vista previa.
- **Fase 1:** prompt de bash de cada modo (capa `shell`) y la transición entre modos.
- **Fase 8:** animaciones de entrada, spinners propios, XP y logros, y el menú interactivo.
