# Avance 5, frente B: ensambles heterogéneos (X5 y X6)

Antes de empezar: [avance5_arranque.md](avance5_arranque.md) (contrato, reglas, cómo se entrega una corrida).

## Objetivo

Los dos ensambles **heterogéneos**, que combinan modelos distintos del avance 4. La rúbrica exige que el stacking o blending use los mejores modelos individuales: E5b `pinn_puff` (11.87 ppb), E5a `pinn_plume` (12.49) y E2 `inversion_puff` (12.50).

## Tareas

| # | Nombre (obligatorio) | Qué es | Bases | Prioridad |
|---|---|---|---|---|
| X5 | `stacking` | Stacking convexo: pesos ≥ 0 que suman 1, aprendidos minimizando el error de las predicciones fuera de muestra, anidado por estación | E5b, E2, E5a | Mínimo para la rúbrica |
| X6 | `bayes_average` | Promedio bayesiano de modelos: pesos proporcionales a la verosimilitud de cada modelo en estación oculta | Modelos elegibles del avance 4 (E5b, E2, E5a, E3, E1, E4) | Mínimo para la rúbrica |

## Datos de entrada: ya existen

Cada corrida del avance 4 guardó `results/runs/<modelo>/oof.parquet`: la predicción de cada estación hecha por el modelo ajustado **sin** esa estación (`station`, `utc`, `nox_ppb_pred`). Las observaciones están en los datos de entrada (`Inputs`, o `nox_ml.validation.loo.station_rows`). Con eso se aprenden los pesos sin volver a correr los modelos base.

## X5: stacking anidado por estación

- **Por qué anidado.** Si los pesos se aprenden con todas las estaciones y luego se evalúa cada una, la estación evaluada ya influyó en los pesos (fuga). Para evaluar la estación `s`: aprender los pesos con los `oof` de las otras 23 estaciones y combinar con ellos las predicciones de `s`. Así el error del stacking es comparable con el de los modelos individuales.
- **Pesos convexos.** Minimizar el error cuadrático con pesos ≥ 0 que suman 1 (`scipy.optimize.minimize` con restricciones, o `scipy.optimize.nnls` y normalizar). Convexos porque así la combinación de predicciones corresponde a la misma combinación de emisiones (la concentración es lineal en la emisión). Sin intercepto: un intercepto sería un fondo inventado.
- **Emisión.** Combinación convexa de las emisiones de las bases con los pesos aprendidos con todas las estaciones. E5b y E2 difieren en un factor de ~2 en emisión absoluta (avance 4, sección 3): reportar el domingo/hábil combinado y presentar la dispersión entre bases como incertidumbre estructural. Seguir la regla que fije el contrato.
- **Placebo y domingo.** El banco de evaluación los calcula reajustando el modelo; para un ensamble eso significa reajustar sus bases (8 reajustes de placebo × costo de E5b + E2 + E5a, ~1.5–2 h). Usar el mecanismo del contrato; si el contrato ofrece una vía barata a partir de las corridas guardadas, documentar cuál se usó.
- **Hiperparámetros.** Qué bases entran (E5b+E2, E5b+E5a, las tres), regularización hacia pesos iguales (`alpha`), y si los pesos son globales o por hora del día. Ajuste: grilla chica; con `oof` cada prueba tarda segundos.
- **Qué esperar.** E5b domina; los pesos de E2 y E5a pueden quedar cerca de 0. Si el stacking no mejora a E5b más allá de ±0.5 ppb, es un resultado válido: decirlo y mostrar los pesos.

## X6: promedio bayesiano de modelos

- **Cómo.** Para cada modelo `k`, una verosimilitud gaussiana de sus residuos en estación oculta: `log L_k = −n/2 · log(σ_k²) − SSE_k / (2σ_k²)`, con `σ_k²` estimado de los mismos residuos. Pesos `w_k ∝ exp(log L_k − max log L)`. También anidado por estación (los pesos para evaluar `s` sin `s`).
- **Cuidado.** Con miles de filas, la verosimilitud suele dar peso ~1 al mejor modelo (el promedio bayesiano colapsa). Mitigarlo con una "temperatura" o con pesos por bloques de días (pseudo-BMA con bootstrap). Documentar la elección y mostrar los pesos.
- **Solo modelos elegibles** (placebo dentro de 1 ± 0.15) y que den emisión absoluta. E6 y E7 son relativos: dejarlos fuera o combinar solo cocientes, y decirlo.

## Pruebas

- Prueba de contrato al registrarlos.
- Stacking anidado: los pesos con que se evalúa la estación `s` no cambian si se modifican las filas de `s`.
- Pesos convexos: no negativos, suman 1, y con una base perfecta su peso es 1.
- Con un solo modelo base, el ensamble coincide con él.
- X6: con modelos idénticos, pesos iguales; con uno claramente mejor, su peso domina.

## Corridas

| Corrida | Qué | Tiempo estimado | Dónde |
|---|---|---|---|
| Tabla con `oof` | Error anidado de X5 y X6 a partir de las corridas guardadas | Segundos | Cualquiera |
| Ajuste de X5 | Grilla de bases y `alpha` | Minutos | Cualquiera |
| Corrida completa | `nox-ml run` de X5 y X6 (placebo y domingo con reajuste de bases) | 1.5–2 h cada uno | Local |

Si no hay máquina local disponible, avisar a coordinación para que corra la corrida completa.

## Cuándo está listo

0. `uv run pytest -m acceptance -k front_b` pasa (ver [avance5_arranque.md](avance5_arranque.md), pruebas de aceptación).
1. X5 y X6 registrados, con configuración y búsqueda.
2. `bin/check` pasa.
3. Filas de `compare` en el pull request, con los pesos aprendidos (globales y su variación entre pliegues) y la comparación con E5b.
4. Nota de 3–5 líneas: qué aportó cada base y por qué.

## Fecha

Implementación el 27–28 de octubre; corridas a más tardar el 29.
