# Avance 5, frente A: ensambles de la inversión física (X1 y X2)

Antes de empezar: [avance5_arranque.md](avance5_arranque.md) (contrato, reglas, cómo se entrega una corrida).

## Objetivo

Dos ensambles **homogéneos** de los modelos de inversión. X1 promedia el mismo modelo sobre remuestreos de días (bagging). X2 promedia el modelo sobre vientos perturbados, porque el viento es la principal fuente de error del transporte. Los dos siguen estimando emisión absoluta por zona y tipo de día.

## Tareas

| # | Nombre sugerido | Qué es | Base | Prioridad |
|---|---|---|---|---|
| X1 | `bagged_inversion` | Bagging: `n_bags` inversiones, cada una sobre un remuestreo con reemplazo de días completos (bloques de días); predicción y emisión = promedio de los miembros | E5b `pinn_puff` (configuración de `configs/experiments/pinn_puff.yaml`) | Mínimo para la rúbrica |
| X2 | `wind_ensemble` | Ensamble de vientos: `n_members` inversiones, cada una con el viento horario perturbado (dirección y velocidad) y la capa límite perturbada; predicción y emisión = promedio | E2 `inversion_puff` (más barato de rearmar que E5b) | Recomendado |

## X1: bagging de la inversión

- **Cómo funciona.** Cada miembro ajusta la misma inversión con los días remuestreados con reemplazo. Bloques de un día completo, porque las horas de un mismo día están correlacionadas (es la misma unidad que el bootstrap de intervalos). La predicción en estaciones es el promedio de las de los miembros; la emisión, el promedio de sus posteriores (media y desviación estándar combinadas como mezcla).
- **Por qué es barato.** El transporte no depende de qué días se usan: las matrices se arman una vez (caché de `Inputs.jacobians`) y cada miembro solo vuelve a resolver el sistema. Ver cómo lo hace el bootstrap de intervalos: `ratio_intervals` en `ml/src/nox_ml/models/inversion_plume.py`, y `hour_systems` / `solve` en `ml/src/nox_ml/inversion/linear.py`.
- **Qué esperar.** La inversión es lineal y gaussiana: el promedio de los bags se parece mucho al posterior completo. Lo probable es que el error no cambie (dentro de ±0.5 ppb) y que la dispersión entre bags dé una incertidumbre más honesta. Es un resultado válido; documentarlo así.
- **Hiperparámetros.** `n_bags` (10–50), tamaño del bloque (1 día; opcional 2–3 días), `seed`. Ajuste: una grilla chica de `n_bags` basta para mostrar que se estabiliza.
- **Implementación sugerida.** Una clase que envuelve a un modelo de la familia de `InversionPlume` (por composición, no copiando código) o el mecanismo de ensamble del contrato si ya lo resuelve. Los días remuestreados con reemplazo necesitan pesos (un día que sale dos veces cuenta doble); revisar si `solve` acepta pesos por hora o si hay que repetir los sistemas de esas horas.

## X2: ensamble de vientos

- **Cómo funciona.** Cada miembro `m` perturba, con su propia semilla, la dirección del viento de cada hora (ruido normal con desviación `sigma_dir_deg`; el error medido de la dirección es de 28–32°), la velocidad (factor log-normal, `sigma_speed`) y la capa límite (factor log-normal, `sigma_pbl`). Con esas entradas arma su propia matriz de transporte y ajusta la inversión. Predicción y emisión: promedio de los miembros.
- **Dónde se perturba.** El viento horario está en `Inputs.hours` (cada `HourData` lleva el viento y la capa límite de su hora) y, para los puffs, en `Inputs.wind` (la historia horaria que usa `HistoryTransport`). Hay que perturbar los dos de forma coherente (la misma perturbación para la misma hora). Ver `ml/src/nox_ml/data/inputs.py` y `ml/src/nox_ml/inversion/linear.py` (`HourData`, `History`, `hour_jacobians`).
- **Caché.** Cada miembro es un transporte distinto: su `transport_key()` debe incluir la semilla y las sigmas del miembro, o la caché devolverá la matriz del viento sin perturbar. Ojo: `Inputs` guarda solo `MAX_CACHED_TRANSPORTS = 4` transportes; con más miembros, la caché se vacía en cada pliegue de la validación y todo se recalcula. Resolverlo antes de correr (por ejemplo, armar las matrices de los miembros una vez por corrida y conservarlas en el ensamble).
- **Por qué E2 y no E5b.** Rearmar las matrices de E2 tarda ~5 min por miembro; las de E5b, ~11 min. Con 8 miembros, E2 cuesta ~40 min solo en matrices. Si sobra tiempo, la misma clase sirve para E5b.
- **Qué esperar.** Promediar sobre la incertidumbre del viento suaviza las plumas mal orientadas: puede bajar el error horario y acercar el domingo/hábil al tráfico. También puede ensanchar el placebo. Las dos cosas se reportan.
- **Hiperparámetros.** `n_members` (5–10), `sigma_dir_deg` (15–30), `sigma_speed` (0.1–0.3), `sigma_pbl` (0.1–0.3), `seed`. Ajuste: grilla chica de `sigma_dir_deg` × `sigma_pbl` con pocos miembros (cada prueba rearma matrices); fijar `n_members` al final.

## Pruebas

- La prueba de contrato los incluye al registrarlos (fuga de información, semilla, emisión sintética, placebo). Con los datos sintéticos deben correr en menos de 30 s: usar pocos miembros en la configuración de prueba si hace falta.
- X1: con `n_bags = 1` y sin remuestreo, coincide con el modelo base; los pesos de un día repetido cuentan doble; misma semilla, mismo resultado.
- X2: con sigmas en 0, cada miembro coincide con el modelo base; dos miembros con semillas distintas dan matrices distintas y claves de caché distintas; la perturbación de una hora es la misma en `hours` y en `wind`.

## Corridas

| Corrida | Configuración | Tiempo estimado | Dónde |
|---|---|---|---|
| X1 | `configs/experiments/bagged_inversion.yaml` | ~1 h (las matrices de E5b una vez, más los solves de los bags en cada pliegue) | Local |
| X1 ajuste | `bagged_inversion.search.yaml` (n_bags) | ~1 h | Local |
| X2 | `configs/experiments/wind_ensemble.yaml` | 1–2 h | Local |
| X2 ajuste | `wind_ensemble.search.yaml` (sigmas) | 2–3 h | Local, de noche |

Entregar según [avance5_arranque.md](avance5_arranque.md): fila de `compare`, tiempos, y la carpeta en `results/runs/`.

## Cuándo está listo

1. X1 y X2 registrados, con su configuración y, si se ajustaron, su búsqueda.
2. `bin/check` pasa.
3. Corridas en nov–dic 2023 con su fila de `compare` en el pull request y la comparación con su base (E5b para X1, E2 para X2): error, domingo/hábil, placebo y tiempo.
4. Una nota de 3–5 líneas en el pull request: qué se esperaba, qué salió y por qué.

## Fecha

Implementación el 27–28 de octubre; corridas a más tardar el 29.
