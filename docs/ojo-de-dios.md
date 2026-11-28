# Ojo de Dios

`ultron ojo` abre God's Eye View en español, con una aproximación orbital
oblicua sobre España. El navegador se conecta a `127.0.0.1:4173`. La primera
apertura prepara Node y las dependencias del proyecto. Usa `ultron ojo parar`
para cerrar el servidor y `ultron ojo estado` para localizar su registro.

```sh
ultron ojo --calidad baja
ultron ojo abrir --calidad media
ultron ojo objetivo "40.4168,-3.7038"
ultron ojo clave google TU_CLAVE
ultron ojo clave cesium TU_TOKEN
ultron ojo clave tomtom TU_CLAVE
```

| Clave | Qué añade |
| --- | --- |
| Google | Ciudades en 3D fotorrealista mediante Map Tiles API, con facturación y disponibilidad según la zona. |
| Cesium | Terreno y mapas de Cesium ion, incluido Google 3D donde el token tenga acceso al recurso. |
| TomTom | Flujo y congestión agregados de las vías. Los puntos animados siguen siendo una representación del flujo. |

Ultron guarda las claves en `config.toml` con permisos 600 en Ubuntu. La
siguiente apertura reinicia el servidor local si has cambiado una clave.
El navegador recibe las credenciales de Google y Cesium porque sus capas
las usan directamente. Restringe la clave de Google a las APIs necesarias y
al origen local, y usa un token de Cesium de solo lectura con restricción
de URL. El proxy mantiene la clave de TomTom en el servidor.

## Cámaras y tráfico

- **Dirección General de Tráfico.** El catálogo nacional DATEX II v3.7 cubre la
  red estatal con las excepciones que documenta la DGT para Cataluña y el País
  Vasco. El Punto de Acceso Nacional lo publica bajo Creative Commons
  Attribution y enlaza a sus términos de uso. Ultron conserva las cámaras
  de tráfico con instantáneas del directorio oficial de eTraffic.
  [Ficha y licencia](https://nap.dgt.es/es/dataset/camaras-dgt-datex2-v3-7) ·
  [XML](https://nap.dgt.es/datex2/v3/dgt/DevicePublication/camaras_datex2_v37.xml) ·
  [Aviso legal](https://www.dgt.es/contenido/aviso-legal/)
- **Ayuntamiento de Madrid.** El catálogo KML de Informo contiene las
  ubicaciones y las capturas periódicas. El Ayuntamiento publica el conjunto
  bajo CC BY 4.0. Ultron conserva únicamente imágenes de su directorio oficial
  de cámaras de tráfico.
  [Ficha y licencia](https://datos.madrid.es/dataset/202088-0-trafico-camaras) ·
  [KML](https://informo.madrid.es/informo/tmadrid/CCTV.kml)
- God's Eye View incorpora también el catálogo del Servei Català de Trànsit
  con cámaras de Barcelona y Terrassa. Consulta la atribución y los términos
  de cada proveedor en la documentación original.
  [Catálogo oficial](https://www.gencat.cat/transit/opendata/cameres.xml) ·
  [Fuentes originales](https://github.com/bilawalsidhu/gods-eye-view/blob/main/DATA_SOURCES.md)

Activa **CCTV** y acércate a una ciudad o carretera. La ficha de cada cámara
indica la fuente. El servidor solicita la imagen al seleccionar una cámara
y reutiliza la captura en memoria durante cinco minutos. El catálogo de cada
fuente se refresca al arrancar el servidor si su copia tiene más de una hora.
Si hay un fallo de descarga, se conserva la última copia válida.

Activa **Tráfico** y baja de 8 km de altitud. La capa **SIMULADO** usa calles
de OpenStreetMap, velocidades por tipo de vía y una densidad mayor en vías
urbanas al acercarte. OpenStreetMap se distribuye bajo ODbL 1.0. En el modo
TomTom los colores describen la congestión agregada. Cada partícula es
sintética y carece de identidad o posición observada.
[OpenStreetMap](https://www.openstreetmap.org/copyright) ·
[Términos de TomTom](https://docs.tomtom.com/legal/terms-and-conditions)

## Pantalla y rendimiento

Usa los controles de estilo o las teclas `1` a `6` para alternar las vistas.
La visión nocturna usa fósforo azul, CRT añade líneas de barrido y FLIR
colorea el brillo de la escena para imitar una cámara térmica.

Si omites `--calidad`, la detección WebGL intenta reconocer renderizadores
por software como SwiftShader y llvmpipe. La calidad baja reduce la escala
de render a 0,55, limita el número de partículas y deja los grupos de
satélites de estaciones y visibles. Los filtros, bloom y nitidez quedan
desactivados. Media usa escala 0,8 y alta, escala 1.

## Actualizar el proyecto

`ultron ojo actualizar` retira el diff gestionado por Ultron, avanza la copia
con `git pull --ff-only` y genera el parche con los archivos nuevos antes de
ejecutar `npm ci`. Si cambia un punto de integración, el mensaje indica el
archivo que hay que revisar en `ojo_parche.py`. El diff aplicado se conserva
en `.git/ultron-ojo.patch` dentro del clon local.

El código de God's Eye View es MIT. Las imágenes base, los vuelos, los
satélites y demás fuentes conservan sus propios términos y atribuciones,
incluidos Google Maps Platform, Cesium ion, OpenSky, ADSB.lol y CelesTrak.
[README original](https://github.com/bilawalsidhu/gods-eye-view/blob/main/README.md) ·
[Licencia MIT](https://github.com/bilawalsidhu/gods-eye-view/blob/main/LICENSE) ·
[Licencias y atribuciones de los datos](https://github.com/bilawalsidhu/gods-eye-view/blob/main/DATA_SOURCES.md)
