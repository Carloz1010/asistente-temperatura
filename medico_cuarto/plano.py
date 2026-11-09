"""Dibujo del cuarto visto desde arriba, con el recorrido del aire.

El frente queda abajo y el fondo arriba, como si se entrara al cuarto desde la calle.
El modelo calcula cuánto aire pasa, no por dónde entra: el sentido de las flechas es
una aproximación que sigue la física de la chimenea (el aire caliente sale por lo alto).
"""

import math
from typing import Literal, NamedTuple

from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, Rectangle

from medico_cuarto.ficha import Abertura, Cuarto, LadoCuarto
from medico_cuarto.ventilacion import deja_pasar_aire, ventilador_funciona

Flujo = Literal["entra", "sale", "entra_y_sale"]

FRACCION_ZONA_ALTA: float = 0.75  # un hueco por encima de esta parte del alto saca el aire caliente
OCUPACION_MAXIMA_PARED: float = 0.9  # si los huecos no caben, se encogen hasta llenar esto

COLOR_ENTRA: str = "#2a78d6"
COLOR_SALE: str = "#eb6834"
COLOR_TINTA: str = "#0b0b0b"
COLOR_TEXTO_SUAVE: str = "#52514e"
COLOR_PARED_INTERIOR: str = "#b8b6ad"
COLOR_PISO: str = "#f6f4ee"
COLOR_FONDO: str = "#ffffff"
COLOR_CERRADA: str = "#8a8880"
COLOR_ABANICO: str = "#52514e"

NOMBRE_ABERTURA: dict[str, str] = {
    "ventana": "Ventana",
    "puerta": "Puerta",
    "calado": "Calado",
    "rejilla": "Rejilla",
}
NOMBRE_PARED: dict[str, str] = {
    "frente": "Frente",
    "fondo": "Fondo",
    "izquierda": "Izquierda",
    "derecha": "Derecha",
}
# Cómo se alinea el texto que va pegado a cada pared, por dentro del cuarto.
ALINEACION_ADENTRO: dict[str, tuple[str, str]] = {
    "frente": ("center", "bottom"),
    "fondo": ("center", "top"),
    "izquierda": ("left", "center"),
    "derecha": ("right", "center"),
}
ALINEACION_AFUERA: dict[str, str] = {"izquierda": "left", "derecha": "right"}

# Distancias del dibujo, como fracción de la dimensión mayor del cuarto.
MARGEN: float = 0.46
BORDE_FIGURA: float = 0.01
PUNTA_FLECHA: float = 0.03
COLA_FLECHA: float = 0.25
MITAD_FLECHA: float = 0.14
SEPARACION_DOBLE_FLECHA: float = 0.07
ETIQUETA_PARED: float = 0.37
ETIQUETA_ABERTURA: float = 0.05
ABANICO_DESDE_PARED: float = 0.27
RADIO_ABANICO: float = 0.07
ALTURA_ABANICO_CENTRAL: float = 0.6  # fracción del largo del cuarto
LADO_FIGURA_IN: float = 5.6  # más pequeño = letra más grande al mostrarlo en la página


class FlujoAbertura(NamedTuple):
    """Abertura por la que pasa aire y en qué sentido se dibuja."""

    abertura: Abertura
    flujo: Flujo


# --- Por dónde se dibuja el aire ---


def _altura_centro_m(abertura: Abertura) -> float:
    return abertura.altura_base_m + abertura.alto_m / 2.0


def _area_m2(abertura: Abertura) -> float:
    return abertura.ancho_m * abertura.alto_m


def _ventana_del_ventilador(cuarto: Cuarto, es_de_noche: bool) -> Abertura | None:
    """El ventilador va en la ventana más grande de las que están abiertas."""
    return max(
        (a for a in cuarto.aberturas if a.tipo == "ventana"),
        key=lambda a: (deja_pasar_aire(a, es_de_noche), _area_m2(a)),
        default=None,
    )


def _ventana_con_abanico(cuarto: Cuarto, es_de_noche: bool) -> Abertura | None:
    """La ventana donde se dibuja el abanico, si es que va en una."""
    if cuarto.ventilador != "en_ventana_sacando":
        return None
    return _ventana_del_ventilador(cuarto, es_de_noche)


def _lado_de_salida(activas: list[Abertura], alto_cuarto_m: float) -> LadoCuarto:
    """El aire caliente sube: sale por el hueco alto o, si no hay, hacia el pasillo."""

    def prioridad(lado: LadoCuarto) -> tuple[bool, bool, float]:
        del_lado = [a for a in activas if a.lado == lado]
        centro_m = max(_altura_centro_m(a) for a in del_lado)
        return (
            centro_m >= FRACCION_ZONA_ALTA * alto_cuarto_m,
            all(a.conexion == "indirecta" for a in del_lado),
            centro_m,
        )

    return max(dict.fromkeys(a.lado for a in activas), key=prioridad)


def flujo_aire(cuarto: Cuarto, es_de_noche: bool = False) -> list[FlujoAbertura]:
    """Sentido del aire en cada abertura que lo deja pasar."""
    activas = [a for a in cuarto.aberturas if deja_pasar_aire(a, es_de_noche)]
    if not activas:
        return []
    if ventilador_funciona(cuarto, es_de_noche):
        # El ventilador saca por su ventana; el aire de reemplazo entra por las demás.
        ventana = _ventana_del_ventilador(cuarto, es_de_noche)
        return [FlujoAbertura(a, "sale" if a is ventana else "entra") for a in activas]
    if len({a.lado for a in activas}) == 1:
        # Sin cruzada, el aire entra y sale por el mismo lado.
        return [FlujoAbertura(a, "entra_y_sale") for a in activas]
    salida = _lado_de_salida(activas, cuarto.alto_m)
    return [FlujoAbertura(a, "sale" if a.lado == salida else "entra") for a in activas]


# --- Geometría ---


def largo_pared_m(cuarto: Cuarto, lado: LadoCuarto) -> float:
    return cuarto.ancho_m if lado in ("frente", "fondo") else cuarto.largo_m


def ubicar_en_pared(largo_m: float, anchos_m: list[float]) -> list[tuple[float, float]]:
    """(centro, ancho dibujado) de cada hueco, con separaciones iguales a lo largo de la pared."""
    if not anchos_m:
        return []
    factor = min(1.0, OCUPACION_MAXIMA_PARED * largo_m / sum(anchos_m))
    dibujados = [ancho * factor for ancho in anchos_m]
    separacion = (largo_m - sum(dibujados)) / (len(dibujados) + 1)
    posiciones = []
    borde = 0.0
    for ancho in dibujados:
        borde += separacion
        posiciones.append((borde + ancho / 2.0, ancho))
        borde += ancho
    return posiciones


def _punto(
    cuarto: Cuarto, lado: LadoCuarto, a_lo_largo_m: float, hacia_afuera_m: float
) -> tuple[float, float]:
    """Pasa de coordenadas de la pared a coordenadas del dibujo."""
    if lado == "frente":
        return (a_lo_largo_m, -hacia_afuera_m)
    if lado == "fondo":
        return (a_lo_largo_m, cuarto.largo_m + hacia_afuera_m)
    if lado == "izquierda":
        return (-hacia_afuera_m, a_lo_largo_m)
    return (cuarto.ancho_m + hacia_afuera_m, a_lo_largo_m)


def _profundidad_m(cuarto: Cuarto, lado: LadoCuarto) -> float:
    """Distancia hasta la pared de enfrente."""
    return cuarto.largo_m if lado in ("frente", "fondo") else cuarto.ancho_m


# --- Dibujo ---


def _dibujar_paredes(ax: Axes, cuarto: Cuarto, unidad_m: float) -> None:
    ax.add_patch(
        Rectangle((0.0, 0.0), cuarto.ancho_m, cuarto.largo_m, facecolor=COLOR_PISO, edgecolor="none")
    )
    for pared in cuarto.paredes:
        largo_m = largo_pared_m(cuarto, pared.lado)
        x, y = zip(_punto(cuarto, pared.lado, 0.0, 0.0), _punto(cuarto, pared.lado, largo_m, 0.0))
        ax.plot(
            x,
            y,
            color=COLOR_TINTA if pared.da_afuera else COLOR_PARED_INTERIOR,
            linewidth=7,
            solid_capstyle="projecting",
            zorder=2,
        )
        nombre = NOMBRE_PARED[pared.lado] + ("" if pared.da_afuera else "\n(interior)")
        # Las de los lados se alinean al borde de la figura para que no se corten.
        distancia = (MARGEN - BORDE_FIGURA) if pared.lado in ALINEACION_AFUERA else ETIQUETA_PARED
        tx, ty = _punto(cuarto, pared.lado, largo_m / 2.0, distancia * unidad_m)
        ha = ALINEACION_AFUERA.get(pared.lado, "center")
        ax.text(tx, ty, nombre, ha=ha, va="center", fontsize=13, color=COLOR_TEXTO_SUAVE)


def _dibujar_abertura(
    ax: Axes,
    cuarto: Cuarto,
    abertura: Abertura,
    centro_m: float,
    ancho_m: float,
    pasa_aire: bool,
    etiquetar: bool,
    unidad_m: float,
) -> None:
    """Abierta: un hueco en la pared. Cerrada: una tapa gris."""
    inicio = _punto(cuarto, abertura.lado, centro_m - ancho_m / 2.0, 0.0)
    fin = _punto(cuarto, abertura.lado, centro_m + ancho_m / 2.0, 0.0)
    ax.plot(
        (inicio[0], fin[0]),
        (inicio[1], fin[1]),
        color=COLOR_FONDO if pasa_aire else COLOR_CERRADA,
        linewidth=8,
        solid_capstyle="butt",
        zorder=3,
    )
    if not etiquetar:
        return
    nombre = NOMBRE_ABERTURA[abertura.tipo]
    if abertura.conexion == "sin_salida":
        nombre += "\nsin salida"
    elif not pasa_aire:
        nombre += "\ncerrada"
    ha, va = ALINEACION_ADENTRO[abertura.lado]
    x, y = _punto(cuarto, abertura.lado, centro_m, -ETIQUETA_ABERTURA * unidad_m)
    ax.text(x, y, nombre, ha=ha, va=va, fontsize=13, color=COLOR_TINTA, zorder=4)


def _dibujar_una_flecha(
    ax: Axes,
    cuarto: Cuarto,
    lado: LadoCuarto,
    a_lo_largo_m: float,
    entra: bool,
    lado_texto: int,
    unidad_m: float,
) -> None:
    """lado_texto: +1 o -1, a qué lado de la flecha va la palabra."""
    cola = _punto(cuarto, lado, a_lo_largo_m, COLA_FLECHA * unidad_m)
    punta = _punto(cuarto, lado, a_lo_largo_m, PUNTA_FLECHA * unidad_m)
    ax.add_patch(
        FancyArrowPatch(
            cola if entra else punta,
            punta if entra else cola,
            arrowstyle="-|>",
            mutation_scale=30,
            linewidth=4,
            color=COLOR_ENTRA if entra else COLOR_SALE,
            zorder=5,
        )
    )
    palabra = "Entra\naire" if entra else "Sale\naire"
    corrimiento_m = lado_texto * 0.035 * unidad_m
    x, y = _punto(cuarto, lado, a_lo_largo_m + corrimiento_m, MITAD_FLECHA * unidad_m)
    if lado in ("frente", "fondo"):
        ha, va = ("left" if lado_texto > 0 else "right"), "center"
    else:
        ha, va = "center", ("bottom" if lado_texto > 0 else "top")
    ax.text(x, y, palabra, ha=ha, va=va, fontsize=12, color=COLOR_TINTA, linespacing=0.95, zorder=5)


def _dibujar_flechas(
    ax: Axes, cuarto: Cuarto, flujo: FlujoAbertura, centro_m: float, unidad_m: float
) -> None:
    lado = flujo.abertura.lado
    if flujo.flujo == "entra_y_sale":
        separacion_m = SEPARACION_DOBLE_FLECHA * unidad_m
        _dibujar_una_flecha(ax, cuarto, lado, centro_m - separacion_m, True, -1, unidad_m)
        _dibujar_una_flecha(ax, cuarto, lado, centro_m + separacion_m, False, 1, unidad_m)
    else:
        _dibujar_una_flecha(ax, cuarto, lado, centro_m, flujo.flujo == "entra", 1, unidad_m)


def _dibujar_abanico(ax: Axes, x: float, y: float, radio_m: float, etiqueta: str) -> None:
    """Rejilla redonda con cuatro aspas, y su nombre debajo."""
    ax.add_patch(
        Circle((x, y), radio_m, facecolor=COLOR_FONDO, edgecolor=COLOR_TINTA, linewidth=2.5, zorder=6)
    )
    for angulo_grados in (45.0, 135.0, 225.0, 315.0):
        angulo_rad = math.radians(angulo_grados)
        centro_aspa = (x + 0.5 * radio_m * math.cos(angulo_rad), y + 0.5 * radio_m * math.sin(angulo_rad))
        ax.add_patch(
            Ellipse(centro_aspa, radio_m * 0.9, radio_m * 0.42, angle=angulo_grados, color=COLOR_ABANICO, zorder=7)
        )
    ax.add_patch(Circle((x, y), radio_m * 0.16, color=COLOR_TINTA, zorder=8))
    ax.text(x, y - radio_m * 1.3, etiqueta, ha="center", va="top", fontsize=13, color=COLOR_TINTA, zorder=6)


def _dibujar_ventilador(
    ax: Axes, cuarto: Cuarto, es_de_noche: bool, centros: dict[int, float], unidad_m: float
) -> None:
    if cuarto.ventilador == "ninguno":
        return
    radio_m = RADIO_ABANICO * unidad_m
    ventana = _ventana_con_abanico(cuarto, es_de_noche)
    if ventana is not None:
        # Pegado a su ventana, sin pasar de la mitad del cuarto.
        distancia_m = min(ABANICO_DESDE_PARED * unidad_m, 0.5 * _profundidad_m(cuarto, ventana.lado))
        x, y = _punto(cuarto, ventana.lado, centros[id(ventana)], -distancia_m)
        _dibujar_abanico(ax, x, y, radio_m, "Ventana con\nabanico,\nsacando aire")
        return
    # Un poco arriba del centro, para no pisar los nombres de la pared del frente.
    _dibujar_abanico(ax, cuarto.ancho_m / 2.0, cuarto.largo_m * ALTURA_ABANICO_CENTRAL, radio_m, "Abanico")


def dibujar_plano(cuarto: Cuarto, es_de_noche: bool = False) -> Figure:
    """Figura del cuarto visto desde arriba, con sus aberturas, el aire y el ventilador."""
    unidad_m = max(cuarto.ancho_m, cuarto.largo_m)
    margen_m = MARGEN * unidad_m
    total_x_m = cuarto.ancho_m + 2.0 * margen_m
    total_y_m = cuarto.largo_m + 2.0 * margen_m
    escala = LADO_FIGURA_IN / max(total_x_m, total_y_m)

    # Figure directa, sin pyplot: Streamlit atiende cada sesión en su propio hilo.
    figura = Figure(figsize=(total_x_m * escala, total_y_m * escala), facecolor=COLOR_FONDO)
    ax = figura.add_axes((0.0, 0.0, 1.0, 1.0))
    ax.set_xlim(-margen_m, cuarto.ancho_m + margen_m)
    ax.set_ylim(-margen_m, cuarto.largo_m + margen_m)
    ax.set_aspect("equal")
    ax.axis("off")

    _dibujar_paredes(ax, cuarto, unidad_m)

    centros: dict[int, float] = {}
    ventana_con_abanico = _ventana_con_abanico(cuarto, es_de_noche)
    for lado in NOMBRE_PARED:
        de_la_pared = [a for a in cuarto.aberturas if a.lado == lado]
        posiciones = ubicar_en_pared(largo_pared_m(cuarto, lado), [a.ancho_m for a in de_la_pared])
        for abertura, (centro_m, ancho_m) in zip(de_la_pared, posiciones):
            centros[id(abertura)] = centro_m
            pasa_aire = deja_pasar_aire(abertura, es_de_noche)
            etiquetar = abertura is not ventana_con_abanico  # el abanico ya la nombra
            _dibujar_abertura(ax, cuarto, abertura, centro_m, ancho_m, pasa_aire, etiquetar, unidad_m)

    flujos = flujo_aire(cuarto, es_de_noche)
    for flujo in flujos:
        _dibujar_flechas(ax, cuarto, flujo, centros[id(flujo.abertura)], unidad_m)
    if not flujos:
        ax.text(
            cuarto.ancho_m / 2.0,
            cuarto.largo_m + 0.1 * unidad_m,
            "El aire casi no circula",
            ha="center",
            va="bottom",
            fontsize=14,
            fontweight="bold",
            color=COLOR_TINTA,
        )

    _dibujar_ventilador(ax, cuarto, es_de_noche, centros, unidad_m)

    if cuarto.extractor_eolico:
        x, y = cuarto.ancho_m * 0.78, cuarto.largo_m * 0.78
        ax.add_patch(Circle((x, y), RADIO_ABANICO * unidad_m, facecolor=COLOR_SALE, edgecolor="none", zorder=6))
        ax.text(
            x, y - RADIO_ABANICO * unidad_m * 1.3, "Extractor", ha="center", va="top", fontsize=13, color=COLOR_TINTA
        )
    return figura
