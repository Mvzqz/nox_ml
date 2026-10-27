# Plan de los avances 3 (baseline) y 4 (modelos alternativos)

Contratos técnicos: `docs/models.md`. Este documento dice **qué** se entrega y **quién** (A, B, C) hace cada parte.

## Problema y métrica (común a los dos avances)

- **Tarea:** dado el NOₓ medido por estaciones y satélite, más la meteorología, **estimar la emisión** (y sus cambios) por zona y tipo de día. **Estimar emisión es requisito de todo modelo candidato.**
- **Referencias de concentración:** IDW (~11.6 ppb) y kriging. Solo predicen concentración y **no son candidatos**. Marcan el piso que un modelo debe empatar o superar al predecir estaciones ocultas.
- **Filtro de elegibilidad:** el placebo (días sin cambio de emisión) debe quedar centrado en 1 ± 0.15. Un modelo que inventa cambios queda fuera, aunque tenga buen error.
- **Métrica principal:** `loo_rmse_ppb`, el error al predecir una estación oculta. Mide si la física y las emisiones estimadas explican lo que se mide donde no hay sensor, y está en ppb.
- **Métricas de emisión (obligatorias):**
  - `sunday_ratio` y su diferencia con el tráfico contado (0.65–0.73): un cambio de emisión con respuesta conocida.
  - `placebo_halfwidth`: el cambio mínimo detectable.
- **Otras métricas:** `loo_bias_ppb` y `loo_hourly_rmse_ppb` (nivel frente a ritmo) y `r_tempo` (instrumento independiente).
- **Costo:** `fit_seconds` y número de parámetros.

## Avance 3: baseline

**Modelo:** inversión bayesiana lineal con pluma estacionaria, zonas 3×3 y viento promedio del dominio. Debe reproducir la fila de referencia: r 0.77/0.74, LOO 13.6/11.6/11.7, domingo 0.42.

| Sección del notebook | Contenido | Rúbrica |
|---|---|---|
| Algoritmo | Por qué una inversión bayesiana con física:<br>• el objetivo es estimar emisión y no hay etiquetas de emisión;<br>• pocos datos (~24 estaciones);<br>• da incertidumbre;<br>• es interpretable (factores por zona);<br>• separa emisión de clima.<br>IDW se muestra como referencia de concentración, que no puede responder la pregunta | 40 |
| Características importantes | Observaciones como características:<br>• **embedded:** cuánta información aporta cada tipo de observación (reducción de varianza posterior por estaciones frente a TEMPO, a partir de Jᵀ R⁻¹ J);<br>• **wrapper:** ablación (sin TEMPO; 24, 15 o 9 estaciones; viento degradado).<br>Con gráficas | 20 |
| Sub/sobreajuste | Error dentro de muestra frente a estación oculta; descomposición nivel y ritmo; curva de aprendizaje por número de días y de estaciones | 10 |
| Métrica | Justificación de la métrica principal y las secundarias (arriba); por qué no R² global | 20 |
| Desempeño | Desempeño mínimo:<br>• placebo dentro de ±15 %;<br>• dirección correcta del domingo;<br>• no quedar muy por debajo de IDW en concentración.<br>Conclusión honesta: el baseline pasa el placebo y ve la baja del domingo, pero la exagera (0.42 frente a 0.65–0.73) y no supera a IDW por sí solo. Eso fija lo que deben mejorar los modelos del avance 4 | 10 |

**Responsables:** el baseline lo cierran S3 (banco de evaluación) y quien coordina. Las gráficas de "características" usan el banco de comparación de datos ya hecho en la investigación.

## Avance 4: modelos alternativos

Se piden al menos 6 modelos individuales con **algoritmos distintos**. **Todos estiman emisión.** Las referencias (IDW, kriging) aparecen en la tabla solo como piso de concentración.

| # | Modelo | Algoritmo | Emisión que estima | Hiperparámetros principales | Responsable |
|---|---|---|---|---|---|
| E1 | `inversion_plume` | Inversión bayesiana lineal + pluma estacionaria (**baseline**) | Absoluta por zona y tipo de día | σθ, viento mínimo, peso de TEMPO, σ del supuesto inicial | A |
| E2 | `inversion_puff` | Inversión bayesiana lineal + puffs y vida química por OH | Absoluta | duración del puff, vida química, σθ, viento mínimo, peso de TEMPO | A |
| E3 | `regularized_ls` | Mínimos cuadrados regularizados y no negativos (ridge/NNLS) sobre la tabla física, sin supuesto bayesiano | Absoluta | α de regularización, tipo de penalización | B |
| E4 | `lognormal_map` | Inversión no lineal: emisiones log-normales (siempre positivas), máximo a posteriori con L-BFGS-B e incertidumbre por aproximación de Laplace | Absoluta | σ log del supuesto inicial, tolerancia, iteraciones | B |
| E5a | `pinn_plume` | PINN (núcleo de pluma aprendido) + inversión bayesiana | Absoluta | capas, ancho, tasa de aprendizaje, peso de la física, pasos | C (hecho) |
| E5b | `pinn_puff` | PINN aplicada a cada tramo de puff + inversión bayesiana | Absoluta | los de E5a + duración del puff, vida química | C |
| E5c | `pinn_joint` | PINN entrenada con física y estaciones a la vez | Absoluta | los de E5a + peso de los datos | C |
| E6 | `rf_deweather` | Normalización meteorológica con bosque aleatorio (aprende concentración ~ meteorología + calendario; la emisión es lo que queda al fijar la meteorología) | Relativa (índice por tipo de día y zona) | número de árboles, profundidad, variables meteorológicas | C |
| E7 | `normalized_ratio` | Estimador normalizado con el modelo de transporte (observado ÷ esperado con emisión fija) | Relativa | modelo de transporte, ventana horaria, bootstrap | B |
| R1, R2 | `idw`, `kriging` | Interpolación (referencias) | — | potencia o kernel | B |

**Flujo:**
1. Cada responsable implementa sus modelos con el contrato y los corre con `nox-ml run`.
2. `nox-ml compare` arma la tabla ordenada por la métrica principal, con las métricas de emisión, las demás métricas, los tiempos y el filtro de elegibilidad. Las referencias van al final como piso.
3. Se eligen los **dos mejores elegibles.** Previsiblemente E2 y uno de E4, E5 o E6, pero lo decide la tabla.
4. Cada uno de los dos se ajusta con `nox-ml tune`. Esa búsqueda incluye las mejoras de la investigación:
   - incertidumbre del viento;
   - peso del satélite;
   - restricción de tráfico;
   - viento mínimo;
   - zonas administrativas;
   - supuestos de centrales corregidos;
   - horas de las 17:00.
5. **Modelo final:** se argumenta con la métrica principal, la exactitud del cambio de emisión y los placebos. También cuentan la interpretabilidad (factores por zona), la incertidumbre, si da emisión absoluta o solo relativa, y el costo.

| Sección del notebook | Rúbrica |
|---|---|
| Tabla comparativa: ≥6 modelos, ordenados por la métrica principal, con ≥2 métricas más y tiempos | 60 |
| Ajuste de los 2 mejores: espacio de búsqueda, número de pruebas, curva de pruebas y mejora obtenida | 30 |
| Modelo final: argumentos más allá de la métrica | 10 |

## Avance 5: ensambles y modelo final (fecha: 1 de noviembre de 2026)

Guías para implementar y correr: [arranque](avance5_arranque.md) y frentes [A](avance5_frente_a.md), [B](avance5_frente_b.md) y [C](avance5_frente_c.md).

Rúbrica: ensambles 60 (al menos 4, homogéneos y heterogéneos; stacking o blending con los mejores modelos del avance 4), selección 20 (tabla con el mejor individual y los ensambles, ordenada por la métrica principal, al menos 2 métricas más y tiempos de entrenamiento; argumentos para elegir), gráficos 20 (al menos 4 del modelo final, cada uno interpretado). Obligatorio: optimizar hiperparámetros de los ensambles relevantes, evaluar en datos no vistos (objetivo 3.6), declaración de IA al final, notebook `notebooks/Avance5.39.ipynb` ejecutado de principio a fin y guardado con sus salidas.

### Ensambles

Todo ensamble debe seguir estimando emisión. Como la concentración es lineal en la emisión, una combinación convexa (pesos ≥ 0 que suman 1) de las predicciones de concentración corresponde a la misma combinación de las emisiones. E5b y E2 difieren en un factor de ~2 en emisión absoluta (avance 4, sección 3): los ensambles heterogéneos se reportan sobre todo con cocientes, y la dispersión entre modelos se presenta como incertidumbre estructural.

| # | Ensamble | Tipo | Base | Costo | Prioridad | Responsable |
|---|---|---|---|---|---|---|
| X1 | Bagging de la inversión: promedio de inversiones sobre remuestreos por bloques de días | Homogéneo | E5b | Bajo (caché de matrices) | Mínimo | A |
| X2 | Ensamble de vientos: inversiones con dirección del viento y capa límite perturbadas, promediadas | Homogéneo | E5b o E2 | Medio (1–2 h en local) | Recomendado: el viento es la fuente principal de error | A |
| X3 | Varias semillas de la PINN, promediadas; la dispersión da incertidumbre | Homogéneo | E5b | Medio | Opcional: en el avance 4 la red no importó (banda de 0.016 ppb) | C |
| X4 | Boosting (gradient boosting) en lugar de bosque aleatorio para la normalización meteorológica, con ajuste de hiperparámetros | Homogéneo | E6 | Bajo | Mínimo | C |
| X5 | Stacking convexo sobre las predicciones fuera de muestra (`oof.parquet`), anidado por estación: los pesos para evaluar una estación se aprenden sin ella | Heterogéneo | E5b, E2, E5a | Muy bajo | Mínimo | B |
| X6 | Promedio bayesiano de modelos (pesos por verosimilitud en estación oculta) | Heterogéneo | Modelos elegibles del avance 4 | Muy bajo | Mínimo | B |

Mínimo para la rúbrica: X1, X4, X5 y X6. Los hiperparámetros se ajustan solo con nov–dic 2023.

### Evaluación en datos no vistos (objetivo 3.6)

1. La tabla de nov–dic 2023 (validación con estación oculta, placebo, domingo/hábil, tiempos) elige el modelo final y uno o dos finalistas.
2. Los finalistas se corren una sola vez en feb–may 2024 con la configuración congelada: error con estación oculta, domingo/hábil frente al tráfico y placebo. Requiere un modo de evaluación en el periodo de prueba (el que hoy rechaza `nox-ml tune`).
3. Contingencias 2024 (caen dentro de feb–may 2024): migrar desde `research-archive` `contingencias_2024.py` y `contingencias_co.py`, y medir si el modelo final ve el cambio de emisión esperado.
4. Fuera de esta entrega: el confinamiento 2020 frente a 2019. El modelo final necesita TEMPO (desde 2023) y MERRA-2 (no descargado para 2019–2020); sin TEMPO, la inversión no pasa el placebo de 2019 (caída falsa de 44 %, `reports/validacion_2020.md` de la investigación). Queda como tarea posterior con E7 y E6, que no necesitan satélite.

### Gráficos del modelo final (al menos 4, con interpretación)

1. Observado frente a predicho en estaciones ocultas, en feb–may 2024.
2. Residuos por estación, por hora y frente a la ventilación.
3. Serie de tiempo con la predicción en 2 o 3 estaciones (tendencia y predicción).
4. Mapa de emisión por zona con su incertidumbre.
5. Domingo/hábil con su intervalo frente al tráfico contado, y distribución del placebo.
6. Pesos del ensamble o información aportada por tipo de observación (importancia de características).

### Calendario

| Fecha | Trabajo | Dónde |
|---|---|---|
| 26 oct | Contrato de ensambles (un ensamble es un `Model` del registro que envuelve a sus modelos base; stacking anidado por estación) y modo de evaluación en el periodo de prueba | Coordinación |
| 27–29 oct | A: X1, X2. B: X5, X6. C: X4, contingencias 2024 y X3 si hay tiempo | Corridas pesadas en local |
| 29–30 oct | Corridas de nov–dic, tabla comparativa, elección del modelo final y corrida única en feb–may 2024 | Local |
| 30–31 oct | Notebook `Avance5.39.ipynb` con salidas, gráficos, declaración de IA y HTML | Coordinación |
| 1 nov | Revisión final y entrega | — |

Riesgos: el cómputo de X2 y del periodo de prueba (feb–may es el doble de datos que nov–dic; las matrices de E5b tardan ~25 min), y que el stacking no mejore: con el ruido de ±0.5 ppb es probable, y es un resultado válido si se argumenta.

## Notas para el notebook del avance 4

Resultados del ajuste de `pinn_puff` (nov–dic 2023); la configuración final está en `configs/experiments/pinn_puff.yaml`.

- **Configuración final:** `u_min` 2.0, `lifetime: oh`, `kappa` 1500, `tau_h` 12, `max_age_h` 24. Error de validación cruzada (LOO) 11.87 ppb; placebo 1.01 ± 0.12.
- **Robustez:** las búsquedas de transporte, de red, de `kappa` y del peso de TEMPO quedan todas dentro del ruido de ±0.5 ppb; el modelo es robusto a esas elecciones.
- **`kappa` 3000** es claramente peor (12.60).
- **Vida media del NOx por OH:** estrecha el placebo de ±0.20 a ±0.12.
- Las corridas se hicieron en local; `inversion_puff.yaml` (E2) ya usa `lifetime: oh`, por lo que no hace falta otra configuración.

## Reglas de integración

- Una rama por modelo (`models/<nombre>`); un pull request con su fila de `compare` en la descripción.
- No se toca el banco de evaluación ni el contrato sin acordarlo; si hace falta un campo nuevo en el `Dataset`, se pide en un pull request aparte.
- Las pruebas de contrato (`ml/tests/models/test_contract.py`) corren solas para todo modelo registrado.
- Los notebooks (`notebooks/Avance3.39.ipynb`, `notebooks/Avance4.39.ipynb`) solo llaman `nox_ml`. Se ejecutan de principio a fin antes de entregar (CI lo verifica).
- Los notebooks de los avances 4 y 5 llevan al final la **declaración del uso de herramientas de IA**, obligatoria, en una celda de texto. El del avance 3 no la lleva.

## Orden

1. S3 (banco de evaluación) se fusiona y reproduce el baseline.
2. Coordinación: se implementan el contrato (`nox_ml.models`), el registro, `compare`, `tune`, la prueba de contrato y M4 como primer modelo registrado.
3. A, B y C trabajan en paralelo en sus modelos.
4. Se hace la comparación, el ajuste de los dos mejores y la elección del modelo final.
5. Se arman los notebooks de los avances 3 y 4.
