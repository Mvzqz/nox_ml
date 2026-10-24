# Placebo con TEMPO: ¿el estimador normalizado ve cambios donde no los hay?

Script: `scripts/placebo_tempo.py`. Resultados: `data/interim/placebo_tempo.json`. Los estadísticos por granulo están en `data/interim/placebo_tempo_granules.parquet`.

## Resumen

- **El estimador normalizado por meteorología no pasa el placebo con TEMPO.** Hay 18 pares de bloques de 2 semanas sin cambio esperado de emisiones. Con datos de pura suerte, ~2 de ellos tendrían un intervalo del 90 % que excluye "sin cambio" (1.0). Con los estimadores normalizados son **6 a 10**, con cambios aparentes medianos de 23–31 % y de hasta 89 %.
- **Normalizar con nuestro viento empeora las cosas frente a no normalizar.** El contraste crudo centro − periferia, sin modelo, pasa: 2 de 18 pares y cambios medianos de 18 %. La razón:
  - la columna "esperada" que calcula el modelo con el viento medio de las estaciones explica solo el 5–12 % de la variación entre granulos (r = 0.22 en otoño y 0.35 en primavera);
  - dividir entre ella agrega ruido en lugar de quitarlo.
- **En primavera hay una deriva estacional que ningún estimador corrige.** El exceso de columna cae ~30 % de febrero a mayo, pero el modelo con emisión fija no cambia. Lo más probable es la química: con más sol, el NO₂ dura menos. No es un cambio de emisiones. Comparar periodos separados por más de ~1 mes en primavera mide química, no tráfico.
- **Poder de detección:** con bloques de 2 semanas (7–10 días con TEMPO útil), un cambio de emisiones solo es creíble si supera **~30–35 %** con el contraste crudo, o **~45–55 %** con los normalizados. Esa cota es el percentil 90 del cambio aparente en los placebos.
- **Cambios reales:**
  - **Domingos:** se detectan bien con todos los estimadores. El contraste crudo da **0.61** (IC 0.50–0.76) en ambas temporadas, y los normalizados (masa y contraste) dan 0.50–0.67. Estas cifras están más cerca de lo plausible que el 0.31–0.51 de las estaciones.
  - **Semana Santa, contingencias y sábados:** no se distinguen del ruido.
  - **Vacaciones de diciembre:** salen con un *aumento* de 50–75 %. Lo atribuimos a estancamiento y química de invierno, quizá más tráfico comercial. Es una hipótesis sin verificar. En la práctica es un caso más de placebo fallido: el estimador no aísla la emisión.

**Conclusión para el proyecto:**
- Con el viento actual, TEMPO no sirve para medir cambios de emisión entre periodos menores a ~30 %.
- Sí sirve para:
  - efectos grandes y recurrentes, como el domingo;
  - comparar días de la semana dentro de la misma temporada, donde la química se cancela.
- El estimador normalizado que pasó el placebo 2019 con estaciones **no debe aplicarse a TEMPO tal cual**. Para TEMPO conviene el contraste crudo centro − periferia, siempre con un placebo de referencia en la misma temporada.

## Método

- **Datos:**
  - TEMPO NO₂ L2 V04, píxeles válidos (bandera de calidad 0, nubes < 0.2, sin nieve), 12–17 h locales;
  - nov–dic 2023 (264 granulos) y 15 feb–31 may 2024 (611 granulos);
  - 875 granulos en 164 días.
- **Modelo con emisión fija (denominador):**
  - columna de NO₂ en cada píxel por la emisión a priori (vialidades + 16 fuentes puntuales);
  - pluma gaussiana vertical integrada (`feasibility_linear.plume`) con el viento medio de las estaciones en esa hora y σθ = 30°;
  - la columna integrada no depende de la capa límite, solo de la velocidad y dirección del viento;
  - cociente NO₂/NOₓ constante, para no meter información de las estaciones por periodo.
- **Estimadores.** Los tres primeros son normalizados y los dos últimos crudos. Cada uno es un cociente de sumas sobre los granulos del grupo, igual que en `val2020_ratio.py`:

| Estimador | Numerador | Denominador |
|---|---|---|
| pendiente | covarianza obs–modelo dentro del granulo | varianza del modelo |
| masa | columna media − percentil 10 (obs) | lo mismo en el modelo |
| contraste | centro − periferia (obs) | lo mismo en el modelo |
| masa cruda | columna media − percentil 10 | n.º de granulos |
| contraste crudo | centro − periferia | n.º de granulos |

  "Centro" es el cuartil alto y "periferia" el cuartil bajo de densidad vial a ≤ 3 km del píxel. Esa división es fija para todos los granulos.
- **Días "normales":** de lunes a viernes, sin festivos (2 nov, 20 nov, 12 dic, 5 feb, 18 mar, 1 may), vacaciones de diciembre (18–31) ni Semana Santa (25 mar–5 abr), y sin los 23 días de contingencia de 2024.
- **IC 90 %:** bootstrap de días (1,000 réplicas), con cada grupo remuestreado por separado.

## 1. Placebo: bloques de 2 semanas sin cambio esperado

Bloques:
- otoño: nov 1–15, nov 16–30, dic 1–15;
- primavera: feb 15–29, mar 1–15, abr 8–19, abr 22–may 3, may 6–17, may 20–31.

Se comparan todos los pares de la misma temporada (18). Entre paréntesis va el número de días con TEMPO de cada bloque.

| Par (días) | Pendiente | Masa | Contraste | Masa cruda | Contraste crudo |
|---|---|---|---|---|---|
| nov 16–30 / nov 1–15 (10, 10) | **1.89** (1.23–2.50) | **1.53** (1.17–1.90) | **1.37** (1.06–1.69) | 1.30 (0.98–1.66) | 1.20 (0.82–1.64) |
| dic 1–15 / nov 1–15 (10, 8) | **1.37** | **1.28** | 0.83 | 1.16 | 0.93 |
| dic 1–15 / nov 16–30 (10, 8) | 0.73 | 0.83 | **0.60** | 0.89 | 0.77 |
| mar 1–15 / feb 15–29 (9, 10) | 1.18 | 1.02 | 1.13 | 0.98 | 0.85 |
| abr 8–19 / feb 15–29 (9, 10) | **0.66** | **0.71** | 0.75 | **0.68** | **0.63** |
| abr 22–may 3 / feb 15–29 (9, 7) | 0.91 | 0.90 | 0.94 | **0.74** | 0.78 |
| may 6–17 / feb 15–29 (9, 4) | **0.62** | **0.61** | 0.74 | **0.69** | 0.76 |
| may 20–31 / feb 15–29 (9, 7) | 0.81 | 0.78 | 0.75 | **0.70** | 0.71 |
| abr 8–19 / mar 1–15 (10, 10) | **0.56** | **0.70** | **0.66** | **0.69** | **0.74** |
| abr 22–may 3 / mar 1–15 (10, 7) | 0.77 | 0.89 | 0.84 | **0.75** | 0.92 |
| may 6–17 / mar 1–15 (10, 4) | **0.53** | **0.60** | **0.65** | **0.70** | 0.89 |
| may 20–31 / mar 1–15 (10, 7) | **0.69** | **0.77** | **0.67** | **0.71** | 0.83 |
| abr 22–may 3 / abr 8–19 (10, 7) | 1.38 | **1.28** | 1.26 | 1.10 | 1.23 |
| may 6–17 / abr 8–19 (10, 4) | 0.94 | 0.87 | 0.98 | 1.02 | 1.19 |
| may 20–31 / abr 8–19 (10, 7) | 1.24 | 1.11 | 1.01 | 1.04 | 1.11 |
| may 6–17 / abr 22–may 3 (7, 4) | **0.68** | **0.68** | 0.78 | 0.93 | 0.97 |
| may 20–31 / abr 22–may 3 (7, 7) | 0.90 | 0.87 | 0.80 | 0.95 | 0.90 |
| may 20–31 / may 6–17 (4, 7) | **1.32** | **1.28** | 1.03 | 1.02 | 0.93 |

En **negritas**, los pares cuyo IC 90 % excluye 1, es decir, un "cambio" falso estadísticamente significativo.

| Estimador | Pares con IC que excluye 1 (de 18; ~2 esperados) | Solo bloques consecutivos (de 7) | Cambio aparente mediano | Percentil 90 del cambio |
|---|---|---|---|---|
| Pendiente | 9 | 4 | 31 % | ×/÷ 1.8 |
| Masa | 10 | 5 | 25 % | ×/÷ 1.6 |
| Contraste | 6 | 3 | 23 % | ×/÷ 1.5 |
| Masa cruda | 8 | 1 | 20 % | ×/÷ 1.45 |
| **Contraste crudo** | **2** | **1** | **18 %** | **×/÷ 1.35** |

**Cómo leer los dos tipos de falla:**
- **Bloques consecutivos.** Aquí los normalizados fallan aun con 2 semanas de distancia. El bootstrap de días subestima la incertidumbre real, porque la meteorología que el viento medio no captura (estancamiento, recirculación, nubes) cambia de una quincena a otra.
- **Pares de primavera contra feb–mar.** Todos los estimadores, incluidos los crudos, dan 0.6–0.75. Por mes, el exceso de columna observado cae así respecto a febrero, mientras el modelo se mantiene en 0.98–1.07:

| Mes | Exceso observado (relativo a febrero) |
|---|---|
| marzo | 0.81 |
| abril | 0.70 |
| mayo | 0.67 |

  Es química estacional (vida media del NO₂ más corta con más radiación), no emisiones. Nuestro modelo es inerte y no la puede quitar.

## 2. Ruido puro: divisiones al azar de días de la misma temporada

Se toman días hábiles normales al azar para formar dos grupos de n días cada uno, sin efectos de calendario. Este es el piso de ruido: aunque la meteorología estuviera perfectamente corregida, no se podría bajar de aquí.

| Grupo | Pendiente | Masa | Contraste | Masa cruda | Contraste crudo |
|---|---|---|---|---|---|
| otoño, 5 días | 0.50–2.01 | 0.66–1.56 | 0.66–1.57 | 0.68–1.50 | 0.57–1.74 |
| otoño, 10 días | 0.59–1.72 | 0.74–1.38 | 0.74–1.34 | 0.74–1.33 | 0.67–1.48 |
| primavera, 5 días | 0.61–1.71 | 0.71–1.44 | 0.69–1.48 | 0.73–1.39 | 0.63–1.64 |
| primavera, 10 días | 0.69–1.46 | 0.78–1.28 | 0.76–1.33 | 0.80–1.25 | 0.73–1.39 |
| primavera, 20 días | 0.77–1.31 | 0.84–1.20 | 0.82–1.21 | 0.85–1.17 | 0.80–1.27 |

Lo que muestra esta tabla:
- Con 10 días por grupo, el rango del 90 % es ±25–35 %. Con 20 días baja a ±15–25 %.
- La pendiente es siempre la más ruidosa. Depende de que el modelo ponga la pluma en el lugar correcto, y con el error de dirección de ~30° casi nunca lo hace.

## 3. Cambios reales conocidos

| Comparación (días) | Pendiente | Masa | Contraste | Masa cruda | Contraste crudo | Lo esperado |
|---|---|---|---|---|---|---|
| Domingos / hábiles, otoño (28, 6) | **0.47** (0.37–0.63) | **0.53** (0.42–0.66) | **0.50** (0.40–0.67) | **0.71** (0.60–0.83) | **0.61** (0.50–0.76) | Bajada. Tráfico Infovial ~0.80; NOₓ algo menor por menos camiones diésel |
| Domingos / hábiles, primavera (51, 11) | **0.45** (0.32–0.63) | **0.63** (0.53–0.75) | **0.67** (0.57–0.78) | **0.59** (0.53–0.66) | **0.61** (0.50–0.74) | Igual |
| Sábados / hábiles, otoño (28, 5) | 1.13 | 1.05 | 0.89 | 0.81 | 0.74 | Bajada pequeña |
| Sábados / hábiles, primavera (51, 9) | **0.76** | 0.98 | 1.00 | 0.94 | 0.93 | Igual |
| Vacaciones dic 18–29 / hábiles nov 27–dic 15 (12, 8) | **1.66** | **1.48** | **1.50** | **1.63** | **1.75** | ¿Bajada? Sin dato de tráfico |
| Semana Santa / hábiles vecinos (28, 10) | 0.77 (0.54–1.03) | 0.89 | 0.96 | 0.88 | 0.77 (0.51–1.12) | Bajada (vacaciones escolares) |
| Contingencias / hábiles normales, primavera (47, 15) | 1.18 | 1.06 | 1.08 | 1.00 | 1.12 | Bajada pequeña (Hoy No Circula ampliado) |

Viento medio en las tardes usadas: 1.5 m/s en otoño y 1.9 m/s en primavera.

**Lo que dicen estos resultados:**
- **Domingos.** Es el único cambio real que se ve con claridad. El efecto es grande (−35 a −40 %), se repite cada semana y la química se cancela porque la comparación es dentro de la misma temporada.
  - Los estimadores masa y contraste (0.50–0.67) y el contraste crudo (0.61) quedan **más cerca de lo plausible que el 0.31–0.51 de las estaciones**.
  - Aun así son más bajos que el tráfico de Infovial (0.80). Parte de la diferencia es real: los camiones pesados, que emiten mucho NOₓ, casi no circulan en domingo.
- **Diciembre.** Sale al revés de lo esperado y con fuerza: +50 a +75 %. En la segunda quincena de diciembre hay más inversiones térmicas, menos radiación (el NO₂ vive más) y probablemente tráfico comercial navideño. El viento medio no captura nada de eso.

  Lección: el estimador no aísla emisiones cuando la meteorología cambia de régimen.
- **Semana Santa y contingencias.** Si los cambios existen, son menores que el ruido (~25–35 % con estos tamaños de muestra). No se puede afirmar nada.

## 4. Cambio mínimo detectable

El cambio mínimo creíble es el que supera la cota de falsos cambios, tomada del percentil 90 del placebo y del ruido puro:

| Estimador | Bloques de 2 semanas (7–10 días) | 20 días por grupo, misma temporada |
|---|---|---|
| Contraste crudo | ~30–35 % | ~20–25 % |
| Masa / contraste normalizados | ~45–55 % | ~20 % (ruido), pero con sesgos de placebo de hasta 50 % |
| Pendiente | ~60–80 % | ~25–30 % |

Esto aplica a comparaciones **dentro de la misma temporada y a menos de ~1 mes de distancia**. Entre temporadas (primavera/otoño), todos los estimadores dan 0.6–0.9 sin cambio de emisiones conocido.

## Qué cambia para el proyecto

1. **No usar la normalización por viento con TEMPO para comparar periodos.** Con el viento medio de las estaciones (error de dirección ~30°), el modelo explica muy poco de la columna observada y dividir entre él agrega ruido.

   Para comparar periodos con TEMPO, usar el contraste crudo centro − periferia y reportar siempre:
   - el placebo de la misma temporada como cota de falsos cambios;
   - comparaciones de ≤ 1 mes de distancia o por día de la semana.
2. **Rol de TEMPO en el POC.** Sirve para el mapa espacial (dónde están los puntos calientes, ver `puntos_calientes.html`) y para efectos grandes y recurrentes (domingo). No sirve para evaluar medidas como el Hoy No Circula de una contingencia: su efecto esperado (< 20 %) queda debajo del ruido.
3. **Lo que podría arreglarlo:**
   - un viento con mejor dirección, como un WRF a 1 km (ver `solicitudes_datos.md`), haría útil el modelo como denominador;
   - una corrección química simple, como la vida media del NO₂ por mes o por radiación, quitaría la deriva estacional;
   - ambas se pueden probar con este mismo script cuando haya datos.
4. **El estimador de estaciones que pasó el placebo 2019** compara tres meses contra el mismo periodo del año anterior. Eso cancela la química estacional. Con TEMPO solo se puede hacer igual comparando el mismo periodo de dos años. Ya hay datos de TEMPO V04 para la primavera de 2025, pero falta descargarlos.

   El diseño correcto es el mismo de `val2020_ratio.py`: comparar mar–may 2025 contra mar–may 2024, con un placebo sin cambio.

## Limitaciones

- El número de días con TEMPO útil por bloque es pequeño (4–10). Los IC por bootstrap de días con tan pocos días son aproximados.
- Los bloques comparten días entre pares (cada bloque entra en varios pares), así que los 18 placebos no son independientes. El conteo "6–10 de 18" es indicativo y no una prueba formal.
- La lista de festivos y de contingencias viene de fuentes periodísticas sin verificar (ver `data/raw/contingencias`).
- Se usa el viento medio del dominio. No se probaron el campo IDW ni el viento METAR para este estimador.
