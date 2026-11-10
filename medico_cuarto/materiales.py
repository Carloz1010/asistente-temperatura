"""Constantes físicas y tablas de materiales: U, alfa, SHGC y calor de aparatos.

Todo está en unidades SI, salvo las temperaturas de confort (°C) y las horas del día.
Los alias Literal definen las opciones válidas: la ficha los usa, y cada tabla
tiene exactamente esas claves.
"""

from typing import Literal

# --- Opciones válidas de la ficha (son las claves de las tablas de abajo) ---
MaterialTecho = Literal["zinc", "eternit", "teja_barro", "concreto"]
CieloRaso = Literal["sin_cielo_raso", "con_cielo_raso", "con_cielo_raso_y_aislante"]
ColorTecho = Literal["natural", "oscuro", "claro", "blanco"]
ColorSuperficie = Literal["oscuro", "claro", "blanco"]
MaterialPared = Literal["bloque", "ladrillo", "madera", "zinc", "bahareque"]
SolPared = Literal["manana", "tarde", "mediodia", "ninguno"]
CerramientoAbertura = Literal["vidrio", "hueco_con_reja", "postigo"]
ProteccionAbertura = Literal[
    "ninguna", "cortina_tela", "cortina_reflectiva", "polisombra", "alero"
]
# El ventilador no está aquí: se registra aparte en Cuarto.ventilador, porque su
# efecto depende de cómo se use y así su calor no se cuenta dos veces.
TipoAparato = Literal[
    "portatil",
    "computador",
    "televisor",
    "nevera",
    "bombillo_incandescente",
    "bombillo_ahorrador",
    "bombillo_led",
    "consola",
]

# --- Propiedades del aire y constantes generales ---
RHO_AIRE_KG_M3: float = 1.16  # densidad del aire caliente
CP_AIRE_J_KGK: float = 1005.0  # calor específico del aire a presión constante
GRAVEDAD_M_S2: float = 9.81  # aceleración de la gravedad (mueve la chimenea térmica)
CERO_CELSIUS_K: float = 273.15  # suma para pasar de °C a Kelvin
SEGUNDOS_POR_HORA: int = 3600  # conversión usada en ACH = Q · 3600 / V
HORAS_POR_DIA: int = 24  # registros horarios de un día

# --- Ventilación ---
FACTOR_VIENTO_LOCAL: float = 0.35  # fracción del viento a 10 m que llega a un primer piso de barrio denso
ALTURA_POR_PISO_M: float = 3.0  # cada piso sube la ventana unos 3 m
ALTURA_VENTANA_PRIMER_PISO_M: float = 1.5  # centro de una ventana de primer piso sobre la calle
EXPONENTE_PERFIL_VIENTO: float = 0.33  # perfil de potencia del viento en terreno urbano (ASHRAE)
FACTOR_VIENTO_MAXIMO: float = 1.0  # en la ciudad el viento no supera el que mide el pronóstico
COEF_DESCARGA: float = 0.6  # Cd: pérdida de caudal al pasar el aire por una abertura
DELTA_CP: float = 0.5  # ΔCp: diferencia de presión del viento entre los dos lados
COEF_UNA_ABERTURA: float = 0.025  # coeficiente de Q = 0.025 · A · U con una sola abertura
DIVISOR_CHIMENEA_UNA_ABERTURA: float = 3.0  # el aire entra y sale por el mismo hueco: Cd·A/3
ACH_MINIMO_INFILTRACION: float = 0.5  # cambios de aire por hora que se cuelan por rendijas
FACTOR_ABERTURA_INDIRECTA: float = 0.5  # una puerta a un pasillo con salida cuenta al 50 %
CAUDAL_VENTILADOR_VENTANA_M3S: float = 0.30  # caudal de un ventilador en la ventana sacando aire
REDUCCION_SENSACION_VENTILADOR_C: float = 2.5  # baja la sensación térmica, no la temperatura
CAUDAL_EXTRACTOR_EOLICO_M3S: float = 0.08  # caudal que suma un extractor eólico en el techo

# --- Ganancias de calor ---
H_EXTERIOR_W_M2K: float = 20.0  # h_o: convección y radiación en la cara exterior
RADIACION_CIELO_TECHO_K: float = 4.0  # el techo pierde calor hacia el cielo: se restan 4 K
CALOR_PERSONA_W: float = 75.0  # calor que suelta una persona en reposo
HORA_INICIO_BOMBILLOS: int = 18  # hora en que se prenden los bombillos
HORA_FIN_BOMBILLOS: int = 23  # hora en que se apagan los bombillos

# --- Radiación solar ---
F_CIELO_VERTICAL: float = 0.5  # fracción del cielo que ve una superficie vertical
F_SUELO_VERTICAL: float = 0.5  # fracción del suelo que ve una superficie vertical
ALBEDO_SUELO: float = 0.2  # fracción de la radiación que refleja el suelo

# Azimut de la pared según cuándo le da el sol. None = solo recibe radiación difusa.
AZIMUT_PARED_GRADOS: dict[SolPared, float | None] = {
    "manana": 90.0,  # este
    "tarde": 270.0,  # oeste
    "mediodia": 180.0,  # sur
    "ninguno": None,
}

# --- Simulación de 24 h (modelo RC) ---
PASO_SIMULACION_S: int = 300  # paso de tiempo de Euler explícito
DIAS_SIMULADOS: int = 3  # se repite el día y se reporta el último (borra la condición inicial)
ESPESOR_MASA_M: float = 0.05  # espesor de muros y piso que alcanza a guardar calor en un día
CAPACIDAD_MASA_J_M3K: float = 1.8e6  # calor que guarda 1 m³ de mampostería por cada kelvin

# --- Confort: límites del semáforo sobre el índice de calor (°C) ---
LIMITE_FRESCO_C: float = 27.0  # por debajo: 🟢 fresco
LIMITE_ACEPTABLE_C: float = 32.0  # entre 27 y 32: 🟡 aceptable
LIMITE_CALUROSO_C: float = 41.0  # entre 32 y 41: 🟠 caluroso; por encima: 🔴 peligroso

# --- Confort: fórmula de Magnus para la presión de saturación del vapor ---
MAGNUS_ES0_HPA: float = 6.112  # presión de saturación a 0 °C
MAGNUS_A: float = 17.62  # coeficiente adimensional
MAGNUS_B_C: float = 243.12  # coeficiente en °C

# --- Tablas de materiales ---

# U del techo (W/m²K): calor que deja pasar cada m² por cada kelvin de diferencia.
U_TECHO_W_M2K: dict[MaterialTecho, dict[CieloRaso, float]] = {
    "zinc": {"sin_cielo_raso": 6.5, "con_cielo_raso": 2.0, "con_cielo_raso_y_aislante": 0.6},
    "eternit": {"sin_cielo_raso": 5.0, "con_cielo_raso": 1.8, "con_cielo_raso_y_aislante": 0.6},
    "teja_barro": {"sin_cielo_raso": 4.5, "con_cielo_raso": 1.7, "con_cielo_raso_y_aislante": 0.6},
    "concreto": {"sin_cielo_raso": 3.0, "con_cielo_raso": 1.5, "con_cielo_raso_y_aislante": 0.6},
}

# α: fracción de la radiación solar que absorbe el techo sin pintar.
ALFA_TECHO_NATURAL: dict[MaterialTecho, float] = {
    "zinc": 0.80,
    "eternit": 0.70,
    "teja_barro": 0.65,
    "concreto": 0.70,
}

# α de una superficie pintada, según su color ("blanco" incluye lo reflectivo).
ALFA_POR_COLOR: dict[ColorSuperficie, float] = {
    "oscuro": 0.85,
    "claro": 0.45,
    "blanco": 0.25,
}

# U de las paredes (W/m²K).
U_PARED_W_M2K: dict[MaterialPared, float] = {
    "bloque": 2.8,
    "ladrillo": 2.3,
    "madera": 2.5,
    "zinc": 6.0,
    "bahareque": 1.8,
}

# SHGC: fracción del sol que cae en la abertura y termina como calor adentro.
SHGC: dict[CerramientoAbertura, float] = {
    "vidrio": 0.80,
    "hueco_con_reja": 1.00,
    "postigo": 0.10,  # postigo de madera o metal
}

# Factor de protección: fracción del sol que deja pasar lo que cubre la abertura.
FACTOR_PROTECCION: dict[ProteccionAbertura, float] = {
    "ninguna": 1.00,
    "cortina_tela": 0.65,
    "cortina_reflectiva": 0.30,
    "polisombra": 0.35,
    "alero": 0.50,
}

# Calor que suelta cada aparato encendido (W).
APARATOS_W: dict[TipoAparato | Literal["ventilador"], float] = {
    "portatil": 40.0,
    "computador": 150.0,
    "televisor": 80.0,
    "nevera": 60.0,
    "bombillo_incandescente": 60.0,
    "bombillo_ahorrador": 15.0,
    "bombillo_led": 9.0,
    "ventilador": 50.0,
    "consola": 120.0,
}
