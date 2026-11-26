# Encargo de imágenes: modo NETANYAHU

Genera con tu herramienta de imágenes **todos** los recursos de esta lista y guárdalos en
`recursos/netanyahu/` con el nombre exacto indicado. **No toques nada más del repositorio.**

## Estilo común (obligatorio en todos los iconos)

- Estética de la **bandera de Israel**: blanco puro `#FFFFFF` como base y azul `#0038B8`
  para las dos franjas horizontales y la **estrella de David** (dos triángulos entrelazados,
  de trazo, nunca rellena).
- Iconos **planos y modernos** de sistema operativo (en la línea de Yaru o macOS Big Sur):
  formas redondeadas, un degradado muy suave como máximo, una sombra interior ligera y
  **ninguna** sombra exterior.
- **Sin texto, letras ni números** dentro de los iconos.
- **Fondo transparente**, la forma centrada y un margen transparente del 8 % en cada lado.
- Coherencia total: el mismo grosor de trazo, los mismos radios, la misma posición de la
  estrella y la misma luz en todos. Tienen que parecer de **una sola familia**.
- Tamaño final de **512 × 512 px**, en PNG RGBA.

## 1. Fondo de escritorio: `fondo.png`

Cartel panorámico 16:9 con estética de **ciberinteligencia israelí**:
- un retrato de **Benjamín Netanyahu** a la derecha, de tres cuartos, serio y mirando al
  frente, con un estilo de ilustración editorial y digital, no una foto falsa;
- iluminación fría en azul y blanco;
- detrás, una cuadrícula de radar, líneas topográficas de Jerusalén y Tel Aviv, ondas de
  telecomunicaciones y una estrella de David geométrica grande de baja opacidad;
- el tercio izquierdo oscuro (azul marino `#0A1A3F`) y despejado, para que se lean los
  iconos del escritorio;
- sin texto.

Genera en el mayor tamaño apaisado que permita la herramienta y luego escálalo a
**3840 × 2160** con Pillow (LANCZOS).

## 2. Fondo de bloqueo: `bloqueo.png`

La misma escena, pero **sin el retrato**: solo el radar, la estrella y las líneas, más
oscura. Tamaño de 3840 × 2160.

## 3. Emblema: `emblema.png`

Estrella de David **blanca** de trazo grueso con un borde azul `#0038B8`, sobre fondo
transparente, de 512 × 512. Se pone en la esquina de todas las carpetas.

## 4. Carpetas (en `iconos/`)

Una **carpeta** con la forma clásica de pestaña: cuerpo blanco, las dos franjas azules de la
bandera cruzándola en horizontal y, en el centro, el símbolo de cada tipo dentro de una
estrella de David pequeña o junto a ella.

| Archivo | Símbolo |
|---|---|
| `folder.png` | solo la estrella de David |
| `folder-documents.png` | hoja con líneas |
| `folder-download.png` | flecha hacia abajo |
| `folder-music.png` | nota musical |
| `folder-pictures.png` | montaña y sol |
| `folder-videos.png` | triángulo de reproducción |
| `folder-templates.png` | regla y escuadra |
| `folder-publicshare.png` | dos personas |
| `folder-remote.png` | globo terráqueo |
| `user-home.png` | casa |
| `user-desktop.png` | monitor |
| `user-trash.png` | papelera vacía (no es una carpeta: un cesto blanco con las franjas azules) |
| `user-trash-full.png` | la misma papelera con papeles |

## 5. Tipos de archivo (en `iconos/`)

Una **hoja con la esquina doblada**, blanca con las dos franjas azules finas arriba y abajo,
y el símbolo en azul en el centro:

| Archivo | Símbolo |
|---|---|
| `text-x-generic.png` | líneas de texto |
| `application-pdf.png` | hoja con un sello de estrella de David |
| `image-x-generic.png` | montaña y sol |
| `audio-x-generic.png` | onda de sonido |
| `video-x-generic.png` | claqueta |
| `package-x-generic.png` | caja |
| `text-x-script.png` | chevrón `>_` dibujado como símbolo, sin letras |
| `x-office-document.png` | hoja con una gráfica de barras |

## 6. Aplicaciones (en `iconos/`)

Iconos cuadrados redondeados (*squircle*) blancos con las franjas azules y el motivo de la
app en azul. **No copies los logotipos oficiales**: haz una reinterpretación propia con la
estética de la bandera.

| Archivo | Motivo |
|---|---|
| `firefox.png` | un zorro estilizado envolviendo un globo con la estrella de David |
| `org.gnome.Nautilus.png` | carpeta abierta |
| `org.gnome.Terminal.png` | ventana de consola con chevrón y cursor |
| `org.gnome.Settings.png` | engranaje con la estrella en el centro |
| `org.gnome.Calculator.png` | calculadora |
| `org.gnome.Software.png` | bolsa de tienda con un cubo |
| `org.gnome.TextEditor.png` | hoja con lápiz |
| `org.gnome.Loupe.png` | marco con montaña |
| `org.gnome.Music.png` | disco con nota |
| `org.gnome.Totem.png` | fotograma con triángulo de reproducción |
| `org.gnome.Evolution.png` | sobre de correo |
| `org.gnome.Calendar.png` | almanaque |
| `org.gnome.Screenshot.png` | marco de recorte con obturador |
| `snap-store.png` | bolsa con asa |
| `gnome-control-center.png` | el mismo engranaje de Ajustes |

## Después de generar cada imagen (con `.venv/Scripts/python` y Pillow)

1. **Transparencia:** si la imagen no tiene canal alfa real, quita el fondo de forma
   uniforme (relleno desde las cuatro esquinas con tolerancia) y guárdala como RGBA.
2. **Tamaño:** iconos a 512 × 512 y fondos a 3840 × 2160.
3. **Comprobación:** abre cada archivo y verifica el tamaño y el modo. Si una imagen sale con
   texto o mal recortada, genérala otra vez.
4. **Reanudar:** si un archivo ya existe y es correcto, **no lo vuelvas a generar**.
5. **Índice:** escribe `recursos/netanyahu/INDICE.md` con una línea por archivo
   (nombre, tamaño y estado), y en un apartado aparte lo que no se haya podido generar y
   por qué.

Orden de prioridad (por si se acaba el saldo): `fondo.png`, `emblema.png`, `folder.png`,
el resto de carpetas, las apps, los tipos de archivo y, por último, `bloqueo.png`.
