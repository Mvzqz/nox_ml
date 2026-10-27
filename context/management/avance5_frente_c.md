# Avance 5, frente C: boosting, semillas de la PINN y evaluación en datos no vistos

Antes de empezar: [avance5_arranque.md](avance5_arranque.md) (contrato, reglas, cómo se entrega una corrida).

## Objetivo

Un ensamble homogéneo de boosting (X4), opcionalmente el de semillas de la PINN (X3), y la parte de datos no vistos: las contingencias de 2024 y la corrida única del modelo final en feb–may 2024.

## Tareas

| # | Qué | Prioridad |
|---|---|---|
| X4 | `gb_deweather`: normalización meteorológica con gradient boosting en lugar de bosque aleatorio, con ajuste de hiperparámetros | Mínimo para la rúbrica |
| C1 | Contingencias 2024: datos, cálculo y prueba con el modelo final | Necesario (objetivo 3.6) |
| C2 | Corrida única del modelo final (y finalistas) en feb–may 2024 | Necesario (objetivo 3.6), después de elegir |
| X3 | `pinn_seeds`: E5b con varias semillas de la red, promediadas | Opcional |

## X4: boosting para la normalización meteorológica

- **Qué cambia.** Lo mismo que E6 (`ml/src/nox_ml/models/rf_deweather.py`): mismas características (`hour_table`, `ventilation_features`), misma normalización (cada fila con el clima de 20 filas sorteadas del periodo), misma escala logarítmica sobre un fondo de 5 ppb y el mismo índice relativo por tipo de día. Solo cambia el estimador: `sklearn.ensemble.HistGradientBoostingRegressor` (ya está en las dependencias; no agregar LightGBM ni XGBoost).
- **Implementación.** Heredar de `RfDeweather` y sustituir `_new_forest` (y `n_params`), o extraer el estimador como un punto de extensión. Los intervalos siguen saliendo del remuestreo de días (`sample_weight`).
- **Hiperparámetros y ajuste.** `learning_rate` (0.02–0.2), `max_iter` (100–1 000), `max_leaf_nodes` (15–63), `min_samples_leaf` (5–50), `l2_regularization` (0–1). Búsqueda aleatoria de ~30 pruebas con `nox-ml tune` (cada prueba tarda segundos o minutos). Mostrar la curva de pruebas.
- **Cuidado.** El boosting sobreajusta más que el bosque: vigilar el placebo (E6 tiene 0.97 ± 0.09) y la atenuación del domingo hacia 1. En nov–dic `doy_sin` y `doy_cos` tienen correlación 1.00 (tarea abierta de ablación): si el ajuste lo permite, probar sin ellas.
- **Qué esperar.** E6 dio 14.61 ppb y domingo 0.53 (0.42–0.57). Si X4 baja el error sin romper el placebo, es candidato para el componente relativo del modelo final.

## C1: contingencias 2024

- **Datos.** `data/raw/contingencias/contingencias_ozono_2024.csv`: 23 fechas del 22 de febrero al 31 de mayo (de notas de prensa; verificar con los comunicados de la CAMe si hay tiempo). Caen dentro del periodo de prueba: **nada de esto se usa para ajustar ni elegir.**
- **Referencia de la investigación** (`reports/contingencias_2024.md` y `scripts/contingencias_2024.py`, `scripts/contingencias_co.py` en la rama `research-archive`): con el estimador normalizado, contingencia ÷ referencia = 1.13 (1.05–1.22) en todos los días y 1.07 (0.97–1.18) en días hábiles; los placebos de días falsos dan 0.9–1.0. Conclusión: no se detecta una reducción de la emisión vial de la tarde mayor a ~10 %.
- **Con el modelo final.** Usar el mismo mecanismo que el placebo (`placebo_ratios` en `ml/src/nox_ml/validation/experiment.py`): en el periodo de prueba, quedarse con los días hábiles (`Inputs.on_days`) y reetiquetar como "domingo" los días de contingencia (`Inputs.with_day_kinds`); el cociente domingo ÷ hábil del modelo ajustado es contingencia ÷ normal. Compararlo con el placebo del mismo periodo (días falsos al azar y días poco ventilados, como en la investigación) y con el estimador normalizado (E7).
- **Implementación.** Funciones en `nox_ml.validation` (por ejemplo `events.py`) y un subcomando o una opción de `nox-ml evaluate` que solo funcione en el periodo de prueba. Lectura del CSV en `nox_ml.data`. Pruebas con datos sintéticos: sin cambio en los días marcados, el cociente queda en 1; con una caída impuesta, la recupera.
- **Se puede preparar ya** (no depende de elegir el modelo final): código, pruebas y una corrida con E2 o E7 para comprobar que reproduce la investigación en orden de magnitud. La corrida con el modelo final va en C2.

## C2: corrida única en feb–may 2024

- **Cuándo.** Después de la tabla de nov–dic y de elegir el modelo final (29–30 de octubre). Una sola vez, con la configuración congelada; no se vuelve a elegir con estos resultados.
- **Periodo.** `2024-02-15` a `2024-05-31` (es el archivo de píxeles de TEMPO que existe: `data/interim/tempo_pixels_2024-02-15_2024-05-31.parquet`). Los festivos del periodo ya están en `HOLIDAYS` (`ml/src/nox_ml/inversion/linear.py`). El viento de 2024 ya trae la corrección de mph.
- **Qué se corre.** `uv run nox-ml evaluate configs/experiments/<final>.yaml --period test` para el modelo final y uno o dos finalistas (por ejemplo, el mejor individual E5b si el final es un ensamble). Mide error con estación oculta, domingo/hábil frente al tráfico, placebo y tiempos. Después, C1 con el modelo final.
- **Costo.** Feb–may es ~2 veces nov–dic en horas: las matrices de E5b tardan ~25 min y la corrida completa puede pasar de 2 h. Local, con `systemd-inhibit`.
- **Para el notebook.** Guardar en `results/runs/<final>.test/` las predicciones fuera de muestra (`oof.parquet`), que alimentan los gráficos de observado frente a predicho, residuos y series de tiempo.

## X3 (opcional): semillas de la PINN

- E5b con 3–5 semillas de la red (`seed` de `PinnPuffParams`; cada valor entrena una red nueva, ~3 min, guardada en `kernel_dir`), promediadas. Cada semilla rearma las matrices (~11 min).
- En el avance 4, 8 redes distintas quedaron en una banda de 0.016 ppb: casi seguro no mejora el error. Su valor es dar la incertidumbre de la red. Hacerlo solo si X4, C1 y C2 están cubiertos.

## Corridas

| Corrida | Tiempo estimado | Dónde |
|---|---|---|
| X4 y su ajuste (~30 pruebas) | 30–60 min | Cualquiera |
| C1 de prueba con E2 o E7 en feb–may | ~30 min | Local |
| C2: modelo final y finalistas en feb–may | 2–4 h | Local, de noche |
| C1 con el modelo final | ~1 h (8 reajustes) | Local |
| X3 (opcional) | ~1.5 h | Local |

## Cuándo está listo

0. `uv run pytest -m acceptance -k front_c` pasa (ver [avance5_arranque.md](avance5_arranque.md), pruebas de aceptación). Los nombres `gb_deweather` y `pinn_seeds` son obligatorios.
1. X4 registrado, con configuración, búsqueda y su fila de `compare` en nov–dic 2023.
2. C1: código y pruebas fusionados; resultado de prueba con E2 o E7 comparado con la investigación.
3. C2 y C1 con el modelo final, en `results/runs/`, con un resumen en el pull request.
4. `bin/check` pasa en cada pull request.

## Fechas

X4 y el código de C1 el 27–28 de octubre; C2 y C1 con el modelo final el 29–30.
