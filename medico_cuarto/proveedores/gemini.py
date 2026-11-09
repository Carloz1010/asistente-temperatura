"""Adaptador de Gemini (SDK google-genai)."""

import os
from typing import Any

import httpx2  # cliente HTTP que usa google-genai; de aquí salen sus errores de red
from google import genai
from google.genai import errors, types

from medico_cuarto.proveedores.base import (
    ErrorProveedor,
    Herramienta,
    LimiteExcedido,
    LlamadaHerramienta,
    RespuestaModelo,
)

MODELO_POR_DEFECTO: str = "gemini-3.6-flash"  # el Flash más nuevo que responde rápido
TEMPERATURA_MODELO: float = 0.4  # baja, para que siga las reglas del prompt
TIMEOUT_LLAMADA_MS: int = 60_000  # para que la app no se quede colgada


class ProveedorGemini:
    """Traduce entre el agente y la API de Gemini."""

    nombre: str = "gemini"

    def __init__(self, modelo: str | None = None, cliente: Any = None) -> None:
        self.modelo = modelo or MODELO_POR_DEFECTO
        if cliente is None:
            clave = os.environ.get("GEMINI_API_KEY")
            if not clave:
                raise ValueError("Falta GEMINI_API_KEY en el archivo .env.")
            cliente = genai.Client(
                api_key=clave, http_options=types.HttpOptions(timeout=TIMEOUT_LLAMADA_MS)
            )
        self.cliente = cliente

    def mensaje_usuario(self, texto: str) -> types.Content:
        return types.Content(role="user", parts=[types.Part.from_text(text=texto)])

    def generar(
        self, sistema: str, herramientas: list[Herramienta], historial: list[Any]
    ) -> RespuestaModelo:
        configuracion = types.GenerateContentConfig(
            system_instruction=sistema,
            temperature=TEMPERATURA_MODELO,
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=h.nombre,
                            description=h.descripcion,
                            parameters_json_schema=h.parametros,
                        )
                        for h in herramientas
                    ]
                )
            ],
        )
        try:
            respuesta = self.cliente.models.generate_content(
                model=self.modelo, contents=historial, config=configuracion
            )
        except errors.ClientError as error:
            if error.code == 429:
                raise LimiteExcedido(str(error)) from error
            raise ErrorProveedor(str(error)) from error
        except (errors.APIError, httpx2.HTTPError) as error:
            raise ErrorProveedor(str(error)) from error

        if not respuesta.candidates or respuesta.candidates[0].content is None:
            return RespuestaModelo("", [], None)
        llamadas = [
            LlamadaHerramienta(llamada.id, llamada.name or "", dict(llamada.args or {}))
            for llamada in respuesta.function_calls or []
        ]
        texto = "" if llamadas else (respuesta.text or "").strip()
        # El contenido va intacto: el modelo exige que le devuelvan su thought_signature.
        return RespuestaModelo(texto, llamadas, respuesta.candidates[0].content)

    def mensaje_resultados(
        self, resultados: list[tuple[LlamadaHerramienta, dict[str, Any]]]
    ) -> types.Content:
        return types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id=llamada.id, name=llamada.nombre, response=resultado
                    )
                )
                for llamada, resultado in resultados
            ],
        )
