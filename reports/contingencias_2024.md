# Contingencias ambientales de 2024: ¿bajaron las emisiones?

Fecha: 2026-10-21. Script: `scripts/contingencias_2024.py`. Resultados en `data/interim/contingencias_2024.json` (fechas tal cual), `contingencias_2024_shift1.json` (fechas +1 día) y `contingencias_2024_hourly.parquet`.

## Resumen

- **No se detecta una caída de la emisión de NOₓ en los días de contingencia de 2024.** El estimador normalizado por meteorología da 1.13 (IC 90 % 1.05–1.22) en todos los días y 1.07 (0.97–1.18) en días hábiles. Una reducción de 10–15 % o más habría salido por debajo de 1, y no sale.
- **La concentración casi no cambió** (1.06), y la meteorología de esos días tampoco era peor que la de los días de referencia (0.94: un poco *más* ventilada según el modelo). Es decir: en la tarde, el NOₓ de los días de contingencia es el de un día normal de la misma temporada.
- **Que salga mayor que 1 no significa que las emisiones subieran.** Indica un sesgo que el estimador no corrige en estos días: probablemente acumulación de varios días y fondo regional más alto en los episodios. Por eso el resultado se lee como "sin reducción detectable", no como "aumento".
- **Lectura práctica:** si el Hoy No Circula extendido redujo el NOₓ vial de la tarde, fue por menos de ~10 %, por debajo de lo que este método distingue hoy. Concuerda con estudios que no encuentran efectos claros del Hoy No Circula en la calidad del aire.
- **Es justo el caso de uso que buscamos.** El sistema separa "bajó la concentración por clima" de "bajó la emisión", y aquí dice que ninguna de las dos pasó.

## Qué se hizo

| Paso | Detalle |
|---|---|
| Días de contingencia | 23 fechas de `data/raw/contingencias/contingencias_ozono_2024.csv` (22 feb a 31 may; de notas de prensa, **pendiente de verificar con los comunicados de la CAMe**). Agrupadas en 11 episodios |
| Datos | NOₓ SIMAT por estación, tardes de 12 a 17 h; viento REDMET con la corrección de mph de 2024; capa límite ERA5 + MERRA-2 (`pbl_2023_2024.parquet`); O₃ máximo diario de SIMAT |
| Estimador | Por hora: NOₓ observado (promedio de estaciones) ÷ NOₓ que predice el modelo de pluma con la emisión vial fija. El cociente de ese índice entre días de contingencia y de referencia estima el cambio de emisión ya descontada la ventilación. Es el mismo estimador que pasó el placebo de 2019 (`validacion_2020.md`) |
| Días de referencia | Para cada día de contingencia: el mismo día de la semana (festivos cuentan como domingo), ±4 semanas, sin contingencia y que no sea el día siguiente a una |
| Incertidumbre | IC 90 % por bootstrap estratificado: remuestrea días de contingencia y sus referencias (500 réplicas) |
| Placebos | Días **falsos** de contingencia con el mismo patrón de días de la semana, sorteados 500 veces entre días sin contingencia de feb a mediados de jun: (1) al azar; (2) solo días poco ventilados, como los reales; (3) solo días con O₃ alto (cuartil superior, ≥133 ppb) |

## Resultados (cociente contingencia ÷ referencia)

| Grupo | Días | Concentración | Lo que explica la meteorología | **Emisión (normalizado)** |
|---|---|---|---|---|
| Todos | 23 | 1.06 | 0.94 | **1.13 (1.05–1.22)** |
| Hábiles | 14 | 1.07 | 1.00 | **1.07 (0.97–1.18)** |
| Fin de semana / festivo | 9 | 1.04 | 0.85 | **1.22 (1.13–1.31)** |

### Placebos: qué da el estimador cuando no hubo medidas

| Placebo | Todos los días | Hábiles |
|---|---|---|
| Al azar | 0.98 (90 %: 0.88–1.09) | 0.96 (0.86–1.05) |
| Días poco ventilados | 0.91 (0.83–0.99) | 0.90 (0.83–1.00) |
| Días con O₃ alto | 0.95 (0.92–0.99) | 0.95 (0.90–1.00) |

- **Calibración:** sin medidas, el estimador se mueve ±10 % alrededor de 0.9–1.0. Una caída real de la emisión vial de 10–15 % o más daría valores claramente por debajo de ese rango.
- **Los días reales quedan por encima de todos los placebos**, en el 100 % de las 500 comparaciones con el placebo de días poco ventilados. Algo distingue a los días de contingencia de otros días de O₃ alto o poco ventilados, y no es una baja de emisiones. Las explicaciones más probables:
  - acumulación de varios días (los episodios duran 2–4 días);
  - fondo regional mayor;
  - error del modelo con capas límite muy altas (2,600 m en esos días).

### Por episodio

| Episodio | Días | O₃ máx (ppb) | Concentración | Meteorología | Emisión |
|---|---|---|---|---|---|
| 22–25 feb | 4 | 165 | 1.42 | 1.10 | 1.30 (1.16–1.44) |
| 6 mar | 1 | 179 | 0.89 | 0.71 | 1.25 (1.13–1.41) |
| 23–24 mar | 2 | 128 | 1.02 | 0.81 | 1.25 (0.95–1.44) |
| 30 abr–1 may | 2 | 150 | 1.04 | 0.87 | 1.19 (1.02–1.43) |
| 3–4 may | 2 | 160 | 0.95 | 0.81 | 1.16 (1.03–1.39) |
| 9–10 may | 2 | 143 | 0.86 | 0.88 | 0.98 (0.86–1.12) |
| 13–16 may | 4 | 169 | 1.08 | 0.99 | 1.08 (0.93–1.33) |
| 18–19 may | 2 | 144 | 0.95 | 0.85 | 1.11 (0.87–1.29) |
| 22 may | 1 | 170 | 0.97 | 1.50 | 0.65 (0.55–0.75) |
| 25 may | 1 | 174 | 1.13 | 0.95 | 1.19 (0.96–1.34) |
| 30–31 may | 2 | 150 | 1.01 | 1.01 | 1.00 (0.81–1.28) |

- **Un día suelto es ruidoso.** El 22 de mayo sale 0.65 solo porque el modelo esperaba un día muy estancado (meteorología 1.50) y no lo fue tanto. Para decisiones conviene leer el grupo o episodios de varios días, no días aislados.
- **El 6 de marzo muestra la separación:** la concentración bajó 11 %, pero la meteorología explicaba una baja de 29 %. Si solo se mirara la concentración, se habría atribuido a las medidas una mejora que fue del viento.

### Sensibilidad: ¿las medidas aplican el día siguiente?

La contingencia se activa cuando el O₃ supera el umbral, y las restricciones aplican desde la mañana siguiente. Si la lista de prensa registra días de activación y no días con restricciones, los días correctos son los siguientes. Con las fechas desplazadas +1 día:

| Grupo | Emisión |
|---|---|
| Todos | 1.05 (0.97–1.12) |
| Hábiles | 1.03 (0.94–1.16) |

Tampoco hay reducción, así que la conclusión no depende de esa ambigüedad.

## Límites

- **Lista de fechas sin verificar.** Viene de prensa. Antes de presentar esto a SEDEMA hay que confirmarla con los comunicados oficiales de la CAMe y separar fase I de fase II.
- **Solo NOₓ vial de la tarde (12–17 h).** Las restricciones también afectan COV, industria y la mañana. Un efecto en la hora pico matutina no se mide aquí.
- **Sesgo residual hacia arriba en los días de episodio** (1.07–1.22 frente a placebos de 0.90–0.98). Con ese sesgo, no se puede descartar una reducción pequeña (~5–10 %) que quede oculta.
- **Viento con el error de dirección conocido de la CDMX** (28–32°) y modelo de pluma estacionario. Afectan sobre todo días sueltos, menos los promedios de grupo.

## Qué significa para el caso de uso

- **Pregunta que se puede responder hoy:** "¿bajó la emisión vial de NOₓ en las tardes de contingencia, una vez descontado el clima?" Respuesta para 2024: **no de forma detectable** (umbral ~10 %).
- **Valor:** una evaluación así, con su placebo, se puede producir días después de cada contingencia con datos públicos. Hoy la evaluación oficial se apoya en la concentración, que mezcla clima y emisión.
- **Mejoras para bajar el umbral de detección:**
  - viento con ensamble σθ = 30° o WRF;
  - fondo regional estimado con estaciones periféricas;
  - aforos vehiculares de los días de contingencia, para tener la referencia directa de cuántos autos dejaron de circular;
  - TEMPO para las tardes de 2024.

## CO como trazador

**Pregunta.** En Bogotá el Día sin carro mostró NOₓ +3 % pero CO −23 %: la restricción saca autos (mucho CO) y no diésel (mucho NOₓ). ¿Pasa lo mismo en las contingencias de 2024 de la CDMX? Se aplicó el mismo estimador al CO horario de SIMAT (`scripts/contingencias_co.py`, que importa las funciones de `contingencias_2024.py`): mismos 23 días, mismas referencias (mismo día de la semana, ±4 semanas, sin contingencia) y mismos placebos (días falsos al azar y días estancados). Se añade una ventana matutina (7–11 h), porque el Hoy No Circula opera desde las 5 h. El CO es inerte a esta escala, así que se usa la misma dispersión del modelo que para NOₓ. Cada contaminante se promedia con sus propias estaciones, por eso el NOₓ de la tarde sale 1.15 y no 1.13.

**Resultados** (cociente contingencia ÷ referencia, los 23 días; IC 90 % por bootstrap conjunto):

| Ventana | Gas | Concentración | Meteorología | Emisión (IC 90 %) | Placebo al azar (90 %) | Placebo estancado (90 %) |
|---|---|---|---|---|---|---|
| Tarde 12–17 h | NOₓ | 1.06 | 0.93 | 1.15 (1.06–1.23) | 0.98 (0.88–1.08) | 0.92 (0.83–1.00) |
| Tarde 12–17 h | CO | 1.12 | 0.92 | 1.22 (1.12–1.32) | 1.00 (0.89–1.12) | 0.95 (0.84–1.05) |
| Tarde 12–17 h | CO/NOₓ | — | — | 1.06 (0.98–1.16) | 1.02 (0.96–1.08) | 1.04 (0.98–1.09) |
| Mañana 7–11 h | NOₓ | 1.08 | 1.00 | 1.08 (0.97–1.20) | 1.02 (0.91–1.15) | 1.00 (0.90–1.11) |
| Mañana 7–11 h | CO | 1.08 | 1.00 | 1.08 (0.98–1.19) | 1.02 (0.92–1.14) | 1.01 (0.91–1.11) |
| Mañana 7–11 h | CO/NOₓ | — | — | 1.00 (0.93–1.07) | 1.00 (0.97–1.04) | 1.00 (0.96–1.04) |

Solo días hábiles (14): tarde CO 1.19 (1.05–1.33), NOₓ 1.09 (0.97–1.20), CO/NOₓ 1.09 (0.99–1.23); mañana CO 1.11 (1.01–1.22), NOₓ 1.12 (1.01–1.24), CO/NOₓ 0.99 (0.92–1.07).

**Interpretación.**
- **La restricción no se ve en el CO.** No hay baja en ninguna ventana; en la tarde el CO sube incluso más que el NOₓ (1.22 contra 1.15), por encima del rango de los placebos. Eso contradice una reducción de autos de gasolina, que habría bajado el CO. El patrón es el de un sesgo común de los días de episodio (poca ventilación que el modelo no capta del todo, quizá por viento y capa límite), que ya se veía en el NOₓ.
- **El cociente CO/NOₓ es la lectura más robusta**, porque el sesgo meteorológico se cancela en buena parte: 1.06 (0.98–1.16) en la tarde y 1.00 (0.93–1.07) en la mañana, dentro de los placebos (0.96–1.11). Si los autos hubieran salido y el diésel no, el cociente caería (en Bogotá fue ≈0.75); aquí no cae. El umbral de detección es de unos 7–10 %.
- **Implicación sobre qué domina el NOₓ.** Esto no confirma la hipótesis de Bogotá. Hay dos lecturas compatibles: (a) la restricción de contingencia (Hoy No Circula ampliado) saca pocos vehículos, o ese efecto se compensa con otros viajes, y por eso no mueve ni CO ni NOₓ; (b) el efecto existe pero es menor que ~10 %. No se puede concluir que el NOₓ lo dominen los diésel: la prueba no distingue tipos de vehículo porque la restricción no se detecta en ningún gas.
- **Límites propios de esta prueba:** la lista de fechas sigue sin verificar; el CO de la CDMX también tiene fuentes no viales (cocción, industria) y fondo regional; y el Día sin carro de Bogotá es una restricción mucho más fuerte que la contingencia.
