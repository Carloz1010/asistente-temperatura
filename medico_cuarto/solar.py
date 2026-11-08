"""Posición del sol y radiación que recibe cada superficie del cuarto."""

import math
from typing import NamedTuple

from medico_cuarto.materiales import ALBEDO_SUELO, F_CIELO_VERTICAL, F_SUELO_VERTICAL


class PosicionSol(NamedTuple):
    """Dónde está el sol. Azimut: 0 = norte, 90 = este, 180 = sur, 270 = oeste."""

    altura_rad: float  # ángulo sobre el horizonte; negativo si es de noche
    azimut_rad: float


def declinacion_rad(dia_del_anio: int) -> float:
    """Inclinación del sol respecto al ecuador según la época del año (Cooper)."""
    return math.radians(23.45) * math.sin(math.radians(360.0 * (284 + dia_del_anio) / 365.0))


def ecuacion_del_tiempo_min(dia_del_anio: int) -> float:
    """Minutos que el sol real se adelanta o atrasa frente a un reloj uniforme."""
    b_rad = math.radians(360.0 * (dia_del_anio - 81) / 364.0)
    return 9.87 * math.sin(2 * b_rad) - 7.53 * math.cos(b_rad) - 1.5 * math.sin(b_rad)


def angulo_horario_rad(
    hora_local: float, longitud_grados: float, utc_offset_h: float, dia_del_anio: int
) -> float:
    """Ángulo que ha girado la Tierra desde el mediodía solar; negativo en la mañana."""
    # El sol tarda 4 minutos en recorrer cada grado entre el meridiano del huso y el lugar.
    correccion_min = 4.0 * (longitud_grados - 15.0 * utc_offset_h)
    hora_solar = hora_local + (correccion_min + ecuacion_del_tiempo_min(dia_del_anio)) / 60.0
    return math.radians(15.0 * (hora_solar - 12.0))


def posicion_sol(
    latitud_grados: float,
    longitud_grados: float,
    utc_offset_h: float,
    dia_del_anio: int,
    hora_local: float,
) -> PosicionSol:
    """Altura y azimut del sol, por trigonometría esférica."""
    latitud_rad = math.radians(latitud_grados)
    declinacion = declinacion_rad(dia_del_anio)
    horario = angulo_horario_rad(hora_local, longitud_grados, utc_offset_h, dia_del_anio)

    seno_altura = math.sin(latitud_rad) * math.sin(declinacion) + math.cos(latitud_rad) * math.cos(
        declinacion
    ) * math.cos(horario)
    altura_rad = math.asin(max(-1.0, min(1.0, seno_altura)))

    # Componentes del sol hacia el este y hacia el norte; atan2 da el azimut.
    hacia_este = -math.cos(declinacion) * math.sin(horario)
    hacia_norte = math.sin(declinacion) * math.cos(latitud_rad) - math.cos(declinacion) * math.sin(
        latitud_rad
    ) * math.cos(horario)
    azimut_rad = math.atan2(hacia_este, hacia_norte) % (2 * math.pi)
    return PosicionSol(altura_rad, azimut_rad)


def irradiancia_horizontal_w_m2(ghi_w_m2: float) -> float:
    """Sol sobre una superficie horizontal: es justo la radiación global horizontal."""
    return ghi_w_m2


def irradiancia_vertical_w_m2(
    posicion: PosicionSol,
    dni_w_m2: float,
    dhi_w_m2: float,
    ghi_w_m2: float,
    azimut_grados: float | None,
) -> float:
    """Sol sobre una superficie vertical; azimut None significa que solo recibe difusa."""
    directa_w_m2 = 0.0
    if azimut_grados is not None and posicion.altura_rad > 0:
        # cos θ: qué tan de frente le pega el sol a la pared.
        cos_incidencia = math.cos(posicion.altura_rad) * math.cos(
            posicion.azimut_rad - math.radians(azimut_grados)
        )
        directa_w_m2 = dni_w_m2 * max(0.0, cos_incidencia)
    # La pared ve media bóveda de cielo y medio suelo, que refleja parte de la radiación.
    difusa_w_m2 = dhi_w_m2 * F_CIELO_VERTICAL
    reflejada_w_m2 = ghi_w_m2 * ALBEDO_SUELO * F_SUELO_VERTICAL
    return directa_w_m2 + difusa_w_m2 + reflejada_w_m2
