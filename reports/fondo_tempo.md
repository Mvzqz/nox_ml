# ¿El fondo de TEMPO explica el domingo bajo y Valle de México en ~300 t/año?

**Respuesta corta: no.** Ningún tratamiento del fondo arregla ninguno de los dos síntomas, y el gemelo con el patrón real de residuos tampoco los reproduce. Lo que sí aparece:

1. **Alrededor de Acolman, TEMPO ve menos NO₂ del que produciría la central.** No hay una pluma escondida en el fondo.
2. **El domingo bajo viene directamente de TEMPO**, al que hoy le damos demasiado peso.

Script: `scripts/fondo_tempo.py`. Tablas: `fondo_tempo_tablas_2023-11-01_2023-12-31.md`. Configuración: nov–dic 2023, σθ = 30°, industria agrupada y estaciones extra, a priori corregidos de las centrales (Valle 1,600 ± 650, Nonoalco 100 ± 100).

## Cómo se trataba el fondo

- **Fondo de TEMPO:** un solo número por escaneo (por hora), igual en todo el dominio, con a priori 5e15 ± 5e15 molec/cm².
- **Error de cada píxel:** independiente, σ = 5e15.
- **Escala:** son 78,227 píxeles en 258 escaneos.

## Diagnóstico

- **El patrón de residuos es persistente.** El residuo medio (observado − modelo) en celdas de 6 km varía 2.6e15 de una celda a otra. Eso es la mitad del error supuesto por píxel, y no promedia a cero: los errores de píxeles vecinos están correlacionados. Por eso TEMPO pesa en la inversión como si tuviera mucha más información de la que tiene.
- **Cerca de Valle de México el residuo es negativo:**

  | Distancia a Valle | Residuo (1e15) |
  |---|---|
  | 0–5 km | −0.46 |
  | 5–10 km | −1.13 |
  | 10–20 km | −0.88 |

  Aun con solo 320 t/año, el modelo **ya pone más NO₂** del que mide el satélite. Si el fondo uniforme se estuviera "comiendo" una pluma ancha, el residuo sería positivo.
- **AMF:** el AMF troposférico cerca de Valle (1.32) es igual al mediano del dominio (1.30). No hay un problema de sensibilidad del satélite particular de esa zona.

## Variantes con datos reales

| Variante | Domingo/hábil libre (IC 90 %) | Con restricción 0.69 | Valle de México (t/año) | LOO modelo / híbrido (ppb) | TEMPO r |
|---|---|---|---|---|---|
| Base: fondo uniforme por hora | 0.42 (0.34–0.54) | 0.51 | 320 ± 45 | 13.38 / 11.22 | 0.75 |
| Fondo por día | 0.39 | 0.50 | 289 | 13.40 / 11.23 | 0.73 |
| + gradiente lineal libre por hora | 0.49 | 0.59 | **−164** | 13.68 / 11.53 | 0.84 |
| + gradiente lineal fijo | 0.36 | 0.48 | −139 | 13.58 / 11.29 | 0.76 |
| + desplazamiento fijo por región 3×3 | 0.36 | 0.49 | −34 | 13.45 / 11.18 | 0.78 |
| + región 3×3 por tipo de día | 0.41 | 0.54 | −38 | 13.47 / 11.19 | 0.78 |
| Sin píxeles a < 10 km de Valle | 0.43 | 0.51 | **−22 ± 113** | 13.43 / 11.25 | 0.76 |
| Solo píxeles a < 8 km de una estación | 0.43 | 0.51 | 373 | 13.36 / 11.21 | 0.76 |
| AMF constante por escaneo | 0.42 | 0.51 | 258 | 13.56 / 11.34 | 0.74 |
| Sensibilidad a la pluma de Valle × 0.6 | 0.42 | 0.51 | 539 | 13.38 / 11.22 | 0.75 |
| σ TEMPO × 3 | 0.42 | **0.62** | 356 ± 131 | 13.39 / 11.26 | 0.75 |
| σ TEMPO × 10 | 0.45 | **0.67** | 802 ± 344 | 13.62 / 11.58 | 0.72 |
| Sin TEMPO | **0.81** (0.71–1.07) | 0.69 | 2,560 ± 572 | 14.28 / 12.41 | 0.53 |

**Lectura:**

- **Valle de México no es identificable con TEMPO.**
  - Según cómo se modele el fondo, sale entre −164 y 539 t/año, a pesar de que el σ reportado es de ±45. Ese σ es falso: supone errores independientes por píxel.
  - Sin los píxeles cercanos a la central, Valle cae a −22 ± 113. Más allá de 10 km TEMPO no ve ninguna pluma, y lo poco que la fija está en los píxeles cercanos.
  - Ningún fondo más flexible la sube; al contrario, la bajan.
- **El domingo no depende del fondo.**
  - Con cualquier fondo, el cociente libre queda en 0.36–0.49.
  - Solo sube al quitarle peso a TEMPO:
    - con la restricción de Infovial: 0.62 con σ × 3 y 0.67 con σ × 10;
    - sin TEMPO y sin restricción: 0.81, aunque las estaciones solas no deciden el cociente (`sesgo_domingos.md`).
  - Con la restricción de Infovial, la baja de 0.69 a 0.51 la pone TEMPO.
- **LOO de estaciones:** casi no cambia entre variantes (11.2–11.6 ppb en el híbrido). Las estaciones no discriminan entre estas opciones.

## Gemelo

**Verdad:** Valle 1,600, Nonoalco 100, domingo 0.69, sábado 0.87.

| Fondo verdadero de TEMPO | Invertido con | Domingo libre | Valle de México | Vial / verdad |
|---|---|---|---|---|
| uniforme por hora | fondo uniforme (actual) | 0.69 | 1,599 | 1.01 |
| uniforme + **patrón real de residuos** | fondo uniforme (actual) | 0.71 | 1,449 | 1.21 |
| uniforme + patrón real | + gradiente por hora | 0.76 | 1,268 | 1.60 |
| uniforme + patrón real | + región 3×3 fija | 0.71 | 1,372 | 1.16 |
| uniforme + patrón real | σ TEMPO × 10 | 0.64 | 1,110 | 1.40 |

- **El patrón espacial del fondo no reproduce los síntomas.** Con el patrón real de residuos, Valle cae solo 10 % (1,449) y el domingo queda bien (0.71). La diferencia de factor 5 y el domingo en 0.42 **no vienen del fondo**: están en la señal que mide TEMPO.
- **Advertencia:** con σ × 10, el gemelo sesga el vial (1.34–1.40), el domingo (0.59–0.64) y Valle (~1,100). Bajar el peso de TEMPO no es gratis: las variantes con σ × 10 en datos reales tampoco son la verdad.

## Conclusiones

1. **Valle de México (~300 t/año):** el fondo no la explica, y tampoco la química de pluma fresca (`centrales_generacion.md`). TEMPO mide menos NO₂ alrededor de Acolman del que el modelo pone con 320 t/año. Quedan tres explicaciones, sin probar:
   - **La emisión real es menor** que la de Climate TRACE, que es modelada y anual. Los ciclos combinados con control de NOₓ emiten mucho menos que el factor AP-42.
   - **Error de transporte:** con 30° de error de dirección, la pluma se reparte en píxeles equivocados.
   - **Comportamiento de la pluma** que el modelo no representa (sobreelevación, salida rápida de la capa límite).

   En cualquier caso, **la central no es identificable**: el resultado cambia de −164 a 539 con supuestos razonables del fondo. La opción B debe seguir reportándola agrupada, sin cifra propia.
2. **Domingo:** el cociente bajo viene de la señal de TEMPO (columna cruda 0.50–0.67, `placebo_tempo.md`) y de que TEMPO pesa demasiado, porque sus errores entre píxeles están correlacionados. Una explicación física que vale probar: **el efecto de fin de semana en la química**. Con menos NOₓ, el NO₂ se pierde más rápido (más OH), así que la columna de NO₂ baja más que la emisión de NOₓ. El jacobiano supone un cociente y una vida química fijos, y por eso traduce esa baja extra en menos emisión.
3. **Recomendación práctica:**
   - **TEMPO:** inflar σ × 3 (o promediar píxeles en superobservaciones de ~10 km). Es consistente con el patrón de residuos (2.6e15 persistente frente a 5e15 por píxel), no empeora el LOO y da σ honestos (Valle ±131).
   - **Cambios relativos:** seguir reportándolos con el estimador normalizado sobre estaciones (domingo 0.65), no con la inversión conjunta.
   - **Siguiente prueba:** química dependiente del tipo de día (vida del NO₂ y cociente NO₂/NOₓ por tipo de día en el jacobiano de TEMPO). No hace falta volver a probar el fondo.
