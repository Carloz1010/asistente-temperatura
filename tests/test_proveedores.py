"""Pruebas de la capa de proveedores, sin red y sin gastar créditos.

Los de Claude usan el SDK real con un transporte HTTP simulado: así se valida el formato
de lo que se enviaría a la API.
"""

import json
from typing import Any, Callable

import anthropic
import httpx2
import pytest

from medico_cuarto import agente as modulo_agente
from medico_cuarto import proveedores
from medico_cuarto.agente import MENSAJE_ERROR, MENSAJE_LIMITE, Agente, declaraciones_herramientas
from medico_cuarto.clima import dia_tipico_barranquilla
from medico_cuarto.proveedores import claude as modulo_claude
from medico_cuarto.proveedores.base import (
    ErrorProveedor,
    Herramienta,
    LimiteExcedido,
    LlamadaHerramienta,
)
from medico_cuarto.proveedores.claude import ProveedorClaude
from medico_cuarto.proveedores.gemini import ProveedorGemini

HERRAMIENTAS = [Herramienta("obtener_clima", "Clima", {"type": "object", "properties": {}})]


def mensaje_api(contenido: list[dict[str, Any]], stop_reason: str = "end_turn") -> dict[str, Any]:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5-5",
        "content": contenido,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 1, "output_tokens": 1},
    }


def error_api(codigo: int) -> httpx2.Response:
    tipo = "rate_limit_error" if codigo == 429 else "api_error"
    return httpx2.Response(
        codigo, json={"type": "error", "error": {"type": tipo, "message": "falla"}}
    )


class ApiFalsa:
    """Responde en orden y guarda el cuerpo de cada solicitud."""

    def __init__(self, respuestas: list[Any]) -> None:
        self.respuestas = list(respuestas)
        self.solicitudes: list[dict[str, Any]] = []
        self.encabezados: list[httpx2.Headers] = []

    def __call__(self, peticion: httpx2.Request) -> httpx2.Response:
        self.solicitudes.append(json.loads(peticion.content))
        self.encabezados.append(peticion.headers)
        siguiente = self.respuestas.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        if isinstance(siguiente, httpx2.Response):
            return siguiente
        return httpx2.Response(200, json=siguiente)


def claude_con(api: Callable[..., httpx2.Response], modelo: str | None = None) -> ProveedorClaude:
    cliente = anthropic.Anthropic(
        api_key="clave-de-prueba",
        max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(api)),
    )
    return ProveedorClaude(modelo=modelo, cliente=cliente)


# --- Elegir proveedor ---


@pytest.fixture
def entorno(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """Entorno limpio: no lee el .env real."""
    monkeypatch.setattr(proveedores, "load_dotenv", lambda: None)
    for variable in ("PROVEEDOR_IA", "MODELO_IA", "GEMINI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(variable, raising=False)
    return monkeypatch


def test_sin_configurar_usa_gemini(entorno: pytest.MonkeyPatch) -> None:
    entorno.setenv("GEMINI_API_KEY", "x")
    proveedor = proveedores.crear_proveedor()
    assert isinstance(proveedor, ProveedorGemini)
    assert proveedor.modelo == "gemini-3.6-flash"


def test_el_env_elige_proveedor_y_modelo(entorno: pytest.MonkeyPatch) -> None:
    entorno.setenv("ANTHROPIC_API_KEY", "x")
    entorno.setenv("PROVEEDOR_IA", "Claude")
    entorno.setenv("MODELO_IA", "claude-haiku-5-5")
    proveedor = proveedores.crear_proveedor()
    assert isinstance(proveedor, ProveedorClaude)
    assert proveedor.modelo == "claude-haiku-5-5"


def test_modelo_vacio_usa_el_del_proveedor(entorno: pytest.MonkeyPatch) -> None:
    entorno.setenv("ANTHROPIC_API_KEY", "x")
    entorno.setenv("PROVEEDOR_IA", "claude")
    entorno.setenv("MODELO_IA", "")
    assert proveedores.crear_proveedor().modelo == modulo_claude.MODELO_POR_DEFECTO


def test_proveedor_desconocido(entorno: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError, match="desconocido"):
        proveedores.crear_proveedor("otra_ia")


@pytest.mark.parametrize(
    "nombre, variable", [("gemini", "GEMINI_API_KEY"), ("claude", "ANTHROPIC_API_KEY")]
)
def test_falta_la_clave(entorno: pytest.MonkeyPatch, nombre: str, variable: str) -> None:
    with pytest.raises(ValueError, match=variable):
        proveedores.crear_proveedor(nombre)


# --- Adaptador de Claude ---


def test_claude_arma_la_solicitud() -> None:
    api = ApiFalsa([mensaje_api([{"type": "text", "text": "Hola"}])])
    proveedor = claude_con(api)
    proveedor.generar("Sistema", HERRAMIENTAS, [proveedor.mensaje_usuario("hola")])

    cuerpo = api.solicitudes[0]
    assert cuerpo["model"] == "claude-opus-5-5"
    assert cuerpo["system"] == "Sistema"
    assert cuerpo["tools"][0]["input_schema"] == HERRAMIENTAS[0].parametros
    assert cuerpo["cache_control"] == {"type": "ephemeral"}
    assert cuerpo["fallbacks"] == "default"
    assert "temperature" not in cuerpo  # estos modelos la rechazan con un 400
    assert modulo_claude.BETA_RESPALDO in api.encabezados[0]["anthropic-beta"]


def test_claude_sin_respaldo_en_modelos_que_no_lo_admiten() -> None:
    api = ApiFalsa([mensaje_api([{"type": "text", "text": "Hola"}])])
    claude_con(api, "claude-haiku-5-5").generar("S", HERRAMIENTAS, [{"role": "user", "content": "x"}])
    assert "fallbacks" not in api.solicitudes[0]
    assert "anthropic-beta" not in api.encabezados[0]


def test_el_esquema_real_de_la_ficha_se_envia_completo() -> None:
    api = ApiFalsa([mensaje_api([{"type": "text", "text": "Hola"}])])
    claude_con(api).generar("S", declaraciones_herramientas(), [{"role": "user", "content": "x"}])
    calcular = next(h for h in api.solicitudes[0]["tools"] if h["name"] == "calcular_cuarto")
    assert "Techo" in calcular["input_schema"]["$defs"]


def test_claude_traduce_una_llamada() -> None:
    api = ApiFalsa(
        [
            mensaje_api(
                [
                    {"type": "text", "text": "Ya miro."},
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "obtener_clima",
                        "input": {"ciudad": "Cali"},
                    },
                ],
                "tool_use",
            )
        ]
    )
    respuesta = claude_con(api).generar("S", HERRAMIENTAS, [{"role": "user", "content": "x"}])
    assert respuesta.llamadas == [LlamadaHerramienta("toolu_1", "obtener_clima", {"ciudad": "Cali"})]
    assert respuesta.contenido["role"] == "assistant"


def test_claude_resultados_van_en_un_solo_mensaje() -> None:
    proveedor = claude_con(ApiFalsa([]))
    bien = LlamadaHerramienta("a", "obtener_clima", {})
    mal = LlamadaHerramienta("b", "calcular_cuarto", {})
    mensaje = proveedor.mensaje_resultados([(bien, {"t": "28 °C"}), (mal, {"error": "falta"})])

    assert mensaje["role"] == "user"
    assert [b["tool_use_id"] for b in mensaje["content"]] == ["a", "b"]
    assert json.loads(mensaje["content"][0]["content"]) == {"t": "28 °C"}
    assert [b["is_error"] for b in mensaje["content"]] == [False, True]


@pytest.mark.parametrize(
    "respuesta, excepcion",
    [
        (error_api(429), LimiteExcedido),
        (error_api(500), ErrorProveedor),
        (error_api(401), ErrorProveedor),
        (httpx2.ConnectError("sin red"), ErrorProveedor),
        (mensaje_api([], "refusal"), ErrorProveedor),
        (mensaje_api([{"type": "text", "text": "cortado"}], "max_tokens"), ErrorProveedor),
    ],
)
def test_claude_traduce_fallas(respuesta: Any, excepcion: type[Exception]) -> None:
    with pytest.raises(excepcion):
        claude_con(ApiFalsa([respuesta])).generar("S", HERRAMIENTAS, [{"role": "user", "content": "x"}])


# --- El mismo agente corriendo sobre Claude ---


def test_agente_completo_sobre_claude(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modulo_agente, "obtener_clima", lambda ciudad: dia_tipico_barranquilla())
    api = ApiFalsa(
        [
            mensaje_api(
                [
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "obtener_clima",
                        "input": {"ciudad": "Barranquilla"},
                    }
                ],
                "tool_use",
            ),
            mensaje_api([{"type": "text", "text": "¿Cuánto mide el cuarto?"}]),
        ]
    )
    agente = Agente(proveedor=claude_con(api))

    respuesta = agente.responder("Vivo en Barranquilla")

    assert respuesta.texto == "¿Cuánto mide el cuarto?"
    assert respuesta.herramientas_usadas == ["obtener_clima"]
    segunda = api.solicitudes[1]["messages"]
    assert [m["role"] for m in segunda] == ["user", "assistant", "user"]
    assert segunda[1]["content"][0]["type"] == "tool_use"
    assert segunda[2]["content"][0]["tool_use_id"] == "toolu_1"


def test_agente_sobre_claude_reintenta_429(monkeypatch: pytest.MonkeyPatch) -> None:
    esperas: list[float] = []
    monkeypatch.setattr(modulo_agente.time, "sleep", esperas.append)
    api = ApiFalsa([error_api(429), mensaje_api([{"type": "text", "text": "Hola"}])])
    assert Agente(proveedor=claude_con(api)).responder("hola").texto == "Hola"
    assert esperas == [modulo_agente.ESPERA_REINTENTO_S]


def test_agente_sobre_claude_restaura_tras_fallas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modulo_agente.time, "sleep", lambda _: None)
    agente = Agente(proveedor=claude_con(ApiFalsa([error_api(429), error_api(429), error_api(500)])))
    assert agente.responder("hola").texto == MENSAJE_LIMITE
    assert agente.responder("hola").texto == MENSAJE_ERROR
    assert agente.historial == []
