"""Pruebas del plano: sentido del aire, ubicación de los huecos y figura."""

from matplotlib.figure import Figure
from matplotlib.patches import FancyArrowPatch

from medico_cuarto.ficha import Abertura, Cuarto, cuarto_ejemplo
from medico_cuarto.plano import dibujar_plano, flujo_aire, ubicar_en_pared


def ventana(lado: str = "frente", **cambios: object) -> Abertura:
    return Abertura(tipo="ventana", lado=lado, abierta_de_noche=False, **cambios)


def puerta(lado: str = "fondo", **cambios: object) -> Abertura:
    datos = {"ancho_m": 0.9, "alto_m": 2.0, "altura_base_m": 0.0, **cambios}
    return Abertura(tipo="puerta", lado=lado, abierta_de_noche=False, **datos)


def cuarto_con(*aberturas: Abertura, **cambios: object) -> Cuarto:
    return Cuarto(aberturas=list(aberturas), **cambios)


def sentidos(cuarto: Cuarto, es_de_noche: bool = False) -> dict[str, str]:
    return {f.abertura.tipo: f.flujo for f in flujo_aire(cuarto, es_de_noche)}


def numero_de_flechas(figura: Figure) -> int:
    return sum(isinstance(p, FancyArrowPatch) for p in figura.axes[0].patches)


def textos(figura: Figure) -> str:
    return " ".join(t.get_text() for t in figura.axes[0].texts)


# --- Sentido del aire ---


def test_cruzada_entra_por_la_ventana_y_sale_al_pasillo() -> None:
    cuarto = cuarto_con(ventana(), puerta(conexion="indirecta"))
    assert sentidos(cuarto) == {"ventana": "entra", "puerta": "sale"}


def test_el_aire_caliente_sale_por_el_calado_alto() -> None:
    calado = Abertura(tipo="calado", lado="izquierda", ancho_m=0.6, alto_m=0.2, altura_base_m=2.2)
    cuarto = cuarto_con(ventana(), puerta(conexion="indirecta"), calado)
    assert sentidos(cuarto) == {"ventana": "entra", "puerta": "entra", "calado": "sale"}


def test_un_solo_lado_entra_y_sale_por_el_mismo() -> None:
    assert sentidos(cuarto_con(ventana())) == {"ventana": "entra_y_sale"}


def test_ventilador_en_ventana_saca_y_lo_demas_entra() -> None:
    cuarto = cuarto_con(ventana(), puerta(), ventilador="en_ventana_sacando")
    assert sentidos(cuarto) == {"ventana": "sale", "puerta": "entra"}


def test_ventilador_saca_por_la_ventana_abierta_mas_grande() -> None:
    chica = ventana("frente", ancho_m=0.5, alto_m=0.5)
    grande = ventana("izquierda", ancho_m=1.5, alto_m=1.0)
    cuarto = cuarto_con(chica, grande, ventilador="en_ventana_sacando")
    assert {f.abertura.lado: f.flujo for f in flujo_aire(cuarto)} == {
        "frente": "entra",
        "izquierda": "sale",
    }


def test_cerrada_o_sin_salida_no_pasa_aire() -> None:
    cuarto = cuarto_con(ventana(abierta=False), puerta(conexion="sin_salida"))
    assert flujo_aire(cuarto) == []


def test_de_noche_cuenta_abierta_de_noche() -> None:
    cuarto = cuarto_con(ventana(), puerta())  # ambas se cierran al anochecer
    assert sentidos(cuarto, es_de_noche=False) != {}
    assert sentidos(cuarto, es_de_noche=True) == {}


# --- Ubicación en la pared ---


def test_los_huecos_quedan_dentro_de_la_pared_y_sin_montarse() -> None:
    posiciones = ubicar_en_pared(3.0, [1.0, 0.9])
    bordes = [(c - a / 2.0, c + a / 2.0) for c, a in posiciones]
    assert bordes[0][0] > 0.0
    assert bordes[0][1] < bordes[1][0]
    assert bordes[1][1] < 3.0


def test_los_huecos_que_no_caben_se_encogen() -> None:
    posiciones = ubicar_en_pared(2.0, [1.5, 1.5, 1.5])
    assert sum(ancho for _, ancho in posiciones) <= 2.0
    assert posiciones[-1][0] + posiciones[-1][1] / 2.0 < 2.0


def test_pared_sin_huecos() -> None:
    assert ubicar_en_pared(3.0, []) == []


# --- Figura ---


def test_plano_del_cuarto_de_ejemplo() -> None:
    figura = dibujar_plano(cuarto_ejemplo())
    assert numero_de_flechas(figura) == 2  # una entrada y una salida
    assert "Ventana" in textos(figura)
    assert "Puerta" in textos(figura)
    assert "Abanico" in textos(figura)


def test_un_solo_lado_dibuja_dos_flechas() -> None:
    assert numero_de_flechas(dibujar_plano(cuarto_con(ventana()))) == 2


def test_cuarto_sin_aire_lo_dice_y_no_dibuja_flechas() -> None:
    figura = dibujar_plano(cuarto_con(ventana(abierta=False)))
    assert numero_de_flechas(figura) == 0
    assert "cerrada" in textos(figura)
    assert "casi no circula" in textos(figura)


def test_abanico_en_ventana_se_rotula_y_extractor_aparece() -> None:
    figura = dibujar_plano(
        cuarto_con(ventana(), ventilador="en_ventana_sacando", extractor_eolico=True)
    )
    assert "sacando aire" in textos(figura)
    assert "Extractor" in textos(figura)


def test_abanico_en_cuarto_sin_ventanas_no_falla() -> None:
    figura = dibujar_plano(cuarto_con(puerta(), ventilador="en_ventana_sacando"))
    assert "Abanico" in textos(figura)
