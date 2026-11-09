"""Ganancias de calor y simulación RC de 24 horas de la temperatura interior."""

from typing import NamedTuple

from medico_cuarto.clima import ClimaDia, ClimaHora
from medico_cuarto.ficha import Cuarto, Pared, Techo, exigir_dato_de_noche
from medico_cuarto.materiales import (
    ALFA_POR_COLOR,
    ALFA_TECHO_NATURAL,
    APARATOS_W,
    AZIMUT_PARED_GRADOS,
    CALOR_PERSONA_W,
    CAPACIDAD_MASA_J_M3K,
    CP_AIRE_J_KGK,
    DIAS_SIMULADOS,
    ESPESOR_MASA_M,
    FACTOR_PROTECCION,
    H_EXTERIOR_W_M2K,
    HORA_FIN_BOMBILLOS,
    HORA_INICIO_BOMBILLOS,
    HORAS_POR_DIA,
    PASO_SIMULACION_S,
    RADIACION_CIELO_TECHO_K,
    RHO_AIRE_KG_M3,
    SEGUNDOS_POR_HORA,
    SHGC,
    U_PARED_W_M2K,
    U_TECHO_W_M2K,
)
from medico_cuarto.solar import (
    PosicionSol,
    irradiancia_horizontal_w_m2,
    irradiancia_vertical_w_m2,
    posicion_sol,
)
from medico_cuarto.ventilacion import caudal_infiltracion_m3s, caudal_total_m3s, ventilador_funciona

ITERACIONES_BISECCION: int = 60  # cada una parte el intervalo a la mitad: sobra precisión


class _Superficie(NamedTuple):
    """Superficie que da afuera: conduce calor según su temperatura sol-aire."""

    nombre: str
    conductancia_w_k: float  # U · A
    t_sol_aire_c: float


def _posicion_sol_de_la_hora(clima_hora: ClimaHora) -> PosicionSol:
    """Sol a la mitad de la hora, porque la radiación es el promedio de la hora anterior."""
    return posicion_sol(
        clima_hora.latitud_grados,
        clima_hora.longitud_grados,
        clima_hora.utc_offset_h,
        clima_hora.dia_del_anio,
        clima_hora.hora_local - 0.5,
    )


def temperatura_sol_aire_c(to_c: float, alfa: float, irradiancia_w_m2: float) -> float:
    """Temperatura equivalente de la cara exterior: el aire más el sol que absorbe."""
    return to_c + alfa * irradiancia_w_m2 / H_EXTERIOR_W_M2K


def _alfa_techo(techo: Techo) -> float:
    """Sin pintar absorbe según su material; pintado, según su color."""
    if techo.color == "natural":
        return ALFA_TECHO_NATURAL[techo.material]
    return ALFA_POR_COLOR[techo.color]


def area_pared_m2(cuarto: Cuarto, pared: Pared) -> float:
    """Área de muro de una pared, sin contar los huecos que tiene."""
    largo_pared_m = cuarto.ancho_m if pared.lado in ("frente", "fondo") else cuarto.largo_m
    area_huecos_m2 = sum(a.ancho_m * a.alto_m for a in cuarto.aberturas if a.lado == pared.lado)
    return max(0.0, largo_pared_m * cuarto.alto_m - area_huecos_m2)


def _superficies_exteriores(
    cuarto: Cuarto,
    clima_hora: ClimaHora,
    posicion: PosicionSol,
    descuento_cielo_k: float,
) -> list[_Superficie]:
    """Techo y paredes que dan afuera; las interiores no intercambian calor."""
    to_c = clima_hora.temperatura_c
    irradiancia_techo_w_m2 = irradiancia_horizontal_w_m2(clima_hora.ghi_w_m2)
    superficies = [
        _Superficie(
            nombre="techo",
            conductancia_w_k=U_TECHO_W_M2K[cuarto.techo.material][cuarto.techo.cielo_raso]
            * cuarto.area_techo_m2,
            # El techo ve el cielo frío y pierde calor por radiación.
            t_sol_aire_c=temperatura_sol_aire_c(to_c, _alfa_techo(cuarto.techo), irradiancia_techo_w_m2)
            - descuento_cielo_k,
        )
    ]
    for pared in cuarto.paredes:
        if not pared.da_afuera:
            continue
        irradiancia_pared_w_m2 = irradiancia_vertical_w_m2(
            posicion,
            clima_hora.dni_w_m2,
            clima_hora.dhi_w_m2,
            clima_hora.ghi_w_m2,
            AZIMUT_PARED_GRADOS[pared.sol],
        )
        if pared.polisombra:  # la malla deja pasar solo una parte del sol
            irradiancia_pared_w_m2 *= FACTOR_PROTECCION["polisombra"]
        superficies.append(
            _Superficie(
                nombre=f"pared_{pared.lado}",
                conductancia_w_k=U_PARED_W_M2K[pared.material] * area_pared_m2(cuarto, pared),
                t_sol_aire_c=temperatura_sol_aire_c(
                    to_c, ALFA_POR_COLOR[pared.color], irradiancia_pared_w_m2
                ),
            )
        )
    return superficies


def _calor_ventanas_w(cuarto: Cuarto, clima_hora: ClimaHora, posicion: PosicionSol) -> float:
    """Sol que entra por las aberturas de las paredes que dan afuera."""
    paredes = {pared.lado: pared for pared in cuarto.paredes}
    total_w = 0.0
    for abertura in cuarto.aberturas:
        pared = paredes.get(abertura.lado)
        if pared is None or not pared.da_afuera:
            continue
        irradiancia_w_m2 = irradiancia_vertical_w_m2(
            posicion,
            clima_hora.dni_w_m2,
            clima_hora.dhi_w_m2,
            clima_hora.ghi_w_m2,
            AZIMUT_PARED_GRADOS[pared.sol],
        )
        area_m2 = abertura.ancho_m * abertura.alto_m
        total_w += (
            SHGC[abertura.cerramiento] * FACTOR_PROTECCION[abertura.proteccion] * area_m2 * irradiancia_w_m2
        )
    return total_w


def _calor_aparatos_w(cuarto: Cuarto, hora_local: float, es_de_noche: bool) -> float:
    """Aparatos encendidos a esa hora; los bombillos solo prenden de 18 h a 23 h."""
    bombillos_prendidos = HORA_INICIO_BOMBILLOS <= hora_local < HORA_FIN_BOMBILLOS
    total_w = sum(
        APARATOS_W[aparato]
        for aparato in cuarto.aparatos
        if bombillos_prendidos or not aparato.startswith("bombillo")
    )
    # Apuntando a las personas no cambia la temperatura del aire: solo la sensación.
    if ventilador_funciona(cuarto, es_de_noche):
        total_w += APARATOS_W["ventilador"]
    return total_w


def _calor_directo_w(
    cuarto: Cuarto, clima_hora: ClimaHora, posicion: PosicionSol
) -> dict[str, float]:
    """Calor que entra al aire sin importar la temperatura interior."""
    return {
        "ventanas": _calor_ventanas_w(cuarto, clima_hora, posicion),
        "personas": cuarto.personas * CALOR_PERSONA_W,
        # hora_local cierra la hora que describe el registro: los aparatos, a su mitad.
        "aparatos": _calor_aparatos_w(
            cuarto, clima_hora.hora_local - 0.5, posicion.altura_rad <= 0
        ),
    }


def ganancias_w(
    cuarto: Cuarto,
    clima_hora: ClimaHora,
    ti_c: float,
    descuento_cielo_k: float = RADIACION_CIELO_TECHO_K,
    quitar: frozenset[str] = frozenset(),
) -> dict[str, float]:
    """Aporte en W de cada fuente a esa Ti; positivo calienta y negativo enfría.

    Las fuentes en `quitar` valen cero: sirve para medir cuánto aporta cada una.
    """
    posicion = _posicion_sol_de_la_hora(clima_hora)
    aportes: dict[str, float] = {"techo": 0.0}
    aportes.update({f"pared_{pared.lado}": 0.0 for pared in cuarto.paredes})

    # Conducción: q = U · A · (T_sa − Ti).
    for superficie in _superficies_exteriores(cuarto, clima_hora, posicion, descuento_cielo_k):
        aportes[superficie.nombre] = superficie.conductancia_w_k * (superficie.t_sol_aire_c - ti_c)

    aportes.update(_calor_directo_w(cuarto, clima_hora, posicion))

    # El aire que entra a To reemplaza al de adentro: q = ρ · c · Q · (To − Ti).
    es_de_noche = posicion.altura_rad <= 0
    caudal_m3s = caudal_total_m3s(cuarto, clima_hora, ti_c, es_de_noche)
    aportes["ventilacion"] = (
        RHO_AIRE_KG_M3 * CP_AIRE_J_KGK * caudal_m3s * (clima_hora.temperatura_c - ti_c)
    )
    aportes.update({fuente: 0.0 for fuente in quitar})
    return aportes


def temperatura_estacionaria_c(
    cuarto: Cuarto,
    clima_hora: ClimaHora,
    descuento_cielo_k: float = RADIACION_CIELO_TECHO_K,
) -> float:
    """Ti en °C donde el calor que entra iguala al que sale.

    Q depende de Ti por la chimenea, así que no se puede despejar directo. La suma de
    ganancias siempre baja cuando Ti sube, entonces hay una sola raíz y sirve la bisección.
    """
    posicion = _posicion_sol_de_la_hora(clima_hora)
    superficies = _superficies_exteriores(cuarto, clima_hora, posicion, descuento_cielo_k)
    calor_directo_w = sum(_calor_directo_w(cuarto, clima_hora, posicion).values())

    # Ti no puede pasar de la fuente más caliente más lo que suba por el calor directo.
    temperaturas_c = [clima_hora.temperatura_c] + [s.t_sol_aire_c for s in superficies]
    conductancia_minima_w_k = sum(s.conductancia_w_k for s in superficies) + (
        RHO_AIRE_KG_M3 * CP_AIRE_J_KGK * caudal_infiltracion_m3s(cuarto.volumen_m3)
    )
    baja_c = min(temperaturas_c)
    alta_c = max(temperaturas_c) + calor_directo_w / conductancia_minima_w_k

    for _ in range(ITERACIONES_BISECCION):
        media_c = (baja_c + alta_c) / 2.0
        balance_w = sum(ganancias_w(cuarto, clima_hora, media_c, descuento_cielo_k).values())
        if balance_w > 0:  # sigue entrando calor: el equilibrio está más arriba
            baja_c = media_c
        else:
            alta_c = media_c
    return (baja_c + alta_c) / 2.0


class ResultadoSimulacion(NamedTuple):
    """Último día simulado, hora por hora, y el día anterior para ver si convergió."""

    hora: list[int]
    ti_c: list[float]
    to_c: list[float]
    caudal_m3s: list[float]
    ti_dia_anterior_c: list[float]


def capacidad_termica_j_k(cuarto: Cuarto) -> float:
    """Calor que guardan el aire y la masa: C = ρ·c·V + (muros y piso)·espesor·capacidad."""
    area_muros_m2 = sum(area_pared_m2(cuarto, pared) for pared in cuarto.paredes)
    area_masa_m2 = area_muros_m2 + cuarto.area_techo_m2  # el piso mide lo mismo que el techo
    return (
        RHO_AIRE_KG_M3 * CP_AIRE_J_KGK * cuarto.volumen_m3
        + area_masa_m2 * ESPESOR_MASA_M * CAPACIDAD_MASA_J_M3K
    )


def _clima_en(clima: ClimaDia, tiempo_h: float) -> ClimaHora:
    """Clima en un instante del día, dentro del tramo entre las horas h y h+1."""
    hora = int(tiempo_h)
    fraccion = tiempo_h - hora
    inicio = clima.horas[hora]
    fin = clima.horas[(hora + 1) % HORAS_POR_DIA]  # el día se repite: a la hora 24 sigue la 0

    def interpolar(clave: str) -> float:
        """Aire y viento son valores puntuales: cambian suave entre dos registros."""
        return inicio[clave] + (fin[clave] - inicio[clave]) * fraccion  # type: ignore[literal-required]

    # La radiación del registro h+1 es el promedio justo de este tramo.
    return ClimaHora(
        temperatura_c=interpolar("t_ext_c"),
        humedad_pct=interpolar("hr_pct"),
        viento_10m_ms=interpolar("viento_ms"),
        ghi_w_m2=fin["ghi_w_m2"],
        dni_w_m2=fin["dni_w_m2"],
        dhi_w_m2=fin["dhi_w_m2"],
        latitud_grados=clima.latitud_grados,
        longitud_grados=clima.longitud_grados,
        utc_offset_h=clima.utc_offset_h,
        dia_del_anio=clima.dia_del_anio,
        hora_local=float(hora + 1),
    )


def simular_24h(
    cuarto: Cuarto, clima: ClimaDia, quitar: frozenset[str] = frozenset()
) -> ResultadoSimulacion:
    """Evolución de Ti con Euler explícito: C · dTi/dt = Σ ganancias.

    Se repite el mismo día para borrar el efecto de la temperatura inicial.
    Las fuentes en `quitar` no calientan, pero la masa de muros y piso se conserva.
    Falla si no se sabe qué ventanas y puertas quedan abiertas de noche.
    """
    exigir_dato_de_noche(cuarto)
    capacidad_j_k = capacidad_termica_j_k(cuarto)
    pasos_por_hora = SEGUNDOS_POR_HORA // PASO_SIMULACION_S
    ti_c = sum(registro["t_ext_c"] for registro in clima.horas) / len(clima.horas)

    ti_dia_c: list[float] = []
    ti_dia_anterior_c: list[float] = []
    to_dia_c: list[float] = []
    caudal_dia_m3s: list[float] = []

    for _ in range(DIAS_SIMULADOS):
        ti_dia_anterior_c = ti_dia_c
        ti_dia_c, to_dia_c, caudal_dia_m3s = [], [], []
        for paso in range(HORAS_POR_DIA * pasos_por_hora):
            clima_paso = _clima_en(clima, paso / pasos_por_hora)
            if paso % pasos_por_hora == 0:  # se guarda cada hora en punto
                es_de_noche = _posicion_sol_de_la_hora(clima_paso).altura_rad <= 0
                ti_dia_c.append(ti_c)
                to_dia_c.append(clima_paso.temperatura_c)
                caudal_dia_m3s.append(caudal_total_m3s(cuarto, clima_paso, ti_c, es_de_noche))
            balance_w = sum(
                ganancias_w(cuarto, clima_paso, ti_c, quitar=quitar).values()
            )
            ti_c += PASO_SIMULACION_S * balance_w / capacidad_j_k

    return ResultadoSimulacion(
        hora=list(range(HORAS_POR_DIA)),
        ti_c=ti_dia_c,
        to_c=to_dia_c,
        caudal_m3s=caudal_dia_m3s,
        ti_dia_anterior_c=ti_dia_anterior_c,
    )
