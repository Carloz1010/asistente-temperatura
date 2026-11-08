"""Clima horario desde Open-Meteo y día típico de respaldo (Barranquilla)."""

import math
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict

import requests
from pydantic import BaseModel

from medico_cuarto.materiales import HORAS_POR_DIA
from medico_cuarto.solar import posicion_sol

URL_GEOCODIFICACION: str = "https://geocoding-api.open-meteo.com/v1/search"
URL_PRONOSTICO: str = "https://api.open-meteo.com/v1/forecast"
VARIABLES_HORARIAS: str = (
    "temperature_2m,relative_humidity_2m,wind_speed_10m,"
    "shortwave_radiation,direct_normal_irradiance,diffuse_radiation"
)
TIMEOUT_S: float = 10.0

# --- Día típico de respaldo ---
LATITUD_BARRANQUILLA_GRADOS: float = 10.98
LONGITUD_BARRANQUILLA_GRADOS: float = -74.80
UTC_OFFSET_COLOMBIA_H: float = -5.0
DIA_TIPICO_DEL_ANIO: int = 227  # 15 de agosto, temporada de calor
T_MEDIA_TIPICA_C: float = 30.0
T_AMPLITUD_TIPICA_C: float = 2.0
HR_MEDIA_TIPICA_PCT: float = 75.0
HR_AMPLITUD_TIPICA_PCT: float = 5.0
HORA_MAS_CALIENTE: float = 14.0
VIENTO_TIPICO_MS: float = 3.5
GHI_PICO_TIPICO_W_M2: float = 900.0
HORA_SALIDA_SOL: float = 6.0
HORA_PUESTA_SOL: float = 18.0
FRACCION_DIFUSA_TIPICA: float = 0.30  # parte de la radiación global que llega difusa
SENO_ALTURA_MINIMO: float = 0.1  # evita que la DNI se dispare con el sol en el horizonte


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


class HoraClima(TypedDict):
    """Un registro horario: °C, %, m/s y W/m². La radiación es de la hora anterior."""

    hora: int
    t_ext: float
    hr: float
    viento_ms: float
    ghi: float
    dni: float
    dhi: float


class ClimaDia(BaseModel):
    """Las 24 horas de un día, con el lugar y si vienen del respaldo."""

    horas: list[HoraClima]
    latitud_grados: float
    longitud_grados: float
    utc_offset_h: float
    dia_del_anio: int
    hora_actual: int
    respaldo: bool = False


def _hora_actual(utc_offset_h: float) -> int:
    """Hora en punto que marca el reloj en el lugar."""
    return (datetime.now(timezone.utc) + timedelta(hours=utc_offset_h)).hour


def _hora_tipica(hora: int) -> HoraClima:
    """Registro del día típico: la humedad baja cuando la temperatura sube."""
    ciclo = math.cos(2.0 * math.pi * (hora - HORA_MAS_CALIENTE) / HORAS_POR_DIA)

    # La radiación del registro es el promedio de la hora anterior: se evalúa a su mitad.
    media_hora = hora - 0.5
    ghi_w_m2 = dni_w_m2 = dhi_w_m2 = 0.0
    if HORA_SALIDA_SOL < media_hora < HORA_PUESTA_SOL:
        duracion_dia_h = HORA_PUESTA_SOL - HORA_SALIDA_SOL
        ghi_w_m2 = GHI_PICO_TIPICO_W_M2 * math.sin(
            math.pi * (media_hora - HORA_SALIDA_SOL) / duracion_dia_h
        )
        dhi_w_m2 = FRACCION_DIFUSA_TIPICA * ghi_w_m2
        altura_rad = posicion_sol(
            LATITUD_BARRANQUILLA_GRADOS,
            LONGITUD_BARRANQUILLA_GRADOS,
            UTC_OFFSET_COLOMBIA_H,
            DIA_TIPICO_DEL_ANIO,
            media_hora,
        ).altura_rad
        # GHI = DNI · sen(altura) + DHI, despejando la directa.
        dni_w_m2 = (ghi_w_m2 - dhi_w_m2) / max(math.sin(altura_rad), SENO_ALTURA_MINIMO)

    return HoraClima(
        hora=hora,
        t_ext=T_MEDIA_TIPICA_C + T_AMPLITUD_TIPICA_C * ciclo,
        hr=HR_MEDIA_TIPICA_PCT - HR_AMPLITUD_TIPICA_PCT * ciclo,
        viento_ms=VIENTO_TIPICO_MS,
        ghi=ghi_w_m2,
        dni=dni_w_m2,
        dhi=dhi_w_m2,
    )


def dia_tipico_barranquilla() -> ClimaDia:
    """Día caluroso típico, para cuando no se puede consultar el pronóstico."""
    return ClimaDia(
        horas=[_hora_tipica(hora) for hora in range(HORAS_POR_DIA)],
        latitud_grados=LATITUD_BARRANQUILLA_GRADOS,
        longitud_grados=LONGITUD_BARRANQUILLA_GRADOS,
        utc_offset_h=UTC_OFFSET_COLOMBIA_H,
        dia_del_anio=DIA_TIPICO_DEL_ANIO,
        hora_actual=_hora_actual(UTC_OFFSET_COLOMBIA_H),
        respaldo=True,
    )


def _geocodificar(ciudad: str) -> tuple[float, float]:
    """Latitud y longitud de la ciudad; falla si Open-Meteo no la encuentra."""
    respuesta = requests.get(
        URL_GEOCODIFICACION,
        params={"name": ciudad, "count": 1, "language": "es"},
        timeout=TIMEOUT_S,
    )
    respuesta.raise_for_status()
    lugar = respuesta.json()["results"][0]
    return float(lugar["latitude"]), float(lugar["longitude"])


def _pedir_pronostico(latitud_grados: float, longitud_grados: float) -> dict[str, Any]:
    """Pronóstico horario de hoy, en la hora local del lugar."""
    respuesta = requests.get(
        URL_PRONOSTICO,
        params={
            "latitude": latitud_grados,
            "longitude": longitud_grados,
            "hourly": VARIABLES_HORARIAS,
            "wind_speed_unit": "ms",
            "timezone": "auto",
            "forecast_days": 1,
        },
        timeout=TIMEOUT_S,
    )
    respuesta.raise_for_status()
    return respuesta.json()


def _leer_pronostico(
    datos: dict[str, Any], latitud_grados: float, longitud_grados: float
) -> ClimaDia:
    """Convierte la respuesta de Open-Meteo; falla si viene incompleta."""
    horario = datos["hourly"]
    fechas = [datetime.fromisoformat(texto) for texto in horario["time"]]
    if len(fechas) != HORAS_POR_DIA:
        raise ValueError("El pronóstico no trae 24 horas.")

    horas = [
        HoraClima(
            hora=fecha.hour,
            t_ext=float(horario["temperature_2m"][i]),
            hr=float(horario["relative_humidity_2m"][i]),
            viento_ms=float(horario["wind_speed_10m"][i]),
            ghi=float(horario["shortwave_radiation"][i]),
            dni=float(horario["direct_normal_irradiance"][i]),
            dhi=float(horario["diffuse_radiation"][i]),
        )
        for i, fecha in enumerate(fechas)
    ]
    utc_offset_h = float(datos["utc_offset_seconds"]) / 3600.0
    return ClimaDia(
        horas=horas,
        latitud_grados=latitud_grados,
        longitud_grados=longitud_grados,
        utc_offset_h=utc_offset_h,
        dia_del_anio=fechas[0].timetuple().tm_yday,
        hora_actual=_hora_actual(utc_offset_h),
    )


def obtener_clima(ciudad: str) -> ClimaDia:
    """Pronóstico de hoy en la ciudad; si algo falla, el día típico con respaldo=True."""
    try:
        latitud_grados, longitud_grados = _geocodificar(ciudad)
        datos = _pedir_pronostico(latitud_grados, longitud_grados)
        return _leer_pronostico(datos, latitud_grados, longitud_grados)
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
        return dia_tipico_barranquilla()
