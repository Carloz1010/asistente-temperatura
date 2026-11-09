# Guion de la demo (3 minutos)

## Antes de empezar

- Abre la app (`streamlit run app.py`) con el botón **Reiniciar** ya presionado.
- Ten a mano `docs/sensibilidad.png` y este guion con los mensajes para **copiar y pegar**.
- **Cuota:** una conversación completa gasta unas 17 de las 20 solicitudes diarias de Gemini.
  No ensayes con Gemini el mismo día de la entrega. Ensaya con `PROVEEDOR_IA=claude` o el día anterior.
- **Respaldo:** graba el ensayo en video. Si falla internet o la IA, muestra el video.
- Si en el ensayo cada respuesta tarda más de 10 s, deja hechos los mensajes 1 a 3 antes de empezar.

## Los números de referencia

Salen del día típico de Barranquilla. En vivo cambian con el pronóstico: **lee los de la pantalla**.

| Dato | Valor |
|---|---|
| Hora más caliente | 2 p. m. |
| Adentro / afuera | 35.8 °C / 32.0 °C |
| Sensación térmica | 45.8 °C (🔴 peligroso); con el abanico, 43.3 °C |
| Promedio de noche | 31.0 °C |
| Techo | +3.2 °C, 81 % del calor |
| Ventilar de noche | Baja 2.3 °C de noche; no cambia el pico |
| Pintar el techo de blanco | Baja 2.6 °C en el pico (queda en 33.3 °C; en 33.2 °C si antes aplicaste ventilar de noche) |
| Cielo raso con aislante | Baja 2.9 °C en el pico, pero **sube 1.9 °C de noche** |

## El guion

| Tiempo | Qué haces | Qué dices |
|---|---|---|
| 0:00–0:25 | App en pantalla, con el saludo del asistente | "En la Costa, muchas familias duermen bajo un techo de zinc sin aire acondicionado. No saben por qué se les calienta el cuarto ni qué vale la pena arreglar. El Médico del Cuarto se lo explica conversando. Lo importante: **la IA no inventa ningún número**. Solo conversa; las temperaturas salen de un motor físico que programamos." |
| 0:25–1:20 | Pega los mensajes 1 a 5 | Mientras responde: "Le hablo como a un vecino. No me pregunta puntos cardinales, sino si a la pared le da el sol en la mañana o en la tarde. Y siempre pregunta si de noche queda abierta cada ventana, porque eso cambia varios grados." |
| 1:20–1:55 | Señala la tarjeta, las fuentes y la gráfica de 24 h | "El motor simuló tres días con balance de energía y ventilación. Son 35.8 grados adentro con 32 afuera, y el cuerpo los siente como 45.8: rojo, peligroso. El 81 % viene del techo. Aquí se ve la curva del día, y aquí abajo el plano con el recorrido del aire." |
| 1:55–2:30 | Pega el mensaje 6. Luego, en **Pintar el techo de blanco**, oprime **Ya lo hice** | "Le pregunto qué pasa si ventilo de noche: es gratis y baja dos grados al dormir. Si además pinto el techo, el motor recalcula sin gastar consultas de IA: de 35.8 a unos 33 grados. Y como implica subirse al techo, trae su advertencia de seguridad." |
| 2:30–2:50 | Muestra `docs/sensibilidad.png` | "¿Qué tanto dependen los resultados de lo que asumimos? El techo y el viento mandan. Y un hallazgo: aislar baja el pico casi lo mismo que pintar, pero sube la noche 1.9 grados si el cuarto queda cerrado. Eso solo se ve simulando el día completo." |
| 2:50–3:00 | Vuelve a la app | "No está calibrado con mediciones, y son estimaciones para comparar opciones. Pero una familia ya sabe por dónde empezar y cuántos grados gana con cada arreglo." |

## La conversación

Los mensajes están listos para pegar. El asistente hace una pregunta a la vez y su orden puede
variar: **contesta según lo que pregunte**, usando la tabla de abajo.

**Mensaje 1 (para abrir):**

> Hola, vivo en Barranquilla. Mi cuarto mide 3 por 3 metros, con techo de zinc, y desde adentro se ve el zinc porque no tiene cielo raso. Normalmente estamos 2 personas, con un portátil y un abanico apuntándonos.

**Mensaje 2 (aberturas):**

> Tiene una ventana de vidrio de un metro por un metro en la pared de la calle, y una puerta en la pared del fondo que da a un pasillo con salida al patio. De día las dos están abiertas.

**Mensaje 3 (ventana de noche):**

> La ventana la cerramos de noche.

**Mensaje 4 (puerta de noche):**

> La puerta también la cerramos.

**Mensaje 5 (paredes):**

> Solo la pared de la calle da afuera, las otras tres están pegadas a otros cuartos. A esa pared no le da el sol directo.

**Mensaje 6 (después de los resultados):**

> ¿Y qué pasa si dejo la ventana y la puerta abiertas de noche?

### Si pregunta otra cosa

| Si pregunta… | Responde |
|---|---|
| Alto del cuarto | "Como 2 metros y medio." |
| De qué son las paredes | "De bloque, pintadas de claro." |
| Si la ventana tiene cortina | "No, ninguna." |
| Aparatos | "Solo el portátil." |
| Cómo usan el abanico | "Nos apunta a nosotros." |
| A qué lado está la ventana | "En la pared del frente, la de la calle." |

## Si algo sale mal

| Qué pasa | Qué haces |
|---|---|
| "Se me acabaron las consultas" o se cae la IA | Pasa al video de respaldo. El resto del discurso no cambia. |
| Aparece el aviso del día típico | Dilo: "No hay internet para el pronóstico, y el sistema lo avisa y usa un día típico." Es una función, no un error. |
| Los números son distintos a los de arriba | Es lo esperado: el pronóstico de hoy no es el día típico. Lee los de la pantalla. |
| Te preguntan "¿y si la IA se equivoca?" | "La IA nunca da números: los pide al motor. Y todo lo que asume se lo cuenta a la persona." |
