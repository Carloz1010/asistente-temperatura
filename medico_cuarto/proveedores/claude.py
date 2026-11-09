"""Adaptador de Claude (SDK oficial anthropic)."""

import json
import os
from typing import Any

import anthropic

from medico_cuarto.proveedores.base import (
    ErrorProveedor,
    Herramienta,
    LimiteExcedido,
    LlamadaHerramienta,
    RespuestaModelo,
)

MODELO_POR_DEFECTO: str = "claude-opus-5-5"
MAX_TOKENS: int = 16_000  # incluye el razonamiento interno y la respuesta
ESFUERZO: str = "medium"
TIMEOUT_LLAMADA_S: float = 120.0  # el razonamiento puede tardar más que una llamada simple

# Si el filtro de seguridad rechaza una solicitud, la API la repite en otro modelo.
BETA_RESPALDO: str = "server-side-fallback-2026-07-01"
MODELOS_CON_RESPALDO: frozenset[str] = frozenset(
    {"claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5"}
)


class ProveedorClaude:
    """Traduce entre el agente y la API de Claude."""

    nombre: str = "claude"

    def __init__(self, modelo: str | None = None, cliente: Any = None) -> None:
        self.modelo = modelo or MODELO_POR_DEFECTO
        if cliente is None:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise ValueError("Falta ANTHROPIC_API_KEY en el archivo .env.")
            # Sin reintentos del SDK: la política de reintento es la misma para toda IA
            # y vive en el agente.
            cliente = anthropic.Anthropic(timeout=TIMEOUT_LLAMADA_S, max_retries=0)
        self.cliente = cliente

    def mensaje_usuario(self, texto: str) -> dict[str, Any]:
        return {"role": "user", "content": texto}

    def generar(
        self, sistema: str, herramientas: list[Herramienta], historial: list[Any]
    ) -> RespuestaModelo:
        respaldo: dict[str, Any] = {}
        if self.modelo in MODELOS_CON_RESPALDO:
            respaldo = {"betas": [BETA_RESPALDO], "fallbacks": "default"}
        try:
            respuesta = self.cliente.beta.messages.create(
                model=self.modelo,
                max_tokens=MAX_TOKENS,
                system=sistema,
                tools=[
                    {"name": h.nombre, "description": h.descripcion, "input_schema": h.parametros}
                    for h in herramientas
                ],
                messages=historial,
                cache_control={"type": "ephemeral"},  # el prompt y la ficha se repiten en cada turno
                output_config={"effort": ESFUERZO},
                **respaldo,
            )
        except anthropic.RateLimitError as error:
            raise LimiteExcedido(str(error)) from error
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as error:
            raise ErrorProveedor(str(error)) from error

        # Rechazada o cortada: una llamada a herramienta aquí podría venir incompleta.
        if respuesta.stop_reason in ("refusal", "max_tokens"):
            raise ErrorProveedor(f"Claude terminó con stop_reason={respuesta.stop_reason}.")
        llamadas = [
            LlamadaHerramienta(bloque.id, bloque.name, dict(bloque.input))
            for bloque in respuesta.content
            if bloque.type == "tool_use"
        ]
        texto = "".join(b.text for b in respuesta.content if b.type == "text").strip()
        # El contenido va completo: los bloques de razonamiento deben volver sin cambios.
        return RespuestaModelo(texto, llamadas, {"role": "assistant", "content": respuesta.content})

    def mensaje_resultados(
        self, resultados: list[tuple[LlamadaHerramienta, dict[str, Any]]]
    ) -> dict[str, Any]:
        # Todos los resultados de un turno van juntos en un solo mensaje.
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": llamada.id,
                    "content": json.dumps(resultado, ensure_ascii=False),
                    "is_error": "error" in resultado,
                }
                for llamada, resultado in resultados
            ],
        }
