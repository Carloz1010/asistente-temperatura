"""Dibujo del cuarto visto desde arriba, con el recorrido del aire.

El frente queda abajo y el fondo arriba, como si se entrara al cuarto desde la calle.
El modelo calcula cuánto aire pasa, no por dónde entra: el sentido de las flechas es
una aproximación que sigue la física de la chimenea (el aire caliente sale por lo alto).
"""

import math
from typing import Literal, NamedTuple

import numpy as np
from matplotlib.axes import Axes
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Ellipse, FancyArrowPatch, Rectangle

from medico_cuarto.ficha import Abertura, Cuarto, LadoCuarto, Pared
from medico_cuarto.ventilacion import deja_pasar_aire, ventilador_funciona

Flujo = Literal["entra", "sale", "entra_y_sale"]

FRACCION_ZONA_ALTA: float = 0.75  # un hueco por encima de esta parte del alto saca el aire caliente
OCUPACION_MAXIMA_PARED: float = 0.9  # si los huecos no caben, se encogen hasta llenar esto
LADO_BALDOSA_M: float = 0.6  # baldosa típica: da la escala del dibujo
PERSONAS_DIBUJADAS_MAX: int = 3

COLOR_ENTRA: str = "#1c7ed6"
COLOR_SALE: str = "#e8590c"
COLOR_TINTA: str = "#12302f"
COLOR_TEXTO_SUAVE: str = "#4a6663"
COLOR_PARED_CALLE: str = "#12302f"
COLOR_PARED_SOL: str = "#f08c00"
COLOR_PARED_INTERIOR: str = "#b8c4c2"
COLOR_PISO_DIA: str = "#fbf7ef"
COLOR_PISO_NOCHE: str = "#e7eef6"
COLOR_BALDOSA: str = "#ece4d4"
COLOR_BALDOSA_NOCHE: str = "#d6e0ec"
COLOR_FONDO: str = "#ffffff"
COLOR_CERRADA: str = "#868e96"
COLOR_ABANICO: str = "#4a6663"
COLOR_PERSONA: str = "#0b7285"

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
TEXTO_SOL: dict[str, str] = {
    "manana": "sol de mañana",
    "mediodia": "sol de mediodía",
    "tarde": "sol de tarde",
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
ETIQUETA_PARED_LATERAL: float = 0.39
ETIQUETA_ABERTURA: float = 0.05
ABANICO_DESDE_PARED: float = 0.27
RADIO_ABANICO: float = 0.07
ALTURA_ABANICO_CENTRAL: float = 0.6  # fracción del largo del cuarto
LADO_FIGURA_IN: float = 5.6  # más pequeño = letra más grande al mostrarlo en la página
ALTO_LEYENDA_IN: float = 0.95

# El aire se calienta mientras cruza el cuarto: azul al entrar, naranja al salir.
MAPA_RECORRIDO = LinearSegmentedColormap.from_list("recorrido", [COLOR_ENTRA, "#ae3ec9", COLOR_SALE])


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


def _hacia_adentro(lado: LadoCuarto) -> tuple[float, float]:
    """Vector unitario que apunta desde la pared hacia el centro del cuarto."""
    return {"frente": (0.0, 1.0), "fondo": (0.0, -1.0), "izquierda": (1.0, 0.0), "derecha": (-1.0, 0.0)}[lado]


# --- Dibujo ---


def _dibujar_piso(ax: Axes, cuarto: Cuarto, es_de_noche: bool) -> None:
    """Piso con baldosas de 60 cm: así se ve a ojo qué tan grande es el cuarto."""
    ax.add_patch(
        Rectangle(
            (0.0, 0.0),
            cuarto.ancho_m,
            cuarto.largo_m,
            facecolor=COLOR_PISO_NOCHE if es_de_noche else COLOR_PISO_DIA,
            edgecolor="none",
            zorder=0,
        )
    )
    color = COLOR_BALDOSA_NOCHE if es_de_noche else COLOR_BALDOSA
    for x in np.arange(LADO_BALDOSA_M, cuarto.ancho_m, LADO_BALDOSA_M):
        ax.plot((x, x), (0.0, cuarto.largo_m), color=color, linewidth=0.9, zorder=0.5)
    for y in np.arange(LADO_BALDOSA_M, cuarto.largo_m, LADO_BALDOSA_M):
        ax.plot((0.0, cuarto.ancho_m), (y, y), color=color, linewidth=0.9, zorder=0.5)


def _color_pared(pared: Pared, es_de_noche: bool) -> str:
    if not pared.da_afuera:
        return COLOR_PARED_INTERIOR
    if pared.sol != "ninguno" and not es_de_noche:
        return COLOR_PARED_SOL
    return COLOR_PARED_CALLE


def _dibujar_paredes(ax: Axes, cuarto: Cuarto, unidad_m: float, es_de_noche: bool) -> None:
    for pared in cuarto.paredes:
        largo_m = largo_pared_m(cuarto, pared.lado)
        x, y = zip(_punto(cuarto, pared.lado, 0.0, 0.0), _punto(cuarto, pared.lado, largo_m, 0.0))
        ax.plot(
            x,
            y,
            color=_color_pared(pared, es_de_noche),
            linewidth=8,
            solid_capstyle="projecting",
            zorder=2,
        )
        con_sol = pared.da_afuera and pared.sol != "ninguno" and not es_de_noche
        if not pared.da_afuera:
            detalle = "interior"
        elif pared.sol != "ninguno":
            detalle = "☀ " + TEXTO_SOL[pared.sol] if con_sol else TEXTO_SOL[pared.sol]
        else:
            detalle = "da afuera"
        color = "#c25e00" if con_sol else COLOR_TEXTO_SUAVE
        peso = "bold" if con_sol else "normal"
        if pared.lado in ALINEACION_AFUERA:
            # De lado y girado, pegado al borde: así no choca con las flechas de esa pared.
            tx, ty = _punto(cuarto, pared.lado, largo_m / 2.0, ETIQUETA_PARED_LATERAL * unidad_m)
            ax.text(tx, ty, f"{NOMBRE_PARED[pared.lado]} · {detalle}", ha="center", va="center",
                    rotation=90 if pared.lado == "izquierda" else -90, fontsize=11.5,
                    color=color, fontweight=peso)
        else:
            tx, ty = _punto(cuarto, pared.lado, largo_m / 2.0, ETIQUETA_PARED * unidad_m)
            ax.text(tx, ty, f"{NOMBRE_PARED[pared.lado]}\n{detalle}", ha="center", va="center",
                    fontsize=12, linespacing=1.05, color=color, fontweight=peso)


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
    """Abierta: un hueco en la pared con marco. Cerrada: una tapa gris."""
    inicio = _punto(cuarto, abertura.lado, centro_m - ancho_m / 2.0, 0.0)
    fin = _punto(cuarto, abertura.lado, centro_m + ancho_m / 2.0, 0.0)
    ax.plot(
        (inicio[0], fin[0]),
        (inicio[1], fin[1]),
        color=COLOR_FONDO if pasa_aire else COLOR_CERRADA,
        linewidth=9,
        solid_capstyle="butt",
        zorder=3,
    )
    if pasa_aire:
        # Marco del hueco: dos rayitas en las jambas.
        for extremo in (inicio, fin):
            ax.plot(*extremo, marker="o", markersize=4, color=COLOR_TINTA, zorder=3.5)
    if not etiquetar:
        return
    nombre = NOMBRE_ABERTURA[abertura.tipo]
    if abertura.conexion == "sin_salida":
        nombre += "\nsin salida"
    elif not pasa_aire:
        nombre += "\ncerrada"
    elif abertura.conexion == "indirecta":
        nombre += "\nal pasillo"
    ha, va = ALINEACION_ADENTRO[abertura.lado]
    x, y = _punto(cuarto, abertura.lado, centro_m, -ETIQUETA_ABERTURA * unidad_m)
    ax.text(
        x,
        y,
        nombre,
        ha=ha,
        va=va,
        fontsize=12,
        linespacing=1.0,
        color=COLOR_TINTA,
        zorder=4,
        bbox={"boxstyle": "round,pad=0.18", "facecolor": COLOR_FONDO, "edgecolor": "none", "alpha": 0.75},
    )


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
            arrowstyle="simple,head_length=0.9,head_width=1.1,tail_width=0.45",
            mutation_scale=22,
            linewidth=0,
            color=COLOR_ENTRA if entra else COLOR_SALE,
            zorder=5,
        )
    )
    palabra = "Entra\naire" if entra else "Sale\naire"
    corrimiento_m = lado_texto * 0.045 * unidad_m
    x, y = _punto(cuarto, lado, a_lo_largo_m + corrimiento_m, MITAD_FLECHA * unidad_m)
    if lado in ("frente", "fondo"):
        ha, va = ("left" if lado_texto > 0 else "right"), "center"
    else:
        ha, va = "center", ("bottom" if lado_texto > 0 else "top")
    ax.text(
        x,
        y,
        palabra,
        ha=ha,
        va=va,
        fontsize=11,
        fontweight="bold",
        color=COLOR_ENTRA if entra else COLOR_SALE,
        linespacing=0.95,
        zorder=5,
    )


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


def _curva(
    inicio: tuple[float, float],
    control_1: tuple[float, float],
    control_2: tuple[float, float],
    fin: tuple[float, float],
    puntos: int = 60,
) -> np.ndarray:
    """Curva de Bézier cúbica: un recorrido suave en vez de una línea recta."""
    t = np.linspace(0.0, 1.0, puntos)[:, None]
    p0, p1, p2, p3 = (np.array(p) for p in (inicio, control_1, control_2, fin))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t**2 * p2 + t**3 * p3


def _trazo_degradado(ax: Axes, recorrido: np.ndarray, ancho: float) -> None:
    """Línea punteada que pasa de azul (aire fresco) a naranja (aire que ya se calentó)."""
    segmentos = np.stack([recorrido[:-1], recorrido[1:]], axis=1)
    # Se deja un hueco cada tanto para que se lea como corriente de aire.
    visibles = [i for i in range(len(segmentos)) if (i // 3) % 2 == 0]
    trazo = LineCollection(
        segmentos[visibles],
        cmap=MAPA_RECORRIDO,
        linewidths=ancho,
        capstyle="round",
        alpha=0.8,
        zorder=1.5,
    )
    trazo.set_array(np.linspace(0.0, 1.0, len(segmentos))[visibles])
    ax.add_collection(trazo)


def _dibujar_recorrido(
    ax: Axes, cuarto: Cuarto, flujos: list[FlujoAbertura], centros: dict[int, float], unidad_m: float
) -> None:
    """Camino aproximado del aire por dentro: de cada entrada a cada salida."""
    entradas = [f for f in flujos if f.flujo == "entra"]
    salidas = [f for f in flujos if f.flujo == "sale"]
    adentro_m = 0.12 * unidad_m

    def borde(flujo: FlujoAbertura) -> tuple[tuple[float, float], tuple[float, float]]:
        lado = flujo.abertura.lado
        punto = _punto(cuarto, lado, centros[id(flujo.abertura)], -adentro_m)
        return punto, _hacia_adentro(lado)

    for entrada in entradas:
        for salida in salidas:
            (x0, y0), (dx0, dy0) = borde(entrada)
            (x1, y1), (dx1, dy1) = borde(salida)
            alcance = 0.4 * math.hypot(x1 - x0, y1 - y0) + 0.15 * unidad_m
            recorrido = _curva(
                (x0, y0),
                (x0 + dx0 * alcance, y0 + dy0 * alcance),
                (x1 + dx1 * alcance, y1 + dy1 * alcance),
                (x1, y1),
            )
            _trazo_degradado(ax, recorrido, 3.0)

    # Un solo lado: el aire entra, da una vuelta corta y sale por el mismo hueco.
    for flujo in flujos:
        if flujo.flujo != "entra_y_sale":
            continue
        lado = flujo.abertura.lado
        centro_m = centros[id(flujo.abertura)]
        separacion_m = SEPARACION_DOBLE_FLECHA * unidad_m
        fondo_m = min(0.45 * _profundidad_m(cuarto, lado), 0.55 * unidad_m)
        inicio = _punto(cuarto, lado, centro_m - separacion_m, -adentro_m)
        fin = _punto(cuarto, lado, centro_m + separacion_m, -adentro_m)
        control_1 = _punto(cuarto, lado, centro_m - 3.5 * separacion_m, -fondo_m)
        control_2 = _punto(cuarto, lado, centro_m + 3.5 * separacion_m, -fondo_m)
        _trazo_degradado(ax, _curva(inicio, control_1, control_2, fin), 3.0)


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
    ax.text(
        x,
        y - radio_m * 1.3,
        etiqueta,
        ha="center",
        va="top",
        fontsize=11.5,
        color=COLOR_TINTA,
        zorder=6,
        linespacing=1.0,
        bbox={"boxstyle": "round,pad=0.2", "facecolor": COLOR_FONDO, "edgecolor": "none", "alpha": 0.8},
    )


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


def _sitio_despejado(
    cuarto: Cuarto, ocupados: list[tuple[float, float]], medio_ancho_m: float, alto_fila_m: float
) -> tuple[float, float]:
    """Entre varios sitios candidatos, el que deja la fila de personas más lejos de lo dibujado."""
    fracciones = (0.2, 0.35, 0.5, 0.65, 0.8)
    candidatos = [
        (min(max(cuarto.ancho_m * fx, medio_ancho_m), cuarto.ancho_m - medio_ancho_m), cuarto.largo_m * fy)
        for fy in fracciones
        for fx in fracciones
    ]
    if not ocupados:
        return candidatos[0]

    def distancia_a_la_fila(centro: tuple[float, float], punto: tuple[float, float]) -> float:
        """La fila ocupa un rectángulo: los muñequitos y, debajo, su letrero."""
        x = min(max(punto[0], centro[0] - medio_ancho_m), centro[0] + medio_ancho_m)
        y = min(max(punto[1], centro[1] - alto_fila_m), centro[1])
        return math.dist((x, y), punto)

    return max(candidatos, key=lambda c: min(distancia_a_la_fila(c, o) for o in ocupados))


def _dibujar_personas(
    ax: Axes, cuarto: Cuarto, unidad_m: float, ocupados: list[tuple[float, float]]
) -> None:
    """Muñequitos vistos desde arriba (cabeza y hombros), con cuántas personas hay."""
    if cuarto.personas <= 0:
        return
    cantidad = min(cuarto.personas, PERSONAS_DIBUJADAS_MAX)
    paso_m = 0.085 * unidad_m
    cx, y = _sitio_despejado(
        cuarto, ocupados, paso_m * (cantidad - 1) / 2.0 + 0.05 * unidad_m, 0.11 * unidad_m
    )
    x0 = cx - paso_m * (cantidad - 1) / 2.0
    for k in range(cantidad):
        x = x0 + k * paso_m
        ax.add_patch(
            Ellipse((x, y), 0.08 * unidad_m, 0.042 * unidad_m, color=COLOR_PERSONA, alpha=0.85, zorder=4)
        )
        ax.add_patch(Circle((x, y), 0.019 * unidad_m, color=COLOR_FONDO, zorder=4.1))
        ax.add_patch(Circle((x, y), 0.014 * unidad_m, color=COLOR_PERSONA, zorder=4.2))
    texto = "1 persona" if cuarto.personas == 1 else f"{cuarto.personas} personas"
    ax.text(cx, y - 0.05 * unidad_m, texto, ha="center", va="top", fontsize=11,
            color=COLOR_PERSONA, fontweight="bold", zorder=4)


def _dibujar_momento(ax: Axes, cuarto: Cuarto, es_de_noche: bool, unidad_m: float, margen_m: float) -> None:
    """Etiqueta en la esquina: de día o de noche, y las medidas del cuarto."""
    texto = "De noche" if es_de_noche else "De día"
    ax.text(
        -margen_m + 0.02 * unidad_m,
        cuarto.largo_m + margen_m - 0.02 * unidad_m,
        texto,
        ha="left",
        va="top",
        fontsize=12,
        fontweight="bold",
        color=COLOR_FONDO,
        bbox={
            "boxstyle": "round,pad=0.35",
            "facecolor": "#1864ab" if es_de_noche else "#f08c00",
            "edgecolor": "none",
        },
    )
    ax.text(
        cuarto.ancho_m + margen_m - 0.02 * unidad_m,
        cuarto.largo_m + margen_m - 0.02 * unidad_m,
        f"{cuarto.ancho_m:g} × {cuarto.largo_m:g} m",
        ha="right",
        va="top",
        fontsize=11.5,
        color=COLOR_TEXTO_SUAVE,
    )


def _dibujar_leyenda(figura: Figure, alto_relativo: float, es_de_noche: bool) -> None:
    """Leyenda aparte, en su propio eje, para no mezclarse con el plano."""
    ax = figura.add_axes((0.0, 0.0, 1.0, alto_relativo))
    ax.axis("off")
    elementos = [
        Line2D([], [], color=COLOR_ENTRA, linewidth=5, label="Entra aire"),
        Line2D([], [], color=COLOR_SALE, linewidth=5, label="Sale aire"),
        Line2D([], [], color=COLOR_PARED_CALLE, linewidth=5, label="Pared a la calle"),
        Line2D([], [], color=COLOR_PARED_INTERIOR, linewidth=5, label="Pared interior"),
        Line2D([], [], color=COLOR_CERRADA, linewidth=5, label="Hueco cerrado"),
    ]
    if not es_de_noche:
        elementos.insert(3, Line2D([], [], color=COLOR_PARED_SOL, linewidth=5, label="Pared con sol"))
    ax.legend(
        handles=elementos,
        loc="center",
        ncols=3,
        frameon=False,
        fontsize=11,
        handlelength=1.4,
        columnspacing=1.2,
        labelcolor=COLOR_TINTA,
    )


def dibujar_plano(cuarto: Cuarto, es_de_noche: bool = False) -> Figure:
    """Figura del cuarto visto desde arriba, con sus aberturas, el aire y el ventilador."""
    unidad_m = max(cuarto.ancho_m, cuarto.largo_m)
    margen_m = MARGEN * unidad_m
    total_x_m = cuarto.ancho_m + 2.0 * margen_m
    total_y_m = cuarto.largo_m + 2.0 * margen_m
    escala = LADO_FIGURA_IN / max(total_x_m, total_y_m)
    ancho_in = total_x_m * escala
    alto_plano_in = total_y_m * escala
    alto_total_in = alto_plano_in + ALTO_LEYENDA_IN

    # Figure directa, sin pyplot: Streamlit atiende cada sesión en su propio hilo.
    figura = Figure(figsize=(ancho_in, alto_total_in), facecolor=COLOR_FONDO)
    alto_leyenda = ALTO_LEYENDA_IN / alto_total_in
    ax = figura.add_axes((0.0, alto_leyenda, 1.0, 1.0 - alto_leyenda))
    ax.set_xlim(-margen_m, cuarto.ancho_m + margen_m)
    ax.set_ylim(-margen_m, cuarto.largo_m + margen_m)
    ax.set_aspect("equal")
    ax.axis("off")

    _dibujar_piso(ax, cuarto, es_de_noche)
    _dibujar_paredes(ax, cuarto, unidad_m, es_de_noche)

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
    _dibujar_recorrido(ax, cuarto, flujos, centros, unidad_m)
    for flujo in flujos:
        _dibujar_flechas(ax, cuarto, flujo, centros[id(flujo.abertura)], unidad_m)
    if not flujos:
        ax.text(
            cuarto.ancho_m / 2.0,
            cuarto.largo_m / 2.0,
            "El aire\ncasi no circula",
            ha="center",
            va="center",
            fontsize=14,
            fontweight="bold",
            color="#c92a2a",
            zorder=6,
            bbox={"boxstyle": "round,pad=0.5", "facecolor": "#fff5f5", "edgecolor": "#ffc9c9"},
        )

    _dibujar_ventilador(ax, cuarto, es_de_noche, centros, unidad_m)

    if cuarto.extractor_eolico:
        x, y = cuarto.ancho_m * 0.78, cuarto.largo_m * 0.78
        radio_m = RADIO_ABANICO * unidad_m
        ax.add_patch(Circle((x, y), radio_m, facecolor=COLOR_SALE, edgecolor="none", zorder=6))
        for k in range(6):
            angulo = k * math.pi / 3.0
            ax.plot(
                (x, x + 0.85 * radio_m * math.cos(angulo)),
                (y, y + 0.85 * radio_m * math.sin(angulo)),
                color=COLOR_FONDO,
                linewidth=1.6,
                zorder=6.5,
            )
        ax.text(
            x, y - radio_m * 1.3, "Extractor", ha="center", va="top",
            fontsize=11, color=COLOR_TINTA, linespacing=1.0, zorder=6,
        )

    # Lo ya dibujado adentro: los nombres de los huecos, el abanico y el extractor.
    ocupados = [
        _punto(cuarto, a.lado, centros[id(a)], -profundidad * unidad_m)
        for a in cuarto.aberturas
        for profundidad in (0.1, 0.25)
    ]
    if len(flujos) > 1:  # por el centro suele pasar el recorrido del aire
        ocupados.append((cuarto.ancho_m / 2.0, cuarto.largo_m / 2.0))
    if cuarto.ventilador == "a_las_personas" or (
        cuarto.ventilador == "en_ventana_sacando" and ventana_con_abanico is None
    ):
        ocupados.append((cuarto.ancho_m / 2.0, cuarto.largo_m * ALTURA_ABANICO_CENTRAL))
    elif ventana_con_abanico is not None:
        # El abanico y su letrero, que queda entre el abanico y la ventana.
        centro_m = centros[id(ventana_con_abanico)]
        for corrido, profundidad in ((0.0, ABANICO_DESDE_PARED), (-0.13, 0.13), (0.13, 0.13)):
            ocupados.append(_punto(cuarto, ventana_con_abanico.lado, centro_m + corrido * unidad_m,
                                   -profundidad * unidad_m))
    if cuarto.extractor_eolico:
        ocupados.append((cuarto.ancho_m * 0.78, cuarto.largo_m * 0.78))
    _dibujar_personas(ax, cuarto, unidad_m, ocupados)

    _dibujar_momento(ax, cuarto, es_de_noche, unidad_m, margen_m)
    _dibujar_leyenda(figura, alto_leyenda, es_de_noche)
    return figura


__all__ = ["dibujar_plano", "flujo_aire", "ubicar_en_pared", "largo_pared_m"]
