# Arquitectura de Ultron

Typer registra los comandos y Rich representa la salida con el tema de la sesión. El
registro descubre las definiciones YAML integradas y las instaladas por el usuario.
La API de IA se parametriza independientemente del motor mediante los adaptadores HTTP.

## Capas e instantáneas

Cada capa declara su disponibilidad y su orden. El motor captura su estado antes de
aplicarla y escribe la captura en `$XDG_STATE_HOME/ultron/instantanea.json`. En caso de
interrupción, `ultron salir` lee la instantánea y recorre las capas en orden inverso.
`Ejecutor` centraliza los comandos externos y la simulación evita las escrituras.

La extensión `ultron@ultron` lee el estado del panel y muestra el selector de modos,
el botón de silencio y los indicadores de sesión. La extensión usa módulos ES de GNOME.
Instálala con `ultron instalar` y vuelve a iniciar sesión para cargarla.

## Crear un modo

```bash
ultron modos nuevo lectura
ultron modos --detalle lectura
ultron entrar lectura --simular
```

En Ubuntu la plantilla queda en `~/.local/share/ultron/modos/lectura/` con las rutas XDG
por defecto. Edita `modo.yaml` para elegir las capas, la descripción y la personalidad.
`tema.toml` contiene la paleta, el banner y el prompt. Pon los recursos en `tema/` y
refiérelos desde el YAML con rutas relativas. Usa un identificador de 2 a 31 caracteres
que empiece por una letra minúscula y contenga minúsculas, números, guiones o guiones bajos.
Un identificador existente se rechaza para preservar su configuración.
