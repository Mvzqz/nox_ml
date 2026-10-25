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

### Notas para el notebook del avance 4

- **Ajuste fino no anidado, justificado por costo.** `nox-ml tune` elige y reporta con la misma validación dejando una estación fuera (nov–dic 2023), así que el error del mejor modelo es ligeramente optimista. La validación anidada completa costaría ~24 veces más cómputo (una búsqueda completa por cada estación oculta): para `pinn_puff`, cuyas pruebas tardan ~10–30 min, serían días de CPU. Se reportan los tiempos medidos y se aclara que la evaluación sin sesgo se hace en el avance 5 sobre feb–may 2024, periodo que no se usó para ajustar ni seleccionar.

## Avance 5: ensambles y modelo final (fecha: 1 de noviembre de 2026)

Todo ensamble debe seguir **estimando emisión**. Como la concentración es lineal en la emisión, una combinación convexa (pesos ≥ 0 que suman 1) de las predicciones de concentración corresponde a la misma combinación de las emisiones.

| # | Ensamble | Tipo | Base | Responsable |
|---|---|---|---|---|
| X1 | Bagging de la inversión: promedio de inversiones sobre remuestreos por bloques de días | Homogéneo | Mejor modelo físico (previsiblemente E2) | A |
| X2 | Ensamble de vientos: inversiones con viento perturbado (dirección y capa de mezcla), promediadas | Homogéneo | E2 | A |
| X3 | Ensamble profundo de PINN: 5 semillas o arquitecturas, promediadas; la dispersión da incertidumbre | Homogéneo | E5 | C |
| X4 | Boosting para la normalización meteorológica (en lugar de bosque aleatorio) | Homogéneo | E6 | C |
| X5 | Stacking/blending convexo de los 2 mejores modelos del avance 4, con pesos aprendidos sobre las predicciones fuera de muestra | Heterogéneo | Los 2 mejores del avance 4 | B |
| X6 | Promedio bayesiano de modelos (pesos por verosimilitud en estación oculta) | Heterogéneo | Modelos elegibles del avance 4 | B |

**Evaluación en datos no vistos (objetivo 3.6):**
- periodo de prueba feb–may 2024, que no se toca hasta el avance 5;
- confinamiento 2020 frente a 2019;
- contingencias 2024 (NOₓ y CO).

**Gráficos del modelo final (≥4, con interpretación):**
1. observado frente a predicho en estaciones ocultas;
2. residuos por estación, por hora y frente a ventilación (la pendiente del estancamiento);
3. mapa de emisión por zona con su incertidumbre;
4. cociente domingo/hábil con su intervalo frente al tráfico contado;
5. distribución del placebo;
6. información por tipo de observación (importancia de características);
7. confinamiento 2020: cambio estimado frente al esperado.

**Preparación desde ya:**
1. Cada corrida guarda sus predicciones fuera de muestra y su estimación de emisión (`docs/models.md`, sección 4).
2. Feb–may 2024 queda reservado como periodo de prueba (sección 5). No se usa para ajustar en el avance 4.
3. Migrar los datos y el cálculo del confinamiento 2020 y de las contingencias 2024 (tarea nueva).

## Reglas de integración

- Una rama por modelo (`models/<nombre>`); un pull request con su fila de `compare` en la descripción.
- No se toca el banco de evaluación ni el contrato sin acordarlo; si hace falta un campo nuevo en el `Dataset`, se pide en un pull request aparte.
- Las pruebas de contrato (`ml/tests/models/test_contract.py`) corren solas para todo modelo registrado.
- Los notebooks (`deliverables/Avance3.39.ipynb`, `deliverables/Avance4.39.ipynb`) solo llaman `nox_ml`. Se ejecutan de principio a fin antes de entregar (CI lo verifica).
- El notebook del avance 4 lleva al final la **declaración del uso de herramientas de IA**, obligatoria, en una celda de texto. El del avance 3 no la lleva.

## Orden

1. S3 (banco de evaluación) se fusiona y reproduce el baseline.
2. Coordinación: se implementan el contrato (`nox_ml.models`), el registro, `compare`, `tune`, la prueba de contrato y M4 como primer modelo registrado.
3. A, B y C trabajan en paralelo en sus modelos.
4. Se hace la comparación, el ajuste de los dos mejores y la elección del modelo final.
5. Se arman los notebooks de los avances 3 y 4.
