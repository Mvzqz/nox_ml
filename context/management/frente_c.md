# Frente C: aprendizaje automático

Antes de empezar: [arranque](arranque.md) (preparar la máquina, credenciales, comprobar el baseline). Contrato de modelos: [`docs/models.md`](../../docs/models.md). Plan general: [plan_avances.md](plan_avances.md).

## Objetivo

Llevar al proyecto los modelos de aprendizaje automático: la red neuronal informada por la física (PINN), que es el foco del proyecto, en sus variantes, y una técnica estándar de calidad del aire basada en árboles (normalización meteorológica).

## Tareas

| # | Modelo | Qué es | Estado |
|---|---|---|---|
| E5a | `pinn_plume` | La PINN aprende la pluma de advección–difusión y se usa como transporte de la inversión | **Hecho y registrado** (error en estación oculta 12.49, híbrido 10.66) |
| E5b | `pinn_puff` | El núcleo de la PINN aplicado a cada tramo de cada puff (transporte hora por hora) | **Por hacer** |
| E5c | `pinn_joint` | PINN entrenada con la física y con las estaciones a la vez | **Por hacer** (opcional si falta tiempo) |
| E6 | `rf_deweather` | Normalización meteorológica con bosque aleatorio: aprende concentración ~ meteorología + calendario; la emisión es lo que queda al fijar la meteorología | **Por hacer** |

## Código relevante

- `ml/src/nox_ml/models/pinn/`:
  - `model.py`: `PinnPlume`, que hereda de `InversionPlume` y solo cambia el transporte. **E5b debe seguir el mismo patrón.**
  - `kernel.py` (red, pérdidas, entrenamiento, validación), `equation.py` (ecuación y solución exacta), `transport.py` (`KernelTable`, `jacobian_hour_pinn`), `cache.py` (núcleos entrenados guardados por hash), `params.py`.
  - `bundled/`: el núcleo por defecto ya entrenado; las pruebas no entrenan.
- `ml/src/nox_ml/inversion/jacobian.py`: `jacobian_hour_puff` y `_block` muestran cómo se arma la tabla con puffs; E5b sustituye la pluma gaussiana de cada tramo por el núcleo de la PINN.
- `ml/src/nox_ml/physics/puff.py`: trayectorias y supervivencia de los puffs.
- `ml/src/nox_ml/inversion/normalized.py`: cómo se reportan cambios relativos (domingo/hábil con bootstrap), que E6 debe imitar.
- `scikit-learn` ya está en las dependencias (`RandomForestRegressor`).

## Cuándo está listo

1. E5b, E6 (y E5c si da tiempo) registrados en `REGISTRY`, con su `configs/experiments/<nombre>.yaml`.
2. `bin/check` pasa; la prueba de contrato los incluye sola.
3. `nox-ml run` de cada uno en nov–dic 2023 y su fila de `nox-ml compare runs/*` en el pull request.
4. Referencias: E5b debería acercarse a E2 (puffs con física exacta) o mejorarlo; E6 debería dar domingo/hábil en el rango del tráfico (0.65–0.73) y pasar el placebo.

## Cómo funcionan las pruebas relevantes

- **Prueba de contrato** (`ml/tests/models/test_contract.py`): para cada modelo registrado revisa columnas, reproducibilidad, fuga de información, YAML de parámetros, recuperación de la emisión sintética y placebo centrado en 1.
- **Pruebas de la PINN** (`ml/tests/models/test_pinn_*.py`): la solución exacta conserva masa, invariancia por rotación, monotonía con la vida química y el viento, caché del núcleo, entrenamiento determinista. Usan la red de referencia (`pinn_kernel_fixture.py`), así que son rápidas.
- **Prueba lenta** (`ml/tests/test_pinn_run.py`, `-m slow`): entrena desde cero y revisa el error del núcleo y las métricas reales (~9 min). Correrla antes de abrir el pull request si cambias el núcleo.
- **Pruebas propias recomendadas:**
  - E5b: con un solo puff sin edad, la tabla coincide con la de `pinn_plume`; y se acerca a `jacobian_hour_puff` dentro del error del núcleo.
  - E6: con datos sintéticos donde el domingo emite la mitad, el índice relativo da ~0.5; si la meteorología se mezcla con el día, el modelo no debe atribuirle el cambio al día.

## Trampas y riesgos

- **Fuga de información en E5c.** Si la PINN se entrena con las estaciones, cada estación oculta debe quedar fuera del entrenamiento. Reentrenar 24 veces (~18 min cada una) son ~7 h: validar con **4 grupos de estaciones** y decirlo en el notebook. Es la variante a dejar fuera si falta tiempo.
- **E6 es relativo.** Su `EmissionEstimate` es de tipo `relative` (índice por tipo de día y zona). No da toneladas.
- **E6 y la meteorología.** Un bosque aleatorio puede "aprender" el día de la semana a través de la meteorología si están correlacionadas. Las características deben separar bien tiempo y clima: hora y día en forma cíclica, ventilación (viento × capa de mezcla) y su acumulado de horas previas, dirección del viento con seno y coseno, tipo de día. Justificar cada transformación en el pull request (sirve para el reporte).
- **Torch.** Se instala con `uv sync --extra pinn` (ya lo hace `bin/uptodate`). En la nube hay que permitir `download-r2.pytorch.org` y `download.pytorch.org`.
- **Cómputo.** Entrenar un núcleo nuevo: ~3–18 min de CPU según los parámetros (se guarda en caché). El ajuste fino de la PINN cuesta un entrenamiento por prueba: limitarse a 6–8 pruebas.
- **Caché.** E5b debe definir su `transport_key()` con la identidad del núcleo y los parámetros del puff, para no mezclarse con `pinn_plume` ni con E2.
- **No usar feb–may 2024**: es el periodo de prueba del avance 5.
- **Conflictos.** `models/__init__.py` (registro) lo tocan los tres frentes; conservar todas las entradas.

## Tiempo estimado

Trabajo con agentes: E5b ~2–3 h, E5c ~1–2 h, E6 ~1–1.5 h. Cómputo: E5b 20–40 min, E5c ~1.2 h con 4 grupos, E6 minutos. Es el frente con más riesgo: lo mínimo para mañana es E5a (ya hecho) + E6.
