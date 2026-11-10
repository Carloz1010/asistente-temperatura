# CLAUDE.md — Médico del Cuarto

## Qué es
Un asistente web con IA para hogares de bajos recursos sin aire acondicionado. La persona describe su cuarto conversando, como si le hablara a un vecino. El asistente estima qué tan caliente queda el cuarto, explica de dónde viene el calor y propone soluciones ordenadas por costo, con los grados que baja cada una.

Es el proyecto final de Física (Ingeniería de Sistemas). Hay **2 días** para entregarlo y un solo desarrollador. Prioridad: **la física primero, lo visual al final.**

## Regla de oro
**Los números salen del motor físico, nunca de la IA.** La IA solo conversa, arma la ficha del cuarto, llama al motor y explica los resultados. Si la IA necesita un número, lo pide a una función del motor.

## Stack
- Python 3.11+, entorno virtual `.venv`
- `streamlit` (interfaz web), `google-genai` (Gemini) y `anthropic` (Claude), `pydantic` (ficha del cuarto), `requests`, `matplotlib`, `pytest`
- Clima: **Open-Meteo** (gratis, sin API key)
  - Geocodificación: `https://geocoding-api.open-meteo.com/v1/search?name=<ciudad>&count=1&language=es`
  - Pronóstico: `https://api.open-meteo.com/v1/forecast` con `hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,shortwave_radiation,direct_normal_irradiance,diffuse_radiation`, `wind_speed_unit=ms`, `timezone=auto`, `forecast_days=1`
  - La radiación de Open-Meteo es el promedio de la hora anterior: para la posición del sol se usa la mitad de esa hora.
- IA: se elige en `.env` con `PROVEEDOR_IA` (`gemini` o `claude`) y `MODELO_IA` (vacío = el modelo por defecto de ese proveedor). Las claves van en `.env` como `GEMINI_API_KEY` y `ANTHROPIC_API_KEY` y **nunca se suben a GitHub**.

## Estructura
```
medico_cuarto/
  materiales.py   # constantes y tablas (U, alfa, SHGC, calor de aparatos)
  ficha.py        # modelos Pydantic: Cuarto, Techo, Pared, Abertura
  clima.py        # Open-Meteo + día típico de respaldo (Barranquilla)
  solar.py        # posición del sol y radiación sobre cada superficie
  ventilacion.py  # caudal Q por viento, chimenea, ventilador
  termico.py      # ganancias de calor + simulación RC de 24 h
  confort.py      # índice de calor y semáforo
  diagnostico.py  # aporte de cada fuente en °C
  mejoras.py      # catálogo de mejoras por nivel + antes/después
  plano.py        # dibujo del cuarto con el recorrido del aire
  agente.py       # prompt, extracción de la ficha, function calling (sin ningún SDK de IA)
  proveedores/    # un adaptador por IA: base.py (contrato), gemini.py, claude.py
app.py            # Streamlit
tests/            # pytest
```

## Modelo físico (unidades SI)
**Ventilación (Q en m³/s)**
- Viento local: `U = U10 · min(0.35 · (z / 1.5)^0.33, 1)`, con `z = 1.5 + (piso − 1) · 3 m` la altura de la ventana (barrio denso; el viento del pronóstico es a 10 m de altura). En el primer piso queda `U10 · 0.35`.
- Cruzada (aberturas abiertas en lados distintos que conectan afuera): `Q = Cd · A_ef · U · √ΔCp`, con `Cd = 0.6`, `ΔCp = 0.5` y `1/A_ef² = 1/A₁² + 1/A₂²`.
- Una sola abertura: `Q = 0.025 · A · U`.
- Chimenea: `Q = Cd · A · √(2 · g · Δh · |Ti − To| / Ti)`, con T en Kelvin. Con una sola abertura: `Q = (Cd · A / 3) · √(g · H · |ΔT| / T)`.
- Combinación: `Q = √(Q_viento² + Q_chimenea²)`. Mínimo por infiltración: 0.5 cambios de aire por hora.
- Abertura "indirecta" (puerta a un pasillo con salida): su área cuenta al 50 %.
- Ventilador en la ventana sacando aire: `Q = max(Q_natural, 0.30)`; aporta 50 W de calor.
- Ventilador apuntando a las personas: no cambia la temperatura del aire, solo baja la sensación térmica unos 2.5 °C (se muestra aparte).
- Cambios de aire por hora: `ACH = Q · 3600 / V`.
- De noche, cada ventana o puerta deja pasar aire solo si su `abierta_de_noche` es True. Ese dato se le pregunta a la persona por cada una y la simulación no corre sin él. Calados y rejillas siempre quedan abiertos.

**Ganancias de calor (W)**
- Temperatura sol-aire: `T_sa = T_ext + α · I / h_o`, con `h_o = 20 W/m²K`. Al techo se le restan 4 K por radiación al cielo.
- Techo y paredes que dan afuera: `q = U · A · (T_sa − Ti)`. Las paredes interiores no intercambian calor (solo aportan masa).
- Con otro piso encima (`techo.otro_piso_encima`), el techo no intercambia calor y su placa suma masa: el área del techo se cuenta dos veces en `C`. No se ofrecen las mejoras del techo.
- Ventana: `q = SHGC · factor_protección · A · I_vertical`.
- Sol sobre una superficie: `I = DNI · max(0, cos θ) + DHI · F_cielo + GHI · 0.2 · F_suelo`, con `F = 0.5` para superficies verticales. El techo recibe la radiación global horizontal.
- Orientación de las paredes según cuándo les da el sol: mañana = este (90°), tarde = oeste (270°), mediodía = sur (180°), ninguno = solo radiación difusa.
- Calor interno: 75 W por persona. Aparatos según la tabla. Los bombillos solo prenden de 18 h a 23 h.

**Simulación de 24 h (modelo RC, un nodo)**
`C · dTi/dt = Σ U·A·(T_sa − Ti) + ρ·c·Q·(To − Ti) + P_internas + P_ventanas`
- `C = ρ·c·V + (área de muros y piso) · 0.05 m · 1.8e6 J/m³K`
- Euler explícito con paso de 300 s. Se repite el mismo día 3 veces y se reporta el último, para quitar el efecto de la condición inicial.
- Constantes: `ρ = 1.16 kg/m³`, `c = 1005 J/kg·K`, `g = 9.81 m/s²`.

**Tablas (valores típicos)**
- U del techo (sin cielo raso / con cielo raso / con cielo raso y aislante): zinc 6.5/2.0/0.6 · eternit 5.0/1.8/0.6 · teja de barro 4.5/1.7/0.6 · placa de concreto 3.0/1.5/0.6
- α natural: zinc 0.80 · eternit 0.70 · teja de barro 0.65 · concreto 0.70. Por color: oscuro 0.85 · claro 0.45 · blanco o reflectivo 0.25
- U de paredes: bloque 2.8 · ladrillo 2.3 · madera 2.5 · zinc 6.0 · bahareque 1.8
- SHGC: vidrio 0.80 · hueco con reja 1.00 · postigo de madera o metal 0.10. Protección: cortina de tela 0.65 · cortina reflectiva 0.30 · polisombra 0.35 · alero 0.50
- Aparatos (W): portátil 40 · computador 150 · televisor 80 · nevera 60 · bombillo incandescente 60 · bombillo ahorrador 15 · bombillo LED 9 · ventilador 50 · consola 120

**Confort**
- Humedad interior: la presión de vapor es igual a la de afuera, así que `HR_in = HR_out · es(T_out) / es(T_in)` (fórmula de Magnus).
- Índice de calor de NOAA (Rothfusz). Semáforo: 🟢 fresco < 27 · 🟡 aceptable 27–32 · 🟠 caluroso 32–41 · 🔴 peligroso > 41.

**Diagnóstico:** se simula quitando una fuente a la vez (techo, cada pared, ventanas, personas, aparatos). Lo que baja la temperatura a la hora pico es el aporte de esa fuente en °C.

**Mejoras** (cada una modifica una copia de la ficha y se recalcula):
- Gratis: abrir la abertura correcta, ventilador en la ventana sacando aire, ventilar de noche, apagar aparatos.
- Bajo costo: pintar el techo de blanco, cortina reflectiva, polisombra en la pared con sol, cambiar a bombillos LED.
- Mayor: cielo raso con aislante, calado o rejilla alta, extractor eólico (`Q += 0.08 m³/s`), rejilla en la puerta para ventilación cruzada.
- Las mejoras que implican subirse al techo, tocar la estructura o la instalación eléctrica llevan una **advertencia de seguridad**.

## Convenciones de código
- Nombres en español, con type hints. Comentarios cortos que expliquen la física de cada fórmula.
- El motor debe tener **funciones puras** (sin `print` ni Streamlit adentro), para poder probarlas con pytest.
- Las variables con unidad la llevan en el nombre: `area_m2`, `q_w`, `caudal_m3s`.
- Cada valor supuesto se agrega a `cuarto.supuestos` para decírselo al usuario.
- Si la API de clima falla, se usa el día típico de respaldo y se avisa.

## Cómo trabajar conmigo
- Soy intermedio en Python: explícame en 3–5 líneas qué hiciste y por qué.
- Vamos fase por fase. No agregues nada fuera del alcance.
- Al terminar cada fase: corre los tests, marca la fase en la lista de abajo y sugiere el mensaje del commit.

## Comandos
- Instalar: `pip install -r requirements.txt`
- Tests: `pytest -q`
- App: `streamlit run app.py`

## Fases
- [x] 0. Preparación: repo, venv, dependencias, `.env`, `.gitignore`
- [x] 1. Ficha del cuarto y tablas de materiales
- [x] 2. Cálculo en un instante: ventilación y balance de calor
- [x] 3. Clima (Open-Meteo), simulación de 24 h y semáforo
- [x] 4. Diagnóstico por fuente y mejoras por nivel
- [x] 5. Agente Gemini: conversación, ficha y function calling
- [x] 6. Interfaz Streamlit: chat, resultados, gráfica y plano
- [x] 7. Pruebas finales y demo

## Fuera de alcance (trabajo futuro)
Fotos, recordatorios diarios, base de datos (la ficha vive en `st.session_state`), WhatsApp o Telegram, y calibración con mediciones reales.
