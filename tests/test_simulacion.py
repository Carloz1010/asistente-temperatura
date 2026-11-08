"""Pruebas de la simulación de 24 h y del semáforo de confort."""

import math

import pytest

from medico_cuarto.clima import dia_tipico_barranquilla
from medico_cuarto.confort import semaforo
from medico_cuarto.ficha import Cuarto, cuarto_ejemplo
from medico_cuarto.termico import simular_24h


def cuarto_cerrado() -> Cuarto:
    cuarto = cuarto_ejemplo()
    for abertura in cuarto.aberturas:
        abertura.abierta = False
    return cuarto


def test_la_simulacion_converge() -> None:
    resultado = simular_24h(cuarto_ejemplo(), dia_tipico_barranquilla())
    diferencias_c = [
        abs(dia_3 - dia_2) for dia_3, dia_2 in zip(resultado.ti_c, resultado.ti_dia_anterior_c)
    ]
    assert len(diferencias_c) == 24
    assert max(diferencias_c) < 0.2


@pytest.mark.parametrize("crear_cuarto", [cuarto_ejemplo, cuarto_cerrado])
def test_ti_nunca_es_nan(crear_cuarto) -> None:
    resultado = simular_24h(crear_cuarto(), dia_tipico_barranquilla())
    assert len(resultado.ti_c) == 24
    assert all(math.isfinite(ti_c) for ti_c in resultado.ti_c)


def test_semaforo_30_grados_70_por_ciento_es_naranja() -> None:
    # A 30 °C y 70 % el índice de calor es de unos 35 °C: la banda de 32 a 41.
    nivel = semaforo(30.0, 70.0)
    assert nivel.color == "naranja"
    assert nivel.indice_c == pytest.approx(35.0, abs=0.3)
