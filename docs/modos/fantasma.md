# Fantasma

Activa el modo con `ultron entrar fantasma`. Las funciones de privacidad requieren
herramientas distintas según la operación. Consulta `ultron doctor --completo`.

| Ejemplo | Salida |
|---|---|
| `ultron mac --demo` | Conexión ficticia y su dirección MAC local. |
| `ultron dns-seguro --demo` | Estado ficticio del DNS sobre TLS. |
| `ultron tor estado` | Estado del servicio y comprobación de la conexión. |
| `ultron rastros` | Lista de rastros detectados y confirmación antes de borrar. |
| `ultron limpiar-meta foto.jpg` | Ruta del archivo limpio si `mat2` puede procesarlo. |
| `ultron cofre cifrar notas.txt` | Ruta del archivo cifrado. |
| `ultron cofre descifrar notas.txt.age` | Ruta del archivo recuperado. |
| `ultron cofre crear` | Configuración del almacén y solicitud de contraseña. |
| `ultron cofre abrir` | Solicitud de contraseña y ubicación del almacén montado. |
| `ultron cofre cerrar` | Confirmación de desmontaje. |
| `ultron efimero` | Abre una sesión de shell con un espacio de trabajo temporal. |
| `ultron nota-efimera --min 1` | Solicita una nota y la elimina al vencer el plazo. |

`ultron salir` restaura las capas del modo. Para revisar un comando antes de usarlo,
añade `--help`.
