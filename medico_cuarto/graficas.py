"""Gráficas de resultados: curva del día, fuentes de calor y comparación de mejoras.

Aquí no se inventa ningún número: todo sale de ResultadosCuarto (el motor) o de las
funciones de confort.py. Figure directa, sin pyplot: Streamlit atiende cada sesión
en su propio hilo.
"""

from collections.abc import Sequence

from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.lines import Line2D

from medico_cuarto.clima import ClimaDia
from medico_cuarto.confort import hr_interior_pct, indice_calor_c
from medico_cuarto.diagnostico import AporteFuente
from medico_cuarto.materiales import LIMITE_ACEPTABLE_C, LIMITE_CALUROSO_C, LIMITE_FRESCO_C
from medico_cuarto.mejoras import HORAS_NOCHE, MejoraPropuesta, NivelMejora
from medico_cuarto.termico import ResultadoSimulacion

# --- Paleta (la misma de la interfaz) ---
COLOR_ADENTRO: str = "#e8590c"
COLOR_AFUERA: str = "#1c7ed6"
COLOR_SENSACION: str = "#c92a2a"
COLOR_ANTES: str = "#868e96"
COLOR_NOCHE: str = "#1971c2"
COLOR_TINTA: str = "#12302f"
COLOR_TEXTO_SUAVE: str = "#4a6663"
COLOR_GUIAS: str = "#e3edeb"
COLOR_PISTA: str = "#f1f6f5"
COLOR_FONDO: str = "#ffffff"
FUENTE: str = "DejaVu Sans"
TAMANO_LETRA: int = 13

# Fondo del semáforo detrás de la curva: verde, amarillo, naranja, rojo muy suaves.
BANDAS_CONFORT: tuple[tuple[float, float, str, str], ...] = (
    (-100.0, LIMITE_FRESCO_C, "#eaf6ed", "Fresco"),
    (LIMITE_FRESCO_C, LIMITE_ACEPTABLE_C, "#fdf8e1", "Aceptable"),
    (LIMITE_ACEPTABLE_C, LIMITE_CALUROSO_C, "#fdf0e4", "Caluroso"),
    (LIMITE_CALUROSO_C, 100.0, "#fce4e4", "Peligroso"),
)
COLOR_NIVEL: dict[NivelMejora, str] = {"gratis": "#2f9e44", "bajo": "#1c7ed6", "mayor": "#7048e8"}
NOMBRE_NIVEL: dict[NivelMejora, str] = {"gratis": "Gratis", "bajo": "Bajo costo", "mayor": "Mayor"}
NOMBRE_FUENTE: dict[str, str] = {
    "techo": "Techo",
    "pared_frente": "Pared del frente",
    "pared_fondo": "Pared del fondo",
    "pared_izquierda": "Pared izquierda",
    "pared_derecha": "Pared derecha",
    "ventanas": "Sol por ventanas",
    "personas": "Personas",
    "aparatos": "Aparatos",
}
MARCAS_HORA: dict[int, str] = {0: "12 am", 3: "3 am", 6: "6 am", 9: "9 am", 12: "12 m", 15: "3 pm", 18: "6 pm", 21: "9 pm", 23: "11 pm"}
HORA_AMANECE: int = 6
HORA_ANOCHECE: int = 18
ANCHO_IN: float = 7.2


def _estilo(figura: Figure) -> None:
    """Letra y colores comunes a todas las gráficas."""
    for ax in figura.axes:
        for etiqueta in (*ax.get_xticklabels(), *ax.get_yticklabels()):
            etiqueta.set_fontfamily(FUENTE)


def _limpiar_ejes(ax, dejar: Sequence[str] = ()) -> None:
    for borde in ("top", "right", "bottom", "left"):
        ax.spines[borde].set_visible(borde in dejar)
        ax.spines[borde].set_color(COLOR_GUIAS)


def _texto_hora(hora: int) -> str:
    if hora == 0:
        return "12 am"
    if hora == 12:
        return "12 m"
    return f"{hora % 12} {'am' if hora < 12 else 'pm'}"


def sensacion_por_hora(simulacion: ResultadoSimulacion, clima: ClimaDia) -> list[float]:
    """Índice de calor adentro en cada hora, con las mismas fórmulas del semáforo."""
    return [
        indice_calor_c(
            ti_c, hr_interior_pct(clima.horas[hora]["hr_pct"], simulacion.to_c[hora], ti_c)
        )
        for hora, ti_c in zip(simulacion.hora, simulacion.ti_c)
    ]


# --- Curva del día ---


def grafica_24h(
    simulacion: ResultadoSimulacion,
    clima: ClimaDia,
    hora_pico: int,
    simulacion_antes: ResultadoSimulacion | None = None,
    mostrar_sensacion: bool = True,
) -> Figure:
    """Adentro, afuera y sensación térmica, sobre el fondo de colores del semáforo."""
    horas = simulacion.hora
    ti = simulacion.ti_c
    to = simulacion.to_c
    sensacion = sensacion_por_hora(simulacion, clima) if mostrar_sensacion else []

    figura = Figure(figsize=(ANCHO_IN, 4.4), facecolor=COLOR_FONDO, layout="constrained")
    ax = figura.add_subplot()

    valores = [*ti, *to, *sensacion, *(simulacion_antes.ti_c if simulacion_antes else [])]
    y_min = min(valores) - 1.2
    y_max = max(valores) + 2.2
    ax.set_ylim(y_min, y_max)
    ax.set_xlim(0, 23)

    # Fondo: semáforo de confort y horas de noche.
    for desde, hasta, color, nombre in BANDAS_CONFORT:
        if hasta > y_min and desde < y_max:
            ax.axhspan(max(desde, y_min), min(hasta, y_max), color=color, zorder=0, linewidth=0)
            centro = (max(desde, y_min) + min(hasta, y_max)) / 2.0
            if min(hasta, y_max) - max(desde, y_min) > 0.8:
                ax.text(1.008, centro, nombre, transform=ax.get_yaxis_transform(), ha="left",
                        va="center", fontsize=9.5, color=COLOR_TEXTO_SUAVE, clip_on=False)
    for desde, hasta in ((0, HORA_AMANECE), (HORA_ANOCHECE, 23)):
        ax.axvspan(desde, hasta, color="#0b3d5c", alpha=0.07, zorder=0.5, linewidth=0)
    ax.text(HORA_AMANECE / 2.0, y_max - 0.25, "noche", ha="center", va="top", fontsize=10,
            color=COLOR_NOCHE, style="italic")
    ax.text((HORA_ANOCHECE + 23) / 2.0, y_max - 0.25, "noche", ha="center", va="top",
            fontsize=10, color=COLOR_NOCHE, style="italic")

    # Lo que el cuarto suma encima del aire de afuera.
    ax.fill_between(horas, to, ti, where=[a >= b for a, b in zip(ti, to)], interpolate=True,
                    color=COLOR_ADENTRO, alpha=0.13, linewidth=0, zorder=2)

    if simulacion_antes is not None:
        ax.plot(horas, simulacion_antes.ti_c, color=COLOR_ANTES, linewidth=2, linestyle=(0, (5, 3)),
                label="Adentro, antes", zorder=3)
    ax.plot(horas, to, color=COLOR_AFUERA, linewidth=2.6, label="Afuera", zorder=4,
            solid_capstyle="round")
    if sensacion:
        ax.plot(horas, sensacion, color=COLOR_SENSACION, linewidth=1.8, linestyle=(0, (1, 2.2)),
                dash_capstyle="round", label="Se siente como", zorder=4)
    ax.plot(horas, ti, color=COLOR_ADENTRO, linewidth=3.4, label="Adentro", zorder=5,
            solid_capstyle="round")

    # La hora más caliente.
    pico_c = ti[hora_pico]
    ax.axvline(hora_pico, color=COLOR_ADENTRO, linewidth=1, alpha=0.35, zorder=2)
    ax.plot([hora_pico], [pico_c], "o", color=COLOR_ADENTRO, markersize=11,
            markeredgecolor=COLOR_FONDO, markeredgewidth=2.5, zorder=6)
    ax.annotate(
        f"{pico_c:.1f} °C\n{_texto_hora(hora_pico)}",
        (hora_pico, pico_c), xytext=(0, 16), textcoords="offset points",
        ha="center", va="bottom", fontsize=TAMANO_LETRA, fontweight="bold", color=COLOR_TINTA,
        linespacing=1.1, zorder=7,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": COLOR_FONDO, "edgecolor": COLOR_ADENTRO,
              "linewidth": 1.4},
    )

    # La madrugada: lo más fresco de adentro mientras se duerme.
    horas_noche = [h for h in HORAS_NOCHE if h in horas]
    hora_fresca = min(horas_noche, key=lambda h: ti[h])
    ax.plot([hora_fresca], [ti[hora_fresca]], "o", color=COLOR_NOCHE, markersize=8,
            markeredgecolor=COLOR_FONDO, markeredgewidth=2, zorder=6)
    ax.annotate(f"{ti[hora_fresca]:.1f} °C", (hora_fresca, ti[hora_fresca]), xytext=(0, 10),
                textcoords="offset points", ha="center", va="bottom", fontsize=11,
                fontweight="bold", color=COLOR_NOCHE, zorder=7,
                bbox={"boxstyle": "round,pad=0.2", "facecolor": COLOR_FONDO, "edgecolor": "none",
                      "alpha": 0.85})

    # Hora actual en el lugar.
    if 0 <= clima.hora_actual <= 23:
        ax.axvline(clima.hora_actual, color=COLOR_TINTA, linewidth=1.2, linestyle=(0, (2, 2)),
                   alpha=0.55, zorder=3)
        ax.text(clima.hora_actual, y_min + 0.15, " ahora", ha="left", va="bottom", fontsize=9,
                color=COLOR_TINTA, alpha=0.8)

    ax.set_xticks(list(MARCAS_HORA), list(MARCAS_HORA.values()))
    ax.yaxis.set_major_formatter("{x:.0f}°")
    ax.tick_params(length=0, labelsize=TAMANO_LETRA - 2, labelcolor=COLOR_TEXTO_SUAVE, pad=6)
    ax.grid(axis="y", color=COLOR_FONDO, linewidth=1.2, alpha=0.9)
    ax.set_axisbelow(True)
    _limpiar_ejes(ax)
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.01), ncols=4, frameon=False,
              fontsize=TAMANO_LETRA - 1, borderaxespad=0.1, handlelength=2.0, columnspacing=1.3)
    _estilo(figura)
    return figura


# --- De dónde viene el calor ---


def grafica_fuentes(aportes: list[AporteFuente]) -> Figure:
    """Una pista por fuente; la barra llena muestra cuánto calienta comparada con la mayor."""
    maximo_c = max(a.aporte_c for a in aportes)
    figura = Figure(figsize=(ANCHO_IN, 0.6 * len(aportes) + 0.3), facecolor=COLOR_FONDO,
                    layout="constrained")
    ax = figura.add_subplot()
    ax.set_xlim(-0.55, 1.0)
    ax.set_ylim(len(aportes) - 0.5, -0.5)
    largo = 0.72  # fracción del ancho que ocupa la pista

    for fila, aporte in enumerate(aportes):
        fraccion = aporte.aporte_c / maximo_c
        color = COLOR_ADENTRO if fila == 0 else "#f08c4a" if fraccion >= 0.25 else "#f5b183"
        ax.plot([0.0, largo], [fila, fila], color=COLOR_PISTA, linewidth=15,
                solid_capstyle="round", zorder=1)
        ax.plot([0.0, max(largo * fraccion, 0.004)], [fila, fila], color=color, linewidth=15,
                solid_capstyle="round", zorder=2)
        nombre = NOMBRE_FUENTE.get(aporte.fuente, aporte.fuente)
        ax.text(-0.045, fila, nombre, ha="right", va="center", fontsize=TAMANO_LETRA,
                color=COLOR_TINTA, fontweight="bold" if fila == 0 else "normal")
        ax.text(largo + 0.04, fila, f"{aporte.aporte_c:.1f} °C", ha="left", va="center",
                fontsize=TAMANO_LETRA, color=COLOR_TINTA, fontweight="bold")
        ax.text(1.0, fila, f"{aporte.porcentaje:.0f} %", ha="right", va="center",
                fontsize=TAMANO_LETRA - 1, color=COLOR_TEXTO_SUAVE)
    ax.axis("off")
    return figura


# --- Comparación de mejoras ---


def grafica_mejoras(mejoras: list[MejoraPropuesta], maximo: int = 8) -> Figure:
    """Grados que baja cada mejora de día y de noche, de la que más rinde a la que menos."""
    ordenadas = sorted(mejoras, key=lambda m: m.baja_pico_c + max(m.baja_noche_c, 0.0),
                       reverse=True)[:maximo]
    filas = len(ordenadas)
    figura = Figure(figsize=(ANCHO_IN, 0.7 * filas + 0.75), facecolor=COLOR_FONDO,
                    layout="constrained")
    ax = figura.add_subplot()

    valores = [v for m in ordenadas for v in (m.baja_pico_c, m.baja_noche_c)]
    tope = max(max(valores), 0.5)
    piso = min(min(valores), 0.0)
    alto = 0.36
    for fila, mejora in enumerate(ordenadas):
        for desplazamiento, valor, color in (
            (-alto / 2, mejora.baja_pico_c, COLOR_ADENTRO),
            (alto / 2, mejora.baja_noche_c, COLOR_NOCHE),
        ):
            y = fila + desplazamiento
            ax.barh(y, valor, height=alto * 0.9, color=color if valor >= 0 else "#fa5252",
                    zorder=3)
            if abs(valor) >= 0.05:
                positivo = valor > 0
                ax.text(valor + (0.03 if positivo else -0.03) * tope, y,
                        f"{valor:.1f}°" if positivo else f"sube {-valor:.1f}°",
                        ha="left" if positivo else "right", va="center", fontsize=10.5,
                        color=COLOR_TINTA if positivo else "#c92a2a", fontweight="bold")
        # Insignia del nivel de costo, pegada al nombre.
        ax.text(-0.012, fila, NOMBRE_NIVEL[mejora.nivel], transform=ax.get_yaxis_transform(),
                ha="right", va="center", fontsize=9.5, color=COLOR_FONDO, fontweight="bold",
                bbox={"boxstyle": "round,pad=0.28", "facecolor": COLOR_NIVEL[mejora.nivel],
                      "edgecolor": "none"})

    ax.set_yticks(range(filas), [_corto(m.nombre) for m in ordenadas])
    ax.set_ylim(filas - 0.5, -0.6)
    margen_izq = 0.45 * tope if piso < 0 else 0.0
    ax.set_xlim(piso - margen_izq, tope * 1.25)
    ax.axvline(0, color="#ced4da", linewidth=1.5, zorder=2)
    ax.xaxis.set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=11.5, labelcolor=COLOR_TINTA, pad=86)
    _limpiar_ejes(ax)
    figura.legend(
        handles=[Patch(color=COLOR_ADENTRO, label="A la hora de más calor"),
                 Patch(color=COLOR_NOCHE, label="De noche, al dormir")],
        loc="outside upper left", ncols=2, frameon=False, fontsize=11.5, handlelength=1.2,
    )
    _estilo(figura)
    return figura


def _corto(nombre: str, largo: int = 34) -> str:
    """Parte los nombres largos en dos líneas para que no se coman la gráfica."""
    if len(nombre) <= largo:
        return nombre
    corte = nombre.rfind(" ", 0, largo)
    return nombre[:corte] + "\n" + nombre[corte + 1:]


__all__ = [
    "grafica_24h",
    "grafica_fuentes",
    "grafica_mejoras",
    "sensacion_por_hora",
    "Line2D",
]
