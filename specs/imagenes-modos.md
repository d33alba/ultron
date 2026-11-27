# Encargo de imágenes: modos FOCUS, GAMING, PRESENTACIÓN y FANTASMA

Genera con tu herramienta de imágenes los recursos de esta lista y guárdalos en
`recursos/<modo>/` con el nombre exacto. **No toques nada más del repositorio.** Mismo
procedimiento que `specs/imagenes-netanyahu.md` (léelo): post-proceso con Pillow
(`.venv/Scripts/python`), transparencia real en iconos, iconos de 512 × 512 RGBA con un
margen del 8 %, fondos a 3840 × 2160, **sin texto ni letras**, coherencia total dentro de cada
modo, no copiar logotipos oficiales, reanudar sin regenerar lo que ya esté bien y un
`recursos/<modo>/INDICE.md` por modo.

Por modo, la misma lista de archivos:
- `fondo.png` (escritorio), `bloqueo.png` (pantalla de bloqueo, variante más oscura y sin el
  motivo principal), `emblema.png` (512 × 512, transparente, va en la esquina de las carpetas),
- en `iconos/`: `folder.png`, `folder-documents.png`, `folder-download.png`, `folder-music.png`,
  `folder-pictures.png`, `folder-videos.png`, `user-home.png`, `user-desktop.png`,
  `user-trash.png`, `firefox.png`, `org.gnome.Nautilus.png`, `org.gnome.Terminal.png`,
  `org.gnome.Settings.png`, `text-x-generic.png`, `application-pdf.png`.

## FOCUS (estudio, calma, «modo túnel»)
Paleta: fondo `#1E1F22`, salvia `#A8B5A2`, verde suave `#8FBC8F`, papel `#E8E4DA`.
- **Fondo:** biblioteca o escritorio de estudio minimalista al amanecer, ilustración serena
  estilo *lo-fi* sin personas, mucha zona vacía y oscura a la izquierda para los iconos, una
  lámpara cálida, plantas, lluvia suave en la ventana. Nada de saturación.
- **Iconos:** estilo papel y tinta: formas redondeadas planas en salvia y crema, trazo fino
  gris oscuro, como un cuaderno Moleskine. El emblema: un círculo concéntrico tipo diana zen.

## GAMING (cyberpunk hiperfuturista, «que no parezca Ubuntu»)
Paleta: fondo `#0B0B16`, magenta neón `#FF00E6`, cian `#00F0FF`, violeta `#8A2BE2`.
- **Fondo:** ciudad cyberpunk nocturna vista desde una azotea, lluvia, hologramas, reflejos
  de neón magenta y cian en el suelo mojado, tercio izquierdo más oscuro. Muy épico, sin texto
  ni carteles con letras.
- **Iconos:** objetos de cristal oscuro con bordes de neón que brillan (glow), estética HUD,
  ángulos biselados en vez de redondos. Emblema: un rayo dentro de un hexágono de neón.

## PRESENTACIÓN (escenario, foco, elegancia)
Paleta: fondo `#2B2B2E`, oro `#F2C14E`, rojo telón `#B3261E`, blanco cálido.
- **Fondo:** escenario de teatro vacío con telón rojo abierto y un único foco dorado en el
  centro, polvo en el haz de luz, butacas en penumbra. Elegante y cinematográfico.
- **Iconos:** estilo «premios» o art déco: negro mate con filos dorados y un brillo
  metálico suave. Emblema: estrella dorada de cinco puntas.

## FANTASMA (privacidad, sigilo, desaparecer)
Paleta: negro `#000000`, gris niebla `#BDBDBD`, blanco `#E8E8E8`.
- **Fondo:** niebla densa en un bosque nocturno o una calle vacía, monocromo, una silueta
  apenas insinuada que se disuelve en la niebla, grano de película. Inquietante pero bonito.
- **Iconos:** monocromos semitransparentes, como hechos de humo o cristal esmerilado, con un
  contorno blanco fino. Emblema: una máscara o un ojo tachado minimalista.

Orden de prioridad (por si se acaba el saldo): los cuatro `fondo.png`, los cuatro
`emblema.png`, los `folder.png`, el resto de iconos de GAMING, FOCUS, FANTASMA y
PRESENTACIÓN, y al final los `bloqueo.png`.
