# Frente B: estadística

Antes de empezar: [arranque](arranque.md) (preparar la máquina, credenciales, comprobar el baseline). Contrato de modelos: [`docs/models.md`](../../docs/models.md). Plan general: [plan_avances.md](plan_avances.md).

## Objetivo

Resolver la misma pregunta (cuánto emite cada zona) con algoritmos **distintos** a la inversión bayesiana lineal, usando la misma física. Así la comparación del avance 4 tiene variedad real de algoritmos. Además, dejar las **referencias de concentración** (IDW y kriging) que marcan el piso que todo modelo debe empatar o superar.

## Tareas

| # | Nombre | Qué es | Estado |
|---|---|---|---|
| E3 | `regularized_ls` | Mínimos cuadrados regularizados y no negativos (ridge o NNLS) sobre la misma tabla de transporte, sin supuesto bayesiano | **Hecho** (`models/regularized_ls.py`) |
| E4 | `lognormal_map` | Inversión no lineal: emisiones log-normales (siempre positivas), máximo a posteriori con L-BFGS-B; incertidumbre por aproximación de Laplace (inversa de la hessiana) | **Hecho** (`models/lognormal_map.py`) |
| R1 | `idw` | Interpolación por distancia inversa, como referencia (`role: reference`) | **Hecho** (`models/references.py`) |
| R2 | `kriging` | Proceso gaussiano **solo espacial, hora por hora**, como referencia | **Hecho** (`models/references.py`) |
| M1 | Peso de TEMPO y restricción de tráfico | Dos hiperparámetros nuevos del modelo físico base (`PlumeInversionParams`), heredados por E1, E2, E5a y E5b: `tempo_sigma_mult` (multiplica el error de los píxeles; la investigación usó 3, es decir, un tercio de peso) y una restricción opcional del cociente sábado/domingo frente a hábil con el tráfico de Infovial (día completo ponderado por emisión: sábado ~0.87, domingo ~0.65–0.73, con su σ). Valores por defecto = comportamiento actual, para que el baseline no cambie | **Por hacer, prioridad alta** |

## Código relevante

- `ml/src/nox_ml/models/inversion_plume.py`: el ejemplo a copiar del contrato (`fit`, `predict_stations`, `estimate_emissions`).
- `ml/src/nox_ml/inversion/linear.py`:
  - `hour_jacobians`, `hour_systems`: arman, por hora, la tabla de transporte y el sistema con el fondo regional ya eliminado. **E3 y E4 deben partir de aquí**, no de cero.
  - `solve`, `prior_state`, `road_sources`: cómo se arman los parámetros (zona × tipo de día + fuentes puntuales) y el supuesto inicial.
- `ml/src/nox_ml/validation/loo.py`: `idw_and_hybrid` ya calcula IDW e híbrido; R1 lo envuelve como modelo de referencia.
- `ml/src/nox_ml/data/inputs.py`: `Inputs` y la caché `Inputs.jacobians(...)`; las coordenadas de estaciones están ahí.
- `scikit-learn` ya está en las dependencias (`GaussianProcessRegressor` para kriging).

## Por qué M1 es prioritaria

Todos los modelos físicos dan una baja dominical exagerada (domingo/hábil 0.42–0.47 frente a 0.65–0.73 del tráfico). El diagnóstico del baseline mostró que el satélite es quien empuja ese número hacia abajo (sin TEMPO sube a 0.80). En la investigación, darle un tercio de peso a TEMPO y agregar la restricción de tráfico llevó el domingo a 0.62–0.65 sin empeorar el error en estación oculta. Sin estos dos parámetros, el ajuste fino del avance 4 no puede explorar esa mejora.

- Código: `models/inversion_plume.py` (`PlumeInversionParams`), `inversion/linear.py` (dónde entra el error de cada píxel y dónde se agregaría la restricción como pseudo-observación), `data/traffic.py` (perfil de Infovial).
- Referencia en la investigación (`research-archive`): `scripts/real_check_linear.py` (`--tempo-sigma-mult`), `scripts/sunday_fix.py`, `reports/peso_tempo.md`, `reports/sesgo_domingos.md`.
- Pruebas: con los valores por defecto, el baseline da exactamente los mismos números (13.6 / 11.6 / 11.7, domingo 0.42); con la restricción muy fuerte, el cociente estimado coincide con el impuesto; con `tempo_sigma_mult` muy grande, el resultado se acerca al de "sin TEMPO" del diagnóstico.

## Cuándo está listo

1. E3, E4, R1 y R2 registrados en `REGISTRY` (R1 y R2 con `role = "reference"`), cada uno con su `configs/experiments/<nombre>.yaml`.
2. `bin/check` pasa; la prueba de contrato los incluye sola.
3. `nox-ml run` de cada uno en nov–dic 2023 y su fila de `nox-ml compare runs/*` en el pull request.
4. Referencia: IDW debe dar ~11.6 ppb en estación oculta (ya medido). E3 y E4 deberían quedar cerca del baseline (13.6) o mejor; si quedan muy lejos, revisar escalas y regularización.

## Cómo funcionan las pruebas relevantes

- **Prueba de contrato** (`ml/tests/models/test_contract.py`, datos en `ml/tests/models/synthetic.py`): para cada modelo registrado revisa columnas, reproducibilidad con semilla, fuga de información (cambiar la estación excluida no cambia el modelo), YAML de parámetros y, si es `model`, que recupere la emisión sintética y que el placebo quede centrado en 1. Las referencias se prueban sin la parte de emisión.
- **Pruebas propias recomendadas:**
  - E3: con datos sin ruido recupera exactamente la emisión; con α = 0 coincide con mínimos cuadrados ordinarios; nunca da emisiones negativas en NNLS.
  - E4: el gradiente analítico coincide con diferencias finitas; con supuesto inicial muy fuerte devuelve el supuesto; emisiones siempre > 0.
  - Kriging: en un campo constante predice la constante; en una estación conocida coincide con el valor (sin ruido).

## Trampas y riesgos

- **Fondo regional.** Cada hora tiene un fondo desconocido que `hour_systems` elimina analíticamente. Si E3 o E4 resuelven el sistema "a mano" sin ese paso, el fondo se les mete en las emisiones y los resultados no son comparables.
- **Escalas.** Los parámetros mezclan factores por zona (~1) con emisiones de fuentes puntuales (cientos de t/año). E3 y E4 necesitan normalizar (trabajar en factores relativos al supuesto inicial) o la regularización castiga distinto a cada uno.
- **Incertidumbre.** El contrato pide desviación estándar positiva. E3 no la tiene de forma natural: usar bootstrap por bloques de días (`bootstrap_n` en los parámetros) o la aproximación lineal; documentar cuál.
- **Kriging espacio-tiempo es caro.** Un proceso gaussiano con ~7,500 filas, 24 veces, es lento y pesado en memoria. Hora por hora con ~24 puntos es rápido.
- **Elegibilidad.** Un modelo que inventa cambios (placebo fuera de 1 ± 0.15) no es elegible aunque tenga buen error.
- **No usar feb–may 2024**: es el periodo de prueba del avance 5.
- **Conflictos.** `models/__init__.py` (registro) lo tocan los tres frentes; conservar todas las entradas al resolver.

## Tiempo estimado

Trabajo con agentes: E3 ~45 min, E4 ~1–1.5 h, R1 ~15 min, R2 ~45 min. Cómputo: minutos (todo trabaja sobre tablas en caché).
