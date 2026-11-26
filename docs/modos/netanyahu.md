# Netanyahu

Usa `ultron entrar netanyahu` para activar el tema. El fondo de respaldo, el emblema,
los fotogramas de Plymouth y los sonidos se generan en el directorio de datos de Ultron.
Para generarlos de antemano, usa `ultron netanyahu generar-recursos`. El fondo de retrato
y el audio son recursos opcionales. Importa tu audio con `ultron musica importar <url-o-archivo>`.
El tema de arranque se activa con `ultron entrar netanyahu --arranque`.

`ultron radar --demo` y `ultron osint ip 8.8.8.8 --demo` reproducen ejemplos sin red.
Los informes OSINT se guardan en `operaciones` dentro del directorio XDG de datos de Ultron.
La coincidencia de un alias en varias webs es una pista y necesita comprobación manual.
El radar activo se limita a una subred privada conectada al equipo.

## Ojo de Dios

`ultron ojo instalar` descarga [God’s Eye View](https://github.com/bilawalsidhu/gods-eye-view),
de Bilawal Sidhu y sus colaboradores. El código se publica bajo la
[licencia MIT](https://github.com/bilawalsidhu/gods-eye-view/blob/main/LICENSE).
Los [datos y recursos de terceros](https://github.com/bilawalsidhu/gods-eye-view/blob/main/DATA_SOURCES.md)
tienen sus propias condiciones. El proyecto se instala en el directorio XDG de datos de Ultron
y se sirve localmente. `ultron ojo parar` cierra el servidor.
