"""Pruebas del agente sin red: Gemini se reemplaza por un cliente falso."""

import json
import re
from types import SimpleNamespace
from typing import Any

import httpx2
import pytest
from google.genai import errors, types

from medico_cuarto import agente as modulo_agente
from medico_cuarto.agente import (
    MENSAJE_ERROR,
    MENSAJE_LIMITE,
    Agente,
    _completar_supuestos,
    _esquema_herramienta_ficha,
)
from medico_cuarto.clima import dia_tipico_barranquilla
from medico_cuarto.diagnostico import diagnosticar
from medico_cuarto.ficha import Cuarto, cuarto_ejemplo
from medico_cuarto.mejoras import proponer_mejoras
from medico_cuarto.proveedores.gemini import ProveedorGemini
from medico_cuarto.termico import simular_24h

CLIMA = dia_tipico_barranquilla()


class ClienteFalso:
    """Devuelve, en orden, las respuestas dadas; una excepción en la lista se lanza."""

    def __init__(self, guion: list[Any]) -> None:
        self.guion = list(guion)
        self.llamadas = 0
        self.models = SimpleNamespace(generate_content=self._generar)

    def _generar(self, **_: Any) -> Any:
        self.llamadas += 1
        siguiente = self.guion.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente


def respuesta_con(*partes: types.Part) -> types.GenerateContentResponse:
    contenido = types.Content(role="model", parts=list(partes))
    return types.GenerateContentResponse(candidates=[types.Candidate(content=contenido)])


def texto(mensaje: str) -> types.GenerateContentResponse:
    return respuesta_con(types.Part.from_text(text=mensaje))


def llamada(nombre: str, **argumentos: Any) -> types.Part:
    return types.Part(function_call=types.FunctionCall(name=nombre, args=argumentos))


def error_429() -> errors.ClientError:
    return errors.ClientError(429, {"error": {"code": 429, "message": "cuota", "status": "RESOURCE_EXHAUSTED"}})


def crear_agente(cliente: ClienteFalso) -> Agente:
    return Agente(proveedor=ProveedorGemini(cliente=cliente))


def agente_con_clima(guion: list[Any] | None = None) -> Agente:
    agente = crear_agente(ClienteFalso(guion or []))
    agente.clima = CLIMA
    return agente


def ficha_ejemplo() -> dict[str, Any]:
    return cuarto_ejemplo().model_dump()


def ficha_minima() -> dict[str, Any]:
    """Solo los datos críticos: lo demás debe quedar como supuesto."""
    return {
        "largo_m": 3.0,
        "ancho_m": 3.0,
        "techo": {"material": "zinc", "cielo_raso": "sin_cielo_raso"},
        "aberturas": [],
        "personas": 2,
    }


@pytest.fixture
def sin_espera(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Reemplaza time.sleep y anota las esperas."""
    esperas: list[float] = []
    monkeypatch.setattr(modulo_agente.time, "sleep", esperas.append)
    return esperas


# --- calcular_cuarto ---


def test_calcular_cuarto_reporta_los_numeros_del_motor() -> None:
    agente = agente_con_clima()
    resumen = agente.herramienta_calcular_cuarto(ficha_ejemplo())

    cuarto = cuarto_ejemplo()
    simulacion = simular_24h(cuarto, CLIMA)
    diagnostico = diagnosticar(cuarto, CLIMA)
    propuestas = proponer_mejoras(cuarto, CLIMA)

    assert resumen["hora_mas_caliente"] == diagnostico.hora_pico
    assert resumen["temperatura_adentro_pico_c"] == round(max(simulacion.ti_c), 1)
    assert resumen["fuentes_de_calor"][0]["fuente"] == diagnostico.aportes[0].fuente
    assert [m["id"] for m in resumen["mejoras"]] == [p.id for p in propuestas]
    assert resumen["mejoras"][0]["baja_pico_c"] == round(propuestas[0].baja_pico_c, 1)
    assert agente.ficha is not None and agente.resultados is not None


def test_el_abanico_se_reporta_aparte() -> None:
    resumen = agente_con_clima().herramienta_calcular_cuarto(ficha_ejemplo())
    assert resumen["sensacion_termica_con_abanico_c"] == pytest.approx(
        resumen["semaforo"]["sensacion_termica_c"] - 2.5, abs=0.11
    )


def test_resumen_cabe_en_json() -> None:
    resumen = agente_con_clima().herramienta_calcular_cuarto(ficha_ejemplo())
    assert json.dumps(resumen, ensure_ascii=False)


@pytest.mark.parametrize(
    "quitar, esperado",
    [("largo_m", "largo_m"), ("ancho_m", "ancho_m"), ("aberturas", "aberturas"), ("personas", "personas")],
)
def test_falta_dato_critico(quitar: str, esperado: str) -> None:
    ficha = ficha_minima()
    del ficha[quitar]
    resultado = agente_con_clima().herramienta_calcular_cuarto(ficha)
    assert esperado in resultado["error"]


@pytest.mark.parametrize("campo", ["material", "cielo_raso"])
def test_falta_dato_critico_del_techo(campo: str) -> None:
    ficha = ficha_minima()
    del ficha["techo"][campo]
    assert f"techo.{campo}" in agente_con_clima().herramienta_calcular_cuarto(ficha)["error"]


def test_falta_dato_de_noche_vuelve_como_error() -> None:
    ficha = ficha_ejemplo()
    ficha["aberturas"][0]["abierta_de_noche"] = None
    agente = agente_con_clima()
    assert "de noche" in agente.herramienta_calcular_cuarto(ficha)["error"]
    assert agente.ficha is None


def test_sin_clima_no_calcula() -> None:
    assert "obtener_clima" in crear_agente(ClienteFalso([])).herramienta_calcular_cuarto(ficha_ejemplo())["error"]


def test_ficha_invalida_vuelve_como_error() -> None:
    ficha = ficha_minima()
    ficha["techo"]["material"] = "paja"
    assert "techo.material" in agente_con_clima().herramienta_calcular_cuarto(ficha)["error"]


def test_paredes_repetidas_vuelven_como_error() -> None:
    ficha = ficha_minima()
    ficha["paredes"] = [{"lado": "frente"}] * 4
    assert "cuatro paredes" in agente_con_clima().herramienta_calcular_cuarto(ficha)["error"]


def test_lo_no_critico_queda_como_supuesto() -> None:
    resumen = agente_con_clima().herramienta_calcular_cuarto(ficha_minima())
    supuestos = " ".join(resumen["supuestos"])
    assert "alto del cuarto" in supuestos
    assert "Pared frente, material: bloque" in supuestos


def test_los_supuestos_no_se_repiten() -> None:
    cuarto = Cuarto.model_validate(ficha_minima())
    _completar_supuestos(cuarto)
    cantidad = len(cuarto.supuestos)
    _completar_supuestos(cuarto)
    assert len(cuarto.supuestos) == cantidad > 0


# --- aplicar_mejora ---


def test_aplicar_mejora_reporta_antes_y_despues_y_acumula() -> None:
    agente = agente_con_clima()
    agente.herramienta_calcular_cuarto(ficha_ejemplo())
    pico_antes_c = max(agente.resultados.simulacion.ti_c)

    resultado = agente.herramienta_aplicar_mejora("pintar_techo_blanco")

    assert resultado["temperatura_antes_c"] == round(pico_antes_c, 1)
    assert resultado["temperatura_despues_c"] < resultado["temperatura_antes_c"]
    assert "techo" in resultado["advertencia_seguridad"]
    assert agente.ficha.techo.color == "blanco"
    assert agente.resultados.mejora_aplicada == "pintar_techo_blanco"
    assert agente.resultados.simulacion_antes is not None

    agente.herramienta_aplicar_mejora("cielo_raso_aislante")
    assert agente.ficha.techo.color == "blanco"
    assert agente.ficha.techo.cielo_raso == "con_cielo_raso_y_aislante"


def test_mejora_inexistente() -> None:
    agente = agente_con_clima()
    agente.herramienta_calcular_cuarto(ficha_ejemplo())
    assert "No existe" in agente.herramienta_aplicar_mejora("no_existe")["error"]


def test_mejora_que_ya_no_aplica() -> None:
    agente = agente_con_clima()
    agente.herramienta_calcular_cuarto(ficha_ejemplo())
    agente.herramienta_aplicar_mejora("pintar_techo_blanco")
    assert "no aplica" in agente.herramienta_aplicar_mejora("pintar_techo_blanco")["error"]


def test_aplicar_mejora_sin_calcular() -> None:
    assert "calcular_cuarto" in agente_con_clima().herramienta_aplicar_mejora("pintar_techo_blanco")["error"]


# --- obtener_clima ---


def test_clima_de_respaldo_trae_aviso(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modulo_agente, "obtener_clima", lambda ciudad: CLIMA)
    agente = crear_agente(ClienteFalso([]))
    assert "Barranquilla" in agente.herramienta_obtener_clima("Macondo")["aviso"]
    assert agente.clima is CLIMA


# --- Conversación ---


def test_bucle_llama_la_herramienta_y_conserva_el_contenido(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modulo_agente, "obtener_clima", lambda ciudad: CLIMA)
    parte = llamada("obtener_clima", ciudad="Barranquilla")
    parte.thought_signature = b"firma"
    cliente = ClienteFalso([respuesta_con(parte), texto("Listo, vecino.")])
    agente = crear_agente(cliente)

    respuesta = agente.responder("Vivo en Barranquilla")

    assert respuesta.texto == "Listo, vecino."
    assert respuesta.herramientas_usadas == ["obtener_clima"]
    assert [c.role for c in agente.historial] == ["user", "model", "user", "model"]
    assert agente.historial[1].parts[0].thought_signature == b"firma"
    assert agente.historial[2].parts[0].function_response.name == "obtener_clima"


def test_argumentos_mal_formados_vuelven_como_error() -> None:
    cliente = ClienteFalso([respuesta_con(llamada("calcular_cuarto", ficha="tres por tres")), texto("¿Cuánto mide?")])
    agente = crear_agente(cliente)
    assert agente.responder("hola").texto == "¿Cuánto mide?"
    assert "error" in agente.historial[2].parts[0].function_response.response


def test_tope_de_rondas_termina_con_mensaje(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(modulo_agente, "obtener_clima", lambda ciudad: CLIMA)
    guion = [respuesta_con(llamada("obtener_clima", ciudad="X"))] * modulo_agente.MAX_RONDAS_HERRAMIENTAS
    agente = crear_agente(ClienteFalso(guion))
    assert agente.responder("hola").texto == MENSAJE_ERROR
    assert agente.historial == []


def test_429_reintenta_una_vez(sin_espera: list[float]) -> None:
    cliente = ClienteFalso([error_429(), texto("Hola, vecino.")])
    respuesta = crear_agente(cliente).responder("hola")
    assert respuesta.texto == "Hola, vecino."
    assert sin_espera == [modulo_agente.ESPERA_REINTENTO_S]
    assert cliente.llamadas == 2


def test_429_doble_da_mensaje_amable_y_restaura(sin_espera: list[float]) -> None:
    cliente = ClienteFalso([texto("¿En qué ciudad vives?"), error_429(), error_429()])
    agente = crear_agente(cliente)
    agente.responder("hola")
    historial_previo = list(agente.historial)

    respuesta = agente.responder("Barranquilla")

    assert respuesta.texto == MENSAJE_LIMITE
    assert agente.historial == historial_previo
    assert len(sin_espera) == 1


def test_429_tras_una_herramienta_no_deja_el_estado_a_medias(
    sin_espera: list[float], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(modulo_agente, "obtener_clima", lambda ciudad: CLIMA)
    cliente = ClienteFalso([respuesta_con(llamada("obtener_clima", ciudad="X")), error_429(), error_429()])
    agente = crear_agente(cliente)
    assert agente.responder("X").texto == MENSAJE_LIMITE
    assert agente.historial == [] and agente.clima is None


def test_otro_error_de_api_no_reintenta(sin_espera: list[float]) -> None:
    error = errors.ServerError(503, {"error": {"code": 503, "message": "ocupado", "status": "UNAVAILABLE"}})
    cliente = ClienteFalso([error])
    assert crear_agente(cliente).responder("hola").texto == MENSAJE_ERROR
    assert sin_espera == [] and cliente.llamadas == 1


def test_sin_internet_da_mensaje_amable() -> None:
    agente = crear_agente(ClienteFalso([httpx2.ConnectTimeout("sin red")]))
    assert agente.responder("hola").texto == MENSAJE_ERROR
    assert agente.historial == []


def test_esquema_sin_referencias_colgantes() -> None:
    esquema = _esquema_herramienta_ficha()
    referencias = re.findall(r'"\$ref": "#/\$defs/(\w+)"', json.dumps(esquema))
    assert referencias and set(referencias) <= set(esquema["$defs"])
    assert "largo_m" in esquema["properties"]["ficha"]["properties"]
