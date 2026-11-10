"""Pruebas de cuartos en edificios: otro piso encima y viento según el piso."""

import pytest

from medico_cuarto.agente import SUPUESTO_PISO_ENCIMA, Agente
from medico_cuarto.clima import dia_tipico_barranquilla
from medico_cuarto.diagnostico import diagnosticar
from medico_cuarto.ficha import Cuarto, cuarto_ejemplo
from medico_cuarto.materiales import FACTOR_VIENTO_LOCAL, FACTOR_VIENTO_MAXIMO
from medico_cuarto.mejoras import proponer_mejoras
from medico_cuarto.termico import capacidad_termica_j_k, simular_24h
from medico_cuarto.ventilacion import caudal_viento_m3s, factor_viento

CLIMA = dia_tipico_barranquilla()


def apartamento_intermedio() -> Cuarto:
    """El cuarto de ejemplo, pero en un tercer piso con otro apartamento encima."""
    cuarto = cuarto_ejemplo()
    cuarto.piso = 3
    cuarto.techo.otro_piso_encima = True
    return cuarto


# --- Viento ---


def test_en_el_primer_piso_el_viento_es_el_de_siempre() -> None:
    assert factor_viento(1) == pytest.approx(FACTOR_VIENTO_LOCAL)


def test_mas_arriba_sopla_mas_viento() -> None:
    factores = [factor_viento(piso) for piso in range(1, 8)]
    assert factores == sorted(factores)
    assert factores[2] > FACTOR_VIENTO_LOCAL  # tercer piso


def test_el_viento_no_supera_el_del_pronostico() -> None:
    assert factor_viento(60) == pytest.approx(FACTOR_VIENTO_MAXIMO)


def test_en_un_tercer_piso_entra_mas_aire() -> None:
    abajo = cuarto_ejemplo()
    arriba = cuarto_ejemplo()
    arriba.piso = 3
    assert caudal_viento_m3s(arriba, 3.0, False) > caudal_viento_m3s(abajo, 3.0, False)


# --- Otro piso encima ---


def test_con_otro_piso_encima_el_cuarto_queda_mas_fresco() -> None:
    bajo_el_sol = cuarto_ejemplo()
    bajo_el_sol.piso = 3
    assert max(simular_24h(apartamento_intermedio(), CLIMA).ti_c) < max(
        simular_24h(bajo_el_sol, CLIMA).ti_c
    )


def test_la_placa_de_arriba_suma_masa() -> None:
    assert capacidad_termica_j_k(apartamento_intermedio()) > capacidad_termica_j_k(cuarto_ejemplo())


def test_el_techo_no_aparece_en_el_diagnostico() -> None:
    fuentes = {a.fuente for a in diagnosticar(apartamento_intermedio(), CLIMA).aportes}
    assert "techo" not in fuentes


def test_el_material_del_techo_no_cambia_nada() -> None:
    zinc = apartamento_intermedio()
    concreto = apartamento_intermedio()
    concreto.techo.material = "concreto"
    assert simular_24h(zinc, CLIMA).ti_c == simular_24h(concreto, CLIMA).ti_c


def test_no_ofrece_mejoras_del_techo() -> None:
    ids = {p.id for p in proponer_mejoras(apartamento_intermedio(), CLIMA)}
    assert {"pintar_techo_blanco", "cielo_raso_aislante", "extractor_eolico"}.isdisjoint(ids)


# --- Agente ---


def _agente() -> Agente:
    agente = Agente.__new__(Agente)  # sin proveedor: solo se usan las herramientas
    agente.clima = CLIMA
    agente.ficha = None
    agente.resultados = None
    return agente


def test_con_otro_piso_encima_no_exige_material_ni_cielo_raso() -> None:
    ficha = {
        "largo_m": 3.0,
        "ancho_m": 3.0,
        "piso": 3,
        "techo": {"otro_piso_encima": True},
        "aberturas": [],
        "personas": 2,
    }
    resumen = _agente().herramienta_calcular_cuarto(ficha)
    assert "error" not in resumen
    assert SUPUESTO_PISO_ENCIMA in resumen["supuestos"]
    assert not any(s.startswith("Techo,") for s in resumen["supuestos"])


def test_sin_dato_de_piso_queda_como_supuesto() -> None:
    ficha = {
        "largo_m": 3.0,
        "ancho_m": 3.0,
        "techo": {"material": "zinc", "cielo_raso": "sin_cielo_raso"},
        "aberturas": [],
        "personas": 2,
    }
    supuestos = _agente().herramienta_calcular_cuarto(ficha)["supuestos"]
    assert any("piso en que está" in s for s in supuestos)
    assert any("otro piso encima" in s for s in supuestos)
