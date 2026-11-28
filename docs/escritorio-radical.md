# Transformación del escritorio por modo

`ultron entrar gaming --sin-sudo` aplica el modo a la sesión del usuario. Cambia
`gaming` por cualquiera de los otros cuatro modos. `ultron salir` recupera la
configuración capturada. `ultron --simular entrar gaming --sin-sudo` enseña los
cambios previstos sin modificar la sesión.

| Modo | Plasma 5.27 y 6.x | GNOME 42–47 | Cinnamon, XFCE y MATE |
| --- | --- | --- | --- |
| **gaming** | Barra superior fina con menú de aplicación, reloj y medidores de CPU y red. Dock inferior centrado con iconos grandes. Marco cian, bordes redondeados, desenfoque, ventanas elásticas, Konsole translúcido y Dolphin con iconos y vistas previas. | Dock compacto inferior, acentos magenta y cian en la barra superior, batería en porcentaje y accesos a juegos o descargas. | Tema oscuro y paneles grandes visibles. Cinnamon activa los efectos y XFCE conserva la composición. |
| **focus** | Panel inferior mínimo que se oculta. No molestar, Dolphin en detalles con acceso a apuntes y Konsole opaco. | Dock lateral compacto, reloj con día de la semana, marcadores para apuntes y avisos silenciados. | Tipografía serif, paneles estrechos que se ocultan, vista en lista y silencio cuando el daemon lo permite. |
| **netanyahu** | Barra superior azul con tareas, CPU, red, bandeja y reloj. Dolphin en detalles con acceso a operaciones y Konsole azul translúcido. El splash muestra «Acceso concedido». | Dock inferior azul compacto, barra superior azul, porcentaje de batería y acceso a la carpeta de trabajo. | Tema oscuro y panel visible de altura media. Marcador a la carpeta de trabajo. |
| **presentacion** | Panel lateral izquierdo que se oculta, No molestar, cursor de 44 px, consola con letra grande y acceso a presentaciones. | Dock que se oculta, localización del puntero, avisos silenciados y acceso a presentaciones. | Paneles que se ocultan, letra grande y No molestar según el daemon. Tamaño o localización del cursor donde está disponible. |
| **fantasma** | Panel lateral derecho que se oculta, marco oscuro y Dolphin compacto. Desactiva vistas previas y reapertura de pestañas, oculta recientes en Lugares y desactiva el registro de recursos de Actividades en su configuración. | Dock ocultable, avisos silenciados y preferencias de Nautilus para evitar miniaturas y registro de archivos recientes. | Paneles estrechos que se ocultan y tema oscuro. Nemo, Thunar y Caja usan los ajustes de miniaturas que exponga su versión. |

## Plasma

Cada modo genera un paquete Look-and-Feel, un estilo Plasma translúcido, una decoración
Aurorae, un esquema de color y un perfil Konsole bajo `XDG_DATA_HOME`. El splash se
selecciona en `ksplashrc` para los inicios de sesión mientras el modo está activo. Si
`ksplashqml` y `timeout` están disponibles, también se muestra durante la transición,
por un máximo de cuatro segundos. La pantalla de progreso de Ultron sigue disponible.

El script de paneles se ejecuta en la sesión mediante D-Bus. Requiere `qdbus` o una
variante de Qt 6 y un `plasma-plasmashell.service` activo en el gestor de usuario.
Plasma 5.27 conserva el ajuste flotante al recargar plasmashell. Plasma 6 usa el ajuste
del panel donde su versión lo expone. El menú global aparece en aplicaciones que
exportan sus menús. Los medidores dependen de los plasmoides instalados y el desenfoque
depende de KWin y del compositor. Dolphin y Konsole pueden requerir que se cierren y
vuelvan a abrir para leer su configuración. Las decoraciones se aplican a ventanas
decoradas por KWin.

La instantánea guarda los archivos modificados, incluido el diseño de paneles y
`user-places.xbel`, con su contenido y permisos. Al salir, Ultron detiene únicamente
plasmashell para restaurar los archivos de paneles y lo vuelve a iniciar luego. El
diseño capturado corresponde a la sesión previa al modo. Las ediciones manuales
hechas en esos mismos archivos mientras el modo está activo se revierten al salir.

## GNOME y otros escritorios

La barra superior de GNOME usa **Temas de usuario** cuando la extensión está
instalada y activa. El dock requiere Dash to Dock o Ubuntu Dock. Los esquemas GNOME
se consultan antes de escribir cada ajuste, por lo que la compatibilidad depende
de las claves que exponga cada versión. Cinnamon y MATE usan GSettings y XFCE usa
`xfconf-query` para personalizar los paneles que ya existen. Estos escritorios
mantienen sus widgets, decoraciones y disposición física. Los accesos de carpetas
existentes se añaden a los marcadores GTK y se recupera el archivo previo al salir.

SDDM, GDM, Plymouth, GRUB y el tema de arranque del equipo se administran fuera de
esta capa. La pantalla de inicio de sesión de Plasma que se configura aquí es la
que se ve **después de autenticar al usuario**. Fantasma cambia preferencias de
visibilidad y registro de aplicaciones compatibles. Las bases de datos de
historial y las miniaturas existentes permanecen en disco.

Referencias de implementación. [API de paneles de Plasma](https://develop.kde.org/docs/plasma/scripting/api/#panels),
[decoraciones Aurorae](https://develop.kde.org/docs/plasma/aurorae/),
[preferencias de Dolphin](https://docs.kde.org/stable_kf6/en/dolphin/dolphin/).
