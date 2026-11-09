"""Interfaz Streamlit: chat, resultados, gráfica y plano del cuarto.

Aquí no se calcula nada: todos los números vienen del motor, a través del Agente.
"""

from itertools import pairwise
from pathlib import Path
from typing import Any

import streamlit as st
from matplotlib.figure import Figure

from medico_cuarto.agente import Agente, ResultadosCuarto
from medico_cuarto.confort import ColorSemaforo
from medico_cuarto.diagnostico import AporteFuente
from medico_cuarto.materiales import (
    LIMITE_ACEPTABLE_C,
    LIMITE_CALUROSO_C,
    LIMITE_FRESCO_C,
    REDUCCION_SENSACION_VENTILADOR_C,
)
from medico_cuarto.mejoras import MejoraPropuesta, NivelMejora
from medico_cuarto.plano import dibujar_plano

NOMBRE_IA: str = "VentIA"
BIENVENIDA: str = (
    f"¡Hola, vecino! Soy {NOMBRE_IA}. Cuéntame cómo es tu cuarto y en qué ciudad vives."
)
AVISO_ESTIMACIONES: str = "Los resultados son estimaciones"
AVATAR_IA: str = ":material/air:"
RUTA_ESTILOS: Path = Path(__file__).parent / "assets" / "estilos.css"
ALTO_CHAT_PX: int = 620  # base; assets/estilos.css lo ajusta al alto de la pantalla
ANCHO_PLANO_PX: int = 560
ANCHO_GRAFICA_IN: float = 6.2  # más angosta = letra más grande al mostrarla en la página
APORTE_VISIBLE_C: float = 0.05  # lo que se redondea a 0.0 no vale una barra

COLOR_ADENTRO: str = "#eb6834"
COLOR_AFUERA: str = "#2a78d6"
COLOR_ANTES: str = "#8a8880"
COLOR_TINTA: str = "#0b0b0b"
COLOR_TEXTO_SUAVE: str = "#52514e"
COLOR_GUIAS: str = "#e6e4dc"
TAMANO_LETRA: int = 15

FONDO_SEMAFORO: dict[ColorSemaforo, str] = {
    "verde": "#dff3e3",
    "amarillo": "#fdf3c7",
    "naranja": "#fde0c8",
    "rojo": "#f9d0d0",
}
COLOR_ESCALA: dict[ColorSemaforo, str] = {
    "verde": "#3fa866",
    "amarillo": "#efbe2b",
    "naranja": "#ee8434",
    "rojo": "#d93d3d",
}
# Dónde empieza y termina cada nivel en la barra; los extremos solo enmarcan el dibujo.
LIMITES_ESCALA_C: tuple[float, ...] = (
    LIMITE_FRESCO_C - 5.0,
    LIMITE_FRESCO_C,
    LIMITE_ACEPTABLE_C,
    LIMITE_CALUROSO_C,
    LIMITE_CALUROSO_C + 9.0,
)
PESTANAS: tuple[str, ...] = ("🔥 Calor", "🛠️ Mejoras", "🌡️ Tu día", "🗺️ Plano")
NIVELES: tuple[tuple[NivelMejora, str], ...] = (
    ("gratis", "🆓 Gratis"),
    ("bajo", "💰 Bajo costo"),
    ("mayor", "🔨 Mejora mayor"),
)
NOMBRE_FUENTE: dict[str, str] = {
    "techo": "Techo",
    "pared_frente": "Pared del frente",
    "pared_fondo": "Pared del fondo",
    "pared_izquierda": "Pared izquierda",
    "pared_derecha": "Pared derecha",
    "ventanas": "Ventanas y huecos",
    "personas": "Personas",
    "aparatos": "Aparatos",
}
MARCAS_HORA: dict[int, str] = {0: "12 am", 6: "6 am", 12: "12 m", 18: "6 pm", 23: "11 pm"}

# Ícono "air" de Material Symbols.
ICONO_AIRE: str = (
    "<svg viewBox='0 0 24 24' aria-hidden='true'><path d='M14.5 17c0 1.65-1.35 3-3 3s-3-1.35-3-3h2"
    "c0 .55.45 1 1 1s1-.45 1-1-.45-1-1-1H2v-2h9.5c1.65 0 3 1.35 3 3zM19 6.5C19 4.57 17.43 3 15.5 3"
    "S12 4.57 12 6.5h2c0-.83.67-1.5 1.5-1.5s1.5.67 1.5 1.5S16.33 8 15.5 8H2v2h13.5c1.93 0 3.5-1.57"
    " 3.5-3.5zm-.5 4.5H2v2h16.5c.83 0 1.5.67 1.5 1.5s-.67 1.5-1.5 1.5v2c1.93 0 3.5-1.57 3.5-3.5"
    "S20.43 11 18.5 11z'/></svg>"
)
MARCA: str = (
    f"<div class='marca'><span class='marca-logo'>{ICONO_AIRE}</span><div>"
    "<h1 class='marca-nombre'>Vent<em>IA</em></h1>"
    "<p class='marca-lema'>Tu cuarto más fresco, conversando</p>"
    "</div></div>"
)
CABECERA_CHAT: str = (
    f"<div class='chat-cabecera'><span class='chat-avatar'>{ICONO_AIRE}</span><div>"
    f"<strong>{NOMBRE_IA}</strong><small>Te ayuda a entender y bajar el calor de tu cuarto</small>"
    "</div></div>"
)
COMO_FUNCIONA: str = (
    "<p class='pasos-titulo'>Cómo funciona</p>"
    f"<div class='paso'><b>1</b><span>Cuéntale a {NOMBRE_IA} cómo es tu cuarto</span></div>"
    "<div class='paso'><b>2</b><span>Mira qué tan caliente queda y de dónde viene el calor</span></div>"
    "<div class='paso'><b>3</b><span>Escoge qué mejorar, empezando por lo gratis</span></div>"
    "<div class='ejemplo'>Puedes empezar así: «Vivo en Barranquilla, mi cuarto es de 3 por 4 "
    "y tiene techo de zinc».</div>"
)


# --- Textos ---


def hora_en_palabras(hora: int) -> str:
    """14 -> 'a las 2 de la tarde'."""
    if hora == 12:
        return "a las 12 del mediodía"
    if hora == 0:
        return "a las 12 de la noche"
    hora_12 = hora % 12 or 12
    if hora < 6:
        parte = "de la madrugada"
    elif hora < 12:
        parte = "de la mañana"
    elif hora < 19:
        parte = "de la tarde"
    else:
        parte = "de la noche"
    return f"{'a la' if hora_12 == 1 else 'a las'} {hora_12} {parte}"


def efecto_de_mejora(mejora: MejoraPropuesta) -> str:
    """Cuántos grados baja, de día y de noche, en una línea."""
    dia_c = round(mejora.baja_pico_c, 1)
    noche_c = round(mejora.baja_noche_c, 1)
    partes = []
    if dia_c > 0:
        partes.append(f"☀️ Baja **{dia_c:.1f} °C** en la hora de más calor")
    if noche_c > 0:
        partes.append(f"🌙 Baja **{noche_c:.1f} °C** de noche")
    elif noche_c < 0:
        partes.append(f"🌙 Ojo: de noche **sube {-noche_c:.1f} °C**")
    return " · ".join(partes) or "Casi no cambia la temperatura"


def sin_latex(texto: str) -> str:
    """Streamlit leería un precio como $20.000 como si fuera una fórmula."""
    return texto.replace("$", r"\$")


def posicion_en_escala_pct(indice_c: float) -> float:
    """Dónde va el marcador en la barra del semáforo; cada nivel ocupa la misma anchura."""
    ancho_nivel_pct = 100.0 / (len(LIMITES_ESCALA_C) - 1)
    for nivel, (desde_c, hasta_c) in enumerate(pairwise(LIMITES_ESCALA_C)):
        if indice_c < hasta_c:
            fraccion = max(0.0, (indice_c - desde_c) / (hasta_c - desde_c))
            return (nivel + fraccion) * ancho_nivel_pct
    return 100.0


# --- Gráficas (Figure directa, sin pyplot: Streamlit atiende cada sesión en su propio hilo) ---


def grafica_fuentes(aportes: list[AporteFuente]) -> Figure:
    """Barras horizontales, de la fuente que más calienta a la que menos."""
    nombres = [NOMBRE_FUENTE.get(a.fuente, a.fuente) for a in aportes]
    valores_c = [a.aporte_c for a in aportes]

    figura = Figure(figsize=(ANCHO_GRAFICA_IN, 0.55 * len(aportes) + 0.3), facecolor="#ffffff", layout="constrained")
    ax = figura.add_subplot()
    barras = ax.barh(nombres, valores_c, color=COLOR_ADENTRO, height=0.62)
    ax.bar_label(barras, fmt="%.1f °C", padding=6, fontsize=TAMANO_LETRA, color=COLOR_TINTA)
    ax.invert_yaxis()  # la más grande arriba
    ax.set_xlim(0.0, max(valores_c) * 1.25)
    ax.xaxis.set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=TAMANO_LETRA, labelcolor=COLOR_TINTA)
    for borde in ("top", "right", "bottom"):
        ax.spines[borde].set_visible(False)
    ax.spines["left"].set_color(COLOR_GUIAS)
    return figura


def grafica_24h(r: ResultadosCuarto) -> Figure:
    """Temperatura afuera y adentro a lo largo del día, con la hora pico marcada."""
    horas = r.simulacion.hora
    hora_pico = r.diagnostico.hora_pico
    pico_c = r.simulacion.ti_c[hora_pico]

    figura = Figure(figsize=(ANCHO_GRAFICA_IN, 3.7), facecolor="#ffffff", layout="constrained")
    ax = figura.add_subplot()
    if r.simulacion_antes is not None:
        ax.plot(horas, r.simulacion_antes.ti_c, color=COLOR_ANTES, linewidth=2, linestyle="--", label="Adentro, antes")
    ax.plot(horas, r.simulacion.to_c, color=COLOR_AFUERA, linewidth=2.5, label="Afuera")
    ax.plot(horas, r.simulacion.ti_c, color=COLOR_ADENTRO, linewidth=2.5, label="Adentro")
    ax.plot([hora_pico], [pico_c], "o", color=COLOR_ADENTRO, markersize=10, markeredgecolor="#ffffff", markeredgewidth=2)
    ax.annotate(
        f"{pico_c:.1f} °C",
        (hora_pico, pico_c),
        xytext=(0, 12),
        textcoords="offset points",
        ha="center",
        fontsize=TAMANO_LETRA,
        fontweight="bold",
        color=COLOR_TINTA,
        bbox={"facecolor": "#ffffff", "edgecolor": "none", "pad": 1.5},  # legible sobre las líneas
    )

    ax.set_xticks(list(MARCAS_HORA), list(MARCAS_HORA.values()))
    ax.set_xlim(0, 23)
    ax.margins(y=0.2)
    ax.yaxis.set_major_formatter("{x:.0f} °C")
    ax.tick_params(length=0, labelsize=TAMANO_LETRA - 1, labelcolor=COLOR_TEXTO_SUAVE)
    ax.grid(axis="y", color=COLOR_GUIAS, linewidth=1)
    ax.set_axisbelow(True)
    for borde in ("top", "right", "left"):
        ax.spines[borde].set_visible(False)
    ax.spines["bottom"].set_color(COLOR_GUIAS)
    ax.legend(
        loc="lower left",
        bbox_to_anchor=(0.0, 1.0),
        ncols=3,
        frameon=False,
        fontsize=TAMANO_LETRA,
        borderaxespad=0.2,
        handlelength=1.6,
    )
    return figura


# --- Bloques de resultados ---


def html_escala(indice_c: float) -> str:
    """Barra del semáforo con un marcador en la sensación térmica."""
    segmentos = "".join(f"<span style='background:{color}'></span>" for color in COLOR_ESCALA.values())
    rotulos = "<span>Fresco</span><span>Aceptable</span><span>Caluroso</span><span>Peligroso</span>"
    return (
        f"<div class='escala'>{segmentos}<i style='left:{posicion_en_escala_pct(indice_c):.1f}%'></i></div>"
        f"<div class='escala-rotulos'>{rotulos}</div>"
    )


def mostrar_tarjeta(r: ResultadosCuarto) -> None:
    """Temperatura pico, semáforo y hora. Solo lleva textos y números fijos del motor."""
    hora = r.diagnostico.hora_pico
    nivel = r.semaforo
    abanico = ""
    if r.ficha.ventilador == "a_las_personas":
        # El abanico no enfría el aire: solo cambia lo que siente el cuerpo.
        sensacion_c = nivel.indice_c - REDUCCION_SENSACION_VENTILADOR_C
        abanico = f"<div class='detalle'>🌀 Con el abanico encima: {sensacion_c:.1f} °C</div>"
    st.markdown(
        f"<div class='tarjeta' style='background:{FONDO_SEMAFORO[nivel.color]}'>"
        "<div>"
        f"<div class='nivel'>{nivel.emoji} {nivel.etiqueta.capitalize()}</div>"
        f"<div class='grados'>{r.simulacion.ti_c[hora]:.1f} °C</div>"
        "</div>"
        "<div class='tarjeta-lado'>"
        f"<div class='detalle'>Lo más caliente del día, {hora_en_palabras(hora)}</div>"
        f"<div class='detalle'>El cuerpo lo siente como <b>{nivel.indice_c:.1f} °C</b></div>"
        f"{abanico}</div>"
        f"{html_escala(nivel.indice_c)}</div>",
        unsafe_allow_html=True,
    )


def mostrar_hechas(hechas: list[dict[str, Any]]) -> None:
    """El antes y el después de cada mejora marcada; la más reciente va primero."""
    for hecha in reversed(hechas):
        with st.container(border=True):
            st.markdown(f"✅ **{hecha['mejora']}**")
            antes, ahora = st.columns(2)
            antes.metric("Antes", f"{hecha['temperatura_antes_c']:.1f} °C")
            ahora.metric(
                "Ahora",
                f"{hecha['temperatura_despues_c']:.1f} °C",
                delta=f"{-hecha['baja_c']:+.1f} °C" if hecha["baja_c"] else None,
                delta_color="inverse",
            )
            if hecha["noche_antes_c"] != hecha["noche_despues_c"]:
                st.markdown(
                    f"🌙 De noche: {hecha['noche_antes_c']:.1f} °C → {hecha['noche_despues_c']:.1f} °C"
                )


def mostrar_fuentes(r: ResultadosCuarto) -> None:
    # Las fuentes que a esa hora enfrían no son "de dónde viene el calor".
    aportes = [a for a in r.diagnostico.aportes if a.aporte_c >= APORTE_VISIBLE_C]
    st.subheader("De dónde viene el calor")
    if not aportes:
        st.markdown("Ninguna fuente está calentando tu cuarto de forma notable.")
        return
    st.pyplot(grafica_fuentes(aportes), alt="Barras con los grados que aporta cada fuente de calor")


def hacer_mejora(agente: Agente, mejora: MejoraPropuesta) -> None:
    """Botón "Ya lo hice": no gasta consultas de la IA."""
    with st.spinner("Recalculando tu cuarto…"):
        resultado = agente.marcar_mejora_hecha(mejora.id)
    if "error" in resultado:
        st.session_state.aviso = "Esa mejora ya estaba hecha."
    else:
        st.session_state.hechas.append({"nivel": mejora.nivel, **resultado})
        st.session_state.aviso = (
            f"Antes {resultado['temperatura_antes_c']:.1f} °C → "
            f"ahora {resultado['temperatura_despues_c']:.1f} °C"
        )
    st.rerun()


def mostrar_mejora(agente: Agente, mejora: MejoraPropuesta) -> None:
    with st.container(border=True):
        st.markdown(f"**{mejora.nombre}**")
        st.markdown(efecto_de_mejora(mejora))
        st.markdown(mejora.por_que)
        if mejora.advertencia_seguridad:
            st.warning(mejora.advertencia_seguridad, icon="⚠️")
        if st.button("✅ Ya lo hice", key=f"hecho_{mejora.id}"):
            hacer_mejora(agente, mejora)


def mostrar_mejoras(agente: Agente, r: ResultadosCuarto) -> None:
    st.subheader("Qué puedes hacer")
    if not r.mejoras:
        st.markdown("Ya no encuentro más mejoras para tu cuarto.")
    for nivel, titulo in NIVELES:
        del_nivel = [m for m in r.mejoras if m.nivel == nivel]
        hechas = [h for h in st.session_state.hechas if h["nivel"] == nivel]
        if del_nivel or hechas:
            st.markdown(f"### {titulo}")
        # En el mismo bloque del botón: ahí es donde la persona está mirando.
        mostrar_hechas(hechas)
        for mejora in del_nivel:
            mostrar_mejora(agente, mejora)


def mostrar_resultados(agente: Agente, r: ResultadosCuarto) -> None:
    if r.clima.respaldo:
        st.warning("No pude ver el clima de hoy: usé un día caluroso típico de Barranquilla.", icon="📡")
    mostrar_tarjeta(r)
    calor, mejoras, dia, plano = st.tabs(PESTANAS)
    with calor:
        mostrar_fuentes(r)
    with mejoras:
        mostrar_mejoras(agente, r)
    with dia:
        st.subheader("Tu día, hora por hora")
        st.pyplot(grafica_24h(r), alt="Temperatura afuera y adentro durante las 24 horas")
    with plano:
        st.subheader("Tu cuarto visto desde arriba")
        st.pyplot(dibujar_plano(r.ficha), width=ANCHO_PLANO_PX, alt="Plano del cuarto con el recorrido del aire")
        st.caption("Dibujo aproximado, de día. El viento puede cambiar el sentido del aire.")


# --- Chat ---


def burbuja(rol: str) -> Any:
    """Mensaje del chat; los de la IA llevan el ícono de VentIA."""
    return st.chat_message(rol, avatar=AVATAR_IA if rol == "assistant" else None)


def mostrar_chat(agente: Agente) -> None:
    with st.container(key="zona_chat"):
        st.markdown(CABECERA_CHAT, unsafe_allow_html=True)
        caja = st.container(height=ALTO_CHAT_PX, autoscroll=True, key="caja_chat")
        with caja:
            for mensaje in st.session_state.mensajes:
                with burbuja(mensaje["rol"]):
                    st.markdown(sin_latex(mensaje["texto"]))
        entrada = st.chat_input(f"Escríbele a {NOMBRE_IA}…", key="entrada_chat")

    if not entrada:
        return
    st.session_state.mensajes.append({"rol": "user", "texto": entrada})
    with caja:
        with burbuja("user"):
            st.markdown(sin_latex(entrada))
        with burbuja("assistant"):
            with st.spinner(f"{NOMBRE_IA} está pensando…"):
                respuesta = agente.responder(entrada)
    st.session_state.mensajes.append({"rol": "assistant", "texto": respuesta.texto})
    st.rerun()  # así los resultados nuevos aparecen de una vez


# --- Página ---


def mostrar_barra_lateral() -> None:
    with st.sidebar:
        st.markdown(COMO_FUNCIONA, unsafe_allow_html=True)
        st.warning(AVISO_ESTIMACIONES, icon="⚠️")
        if st.button("🔄 Empezar de nuevo", key="reiniciar", width="stretch"):
            st.session_state.clear()
            st.rerun()


def preparar_sesion() -> Agente:
    """La conversación vive en st.session_state; sin clave de IA, la app avisa y para."""
    if "mensajes" not in st.session_state:
        st.session_state.mensajes = [{"rol": "assistant", "texto": BIENVENIDA}]
        st.session_state.hechas = []
    if "agente" not in st.session_state:
        try:
            st.session_state.agente = Agente()
        except ValueError as error:  # falta la clave o el proveedor no existe
            st.error(f"No pude conectar la IA. {error}", icon="🔌")
            st.stop()
    return st.session_state.agente


def main() -> None:
    st.set_page_config(page_title=NOMBRE_IA, page_icon="🌬️", layout="wide")
    st.html(RUTA_ESTILOS)
    mostrar_barra_lateral()
    st.markdown(MARCA, unsafe_allow_html=True)

    agente = preparar_sesion()
    if aviso := st.session_state.pop("aviso", None):
        st.toast(aviso, icon="✅")
    resultados = agente.resultados
    if resultados is None:
        _, centro, _ = st.columns([1, 8, 1])
        with centro:
            mostrar_chat(agente)
    else:
        chat, panel = st.columns([6, 5], gap="large")
        with chat:
            mostrar_chat(agente)
        with panel:
            mostrar_resultados(agente, resultados)


if __name__ == "__main__":
    main()
