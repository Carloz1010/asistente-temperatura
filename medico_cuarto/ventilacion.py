"""Caudal de aire Q por viento, efecto chimenea y ventilador."""

import math
from typing import Literal, NamedTuple

from medico_cuarto.clima import ClimaHora
from medico_cuarto.ficha import Abertura, Cuarto
from medico_cuarto.materiales import (
    ACH_MINIMO_INFILTRACION,
    CAUDAL_VENTILADOR_VENTANA_M3S,
    CERO_CELSIUS_K,
    COEF_DESCARGA,
    COEF_UNA_ABERTURA,
    DELTA_CP,
    DIVISOR_CHIMENEA_UNA_ABERTURA,
    FACTOR_ABERTURA_INDIRECTA,
    FACTOR_VIENTO_LOCAL,
    GRAVEDAD_M_S2,
    SEGUNDOS_POR_HORA,
)

TipoVentilacion = Literal["cruzada", "una_abertura", "ninguna"]


class _AberturaActiva(NamedTuple):
    """Abertura por la que de verdad pasa aire, con su área ya ajustada."""

    lado: str
    area_m2: float
    alto_m: float
    altura_centro_m: float


def _deja_pasar_aire(abertura: Abertura, cuarto: Cuarto, es_de_noche: bool) -> bool:
    """Decide si el aire puede pasar por la abertura a esa hora."""
    if not abertura.abierta or abertura.conexion == "sin_salida":
        return False
    # Calados y rejillas no se pueden cerrar; ventanas y puertas sí.
    se_cierra = abertura.tipo in ("ventana", "puerta")
    return not (es_de_noche and se_cierra and not cuarto.ventila_de_noche)


def _aberturas_activas(cuarto: Cuarto, es_de_noche: bool) -> list[_AberturaActiva]:
    """Aberturas que ventilan, con el área de las indirectas reducida al 50 %."""
    activas = []
    for abertura in cuarto.aberturas:
        if not _deja_pasar_aire(abertura, cuarto, es_de_noche):
            continue
        factor = FACTOR_ABERTURA_INDIRECTA if abertura.conexion == "indirecta" else 1.0
        activas.append(
            _AberturaActiva(
                lado=abertura.lado,
                area_m2=abertura.ancho_m * abertura.alto_m * factor,
                alto_m=abertura.alto_m,
                altura_centro_m=abertura.altura_base_m + abertura.alto_m / 2.0,
            )
        )
    return activas


def tipo_ventilacion(cuarto: Cuarto, es_de_noche: bool) -> TipoVentilacion:
    """Cruzada si el aire entra y sale por lados distintos; si no, una sola abertura."""
    activas = _aberturas_activas(cuarto, es_de_noche)
    if not activas:
        return "ninguna"
    return "cruzada" if len({a.lado for a in activas}) >= 2 else "una_abertura"


def _area_total_m2(aberturas: list[_AberturaActiva]) -> float:
    return sum(a.area_m2 for a in aberturas)


def _grupos_cruzada(
    activas: list[_AberturaActiva],
) -> tuple[list[_AberturaActiva], list[_AberturaActiva]]:
    """Separa el lado con más área (una boca) del resto de lados (la otra boca)."""
    area_por_lado: dict[str, float] = {}
    for abertura in activas:
        area_por_lado[abertura.lado] = area_por_lado.get(abertura.lado, 0.0) + abertura.area_m2
    lado_mayor = max(area_por_lado, key=lambda lado: area_por_lado[lado])
    grupo_mayor = [a for a in activas if a.lado == lado_mayor]
    grupo_resto = [a for a in activas if a.lado != lado_mayor]
    return grupo_mayor, grupo_resto


def _area_efectiva_m2(area_1_m2: float, area_2_m2: float) -> float:
    """Dos huecos en serie: 1/A_ef² = 1/A₁² + 1/A₂². Manda el más pequeño."""
    return 1.0 / math.sqrt(1.0 / area_1_m2**2 + 1.0 / area_2_m2**2)


def _centro_ponderado_m(aberturas: list[_AberturaActiva]) -> float:
    """Altura media de un grupo de aberturas, pesada por el área de cada una."""
    return sum(a.altura_centro_m * a.area_m2 for a in aberturas) / _area_total_m2(aberturas)


def caudal_viento(cuarto: Cuarto, viento_10m_ms: float, es_de_noche: bool) -> float:
    """Caudal en m³/s que mueve el viento, según el tipo de ventilación."""
    activas = _aberturas_activas(cuarto, es_de_noche)
    tipo = tipo_ventilacion(cuarto, es_de_noche)
    viento_local_ms = viento_10m_ms * FACTOR_VIENTO_LOCAL  # el barrio frena el viento

    if tipo == "cruzada":
        grupo_1, grupo_2 = _grupos_cruzada(activas)
        area_ef_m2 = _area_efectiva_m2(_area_total_m2(grupo_1), _area_total_m2(grupo_2))
        return COEF_DESCARGA * area_ef_m2 * viento_local_ms * math.sqrt(DELTA_CP)
    if tipo == "una_abertura":
        return COEF_UNA_ABERTURA * _area_total_m2(activas) * viento_local_ms
    return 0.0


def caudal_chimenea(cuarto: Cuarto, ti_c: float, to_c: float, es_de_noche: bool) -> float:
    """Caudal en m³/s por efecto chimenea: el aire caliente sube y sale por lo alto."""
    activas = _aberturas_activas(cuarto, es_de_noche)
    tipo = tipo_ventilacion(cuarto, es_de_noche)
    ti_k = ti_c + CERO_CELSIUS_K
    diferencia_k = abs(ti_c - to_c)

    if tipo == "cruzada":
        grupo_1, grupo_2 = _grupos_cruzada(activas)
        area_ef_m2 = _area_efectiva_m2(_area_total_m2(grupo_1), _area_total_m2(grupo_2))
        delta_h_m = abs(_centro_ponderado_m(grupo_1) - _centro_ponderado_m(grupo_2))
        return COEF_DESCARGA * area_ef_m2 * math.sqrt(
            2.0 * GRAVEDAD_M_S2 * delta_h_m * diferencia_k / ti_k
        )
    if tipo == "una_abertura":
        # El aire entra por abajo y sale por arriba del mismo hueco.
        alto_m = max(a.alto_m for a in activas)
        area_m2 = _area_total_m2(activas)
        return (COEF_DESCARGA * area_m2 / DIVISOR_CHIMENEA_UNA_ABERTURA) * math.sqrt(
            GRAVEDAD_M_S2 * alto_m * diferencia_k / ti_k
        )
    return 0.0


def caudal_infiltracion_m3s(volumen_m3: float) -> float:
    """Aire que se cuela por rendijas aunque todo esté cerrado."""
    return ACH_MINIMO_INFILTRACION * volumen_m3 / SEGUNDOS_POR_HORA


def caudal_total(
    cuarto: Cuarto, clima_hora: ClimaHora, ti_c: float, es_de_noche: bool
) -> float:
    """Caudal final en m³/s: viento y chimenea combinados, infiltración y ventilador."""
    viento_m3s = caudal_viento(cuarto, clima_hora.viento_10m_ms, es_de_noche)
    chimenea_m3s = caudal_chimenea(cuarto, ti_c, clima_hora.temperatura_c, es_de_noche)
    natural_m3s = math.hypot(viento_m3s, chimenea_m3s)  # √(Qv² + Qch²)
    caudal_m3s = max(natural_m3s, caudal_infiltracion_m3s(cuarto.volumen_m3))
    if cuarto.ventilador == "en_ventana_sacando":
        caudal_m3s = max(caudal_m3s, CAUDAL_VENTILADOR_VENTANA_M3S)
    return caudal_m3s


def ach(caudal_m3s: float, volumen_m3: float) -> float:
    """Cambios de aire por hora: cuántas veces se renueva el aire del cuarto."""
    return caudal_m3s * SEGUNDOS_POR_HORA / volumen_m3
