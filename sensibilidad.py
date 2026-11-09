"""Análisis de sensibilidad del cuarto de ejemplo: tabla y gráfica para la presentación.

Cambia un parámetro a la vez, con el día típico de Barranquilla, y mide cuánto se mueve la
temperatura de adentro. El motor no se toca: α y U se cambian un momento en sus tablas.

Uso: python sensibilidad.py   (escribe docs/sensibilidad.csv, .md y .png)
"""

import csv
from pathlib import Path
from typing import Callable, NamedTuple
from unittest.mock import patch

from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from medico_cuarto.clima import ClimaDia, dia_tipico_barranquilla
from medico_cuarto.confort import hr_interior_pct, semaforo
from medico_cuarto.ficha import Cuarto, cuarto_ejemplo
from medico_cuarto.materiales import ALFA_TECHO_NATURAL, U_TECHO_W_M2K
from medico_cuarto.mejoras import HORAS_NOCHE
from medico_cuarto.termico import simular_24h

CARPETA: Path = Path(__file__).parent / "docs"

FACTORES_VIENTO: tuple[float, ...] = (0.5, 1.0, 1.5)
ALFAS_TECHO: tuple[float, ...] = (0.25, 0.45, 0.65, 0.80, 0.85)
# El rango de la tabla de techos, del zinc desnudo (6.5) al cielo raso con aislante (0.6).
US_TECHO_W_M2K: tuple[float, ...] = (0.6, 1.5, 2.0, 3.0, 4.5, 6.5)

COLOR_ENFRIA: str = "#2a78d6"
COLOR_CALIENTA: str = "#eb6834"
COLOR_TINTA: str = "#0b0b0b"
COLOR_TEXTO_SUAVE: str = "#52514e"
COLOR_GUIAS: str = "#e6e4dc"
TAMANO_LETRA: int = 15
ALTO_BARRA: float = 0.34
SEPARACION_ETIQUETA_C: float = 0.12


class Fila(NamedTuple):
    """Resultado de una corrida con un parámetro cambiado."""

    parametro: str
    valor: float
    valor_texto: str
    es_base: bool
    ti_pico_c: float
    hora_pico: int
    ti_noche_c: float
    delta_pico_c: float
    delta_noche_c: float
    sensacion_c: float
    nivel: str


class Corrida(NamedTuple):
    ti_pico_c: float
    hora_pico: int
    ti_noche_c: float
    sensacion_c: float
    nivel: str


def _correr(cuarto: Cuarto, clima: ClimaDia) -> Corrida:
    sim = simular_24h(cuarto, clima)
    ti_pico_c = max(sim.ti_c)
    hora = sim.ti_c.index(ti_pico_c)
    hr_pct = hr_interior_pct(clima.horas[hora]["hr_pct"], sim.to_c[hora], ti_pico_c)
    nivel = semaforo(ti_pico_c, hr_pct)
    ti_noche_c = sum(sim.ti_c[h] for h in HORAS_NOCHE) / len(HORAS_NOCHE)
    return Corrida(ti_pico_c, hora, ti_noche_c, nivel.indice_c, nivel.etiqueta)


def _clima_con_viento(clima: ClimaDia, factor: float) -> ClimaDia:
    """Copia del día con todo el viento multiplicado."""
    copia = clima.model_copy(deep=True)
    for registro in copia.horas:
        registro["viento_ms"] *= factor
    return copia


def calcular_sensibilidad(cuarto: Cuarto, clima: ClimaDia) -> list[Fila]:
    """Una fila por cada valor probado; la base es el cuarto tal como está en la ficha."""
    material = cuarto.techo.material
    cielo_raso = cuarto.techo.cielo_raso
    alfa_base = ALFA_TECHO_NATURAL[material]
    u_base_w_m2k = U_TECHO_W_M2K[material][cielo_raso]
    base = _correr(cuarto, clima)

    def fila(parametro: str, valor: float, texto: str, es_base: bool, c: Corrida) -> Fila:
        return Fila(
            parametro,
            valor,
            texto,
            es_base,
            c.ti_pico_c,
            c.hora_pico,
            c.ti_noche_c,
            c.ti_pico_c - base.ti_pico_c,
            c.ti_noche_c - base.ti_noche_c,
            c.sensacion_c,
            c.nivel,
        )

    filas: list[Fila] = []
    for factor in FACTORES_VIENTO:
        corrida = _correr(cuarto, _clima_con_viento(clima, factor))
        filas.append(fila("Viento", factor, f"×{factor:g}", factor == 1.0, corrida))
    for alfa in ALFAS_TECHO:
        with patch.dict(ALFA_TECHO_NATURAL, {material: alfa}):
            corrida = _correr(cuarto, clima)
        filas.append(fila("α del techo", alfa, f"{alfa:.2f}", alfa == alfa_base, corrida))
    for u_w_m2k in US_TECHO_W_M2K:
        with patch.dict(U_TECHO_W_M2K[material], {cielo_raso: u_w_m2k}):
            corrida = _correr(cuarto, clima)
        filas.append(
            fila("U del techo (W/m²K)", u_w_m2k, f"{u_w_m2k:.1f}", u_w_m2k == u_base_w_m2k, corrida)
        )
    return filas


# --- Archivos para la presentación ---


def escribir_csv(filas: list[Fila], ruta: Path) -> None:
    # utf-8-sig: para que Excel lea bien la α y el °C.
    with ruta.open("w", newline="", encoding="utf-8-sig") as archivo:
        tabla = csv.writer(archivo)
        tabla.writerow(
            [
                "parametro",
                "valor",
                "es_base",
                "ti_pico_c",
                "hora_pico",
                "ti_noche_c",
                "delta_pico_c",
                "delta_noche_c",
                "sensacion_pico_c",
                "semaforo",
            ]
        )
        for f in filas:
            tabla.writerow(
                [
                    f.parametro,
                    f.valor_texto,
                    "sí" if f.es_base else "",
                    f"{f.ti_pico_c:.2f}",
                    f.hora_pico,
                    f"{f.ti_noche_c:.2f}",
                    f"{f.delta_pico_c:+.2f}",
                    f"{f.delta_noche_c:+.2f}",
                    f"{f.sensacion_c:.1f}",
                    f.nivel,
                ]
            )


def escribir_markdown(filas: list[Fila], ruta: Path) -> None:
    lineas = [
        "| Parámetro | Valor | Ti pico (°C) | Hora pico | Cambio pico (°C) "
        "| Ti noche (°C) | Cambio noche (°C) | Sensación pico (°C) | Semáforo |",
        "|---|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for f in filas:
        valor = f"**{f.valor_texto} (base)**" if f.es_base else f.valor_texto
        lineas.append(
            f"| {f.parametro} | {valor} | {f.ti_pico_c:.1f} | {f.hora_pico} h "
            f"| {f.delta_pico_c:+.1f} | {f.ti_noche_c:.1f} | {f.delta_noche_c:+.1f} "
            f"| {f.sensacion_c:.1f} | {f.nivel} |"
        )
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")


# --- Gráfica ---


def _extremos(filas: list[Fila], parametro: str, delta: Callable[[Fila], float]) -> tuple[Fila, Fila]:
    """La fila que más enfría y la que más calienta para ese parámetro."""
    del_parametro = [f for f in filas if f.parametro == parametro]
    return min(del_parametro, key=delta), max(del_parametro, key=delta)


def _dibujar_panel(
    ax: Axes,
    filas: list[Fila],
    parametros: list[str],
    delta: Callable[[Fila], float],
    titulo: str,
) -> None:
    """Dos barras por parámetro, desde la base: hacia la izquierda enfría, a la derecha calienta."""
    for posicion, parametro in enumerate(parametros):
        menor, mayor = _extremos(filas, parametro, delta)
        for fila, color in ((menor, COLOR_ENFRIA), (mayor, COLOR_CALIENTA)):
            valor_c = delta(fila)
            if abs(valor_c) < 0.05 or fila.es_base:
                continue
            ax.barh(posicion, valor_c, height=ALTO_BARRA, color=color, zorder=2)
            signo = 1 if valor_c > 0 else -1
            ax.text(
                valor_c + signo * SEPARACION_ETIQUETA_C,
                posicion,
                f"{valor_c:+.1f} °C\n{fila.valor_texto}",
                ha="left" if signo > 0 else "right",
                va="center",
                fontsize=TAMANO_LETRA - 2,
                color=COLOR_TINTA,
                linespacing=1.15,
            )
    ax.axvline(0.0, color=COLOR_TEXTO_SUAVE, linewidth=1.2, zorder=3)
    ax.set_yticks(range(len(parametros)), [p.replace(" (", "\n(") for p in parametros])
    ax.set_title(titulo, loc="left", fontsize=TAMANO_LETRA + 1, color=COLOR_TINTA, fontweight="bold")
    ax.xaxis.set_major_formatter(lambda x, _: "0" if abs(x) < 0.01 else f"{x:+.0f} °C")
    ax.tick_params(axis="y", length=0, labelsize=TAMANO_LETRA, labelcolor=COLOR_TINTA)
    ax.tick_params(axis="x", length=0, labelsize=TAMANO_LETRA - 3, labelcolor=COLOR_TEXTO_SUAVE)
    ax.grid(axis="x", color=COLOR_GUIAS, linewidth=1)
    ax.set_axisbelow(True)
    for borde in ("top", "right", "left", "bottom"):
        ax.spines[borde].set_visible(False)


def _ordenar_por_efecto_en_pico(filas: list[Fila]) -> list[str]:
    """El parámetro que más mueve el pico va arriba."""

    def rango_c(parametro: str) -> float:
        deltas = [f.delta_pico_c for f in filas if f.parametro == parametro]
        return max(deltas) - min(deltas)

    return sorted(dict.fromkeys(f.parametro for f in filas), key=rango_c, reverse=True)


def graficar(filas: list[Fila], ti_pico_base_c: float, ti_noche_base_c: float) -> Figure:
    """Figura directa, sin pyplot, igual que en la app."""
    parametros = _ordenar_por_efecto_en_pico(filas)
    figura = Figure(figsize=(12.0, 4.8), facecolor="#ffffff", layout="constrained")
    ax_pico, ax_noche = figura.subplots(1, 2, sharex=True, sharey=True)

    _dibujar_panel(
        ax_pico, filas, parametros, lambda f: f.delta_pico_c, f"A la hora pico (base {ti_pico_base_c:.1f} °C)"
    )
    _dibujar_panel(
        ax_noche, filas, parametros, lambda f: f.delta_noche_c, f"De noche (base {ti_noche_base_c:.1f} °C)"
    )
    extremo_c = max(max(abs(f.delta_pico_c), abs(f.delta_noche_c)) for f in filas)
    ax_pico.set_xlim(-extremo_c * 1.45, extremo_c * 1.45)
    ax_pico.invert_yaxis()  # una sola vez: los dos paneles comparten el eje

    figura.legend(
        handles=[
            Patch(color=COLOR_ENFRIA, label="Enfría el cuarto"),
            Patch(color=COLOR_CALIENTA, label="Calienta el cuarto"),
        ],
        loc="outside lower center",
        ncols=2,
        frameon=False,
        fontsize=TAMANO_LETRA - 1,
        handlelength=1.2,
    )
    return figura


def main() -> None:
    CARPETA.mkdir(exist_ok=True)
    filas = calcular_sensibilidad(cuarto_ejemplo(), dia_tipico_barranquilla())
    escribir_csv(filas, CARPETA / "sensibilidad.csv")
    escribir_markdown(filas, CARPETA / "sensibilidad.md")
    base = next(f for f in filas if f.es_base)
    figura = graficar(filas, base.ti_pico_c, base.ti_noche_c)
    figura.savefig(CARPETA / "sensibilidad.png", dpi=180)
    print((CARPETA / "sensibilidad.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
