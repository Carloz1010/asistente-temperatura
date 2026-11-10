"""Aporte en °C de cada fuente de calor a la hora pico."""

from typing import NamedTuple

from medico_cuarto.clima import ClimaDia
from medico_cuarto.ficha import Cuarto
from medico_cuarto.termico import simular_24h

APORTE_MINIMO_C: float = 0.005  # por debajo no se nota: esa fuente no existe en este cuarto


class AporteFuente(NamedTuple):
    """Cuánto calienta una fuente el cuarto a la hora pico."""

    fuente: str  # "techo", "pared_frente", "ventanas", "personas" o "aparatos"
    aporte_c: float  # negativo si a esa hora la fuente enfría
    porcentaje: float  # parte del calor total; 0 si la fuente enfría


class Diagnostico(NamedTuple):
    """Hora más caliente del cuarto y de dónde viene su calor."""

    hora_pico: int
    ti_pico_c: float
    aportes: list[AporteFuente]  # de mayor a menor


def _fuentes(cuarto: Cuarto) -> list[str]:
    """Fuentes a evaluar; las paredes interiores y el techo bajo otro piso no intercambian calor."""
    techo = [] if cuarto.techo.otro_piso_encima else ["techo"]
    paredes = [f"pared_{pared.lado}" for pared in cuarto.paredes if pared.da_afuera]
    return [*techo, *paredes, "ventanas", "personas", "aparatos"]


def diagnosticar(cuarto: Cuarto, clima: ClimaDia) -> Diagnostico:
    """Quita una fuente a la vez: lo que baja Ti a la hora pico es su aporte."""
    base = simular_24h(cuarto, clima)
    ti_pico_c = max(base.ti_c)
    indice_pico = base.ti_c.index(ti_pico_c)

    aportes_c: dict[str, float] = {}
    for fuente in _fuentes(cuarto):
        sin_fuente = simular_24h(cuarto, clima, quitar=frozenset({fuente}))
        aporte_c = ti_pico_c - sin_fuente.ti_c[indice_pico]
        if abs(aporte_c) >= APORTE_MINIMO_C:
            aportes_c[fuente] = aporte_c

    # Los porcentajes se reparten solo entre las fuentes que calientan.
    total_c = sum(aporte for aporte in aportes_c.values() if aporte > 0)
    aportes = [
        AporteFuente(fuente, aporte, 100.0 * aporte / total_c if aporte > 0 else 0.0)
        for fuente, aporte in sorted(aportes_c.items(), key=lambda par: par[1], reverse=True)
    ]
    return Diagnostico(base.hora[indice_pico], ti_pico_c, aportes)
