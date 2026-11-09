"""Cuatro cuartos completos: sus resultados deben ser coherentes entre sí.

Todos miden 3 × 3 × 2.5 m, tienen las mismas personas y aparatos, y corren con el mismo
día típico. Así, lo único que cambia entre un caso y otro es lo que se quiere comparar.
"""

import math
from typing import NamedTuple

import pytest

from medico_cuarto.clima import ClimaDia, dia_tipico_barranquilla
from medico_cuarto.confort import Semaforo, hr_interior_pct, semaforo
from medico_cuarto.diagnostico import Diagnostico, diagnosticar
from medico_cuarto.ficha import Abertura, Cuarto, Pared, Techo, cuarto_ejemplo
from medico_cuarto.mejoras import HORAS_NOCHE, MejoraPropuesta, proponer_mejoras
from medico_cuarto.termico import ResultadoSimulacion, simular_24h
from medico_cuarto.ventilacion import ach, caudal_chimenea_m3s, caudal_viento_m3s

CASOS: tuple[str, ...] = ("a", "b", "c", "d")
DIAS_REFERENCIA: int = 15  # tantos días que ya no queda rastro de la temperatura inicial
ERROR_MAXIMO_TRES_DIAS_C: float = 0.1  # lo que el día 3 puede diferir del estado estable
TI_MAXIMA_CREIBLE_C: float = 50.0  # un cuarto habitado sin horno no llega a más


def _ventana(lado: str) -> Abertura:
    """Ventana de vidrio de 1 m², abierta de día y cerrada de noche."""
    return Abertura(tipo="ventana", lado=lado, abierta_de_noche=False)


def _paredes(lados_afuera: tuple[str, ...], sol: str = "ninguno") -> list[Pared]:
    """Paredes de bloque claro; el sol solo les da a las que dan afuera."""
    return [
        Pared(
            lado=lado,
            da_afuera=lado in lados_afuera,
            sol=sol if lado in lados_afuera else "ninguno",
        )
        for lado in ("frente", "fondo", "izquierda", "derecha")
    ]


def _cuarto(techo: Techo, paredes: list[Pared], aberturas: list[Abertura]) -> Cuarto:
    return Cuarto(
        techo=techo, paredes=paredes, aberturas=aberturas, personas=2, aparatos=["portatil"]
    )


def caso_a_zinc_una_ventana() -> Cuarto:
    return _cuarto(
        Techo(material="zinc", cielo_raso="sin_cielo_raso"),
        _paredes(("frente",)),
        [_ventana("frente")],
    )


def caso_b_concreto_cruzada() -> Cuarto:
    return _cuarto(
        Techo(material="concreto", cielo_raso="sin_cielo_raso"),
        _paredes(("frente", "fondo")),
        [_ventana("frente"), _ventana("fondo")],
    )


def caso_c_eternit_sol_tarde(sol: str = "tarde") -> Cuarto:
    return _cuarto(
        Techo(material="eternit", cielo_raso="con_cielo_raso"),
        _paredes(("frente",), sol=sol),
        [_ventana("frente")],
    )


class Resultado(NamedTuple):
    """Lo que el motor dice de un caso."""

    cuarto: Cuarto
    simulacion: ResultadoSimulacion
    diagnostico: Diagnostico
    semaforo: Semaforo
    mejoras: list[MejoraPropuesta]

    @property
    def pico_c(self) -> float:
        return self.diagnostico.ti_pico_c

    @property
    def hora_pico(self) -> int:
        return self.diagnostico.hora_pico

    @property
    def noche_c(self) -> float:
        return sum(self.simulacion.ti_c[h] for h in HORAS_NOCHE) / len(HORAS_NOCHE)

    @property
    def ach_pico(self) -> float:
        return ach(self.simulacion.caudal_m3s[self.hora_pico], self.cuarto.volumen_m3)

    def aporte_c(self, fuente: str) -> float:
        return next(a.aporte_c for a in self.diagnostico.aportes if a.fuente == fuente)

    def baja_pico_c(self, id_mejora: str) -> float:
        return next(m.baja_pico_c for m in self.mejoras if m.id == id_mejora)


def _resolver(cuarto: Cuarto, clima: ClimaDia) -> Resultado:
    simulacion = simular_24h(cuarto, clima)
    diagnostico = diagnosticar(cuarto, clima)
    hora = diagnostico.hora_pico
    hr_pct = hr_interior_pct(clima.horas[hora]["hr_pct"], simulacion.to_c[hora], simulacion.ti_c[hora])
    return Resultado(
        cuarto,
        simulacion,
        diagnostico,
        semaforo(simulacion.ti_c[hora], hr_pct),
        proponer_mejoras(cuarto, clima),
    )


@pytest.fixture(scope="module")
def clima() -> ClimaDia:
    return dia_tipico_barranquilla()


@pytest.fixture(scope="module")
def r(clima: ClimaDia) -> dict[str, Resultado]:
    """Una sola corrida por caso: cada una son decenas de simulaciones de 3 días."""
    return {
        "a": _resolver(caso_a_zinc_una_ventana(), clima),
        "b": _resolver(caso_b_concreto_cruzada(), clima),
        "c": _resolver(caso_c_eternit_sol_tarde(), clima),
        "d": _resolver(cuarto_ejemplo(), clima),
    }


# --- Cada caso, por sí solo, es físicamente creíble ---


@pytest.mark.parametrize("caso", CASOS)
def test_tres_dias_bastan_para_olvidar_la_condicion_inicial(
    r: dict[str, Resultado], clima: ClimaDia, caso: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Se compara con una corrida larga: el día 2 todavía puede estar medio grado lejos.
    monkeypatch.setattr("medico_cuarto.termico.DIAS_SIMULADOS", DIAS_REFERENCIA)
    estable = simular_24h(r[caso].cuarto, clima)
    diferencias_c = [abs(a - b) for a, b in zip(r[caso].simulacion.ti_c, estable.ti_c)]
    assert max(diferencias_c) < ERROR_MAXIMO_TRES_DIAS_C


@pytest.mark.parametrize("caso", CASOS)
def test_temperaturas_en_rango_creible(r: dict[str, Resultado], caso: str) -> None:
    sim = r[caso].simulacion
    assert all(math.isfinite(ti_c) for ti_c in sim.ti_c)
    assert min(sim.to_c) <= min(sim.ti_c)  # sin aire acondicionado no baja de lo que hay afuera
    assert max(sim.ti_c) < TI_MAXIMA_CREIBLE_C


@pytest.mark.parametrize("caso", CASOS)
def test_a_la_hora_pico_adentro_esta_mas_caliente(r: dict[str, Resultado], caso: str) -> None:
    res = r[caso]
    assert res.pico_c > res.simulacion.to_c[res.hora_pico]


@pytest.mark.parametrize("caso", CASOS)
def test_el_pico_es_de_dia_y_la_noche_es_mas_fresca(r: dict[str, Resultado], caso: str) -> None:
    res = r[caso]
    assert 10 <= res.hora_pico <= 18
    assert res.noche_c < res.pico_c


@pytest.mark.parametrize("caso", CASOS)
def test_el_ventilado_nunca_baja_del_minimo(r: dict[str, Resultado], caso: str) -> None:
    res = r[caso]
    assert min(ach(q, res.cuarto.volumen_m3) for q in res.simulacion.caudal_m3s) >= 0.5 - 1e-9


@pytest.mark.parametrize("caso", CASOS)
def test_todo_lo_propuesto_ayuda_en_algo(r: dict[str, Resultado], caso: str) -> None:
    propuestas = r[caso].mejoras
    assert propuestas
    assert all(m.baja_pico_c >= 0 for m in propuestas)


# --- Comparaciones entre casos ---


def test_zinc_con_una_ventana_es_mas_caliente_que_concreto_con_cruzada(
    r: dict[str, Resultado],
) -> None:
    assert r["a"].pico_c > r["b"].pico_c + 1.0  # un grado o más: no es ruido numérico


def test_el_caso_a_es_el_mas_caliente_de_los_cuatro(r: dict[str, Resultado]) -> None:
    assert r["a"].pico_c == max(r[caso].pico_c for caso in CASOS)


def test_mismo_zinc_con_mas_aire_es_mas_fresco(r: dict[str, Resultado]) -> None:
    # (a) y (d) tienen el mismo techo; (d) además tiene una puerta en otro lado.
    assert r["d"].ach_pico > r["a"].ach_pico
    assert r["d"].pico_c < r["a"].pico_c


def test_el_concreto_gana_al_zinc_en_ventilacion_cruzada(r: dict[str, Resultado]) -> None:
    # (b) y (d) ventilan de forma cruzada; (b) tiene mejor techo y más área abierta.
    assert r["b"].pico_c < r["d"].pico_c


def test_con_cruzada_entra_mas_aire_que_con_una_sola_ventana(r: dict[str, Resultado]) -> None:
    assert r["b"].ach_pico > r["a"].ach_pico
    assert r["d"].ach_pico > r["a"].ach_pico


def test_el_viento_favorece_a_b_y_la_chimenea_a_d(
    r: dict[str, Resultado], clima: ClimaDia
) -> None:
    # (b) tiene más área efectiva, pero sus dos ventanas están a la misma altura: sin chimenea.
    # La ventana y la puerta de (d) están a alturas distintas, y por eso mueve casi lo mismo.
    hora = r["d"].hora_pico
    viento_ms = clima.horas[hora]["viento_ms"]
    to_c = r["d"].simulacion.to_c[hora]
    b, d = r["b"], r["d"]
    assert caudal_viento_m3s(b.cuarto, viento_ms, False) > caudal_viento_m3s(d.cuarto, viento_ms, False)
    assert caudal_chimenea_m3s(b.cuarto, b.pico_c, to_c, False) == 0.0
    assert caudal_chimenea_m3s(d.cuarto, d.pico_c, to_c, False) > 0.0


def test_el_cielo_raso_le_gana_al_zinc_desnudo(r: dict[str, Resultado]) -> None:
    assert r["c"].pico_c < r["a"].pico_c


def test_el_mas_caliente_tambien_se_siente_peor(r: dict[str, Resultado]) -> None:
    assert r["a"].semaforo.indice_c > r["b"].semaforo.indice_c


# --- La causa y el efecto van en el sentido correcto ---


@pytest.mark.parametrize("caso", ["a", "d"])
def test_con_zinc_desnudo_el_techo_es_la_mayor_fuente(r: dict[str, Resultado], caso: str) -> None:
    assert r[caso].diagnostico.aportes[0].fuente == "techo"


def test_el_techo_aporta_menos_si_tiene_cielo_raso(r: dict[str, Resultado]) -> None:
    assert r["c"].aporte_c("techo") < r["a"].aporte_c("techo")


def test_el_sol_de_la_tarde_calienta_y_atrasa_el_pico(
    r: dict[str, Resultado], clima: ClimaDia
) -> None:
    sin_sol = _resolver(caso_c_eternit_sol_tarde(sol="ninguno"), clima)
    assert r["c"].pico_c > sin_sol.pico_c
    assert r["c"].aporte_c("pared_frente") > sin_sol.aporte_c("pared_frente")
    assert r["c"].aporte_c("ventanas") > sin_sol.aporte_c("ventanas")
    assert r["c"].hora_pico >= sin_sol.hora_pico


def test_aislar_rinde_mas_donde_el_techo_es_peor(r: dict[str, Resultado]) -> None:
    assert r["a"].baja_pico_c("cielo_raso_aislante") > r["b"].baja_pico_c("cielo_raso_aislante")
    assert r["a"].baja_pico_c("cielo_raso_aislante") > r["c"].baja_pico_c("cielo_raso_aislante")


def test_pintar_rinde_mas_en_el_techo_que_mas_calor_deja_pasar(r: dict[str, Resultado]) -> None:
    assert r["a"].baja_pico_c("pintar_techo_blanco") > r["c"].baja_pico_c("pintar_techo_blanco")


def test_todos_cierran_de_noche_y_quedan_en_infiltracion(r: dict[str, Resultado]) -> None:
    for caso in CASOS:
        res = r[caso]
        assert ach(res.simulacion.caudal_m3s[2], res.cuarto.volumen_m3) == pytest.approx(0.5)


def test_ventilar_de_noche_baja_mas_de_noche_que_al_mediodia(r: dict[str, Resultado]) -> None:
    for caso in CASOS:
        mejora = next(m for m in r[caso].mejoras if m.id == "ventilar_noche")
        assert mejora.baja_noche_c > mejora.baja_pico_c
