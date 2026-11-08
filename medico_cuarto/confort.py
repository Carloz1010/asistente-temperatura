"""Humedad interior, índice de calor de NOAA y semáforo de confort."""

import math
from typing import Literal, NamedTuple

from medico_cuarto.materiales import (
    LIMITE_ACEPTABLE_C,
    LIMITE_CALUROSO_C,
    LIMITE_FRESCO_C,
    MAGNUS_A,
    MAGNUS_B_C,
    MAGNUS_ES0_HPA,
)

UMBRAL_ROTHFUSZ_F: float = 80.0  # por debajo, la regresión de Rothfusz no es válida

ColorSemaforo = Literal["verde", "amarillo", "naranja", "rojo"]


class Semaforo(NamedTuple):
    """Nivel de confort que corresponde a un índice de calor."""

    color: ColorSemaforo
    emoji: str
    etiqueta: str
    indice_c: float


def _presion_saturacion_hpa(t_c: float) -> float:
    """Máximo vapor que admite el aire a esa temperatura (fórmula de Magnus)."""
    return MAGNUS_ES0_HPA * math.exp(MAGNUS_A * t_c / (MAGNUS_B_C + t_c))


def hr_interior(hr_ext_pct: float, t_ext_c: float, t_int_c: float) -> float:
    """Humedad adentro: el vapor es el mismo de afuera, pero el aire caliente admite más."""
    hr_pct = (
        hr_ext_pct * _presion_saturacion_hpa(t_ext_c) / _presion_saturacion_hpa(t_int_c)
    )
    return min(hr_pct, 100.0)


def _c_a_f(t_c: float) -> float:
    return t_c * 9.0 / 5.0 + 32.0


def _f_a_c(t_f: float) -> float:
    return (t_f - 32.0) * 5.0 / 9.0


def _rothfusz_f(t_f: float, hr_pct: float) -> float:
    """Regresión de Rothfusz en °F, con las dos correcciones de humedad de NOAA."""
    indice_f = (
        -42.379
        + 2.04901523 * t_f
        + 10.14333127 * hr_pct
        - 0.22475541 * t_f * hr_pct
        - 6.83783e-3 * t_f**2
        - 5.481717e-2 * hr_pct**2
        + 1.22874e-3 * t_f**2 * hr_pct
        + 8.5282e-4 * t_f * hr_pct**2
        - 1.99e-6 * t_f**2 * hr_pct**2
    )
    if hr_pct < 13.0 and 80.0 <= t_f <= 112.0:  # aire muy seco: el sudor enfría mejor
        indice_f -= ((13.0 - hr_pct) / 4.0) * math.sqrt((17.0 - abs(t_f - 95.0)) / 17.0)
    elif hr_pct > 85.0 and 80.0 <= t_f <= 87.0:  # aire muy húmedo: el sudor casi no evapora
        indice_f += ((hr_pct - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)
    return indice_f


def indice_calor(t_c: float, hr_pct: float) -> float:
    """Sensación térmica en °C según el procedimiento de NOAA."""
    t_f = _c_a_f(t_c)
    # NOAA primero usa una fórmula simple, promediada con la temperatura.
    simple_f = 0.5 * (t_f + 61.0 + (t_f - 68.0) * 1.2 + hr_pct * 0.094)
    indice_f = (simple_f + t_f) / 2.0
    if indice_f >= UMBRAL_ROTHFUSZ_F:
        indice_f = _rothfusz_f(t_f, hr_pct)
    return _f_a_c(indice_f)


def semaforo(t_c: float, hr_pct: float) -> Semaforo:
    """Clasifica el índice de calor que producen esa temperatura y humedad."""
    indice_c = indice_calor(t_c, hr_pct)
    if indice_c < LIMITE_FRESCO_C:
        return Semaforo("verde", "🟢", "fresco", indice_c)
    if indice_c < LIMITE_ACEPTABLE_C:
        return Semaforo("amarillo", "🟡", "aceptable", indice_c)
    if indice_c <= LIMITE_CALUROSO_C:
        return Semaforo("naranja", "🟠", "caluroso", indice_c)
    return Semaforo("rojo", "🔴", "peligroso", indice_c)
