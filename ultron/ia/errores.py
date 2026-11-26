"""Errores de IA con mensaje y sugerencia en español (nunca trazas para el usuario)."""

from __future__ import annotations


class IAError(Exception):
    mensaje_base = "La IA ha fallado."

    def __init__(self, mensaje: str | None = None, sugerencia: str = ""):
        self.mensaje = mensaje or self.mensaje_base
        self.sugerencia = sugerencia
        super().__init__(self.mensaje)


class IANoConfigurada(IAError):
    mensaje_base = "No hay ninguna IA configurada."

    def __init__(self, mensaje: str | None = None, sugerencia: str = ""):
        super().__init__(mensaje, sugerencia or "Configura la IA con: ultron ia configurar")


class SinConexion(IAError):
    mensaje_base = "No puedo conectar con el servidor de IA."


class URLIncorrecta(IAError):
    mensaje_base = "La URL del servidor de IA no es correcta."


class ClaveInvalida(IAError):
    mensaje_base = "La clave de API no es válida o no tiene permisos."


class ModeloNoExiste(IAError):
    mensaje_base = "El modelo indicado no existe en el servidor."


class SinSaldo(IAError):
    mensaje_base = "La cuenta de la API no tiene saldo o ha superado su cuota."


class ContextoExcedido(IAError):
    mensaje_base = "El texto es demasiado largo para el modelo."


class TiempoAgotado(IAError):
    mensaje_base = "La IA ha tardado demasiado en responder."


class RespuestaInvalida(IAError):
    mensaje_base = "La IA ha devuelto una respuesta que no entiendo."
