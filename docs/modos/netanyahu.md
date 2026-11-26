# Netanyahu

Usa `ultron entrar netanyahu` para activar el tema. El fondo de respaldo, el emblema,
los fotogramas de Plymouth y los sonidos se generan en el directorio de datos de Ultron.
Para generarlos de antemano, usa `ultron netanyahu generar-recursos`. El fondo de retrato
y el audio son recursos opcionales. Importa tu audio con `ultron musica importar <url-o-archivo>`.
El tema de arranque se activa con `ultron entrar netanyahu --arranque`.

## Operaciones de ejemplo

Los informes OSINT se guardan en `operaciones` dentro del directorio XDG de datos de
Ultron. Usa información pública y limita las comprobaciones activas a sistemas propios
o autorizados. Las dos primeras filas se pueden probar sin conexión.

| Ejemplo | Salida |
|---|---|
| `ultron radar --demo` | Mapa ASCII con dos equipos ficticios y una puerta de enlace. |
| `ultron osint ip 8.8.8.8 --demo` | Dirección, ASN, operador y mapa de ejemplo. |
| `ultron osint dominio example.org` | Informe de DNS, registro y cabeceras públicas. |
| `ultron osint meta foto.jpg` | Metadatos presentes en la foto local. |
| `ultron osint correo mensaje.eml` | Análisis de cabeceras y autenticación del mensaje. |
| `ultron osint usuario --help` | Opciones de búsqueda pública. Una coincidencia de alias requiere comprobación manual. |
| `ultron osint informe operaciones` | Ruta del informe consolidado. |
| `ultron auditar --sin-ia` | Comprobaciones locales y valoración de seguridad. |
| `ultron cve openssl` | Avisos publicados para el paquete instalado. |
| `ultron filtrado` | Solicitud privada de contraseña y número de coincidencias. |
| `ultron web --help` | Opciones de revisión de HTTPS y cabeceras para sitios propios. |
| `ultron ctf codificar base64 "hola"` | `aG9sYQ==`. |
| `ultron ctf decodificar aG9sYQ==` | Posibles decodificaciones, entre ellas `hola`. |
| `ultron ctf hash abc123` | Posibles tipos de huella o formato desconocido. |
| `ultron ctf archivo ejemplo.txt` | Datos de identificación del archivo local. |
| `ultron ctf estego --help` | Opciones de análisis de archivos locales. |
| `ultron hackia --help` | Ayuda del asistente y argumento que acepta. |

## Ojo de Dios

`ultron ojo instalar` descarga [God’s Eye View](https://github.com/bilawalsidhu/gods-eye-view),
de Bilawal Sidhu y sus colaboradores. El código se publica bajo la
[licencia MIT](https://github.com/bilawalsidhu/gods-eye-view/blob/main/LICENSE).
Los [datos y recursos de terceros](https://github.com/bilawalsidhu/gods-eye-view/blob/main/DATA_SOURCES.md)
tienen sus propias condiciones. El proyecto se instala en el directorio XDG de datos de Ultron
y se sirve localmente. `ultron ojo parar` cierra el servidor.

| Ejemplo | Salida |
|---|---|
| `ultron ojo instalar` | Comprobación de Node e instalación local. |
| `ultron ojo abrir` | Abre el visor local en el navegador. |
| `ultron ojo estado` | Estado del servidor local. |
| `ultron ojo objetivo Madrid` | Abre la ubicación pedida en el visor. |
| `ultron ojo actualizar` | Resultado de la actualización del visor. |
| `ultron ojo parar` | Confirmación de parada del servidor. |
| `ultron netanyahu generar-recursos` | Genera los recursos visuales y sonoros de respaldo. |
