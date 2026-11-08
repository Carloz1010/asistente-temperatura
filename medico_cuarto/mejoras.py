"""Catálogo de mejoras por nivel de costo y comparación antes/después."""

from typing import Callable, Literal, NamedTuple

from medico_cuarto.clima import ClimaDia
from medico_cuarto.ficha import Abertura, Cuarto, Pared
from medico_cuarto.materiales import FACTOR_PROTECCION, TipoAparato
from medico_cuarto.termico import simular_24h

NivelMejora = Literal["gratis", "bajo", "mayor"]

ORDEN_NIVEL: dict[NivelMejora, int] = {"gratis": 0, "bajo": 1, "mayor": 2}
HORAS_NOCHE: tuple[int, ...] = (22, 23, 0, 1, 2, 3, 4, 5)  # horas en que la gente duerme
EFECTO_MINIMO_C: float = 0.05  # una mejora que baja menos que esto no vale el esfuerzo

APARATOS_APAGABLES: tuple[TipoAparato, ...] = ("portatil", "computador", "televisor", "consola")
BOMBILLOS_A_CAMBIAR: tuple[TipoAparato, ...] = ("bombillo_incandescente", "bombillo_ahorrador")

# Medidas supuestas de lo que se construye.
ANCHO_CALADO_M: float = 0.60
ALTO_CALADO_M: float = 0.20
SEPARACION_CALADO_TECHO_M: float = 0.10  # lo que queda de muro entre el calado y el techo
ZONA_ALTA_M: float = 0.50  # un hueco a esta distancia del techo ya saca el aire caliente
ALTO_REJILLA_PUERTA_M: float = 0.30

ADVERTENCIA_TECHO: str = (
    "Subirse al techo es peligroso: hazlo acompañado, con escalera firme y nunca si está "
    "mojado o hay viento. Pisa solo sobre los apoyos. Si es de eternit, no lo lijes ni lo "
    "perfores: su polvo puede hacer daño a los pulmones."
)
ADVERTENCIA_CIELO_RASO: str = (
    "Se trabaja en altura y cerca de los cables del techo: corta la electricidad antes de "
    "empezar y, si hay cables pelados o el techo está débil, busca a alguien con experiencia."
)
ADVERTENCIA_MURO: str = (
    "Abrir un hueco toca la estructura: nunca lo hagas en columnas ni vigas, y pregúntale "
    "antes a un maestro de obra si el muro aguanta."
)


class Mejora(NamedTuple):
    """Una entrada del catálogo."""

    id: str
    nombre: str
    nivel: NivelMejora
    por_que: str
    advertencia_seguridad: str | None
    aplica: Callable[[Cuarto], bool]  # si tiene sentido en este cuarto
    modificar: Callable[[Cuarto], None]  # cambia, en su sitio, una copia de la ficha


class MejoraPropuesta(NamedTuple):
    """Una mejora que aplica al cuarto, con lo que se gana al hacerla."""

    id: str
    nombre: str
    nivel: NivelMejora
    por_que: str
    advertencia_seguridad: str | None
    baja_pico_c: float  # °C que baja a la hora más caliente
    baja_noche_c: float  # °C que baja, en promedio, en las horas de dormir


def _pared_de(cuarto: Cuarto, lado: str) -> Pared | None:
    return next((pared for pared in cuarto.paredes if pared.lado == lado), None)


# --- Gratis ---


def _abertura_para_abrir(cuarto: Cuarto) -> Abertura | None:
    """La cerrada que más ayuda: en un lado sin aire crea cruzada; luego, la más grande."""
    lados_abiertos = {
        a.lado for a in cuarto.aberturas if a.abierta and a.conexion != "sin_salida"
    }
    cerradas = [a for a in cuarto.aberturas if not a.abierta and a.conexion != "sin_salida"]
    return max(
        cerradas,
        key=lambda a: (a.lado not in lados_abiertos, a.ancho_m * a.alto_m),
        default=None,
    )


def _abrir_abertura(cuarto: Cuarto) -> None:
    abertura = _abertura_para_abrir(cuarto)
    if abertura is not None:
        abertura.abierta = True


def _hay_ventana_abierta(cuarto: Cuarto) -> bool:
    return any(a.tipo == "ventana" and a.abierta for a in cuarto.aberturas)


def _aplica_ventilador_ventana(cuarto: Cuarto) -> bool:
    return cuarto.ventilador != "en_ventana_sacando" and _hay_ventana_abierta(cuarto)


def _poner_ventilador_ventana(cuarto: Cuarto) -> None:
    cuarto.ventilador = "en_ventana_sacando"


def _cerradas_de_noche(cuarto: Cuarto) -> list[Abertura]:
    """Ventanas y puertas que usan de día, con salida, y que cierran al anochecer."""
    return [
        a
        for a in cuarto.aberturas
        if a.tipo in ("ventana", "puerta")
        and a.abierta
        and a.conexion != "sin_salida"
        and not a.abierta_de_noche
    ]


def _aplica_ventilar_noche(cuarto: Cuarto) -> bool:
    return bool(_cerradas_de_noche(cuarto))


def _ventilar_noche(cuarto: Cuarto) -> None:
    for abertura in _cerradas_de_noche(cuarto):
        abertura.abierta_de_noche = True


def _aplica_apagar_aparatos(cuarto: Cuarto) -> bool:
    return any(aparato in APARATOS_APAGABLES for aparato in cuarto.aparatos)


def _apagar_aparatos(cuarto: Cuarto) -> None:
    """La nevera no se apaga y los bombillos solo prenden de noche."""
    cuarto.aparatos = [a for a in cuarto.aparatos if a not in APARATOS_APAGABLES]


# --- Bajo costo ---


def _aplica_pintar_techo(cuarto: Cuarto) -> bool:
    return cuarto.techo.color != "blanco"


def _pintar_techo(cuarto: Cuarto) -> None:
    cuarto.techo.color = "blanco"


def _ventanas_con_sol_mejorables(cuarto: Cuarto) -> list[Abertura]:
    """Ventanas de paredes que dan afuera que dejan pasar más sol que una cortina reflectiva."""
    resultado = []
    for abertura in cuarto.aberturas:
        pared = _pared_de(cuarto, abertura.lado)
        if (
            abertura.tipo == "ventana"
            and abertura.cerramiento != "postigo"
            and pared is not None
            and pared.da_afuera
            and FACTOR_PROTECCION[abertura.proteccion] > FACTOR_PROTECCION["cortina_reflectiva"]
        ):
            resultado.append(abertura)
    return resultado


def _aplica_cortina(cuarto: Cuarto) -> bool:
    return bool(_ventanas_con_sol_mejorables(cuarto))


def _poner_cortina(cuarto: Cuarto) -> None:
    for abertura in _ventanas_con_sol_mejorables(cuarto):
        abertura.proteccion = "cortina_reflectiva"


def _paredes_con_sol_sin_sombra(cuarto: Cuarto) -> list[Pared]:
    return [p for p in cuarto.paredes if p.da_afuera and p.sol != "ninguno" and not p.polisombra]


def _aplica_polisombra(cuarto: Cuarto) -> bool:
    return bool(_paredes_con_sol_sin_sombra(cuarto))


def _poner_polisombra(cuarto: Cuarto) -> None:
    """La malla cubre la pared y también las ventanas que tenga."""
    for pared in _paredes_con_sol_sin_sombra(cuarto):
        pared.polisombra = True
        for abertura in cuarto.aberturas:
            if (
                abertura.lado == pared.lado
                and FACTOR_PROTECCION[abertura.proteccion] > FACTOR_PROTECCION["polisombra"]
            ):
                abertura.proteccion = "polisombra"


def _aplica_led(cuarto: Cuarto) -> bool:
    return any(aparato in BOMBILLOS_A_CAMBIAR for aparato in cuarto.aparatos)


def _cambiar_a_led(cuarto: Cuarto) -> None:
    cuarto.aparatos = [
        "bombillo_led" if aparato in BOMBILLOS_A_CAMBIAR else aparato for aparato in cuarto.aparatos
    ]


# --- Mayor ---


def _aplica_cielo_raso(cuarto: Cuarto) -> bool:
    """Si tiene cielo raso sin aislante, todavía se le puede poner."""
    return cuarto.techo.cielo_raso != "con_cielo_raso_y_aislante"


def _poner_cielo_raso(cuarto: Cuarto) -> None:
    cuarto.techo.cielo_raso = "con_cielo_raso_y_aislante"


def _tiene_hueco_alto(cuarto: Cuarto) -> bool:
    return any(
        a.tipo in ("calado", "rejilla") and a.altura_base_m + a.alto_m > cuarto.alto_m - ZONA_ALTA_M
        for a in cuarto.aberturas
    )


def _aplica_calado(cuarto: Cuarto) -> bool:
    return not _tiene_hueco_alto(cuarto) and any(p.da_afuera for p in cuarto.paredes)


def _poner_calado(cuarto: Cuarto) -> None:
    """En una pared que da afuera; mejor si no tiene aberturas, para crear cruzada."""
    lados_con_aire = {a.lado for a in cuarto.aberturas if a.abierta}
    pared = max(
        (p for p in cuarto.paredes if p.da_afuera), key=lambda p: p.lado not in lados_con_aire
    )
    cuarto.aberturas.append(
        Abertura(
            tipo="calado",
            lado=pared.lado,
            ancho_m=ANCHO_CALADO_M,
            alto_m=ALTO_CALADO_M,
            altura_base_m=cuarto.alto_m - ALTO_CALADO_M - SEPARACION_CALADO_TECHO_M,
            cerramiento="hueco_con_reja",
        )
    )
    cuarto.supuestos.append(
        f"El calado nuevo mide {ANCHO_CALADO_M:.2f} × {ALTO_CALADO_M:.2f} m "
        f"y va en lo alto de la pared del lado '{pared.lado}'."
    )


def _aplica_extractor(cuarto: Cuarto) -> bool:
    return not cuarto.extractor_eolico


def _poner_extractor(cuarto: Cuarto) -> None:
    cuarto.extractor_eolico = True


def _puerta_para_rejilla(cuarto: Cuarto) -> Abertura | None:
    """Una puerta que pase cerrada algún rato y con otra abertura en otro lado."""
    for puerta in cuarto.aberturas:
        pasa_cerrada = not puerta.abierta or not puerta.abierta_de_noche
        ya_tiene_rejilla = any(
            a.tipo == "rejilla" and a.lado == puerta.lado for a in cuarto.aberturas
        )
        hay_otro_lado = any(
            a.lado != puerta.lado and a.conexion != "sin_salida" for a in cuarto.aberturas
        )
        if (
            puerta.tipo == "puerta"
            and puerta.conexion != "sin_salida"
            and pasa_cerrada
            and not ya_tiene_rejilla
            and hay_otro_lado
            and puerta.alto_m > ALTO_REJILLA_PUERTA_M
        ):
            return puerta
    return None


def _aplica_rejilla(cuarto: Cuarto) -> bool:
    return _puerta_para_rejilla(cuarto) is not None


def _poner_rejilla(cuarto: Cuarto) -> None:
    """La rejilla se saca de la misma hoja: la puerta se acorta para no contar el área doble."""
    puerta = _puerta_para_rejilla(cuarto)
    if puerta is None:
        return
    cuarto.aberturas.append(
        Abertura(
            tipo="rejilla",
            lado=puerta.lado,
            ancho_m=puerta.ancho_m,
            alto_m=ALTO_REJILLA_PUERTA_M,
            altura_base_m=puerta.altura_base_m,
            conexion=puerta.conexion,
            cerramiento="postigo",  # las lamas dejan pasar aire, pero tapan el sol
        )
    )
    puerta.altura_base_m += ALTO_REJILLA_PUERTA_M
    puerta.alto_m -= ALTO_REJILLA_PUERTA_M
    cuarto.supuestos.append(
        f"La rejilla de la puerta ocupa {ALTO_REJILLA_PUERTA_M:.2f} m de alto en la parte de abajo."
    )


CATALOGO: tuple[Mejora, ...] = (
    Mejora(
        "abrir_abertura",
        "Abrir la ventana o puerta que hoy está cerrada",
        "gratis",
        "El aire necesita por dónde entrar y por dónde salir. Si abres un hueco en otro lado "
        "del cuarto, se forma una corriente que se lleva el calor.",
        None,
        lambda cuarto: _abertura_para_abrir(cuarto) is not None,
        _abrir_abertura,
    ),
    Mejora(
        "ventilador_ventana",
        "Poner el ventilador en la ventana sacando aire",
        "gratis",
        "Sacando el aire caliente, el ventilador obliga a que entre aire de afuera, incluso "
        "cuando no hace viento. Eso sí, ya no te da brisa directa en el cuerpo.",
        None,
        _aplica_ventilador_ventana,
        _poner_ventilador_ventana,
    ),
    Mejora(
        "ventilar_noche",
        "Dejar ventanas y puertas abiertas de noche",
        "gratis",
        "De noche el aire de afuera está más fresco y se lleva el calor que guardaron los "
        "muros durante el día. Hazlo solo si es seguro en tu barrio.",
        None,
        _aplica_ventilar_noche,
        _ventilar_noche,
    ),
    Mejora(
        "apagar_aparatos",
        "Apagar los aparatos que no estés usando",
        "gratis",
        "Todo aparato prendido suelta calor adentro, como una pequeña estufa. La nevera se "
        "deja prendida.",
        None,
        _aplica_apagar_aparatos,
        _apagar_aparatos,
    ),
    Mejora(
        "pintar_techo_blanco",
        "Pintar el techo de blanco por encima",
        "bajo",
        "Un techo blanco rebota el sol en vez de tragárselo, así que se calienta mucho menos "
        "y le pasa menos calor al cuarto.",
        ADVERTENCIA_TECHO,
        _aplica_pintar_techo,
        _pintar_techo,
    ),
    Mejora(
        "cortina_reflectiva",
        "Poner cortina reflectiva en la ventana",
        "bajo",
        "La cara brillante devuelve el sol hacia afuera antes de que se vuelva calor dentro "
        "del cuarto.",
        None,
        _aplica_cortina,
        _poner_cortina,
    ),
    Mejora(
        "polisombra_pared",
        "Poner polisombra en la pared donde pega el sol",
        "bajo",
        "La malla le hace sombra a la pared, como un árbol: el muro recibe menos sol y le "
        "pasa menos calor al cuarto.",
        None,
        _aplica_polisombra,
        _poner_polisombra,
    ),
    Mejora(
        "bombillos_led",
        "Cambiar los bombillos por LED",
        "bajo",
        "Un bombillo LED da la misma luz soltando mucho menos calor, y además gasta menos luz "
        "en el recibo.",
        None,
        _aplica_led,
        _cambiar_a_led,
    ),
    Mejora(
        "cielo_raso_aislante",
        "Instalar cielo raso con aislante",
        "mayor",
        "Es una barrera entre el techo caliente y tu cuarto: el calor del techo casi no logra "
        "llegar hasta donde tú estás. Eso sí, de noche también atrapa el calor: hay que dejar "
        "ventilar el cuarto al anochecer.",
        ADVERTENCIA_CIELO_RASO,
        _aplica_cielo_raso,
        _poner_cielo_raso,
    ),
    Mejora(
        "calado_alto",
        "Abrir un calado o rejilla en lo alto de la pared",
        "mayor",
        "El aire caliente sube y se queda arriba. Un hueco alto le da por dónde salir, y "
        "funciona a toda hora porque no hay que abrirlo ni cerrarlo.",
        ADVERTENCIA_MURO,
        _aplica_calado,
        _poner_calado,
    ),
    Mejora(
        "extractor_eolico",
        "Instalar un extractor eólico en el techo",
        "mayor",
        "Es una turbina que gira con el viento, sin gastar luz, y va sacando el aire caliente "
        "del cuarto por arriba.",
        ADVERTENCIA_TECHO,
        _aplica_extractor,
        _poner_extractor,
    ),
    Mejora(
        "rejilla_puerta",
        "Poner una rejilla en la puerta",
        "mayor",
        "Deja pasar el aire aunque la puerta esté cerrada, y así se forma una corriente con "
        "la ventana.",
        None,
        _aplica_rejilla,
        _poner_rejilla,
    ),
)

_POR_ID: dict[str, Mejora] = {mejora.id: mejora for mejora in CATALOGO}


def aplicar_mejora(cuarto: Cuarto, id_mejora: str) -> Cuarto:
    """Copia del cuarto con la mejora hecha; si ya no aplica, la copia queda igual."""
    if id_mejora not in _POR_ID:
        raise ValueError(f"No existe la mejora '{id_mejora}'.")
    mejora = _POR_ID[id_mejora]
    copia = cuarto.model_copy(deep=True)
    if mejora.aplica(copia):
        mejora.modificar(copia)
    return copia


def _promedio_noche_c(ti_c: list[float]) -> float:
    return sum(ti_c[hora] for hora in HORAS_NOCHE) / len(HORAS_NOCHE)


def proponer_mejoras(cuarto: Cuarto, clima: ClimaDia) -> list[MejoraPropuesta]:
    """Mejoras que aplican y sirven, ordenadas por nivel y luego por efecto a la hora pico."""
    base = simular_24h(cuarto, clima)
    indice_pico = base.ti_c.index(max(base.ti_c))
    noche_base_c = _promedio_noche_c(base.ti_c)

    propuestas = []
    for mejora in CATALOGO:
        if not mejora.aplica(cuarto):
            continue
        despues = simular_24h(aplicar_mejora(cuarto, mejora.id), clima)
        baja_pico_c = base.ti_c[indice_pico] - despues.ti_c[indice_pico]
        baja_noche_c = noche_base_c - _promedio_noche_c(despues.ti_c)
        # No se ofrece lo que calienta la hora pico ni lo que no cambia nada.
        if baja_pico_c < 0 or max(baja_pico_c, baja_noche_c) < EFECTO_MINIMO_C:
            continue
        propuestas.append(
            MejoraPropuesta(
                mejora.id,
                mejora.nombre,
                mejora.nivel,
                mejora.por_que,
                mejora.advertencia_seguridad,
                baja_pico_c,
                baja_noche_c,
            )
        )
    return sorted(propuestas, key=lambda p: (ORDEN_NIVEL[p.nivel], -p.baja_pico_c))
