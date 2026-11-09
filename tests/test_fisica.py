"""Pruebas del cálculo en un instante: ventilación, sol y balance de calor."""

import pytest

from medico_cuarto.clima import ClimaHora
from medico_cuarto.ficha import Abertura, Cuarto, cuarto_ejemplo
from medico_cuarto.solar import irradiancia_vertical_w_m2, posicion_sol
from medico_cuarto.termico import ganancias_w, temperatura_estacionaria_c
from medico_cuarto.ventilacion import ach, caudal_total_m3s, deja_pasar_aire, tipo_ventilacion


def clima_tarde(**cambios: float) -> ClimaHora:
    """Barranquilla, 15 de agosto a las 3 p. m., con sol fuerte."""
    datos: dict[str, float] = {
        "temperatura_c": 32.0,
        "humedad_pct": 60.0,
        "viento_10m_ms": 3.0,
        "ghi_w_m2": 620.0,
        "dni_w_m2": 550.0,
        "dhi_w_m2": 170.0,
        "latitud_grados": 10.98,
        "longitud_grados": -74.80,
        "utc_offset_h": -5.0,
        "dia_del_anio": 227,
        "hora_local": 15.0,
    }
    return ClimaHora.model_validate(datos | cambios)


def ejemplo_con_ventana(ancho_m: float) -> Cuarto:
    cuarto = cuarto_ejemplo()
    cuarto.aberturas[0].ancho_m = ancho_m
    return cuarto


# --- Tests obligatorios ---


def test_a_sin_fuentes_ti_igual_a_to() -> None:
    cuarto = cuarto_ejemplo()
    cuarto.personas = 0
    cuarto.aparatos = []
    cuarto.ventilador = "ninguno"
    clima = clima_tarde(ghi_w_m2=0.0, dni_w_m2=0.0, dhi_w_m2=0.0)

    ti_c = temperatura_estacionaria_c(cuarto, clima, descuento_cielo_k=0.0)

    assert ti_c == pytest.approx(clima.temperatura_c, abs=0.1)
    # A Ti = To no debe haber ningún flujo de calor.
    assert sum(ganancias_w(cuarto, clima, clima.temperatura_c, 0.0).values()) == pytest.approx(0.0)


def test_b_mas_abertura_acerca_ti_a_to() -> None:
    clima = clima_tarde()
    excesos_c = [
        temperatura_estacionaria_c(ejemplo_con_ventana(ancho_m), clima) - clima.temperatura_c
        for ancho_m in (0.6, 1.0, 1.5)
    ]
    assert excesos_c[0] > excesos_c[1] > excesos_c[2] > 0


def test_c_techo_blanco_enfria_frente_a_zinc_natural() -> None:
    clima = clima_tarde()
    zinc = cuarto_ejemplo()
    blanco = cuarto_ejemplo()
    blanco.techo.color = "blanco"
    assert temperatura_estacionaria_c(blanco, clima) < temperatura_estacionaria_c(zinc, clima)


def test_d_el_techo_es_la_mayor_ganancia_a_las_3_pm() -> None:
    cuarto = cuarto_ejemplo()
    clima = clima_tarde()
    aportes = ganancias_w(cuarto, clima, temperatura_estacionaria_c(cuarto, clima))
    assert max(aportes, key=lambda fuente: aportes[fuente]) == "techo"


# --- Controles del balance, la ventilación y el sol ---


def test_ganancias_suman_cero_en_el_equilibrio() -> None:
    cuarto = cuarto_ejemplo()
    clima = clima_tarde()
    ti_c = temperatura_estacionaria_c(cuarto, clima)
    assert sum(ganancias_w(cuarto, clima, ti_c).values()) == pytest.approx(0.0, abs=1e-6)


def test_decide_tipo_de_ventilacion() -> None:
    cuarto = cuarto_ejemplo()
    assert tipo_ventilacion(cuarto, es_de_noche=False) == "cruzada"

    cuarto.aberturas[1].conexion = "sin_salida"  # la puerta da a un espacio cerrado
    assert tipo_ventilacion(cuarto, es_de_noche=False) == "una_abertura"

    cuarto.aberturas[0].abierta = False
    assert tipo_ventilacion(cuarto, es_de_noche=False) == "ninguna"


def test_de_noche_se_cierra_salvo_que_ventilen() -> None:
    clima = clima_tarde()
    ti_c = 33.0
    cuarto = cuarto_ejemplo()
    de_dia_m3s = caudal_total_m3s(cuarto, clima, ti_c, es_de_noche=False)
    cerrado_m3s = caudal_total_m3s(cuarto, clima, ti_c, es_de_noche=True)
    assert cerrado_m3s < de_dia_m3s
    # Cerrado solo queda la infiltración mínima: 0.5 cambios de aire por hora.
    assert ach(cerrado_m3s, cuarto.volumen_m3) == pytest.approx(0.5)

    for abertura in cuarto.aberturas:
        abertura.abierta_de_noche = True
    assert caudal_total_m3s(cuarto, clima, ti_c, es_de_noche=True) == pytest.approx(de_dia_m3s)


def test_de_noche_cada_abertura_cuenta_por_separado() -> None:
    cuarto = cuarto_ejemplo()
    assert tipo_ventilacion(cuarto, es_de_noche=True) == "ninguna"

    cuarto.aberturas[0].abierta_de_noche = True  # ventana abierta, puerta cerrada
    assert tipo_ventilacion(cuarto, es_de_noche=True) == "una_abertura"

    cuarto.aberturas[1].abierta_de_noche = True
    assert tipo_ventilacion(cuarto, es_de_noche=True) == "cruzada"


def test_ventilador_no_saca_aire_por_una_ventana_cerrada_de_noche() -> None:
    clima = clima_tarde()
    cuarto = cuarto_ejemplo()
    cuarto.ventilador = "en_ventana_sacando"
    cerrada_m3s = caudal_total_m3s(cuarto, clima, 33.0, es_de_noche=True)
    assert ach(cerrada_m3s, cuarto.volumen_m3) == pytest.approx(0.5)

    cuarto.aberturas[0].abierta_de_noche = True
    assert caudal_total_m3s(cuarto, clima, 33.0, es_de_noche=True) >= 0.30


@pytest.mark.parametrize("es_de_noche", [False, True])
def test_un_calado_no_se_puede_cerrar(es_de_noche: bool) -> None:
    # La IA puede mandar abierta=False; un bloque hueco deja pasar aire de todos modos.
    calado = Abertura(tipo="calado", lado="frente", abierta=False)
    assert deja_pasar_aire(calado, es_de_noche)


def test_de_tarde_la_pared_oeste_recibe_mas_sol_que_la_este() -> None:
    clima = clima_tarde()
    posicion = posicion_sol(
        clima.latitud_grados,
        clima.longitud_grados,
        clima.utc_offset_h,
        clima.dia_del_anio,
        clima.hora_local - 0.5,
    )
    irradiancias = {
        azimut: irradiancia_vertical_w_m2(
            posicion, clima.dni_w_m2, clima.dhi_w_m2, clima.ghi_w_m2, azimut
        )
        for azimut in (90.0, 270.0)
    }
    assert irradiancias[270.0] > irradiancias[90.0]
