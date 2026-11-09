"""Pruebas de la Fase 4: diagnóstico por fuente y mejoras por nivel."""

import pytest

from medico_cuarto.clima import dia_tipico_barranquilla
from medico_cuarto.diagnostico import diagnosticar
from medico_cuarto.ficha import (
    Abertura,
    Cuarto,
    Pared,
    Techo,
    aberturas_sin_dato_de_noche,
    cuarto_ejemplo,
)
from medico_cuarto.mejoras import CATALOGO, HORAS_NOCHE, aplicar_mejora, proponer_mejoras
from medico_cuarto.termico import _clima_en, simular_24h
from medico_cuarto.ventilacion import caudal_total_m3s

CLIMA = dia_tipico_barranquilla()

# El ventilador suma 50 W si no aumenta el caudal. Calado y rejilla son huecos pequeños: si
# solo había una abertura, pasan el cálculo a cruzada, limitada por su área, y Q baja.
PUEDEN_CALENTAR_SEGUN_EL_CUARTO = {"ventilador_ventana", "calado_alto", "rejilla_puerta"}


def cuarto_con_todo_por_mejorar() -> Cuarto:
    """Cuarto soleado y mal ventilado donde aplica todo el catálogo."""
    return Cuarto(
        techo=Techo(material="zinc"),
        paredes=[
            Pared(lado="frente", da_afuera=True, sol="tarde"),
            Pared(lado="fondo", da_afuera=True, sol="manana"),
            Pared(lado="izquierda", da_afuera=False),
            Pared(lado="derecha", da_afuera=False),
        ],
        aberturas=[
            Abertura(tipo="ventana", lado="fondo", abierta=True, abierta_de_noche=False),
            Abertura(tipo="ventana", lado="frente", abierta=False, abierta_de_noche=False),
            Abertura(
                tipo="puerta",
                lado="izquierda",
                ancho_m=0.9,
                alto_m=2.0,
                altura_base_m=0.0,
                abierta=False,
                abierta_de_noche=False,
                conexion="indirecta",
                cerramiento="postigo",
            ),
        ],
        personas=3,
        aparatos=["televisor", "nevera", "bombillo_incandescente"],
    )


def _baja_pico_c(cuarto: Cuarto, id_mejora: str) -> float:
    """°C que baja la mejora a la hora más caliente del cuarto original."""
    base = simular_24h(cuarto, CLIMA).ti_c
    despues = simular_24h(aplicar_mejora(cuarto, id_mejora), CLIMA).ti_c
    indice_pico = base.index(max(base))
    return base[indice_pico] - despues[indice_pico]


def _noche_c(cuarto: Cuarto) -> float:
    """Temperatura promedio en las horas de dormir."""
    ti_c = simular_24h(cuarto, CLIMA).ti_c
    return sum(ti_c[hora] for hora in HORAS_NOCHE) / len(HORAS_NOCHE)


# --- Diagnóstico ---


def test_diagnostico_ordenado_y_porcentajes_suman_100() -> None:
    resultado = diagnosticar(cuarto_ejemplo(), CLIMA)
    valores = [a.aporte_c for a in resultado.aportes]
    assert valores == sorted(valores, reverse=True)
    assert sum(a.porcentaje for a in resultado.aportes) == pytest.approx(100.0)


def test_hora_pico_es_la_mas_caliente_de_la_simulacion() -> None:
    cuarto = cuarto_ejemplo()
    simulacion = simular_24h(cuarto, CLIMA)
    resultado = diagnosticar(cuarto, CLIMA)
    assert resultado.ti_pico_c == pytest.approx(max(simulacion.ti_c))
    assert simulacion.ti_c[resultado.hora_pico] == pytest.approx(resultado.ti_pico_c)


def test_en_el_ejemplo_el_techo_es_la_mayor_fuente() -> None:
    assert diagnosticar(cuarto_ejemplo(), CLIMA).aportes[0].fuente == "techo"


def test_paredes_interiores_no_aparecen_en_el_diagnostico() -> None:
    fuentes = {a.fuente for a in diagnosticar(cuarto_ejemplo(), CLIMA).aportes}
    assert {"pared_fondo", "pared_izquierda", "pared_derecha"}.isdisjoint(fuentes)


def test_fuente_que_no_existe_no_aparece() -> None:
    cuarto = cuarto_ejemplo()
    cuarto.aparatos = []
    assert "aparatos" not in {a.fuente for a in diagnosticar(cuarto, CLIMA).aportes}


def test_quitar_personas_equivale_a_un_cuarto_sin_personas() -> None:
    """Las personas no tienen masa: quitarlas en el motor o en la ficha da lo mismo."""
    cuarto = cuarto_ejemplo()
    sin_ficha = cuarto.model_copy(update={"personas": 0})
    assert simular_24h(cuarto, CLIMA, quitar=frozenset({"personas"})).ti_c == pytest.approx(
        simular_24h(sin_ficha, CLIMA).ti_c
    )


# --- Mejoras: efecto sobre la temperatura ---


@pytest.mark.parametrize("fabrica", [cuarto_ejemplo, cuarto_con_todo_por_mejorar])
def test_ninguna_mejora_propuesta_sube_la_hora_pico(fabrica) -> None:
    propuestas = proponer_mejoras(fabrica(), CLIMA)
    assert propuestas
    assert all(p.baja_pico_c >= 0 for p in propuestas)


@pytest.mark.parametrize("fabrica", [cuarto_ejemplo, cuarto_con_todo_por_mejorar])
def test_ninguna_mejora_del_catalogo_calienta_la_hora_pico(fabrica) -> None:
    """Sin el filtro de proponer_mejoras, salvo las que dependen de cómo circule el aire."""
    cuarto = fabrica()
    for mejora in CATALOGO:
        if mejora.aplica(cuarto) and mejora.id not in PUEDEN_CALENTAR_SEGUN_EL_CUARTO:
            assert _baja_pico_c(cuarto, mejora.id) >= 0, mejora.id


def test_de_noche_solo_el_cielo_raso_puede_subir_la_temperatura() -> None:
    """Con todo cerrado de noche, aislar el techo le quita al cuarto su salida al cielo frío."""
    propuestas = proponer_mejoras(cuarto_ejemplo(), CLIMA)
    assert {p.id for p in propuestas if p.baja_noche_c < 0} == {"cielo_raso_aislante"}


def test_cielo_raso_y_ventilar_de_noche_dejan_la_noche_mas_fresca_que_hoy() -> None:
    cuarto = cuarto_ejemplo()
    con_ambas = aplicar_mejora(aplicar_mejora(cuarto, "cielo_raso_aislante"), "ventilar_noche")
    assert _noche_c(con_ambas) < _noche_c(cuarto)


def test_calado_no_se_ofrece_si_empeora_el_cuarto() -> None:
    """Con una ventana abierta, el calado pasa el cálculo a cruzada, limitada por su área."""
    assert "calado_alto" not in {
        p.id for p in proponer_mejoras(cuarto_con_todo_por_mejorar(), CLIMA)
    }


def test_ventilador_no_se_ofrece_si_el_aire_ya_circula_mas_que_el() -> None:
    """Con cruzada no aumenta el caudal: solo sumaría sus 50 W."""
    assert "ventilador_ventana" not in {
        p.id for p in proponer_mejoras(cuarto_ejemplo(), CLIMA)
    }


def test_ventilador_si_se_ofrece_con_poca_ventilacion() -> None:
    assert "ventilador_ventana" in {
        p.id for p in proponer_mejoras(cuarto_con_todo_por_mejorar(), CLIMA)
    }


def test_en_el_ejemplo_la_de_mayor_efecto_es_cielo_raso() -> None:
    propuestas = proponer_mejoras(cuarto_ejemplo(), CLIMA)
    assert max(propuestas, key=lambda p: p.baja_pico_c).id == "cielo_raso_aislante"


def test_en_el_ejemplo_la_mejor_de_bajo_costo_es_pintar_el_techo() -> None:
    bajo_costo = [p for p in proponer_mejoras(cuarto_ejemplo(), CLIMA) if p.nivel == "bajo"]
    assert max(bajo_costo, key=lambda p: p.baja_pico_c).id == "pintar_techo_blanco"


# --- Mejoras: cuáles aplican y orden ---


def test_ordenadas_por_nivel_y_luego_por_efecto() -> None:
    propuestas = proponer_mejoras(cuarto_con_todo_por_mejorar(), CLIMA)
    orden = {"gratis": 0, "bajo": 1, "mayor": 2}
    claves = [(orden[p.nivel], -p.baja_pico_c) for p in propuestas]
    assert claves == sorted(claves)


def test_no_ofrece_cielo_raso_si_ya_tiene_aislante() -> None:
    cuarto = cuarto_ejemplo()
    cuarto.techo.cielo_raso = "con_cielo_raso_y_aislante"
    assert "cielo_raso_aislante" not in {p.id for p in proponer_mejoras(cuarto, CLIMA)}


def test_no_ofrece_pintar_un_techo_ya_blanco() -> None:
    cuarto = cuarto_ejemplo()
    cuarto.techo.color = "blanco"
    assert "pintar_techo_blanco" not in {p.id for p in proponer_mejoras(cuarto, CLIMA)}


def test_polisombra_solo_si_la_pared_recibe_sol() -> None:
    assert "polisombra_pared" not in {p.id for p in proponer_mejoras(cuarto_ejemplo(), CLIMA)}
    assert "polisombra_pared" in {
        p.id for p in proponer_mejoras(cuarto_con_todo_por_mejorar(), CLIMA)
    }


@pytest.mark.parametrize(
    "id_mejora",
    ["pintar_techo_blanco", "cielo_raso_aislante", "extractor_eolico", "calado_alto"],
)
def test_lo_que_implica_techo_o_estructura_lleva_advertencia(id_mejora: str) -> None:
    mejora = next(m for m in CATALOGO if m.id == id_mejora)
    assert mejora.advertencia_seguridad


# --- Dato de noche ---


def _sin_dato_de_noche() -> Cuarto:
    cuarto = cuarto_ejemplo()
    for abertura in cuarto.aberturas:
        abertura.abierta_de_noche = None
    return cuarto


@pytest.mark.parametrize("calcular", [simular_24h, diagnosticar, proponer_mejoras])
def test_no_se_calcula_sin_saber_que_queda_abierto_de_noche(calcular) -> None:
    with pytest.raises(ValueError, match="ventana del lado frente"):
        calcular(_sin_dato_de_noche(), CLIMA)


def test_solo_se_pregunta_por_lo_que_se_puede_cerrar_y_tiene_salida() -> None:
    cuarto = cuarto_ejemplo()
    cuarto.aberturas = [
        Abertura(tipo="calado", lado="frente"),
        Abertura(tipo="puerta", lado="fondo", conexion="sin_salida"),
    ]
    assert aberturas_sin_dato_de_noche(cuarto) == []


def test_abrir_abertura_ignora_un_calado_marcado_como_cerrado() -> None:
    # Si el calado le ganara, la mejora "gratis" abriría algo que ya deja pasar aire.
    cuarto = cuarto_ejemplo()
    cuarto.aberturas[0].abierta = False  # la ventana del frente
    cuarto.aberturas.append(Abertura(tipo="calado", lado="izquierda", abierta=False))
    assert aplicar_mejora(cuarto, "abrir_abertura").aberturas[0].abierta


def test_dejar_abierto_de_noche_refresca_la_noche() -> None:
    abierta = cuarto_ejemplo()
    abierta.aberturas[0].abierta_de_noche = True
    assert _noche_c(abierta) < _noche_c(cuarto_ejemplo())


def test_no_ofrece_ventilar_de_noche_si_ya_lo_hace() -> None:
    cuarto = cuarto_ejemplo()
    for abertura in cuarto.aberturas:
        abertura.abierta_de_noche = True
    assert "ventilar_noche" not in {p.id for p in proponer_mejoras(cuarto, CLIMA)}


def test_si_solo_deja_la_ventana_todavia_ofrece_abrir_la_puerta() -> None:
    cuarto = cuarto_ejemplo()
    cuarto.aberturas[0].abierta_de_noche = True
    assert "ventilar_noche" in {p.id for p in proponer_mejoras(cuarto, CLIMA)}


# --- aplicar_mejora ---


def test_aplicar_mejora_no_toca_el_original() -> None:
    cuarto = cuarto_ejemplo()
    copia = aplicar_mejora(cuarto, "pintar_techo_blanco")
    assert copia.techo.color == "blanco"
    assert cuarto.techo.color == "natural"


def test_aplicar_mejora_desconocida_falla() -> None:
    with pytest.raises(ValueError):
        aplicar_mejora(cuarto_ejemplo(), "no_existe")


@pytest.mark.parametrize("id_mejora", ["calado_alto", "rejilla_puerta"])
def test_decir_ya_lo_hice_dos_veces_no_construye_dos_veces(id_mejora: str) -> None:
    una_vez = aplicar_mejora(cuarto_ejemplo(), id_mejora)
    dos_veces = aplicar_mejora(una_vez, id_mejora)
    assert len(dos_veces.aberturas) == len(una_vez.aberturas)


def test_rejilla_conserva_el_area_de_la_puerta() -> None:
    cuarto = cuarto_ejemplo()
    area_m2 = sum(a.ancho_m * a.alto_m for a in cuarto.aberturas)
    con_rejilla = aplicar_mejora(cuarto, "rejilla_puerta")
    assert sum(a.ancho_m * a.alto_m for a in con_rejilla.aberturas) == pytest.approx(area_m2)


def test_extractor_suma_su_caudal() -> None:
    cuarto = cuarto_ejemplo()
    clima_hora = _clima_en(CLIMA, 14.0)
    con_extractor = aplicar_mejora(cuarto, "extractor_eolico")
    diferencia = caudal_total_m3s(con_extractor, clima_hora, 33.0, False) - caudal_total_m3s(
        cuarto, clima_hora, 33.0, False
    )
    assert diferencia == pytest.approx(0.08)


def test_polisombra_baja_la_temperatura_de_la_pared_con_sol() -> None:
    cuarto = cuarto_con_todo_por_mejorar()
    assert _baja_pico_c(cuarto, "polisombra_pared") > 0
