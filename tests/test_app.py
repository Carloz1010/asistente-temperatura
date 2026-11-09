"""Pruebas de la interfaz con una IA de mentiras: no gastan cuota ni usan la red."""

from pathlib import Path
from typing import Any

import pytest
from streamlit.testing.v1 import AppTest

from app import (
    AVISO_ESTIMACIONES,
    BIENVENIDA,
    efecto_de_mejora,
    hora_en_palabras,
    posicion_en_escala_pct,
    sin_latex,
)
from medico_cuarto.agente import Agente
from medico_cuarto.materiales import LIMITE_ACEPTABLE_C, LIMITE_CALUROSO_C, LIMITE_FRESCO_C
from medico_cuarto.mejoras import MejoraPropuesta
from tests.test_agente import (
    ClienteFalso,
    agente_con_clima,
    crear_agente,
    ficha_ejemplo,
    llamada,
    respuesta_con,
    texto,
)

TIEMPO_MAXIMO_S: float = 120.0
RUTA_APP: Path = Path(__file__).parent.parent / "app.py"


def abrir_app(agente: Agente) -> AppTest:
    app = AppTest.from_file(RUTA_APP, default_timeout=TIEMPO_MAXIMO_S)
    app.session_state["agente"] = agente
    return app.run()


def agente_con_guion(*respuestas: Any) -> Agente:
    return agente_con_clima(list(respuestas))


def agente_que_calcula(*siguientes: Any) -> Agente:
    return agente_con_guion(
        respuesta_con(llamada("calcular_cuarto", ficha=ficha_ejemplo())),
        texto("Tu cuarto queda caliente."),
        *siguientes,
    )


def conversar(app: AppTest, mensaje: str) -> AppTest:
    return app.chat_input[0].set_value(mensaje).run()


def todo_el_texto(app: AppTest) -> str:
    bloques = [*app.markdown, *app.subheader, *app.warning]
    return " ".join(b.value for b in bloques)


def boton(app: AppTest, clave: str) -> Any:
    return next(b for b in app.button if b.key == clave)


# --- Textos ---


def test_hora_en_palabras() -> None:
    assert hora_en_palabras(14) == "a las 2 de la tarde"
    assert hora_en_palabras(13) == "a la 1 de la tarde"
    assert hora_en_palabras(12) == "a las 12 del mediodía"
    assert hora_en_palabras(0) == "a las 12 de la noche"
    assert hora_en_palabras(3) == "a las 3 de la madrugada"
    assert hora_en_palabras(9) == "a las 9 de la mañana"
    assert hora_en_palabras(20) == "a las 8 de la noche"


def mejora_con(pico_c: float, noche_c: float) -> MejoraPropuesta:
    return MejoraPropuesta("x", "X", "gratis", "porque", None, pico_c, noche_c)


def test_efecto_avisa_si_de_noche_sube() -> None:
    efecto = efecto_de_mejora(mejora_con(2.0, -0.5))
    assert "2.0" in efecto
    assert "sube 0.5" in efecto


def test_efecto_solo_de_noche_no_dice_cero_de_dia() -> None:
    efecto = efecto_de_mejora(mejora_con(0.01, 1.5))
    assert "calor" not in efecto
    assert "1.5" in efecto


def test_los_precios_no_se_vuelven_formulas() -> None:
    assert sin_latex("cuesta $20 o $30") == r"cuesta \$20 o \$30"


def test_cada_limite_del_semaforo_cae_en_su_division_de_la_barra() -> None:
    assert posicion_en_escala_pct(LIMITE_FRESCO_C) == pytest.approx(25.0)
    assert posicion_en_escala_pct(LIMITE_ACEPTABLE_C) == pytest.approx(50.0)
    assert posicion_en_escala_pct(LIMITE_CALUROSO_C) == pytest.approx(75.0)


def test_el_marcador_no_se_sale_de_la_barra() -> None:
    assert posicion_en_escala_pct(-10.0) == 0.0
    assert posicion_en_escala_pct(80.0) == 100.0


# --- Página ---


def test_arranca_con_bienvenida_y_sin_gastar_consultas() -> None:
    cliente = ClienteFalso([])

    app = abrir_app(crear_agente(cliente))

    assert not app.exception
    assert app.chat_message[0].markdown[0].value == BIENVENIDA
    assert cliente.llamadas == 0
    assert app.sidebar.warning[0].value == AVISO_ESTIMACIONES
    assert not any(b.key and b.key.startswith("hecho_") for b in app.button)


def test_sin_clave_avisa_en_vez_de_tumbarse(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("PROVEEDOR_IA", "gemini")
    monkeypatch.setattr("medico_cuarto.proveedores.load_dotenv", lambda: None)

    app = AppTest.from_file(RUTA_APP, default_timeout=TIEMPO_MAXIMO_S).run()

    assert not app.exception
    assert "GEMINI_API_KEY" in app.error[0].value


def test_chat_muestra_resultados_cuando_el_motor_calcula() -> None:
    app = conversar(abrir_app(agente_que_calcula()), "Vivo en Barranquilla")

    assert not app.exception
    assert app.chat_message[-1].markdown[0].value == "Tu cuarto queda caliente."
    contenido = todo_el_texto(app)
    assert "De dónde viene el calor" in contenido
    assert "Qué puedes hacer" in contenido
    assert "Gratis" in contenido and "Bajo costo" in contenido and "Mejora mayor" in contenido
    assert "Tu día, hora por hora" in contenido
    assert "visto desde arriba" in contenido


def test_tarjeta_usa_los_numeros_del_motor() -> None:
    agente = agente_que_calcula()
    app = conversar(abrir_app(agente), "Hola")

    r = agente.resultados
    tarjeta = next(m.value for m in app.markdown if "class='tarjeta'" in m.value)
    assert f"{r.simulacion.ti_c[r.diagnostico.hora_pico]:.1f} °C" in tarjeta
    assert r.semaforo.emoji in tarjeta
    assert hora_en_palabras(r.diagnostico.hora_pico) in tarjeta
    assert "Con el abanico encima" in tarjeta  # el ejemplo tiene abanico a las personas


def test_las_advertencias_de_seguridad_se_ven() -> None:
    app = conversar(abrir_app(agente_que_calcula()), "Hola")
    assert any("Subirse al techo" in w.value for w in app.warning)


def test_ya_lo_hice_recalcula_y_muestra_antes_y_despues_sin_ia() -> None:
    agente = agente_que_calcula()
    app = conversar(abrir_app(agente), "Hola")
    llamadas_antes = agente.proveedor.cliente.llamadas

    app = boton(app, "hecho_pintar_techo_blanco").click().run()

    assert not app.exception
    assert agente.ficha.techo.color == "blanco"
    assert agente.proveedor.cliente.llamadas == llamadas_antes
    hecha = app.session_state["hechas"][0]
    assert [m.label for m in app.metric] == ["Antes", "Ahora"]
    assert app.metric[0].value == f"{hecha['temperatura_antes_c']:.1f} °C"
    assert app.metric[1].value == f"{hecha['temperatura_despues_c']:.1f} °C"
    assert not any(b.key == "hecho_pintar_techo_blanco" for b in app.button)


def test_reiniciar_borra_la_conversacion(monkeypatch: pytest.MonkeyPatch) -> None:
    agente_nuevo = agente_con_guion()
    monkeypatch.setattr("medico_cuarto.agente.Agente", lambda: agente_nuevo)  # sin clave real
    app = conversar(abrir_app(agente_que_calcula()), "Hola")
    assert len(app.chat_message) == 3

    app = boton(app, "reiniciar").click().run()

    assert not app.exception
    assert app.session_state["agente"] is agente_nuevo
    assert app.session_state["hechas"] == []
    assert len(app.chat_message) == 1
    assert "Qué puedes hacer" not in todo_el_texto(app)
