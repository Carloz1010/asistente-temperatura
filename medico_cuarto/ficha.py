"""Modelos Pydantic de la ficha del cuarto: Cuarto, Techo, Pared y Abertura.

Gemini lee las description de cada campo para saber cómo llenar la ficha.
"""

from typing import Literal

from pydantic import BaseModel, Field

from medico_cuarto.materiales import (
    CerramientoAbertura,
    CieloRaso,
    ColorSuperficie,
    ColorTecho,
    MaterialPared,
    MaterialTecho,
    ProteccionAbertura,
    SolPared,
    TipoAparato,
)

LadoCuarto = Literal["frente", "fondo", "izquierda", "derecha"]
TipoAbertura = Literal["ventana", "puerta", "calado", "rejilla"]
ConexionAbertura = Literal["afuera", "indirecta", "sin_salida"]
ModoVentilador = Literal["ninguno", "a_las_personas", "en_ventana_sacando"]


class Techo(BaseModel):
    """Techo del cuarto."""

    material: MaterialTecho = Field(
        default="zinc",
        description="Material del techo: zinc, eternit, teja de barro o placa de concreto.",
    )
    cielo_raso: CieloRaso = Field(
        default="sin_cielo_raso",
        description=(
            "Si hay una capa debajo del techo: sin cielo raso (se ve el techo desde "
            "adentro), con cielo raso, o con cielo raso y aislante."
        ),
    )
    color: ColorTecho = Field(
        default="natural",
        description=(
            "Color de la cara de afuera del techo. 'natural' si nunca se pintó; "
            "'blanco' también incluye la pintura reflectiva."
        ),
    )


class Pared(BaseModel):
    """Una de las cuatro paredes del cuarto. Su área sale de las medidas del cuarto."""

    lado: LadoCuarto = Field(
        default="frente",
        description="Qué pared es, mirando el cuarto desde la entrada principal o la calle.",
    )
    material: MaterialPared = Field(
        default="bloque",
        description="Material de la pared: bloque, ladrillo, madera, zinc o bahareque.",
    )
    da_afuera: bool = Field(
        default=True,
        description=(
            "True si la pared da a la calle o al patio. False si es interior o está "
            "pegada a otro cuarto o a la casa del vecino."
        ),
    )
    sol: SolPared = Field(
        default="ninguno",
        description=(
            "Cuándo le da el sol directo a la pared por fuera: en la mañana ('manana'), "
            "en la tarde, al mediodía ('mediodia') o nunca ('ninguno')."
        ),
    )
    color: ColorSuperficie = Field(
        default="claro",
        description="Color de la cara de afuera de la pared: oscuro, claro o blanco.",
    )


class Abertura(BaseModel):
    """Ventana, puerta u otro hueco por donde puede pasar aire o sol."""

    tipo: TipoAbertura = Field(
        default="ventana",
        description="Clase de abertura: ventana, puerta, calado (bloque hueco) o rejilla.",
    )
    lado: LadoCuarto = Field(
        default="frente",
        description="Pared en la que está la abertura: frente, fondo, izquierda o derecha.",
    )
    ancho_m: float = Field(default=1.0, ge=0.1, description="Ancho de la abertura en metros.")
    alto_m: float = Field(default=1.0, ge=0.1, description="Alto de la abertura en metros.")
    altura_base_m: float = Field(
        default=1.0,
        ge=0.0,
        description="Altura del borde inferior sobre el piso, en metros. Una puerta tiene 0.",
    )
    abierta: bool = Field(
        default=True,
        description="True si normalmente se mantiene abierta en las horas de calor.",
    )
    conexion: ConexionAbertura = Field(
        default="afuera",
        description=(
            "A dónde lleva: 'afuera' (calle o patio), 'indirecta' (a un pasillo o zona "
            "con salida al exterior) o 'sin_salida' (a un espacio cerrado)."
        ),
    )
    cerramiento: CerramientoAbertura = Field(
        default="vidrio",
        description=(
            "Qué tapa la abertura: vidrio, 'hueco_con_reja' (no tiene vidrio) o "
            "'postigo' (hoja de madera o metal, como la de una puerta)."
        ),
    )
    proteccion: ProteccionAbertura = Field(
        default="ninguna",
        description="Lo que da sombra: nada, cortina de tela, cortina reflectiva, polisombra o alero.",
    )


def _paredes_por_defecto() -> list[Pared]:
    """Cuatro paredes con los valores por defecto, una por cada lado."""
    return [
        Pared(lado="frente"),
        Pared(lado="fondo"),
        Pared(lado="izquierda"),
        Pared(lado="derecha"),
    ]


class Cuarto(BaseModel):
    """Ficha completa del cuarto: la entrada del motor físico."""

    largo_m: float = Field(
        default=3.0,
        ge=0.5,
        description="Largo del cuarto en metros: distancia de la pared del frente a la del fondo.",
    )
    ancho_m: float = Field(
        default=3.0,
        ge=0.5,
        description="Ancho del cuarto en metros: distancia entre las paredes izquierda y derecha.",
    )
    alto_m: float = Field(
        default=2.5,
        ge=1.5,
        description="Alto del cuarto en metros, del piso al techo.",
    )
    techo: Techo = Field(default_factory=Techo, description="Datos del techo.")
    paredes: list[Pared] = Field(
        default_factory=_paredes_por_defecto,
        description="Las cuatro paredes del cuarto, una por cada lado.",
    )
    aberturas: list[Abertura] = Field(
        default_factory=list,
        description="Todas las ventanas, puertas, calados y rejillas del cuarto.",
    )
    personas: int = Field(
        default=1,
        ge=0,
        description="Número de personas que suelen estar en el cuarto en las horas de calor.",
    )
    aparatos: list[TipoAparato] = Field(
        default_factory=list,
        description=(
            "Aparatos y bombillos del cuarto; se repite el nombre si hay varios iguales. "
            "El ventilador o abanico no va aquí: va en el campo ventilador."
        ),
    )
    ventilador: ModoVentilador = Field(
        default="ninguno",
        description=(
            "Uso del ventilador o abanico: 'ninguno', 'a_las_personas' (apuntando a la "
            "gente) o 'en_ventana_sacando' (en la ventana, sacando aire)."
        ),
    )
    supuestos: list[str] = Field(
        default_factory=list,
        description="Datos que la persona no dio y se asumieron; hay que contárselos.",
    )

    @property
    def volumen_m3(self) -> float:
        """Volumen de aire del cuarto."""
        return self.largo_m * self.ancho_m * self.alto_m

    @property
    def area_techo_m2(self) -> float:
        """Área del techo, igual a la del piso."""
        return self.largo_m * self.ancho_m


def cuarto_ejemplo() -> Cuarto:
    """Caso de referencia: cuarto de 3×3 m con techo de zinc y dos personas."""
    return Cuarto(
        largo_m=3.0,
        ancho_m=3.0,
        alto_m=2.5,
        techo=Techo(material="zinc", cielo_raso="sin_cielo_raso"),
        paredes=[
            Pared(lado="frente", da_afuera=True),
            Pared(lado="fondo", da_afuera=False),
            Pared(lado="izquierda", da_afuera=False),
            Pared(lado="derecha", da_afuera=False),
        ],
        aberturas=[
            Abertura(tipo="ventana", lado="frente", ancho_m=1.0, alto_m=1.0, altura_base_m=1.0),
            Abertura(
                tipo="puerta",
                lado="fondo",
                ancho_m=0.9,
                alto_m=2.0,
                altura_base_m=0.0,
                conexion="indirecta",
                cerramiento="postigo",
            ),
        ],
        personas=2,
        aparatos=["portatil"],
        ventilador="a_las_personas",
        supuestos=[
            "Las paredes son de bloque y de color claro.",
            "Solo la pared de la ventana da a la calle; las otras tres son interiores o medianeras.",
            "A la pared de la calle no le da el sol directo.",
            "La ventana tiene vidrio, sin cortina, y su borde inferior está a 1 m del piso.",
            "La ventana y la puerta se mantienen abiertas en las horas de calor.",
            "El abanico apunta a las personas.",
        ],
    )
