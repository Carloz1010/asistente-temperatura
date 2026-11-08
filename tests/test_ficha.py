"""Pruebas de la ficha del cuarto."""

import pytest

from medico_cuarto.ficha import Cuarto, cuarto_ejemplo


def test_ejemplo_valida() -> None:
    # Pasa la ficha a datos simples y la vuelve a validar, como cuando llega de Gemini.
    datos = cuarto_ejemplo().model_dump()
    assert Cuarto.model_validate(datos) == cuarto_ejemplo()


def test_volumen_ejemplo() -> None:
    assert cuarto_ejemplo().volumen_m3 == pytest.approx(22.5)
