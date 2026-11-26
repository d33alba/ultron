# Configurar la IA

La IA es opcional para las funciones que trabajan con datos locales. La configuración se
resuelve por este orden: opción del comando, variables de entorno, archivo de configuración
y autodetección de Ollama o LM Studio. `ULTRON_SIN_AUTODETECCION=1` desactiva el último paso.

Usa `ultron ia configurar` para introducir proveedor, URL base, modelo y clave. Los proveedores
compatibles con OpenAI usan una URL que termina en `/v1`. Introduce las claves en el asistente
o mediante `ULTRON_API_KEY` para evitar que aparezcan en el historial de la terminal. El
archivo `~/.config/ultron/config.toml` se guarda con permisos de usuario.

| Servidor | Proveedor | URL base | Modelo |
|---|---|---|---|
| Ollama | `ollama` | `http://localhost:11434/v1` | `llama3.2`, si está instalado |
| LM Studio | `lmstudio` | `http://localhost:1234/v1` | Identificador del modelo cargado |
| vLLM | `local` | `http://localhost:8000/v1` | Nombre anunciado por el servidor |
| OpenAI | `openai` | `https://api.openai.com/v1` | Modelo disponible en tu cuenta |

Variables admitidas: `ULTRON_PROVEEDOR`, `ULTRON_URL_BASE`, `ULTRON_MODELO` y
`ULTRON_API_KEY`. Con `ultron ia modelo` puedes consultar o cambiar el identificador.
Usa `ultron ia probar` para verificar una respuesta y `ultron ia estado` para revisar la
configuración efectiva. Con un servidor remoto, los mensajes se envían a ese servidor.

| Error | Qué revisar |
|---|---|
| Sin conexión | Arranca el servidor y repite `ultron ia probar`. |
| URL incorrecta | Corrige la URL base con `ultron ia configurar`. |
| Clave inválida | Actualiza la credencial con el asistente. |
| Modelo inexistente | Carga el modelo y vuelve a elegirlo. |
| Sin saldo | Revisa la cuota del proveedor o configura un modelo local. |
| Contexto excedido | Reduce el texto de la consulta o cambia de modelo. |
| Tiempo agotado | Comprueba la carga del servidor y prueba una consulta corta. |
| Respuesta inválida | Verifica la compatibilidad de la API y repite la prueba. |
| IA sin configurar | Ejecuta `ultron ia configurar`. |

`ultron doctor --completo` revisa también el modelo y la conexión.
