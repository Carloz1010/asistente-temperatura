"""Contrato común: lo único que el agente sabe de cualquier IA."""

from typing import Any, NamedTuple, Protocol


class Herramienta(NamedTuple):
    """Una función del motor que la IA puede pedir."""

    nombre: str
    descripcion: str
    parametros: dict[str, Any]  # JSON Schema


class LlamadaHerramienta(NamedTuple):
    """La IA pidió correr una herramienta."""

    id: str | None
    nombre: str
    argumentos: dict[str, Any]


class RespuestaModelo(NamedTuple):
    """Una respuesta de la IA, ya traducida."""

    texto: str
    llamadas: list[LlamadaHerramienta]
    contenido: Any  # el mensaje original, que debe volver intacto en el historial


class LimiteExcedido(Exception):
    """La API respondió 429: se pasó del límite de solicitudes."""


class ErrorProveedor(Exception):
    """Cualquier otra falla: red, tiempo agotado, clave mala, respuesta rechazada."""


class Proveedor(Protocol):
    """Lo que debe cumplir cada adaptador.

    El historial es una lista de mensajes en el formato propio de cada IA; el agente solo
    los guarda y los devuelve. Por eso una conversación no cambia de proveedor a la mitad.
    """

    nombre: str
    modelo: str

    def mensaje_usuario(self, texto: str) -> Any:
        """Mensaje de la persona, listo para el historial."""
        ...

    def generar(
        self, sistema: str, herramientas: list[Herramienta], historial: list[Any]
    ) -> RespuestaModelo:
        """Pide la siguiente respuesta. Falla con LimiteExcedido o ErrorProveedor."""
        ...

    def mensaje_resultados(
        self, resultados: list[tuple[LlamadaHerramienta, dict[str, Any]]]
    ) -> Any:
        """Mensaje con lo que devolvió cada herramienta, listo para el historial."""
        ...
