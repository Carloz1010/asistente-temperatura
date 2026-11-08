"""Clima horario desde Open-Meteo y día típico de respaldo (Barranquilla)."""

from pydantic import BaseModel


class ClimaHora(BaseModel):
    """Condiciones de afuera en una hora: lo que el motor físico necesita saber."""

    temperatura_c: float  # temperatura del aire a 2 m
    humedad_pct: float  # humedad relativa
    viento_10m_ms: float  # viento a 10 m de altura
    ghi_w_m2: float  # radiación global sobre un plano horizontal
    dni_w_m2: float  # radiación directa, medida de frente al sol
    dhi_w_m2: float  # radiación difusa que llega del cielo
    latitud_grados: float
    longitud_grados: float  # negativa al oeste de Greenwich
    utc_offset_h: float  # diferencia con UTC; Colombia es -5
    dia_del_anio: int  # 1 = 1 de enero
    hora_local: float  # 0 a 24; la radiación es el promedio de la hora anterior
