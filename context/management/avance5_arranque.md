# Arranque para el avance 5 (entrega: 1 de noviembre de 2026)

Guías por frente: [A](avance5_frente_a.md), [B](avance5_frente_b.md), [C](avance5_frente_c.md). Plan general y rúbrica: [plan_avances.md](plan_avances.md), sección "Avance 5".

## Qué se entrega

`notebooks/Avance5.39.ipynb`, ejecutado de principio a fin y guardado con sus salidas, más su HTML en `docs/entregables/html/`. Contiene:

1. Al menos 4 ensambles, homogéneos y heterogéneos (60 puntos).
2. Tabla con el mejor modelo individual del avance 4 y los ensambles, ordenada por `loo_rmse_ppb`, con al menos dos métricas más y tiempos de entrenamiento, y la elección argumentada del modelo final (20 puntos).
3. Al menos 4 gráficos del modelo final con su interpretación (20 puntos).
4. La evaluación en datos no vistos (feb–may 2024 y contingencias 2024) y la declaración de IA al final.

## Pasos y fechas

| Paso | Qué | Quién | Fecha |
|---|---|---|---|
| 1 | Contrato de ensambles y modo de evaluación en el periodo de prueba | Coordinación | 26 oct |
| 2 | Cada frente implementa sus ensambles y hace sus corridas en nov–dic 2023 | A, B, C | 27–29 oct |
| 3 | Tabla comparativa con todos los modelos y ensambles | Coordinación | 29 oct |
| 4 | Elección del modelo final; corrida única en feb–may 2024 y contingencias | Coordinación y C | 29–30 oct |
| 5 | Notebook, gráficos, declaración de IA y HTML | Coordinación | 30–31 oct |

El contrato ya está en el pull request #49; el paso 2 empieza sobre `main` cuando se fusione.

## El contrato de ensambles (paso 1)

Está en `docs/models.md`, sección 10, y en el ADR 0007. **Si esta guía y `docs/models.md` no coinciden, manda `docs/models.md`.** En resumen:

- `convex_ensemble` (`ml/src/nox_ml/models/ensemble.py`) es el ensamble registrado: un `Model` que envuelve a sus modelos base, declarados en `params.members` como `{name, params}`, con pesos convexos en `params.weights` (`null`: promedio simple). Pasa la prueba de contrato como cualquier modelo. Los ensambles con lógica propia heredan de `ConvexEnsemble`.
- Emisión: absoluta (t/año) solo si todos los miembros son absolutos y comparten `transport_key()`; si no, relativa (índice por tipo de día sobre el hábil, sin zonas).
- `nox_ml.validation.stacking`: aprende pesos a partir de los `oof.parquet` de las corridas sin reajustar los modelos base. `nested_oof` da el error honesto (los pesos con que se evalúa la estación `s` se aprenden sin `s`) y `fit_weights` da los pesos con todas las estaciones, que se congelan en la configuración. Reglas: `stack` (X5) y `likelihood` (X6).
- `uv run nox-ml evaluate runs/<nombre>/config.yaml --period test` corre una configuración congelada en el periodo de prueba y escribe `runs/<nombre>.test/`. `nox-ml compare` muestra la columna `period`. `tune` sigue rechazando ese periodo.
- Un ensamble cuesta la suma de sus miembros: la validación con estación oculta y el placebo reajustan a cada uno.

## Reglas (las mismas del avance 4)

- Preparar la máquina: [arranque.md](arranque.md) (credenciales de DagsHub, `bin/uptodate`, `uv run dvc pull`).
- Una rama por ensamble (`ensembles/<nombre>`). Commits a tu nombre.
- Código, comentarios y documentación de código en inglés; notebooks y `context/` en español.
- Todo ensamble queda registrado en `REGISTRY`, con `configs/experiments/<nombre>.yaml` (nov–dic 2023, `simat_hours: [12, 17]`, el mismo bloque `placebo` que los demás) y, si se ajusta, `<nombre>.search.yaml`.
- `bin/check` pasa antes de abrir el pull request; la prueba de contrato incluye al ensamble sola.
- **No usar feb–may 2024** para implementar, ajustar ni elegir. Solo la corrida única del paso 4 lo toca, con `nox-ml evaluate`.
- El código de los notebooks solo llama a `nox_ml`.

## Cómo se entrega una corrida

1. `uv run nox-ml run configs/experiments/<nombre>.yaml` en nov–dic 2023 → `runs/<nombre>/` (`metrics.json`, `oof.parquet`, `emissions.parquet`, `config.yaml`, `code_version.json`). Corre desde un árbol limpio para que `code_version.json` no quede marcado como modificado.
2. `uv run nox-ml compare results/runs/*/ runs/<nombre>/` y pega la fila del ensamble en el pull request, junto con el tiempo total de la corrida.
3. Si hubo ajuste: `uv run nox-ml tune configs/experiments/<nombre>.search.yaml` → `runs/<nombre>/trials.csv`; pega el rango de las pruebas y la mejor.
4. Copia la carpeta a `results/runs/<nombre>/` en el mismo pull request (son unos KB; `results/` sí está versionado).
5. Corridas pesadas (más de ~30 min): en una máquina local, con `systemd-inhibit` o equivalente para que no se suspenda.

## Pruebas de aceptación

`ml/tests/acceptance/test_avance5.py` comprueba que cada parte está completa: el ensamble registrado como modelo, su configuración en nov–dic 2023 con el mismo placebo que los demás, su búsqueda válida y corrida (`trials.csv` con al menos 4 pruebas), y su corrida guardada en `results/runs/<nombre>/` con métricas de emisión, tiempos, predicciones fuera de muestra (al menos 20 estaciones) y emisiones. No revisan la ciencia; eso lo hacen las pruebas de contrato y la revisión del pull request.

No corren en `bin/check` ni en CI: fallan a propósito hasta que la parte está hecha. Cada frente corre las suyas antes de pedir revisión, y deben pasar todas:

```sh
uv run pytest -m acceptance -k front_a
uv run pytest -m acceptance -k front_b
uv run pytest -m acceptance -k front_c
uv run pytest -m acceptance -k delivery   # la entrega completa (coordinación)
```

Los nombres de las configuraciones (y de sus carpetas en `results/runs/`) son los que esperan las pruebas: `bagged_inversion`, `wind_ensemble`, `stacking`, `bayes_average`, `gb_deweather` y, opcional, `pinn_seeds`. La configuración usa un modelo registrado con ese mismo nombre o `convex_ensemble`. Si hace falta otro nombre, se cambia también en la prueba.

## Cómo se leen los resultados

- El ruido del error con estación oculta es de ~±0.5 ppb: una mejora menor no es una mejora. Un ensamble que no mejora el error pero estrecha el placebo o acerca el domingo/hábil al tráfico (0.65–0.73) sí aporta, y hay que decirlo.
- Elegibilidad: placebo con centro en 1 ± 0.15. Un ensamble que no la cumple no compite.
- Referencias del avance 4 (nov–dic 2023): E5b `pinn_puff` 11.87 ppb, domingo 0.48 (0.36–0.62), placebo 1.01 ± 0.12, 529 s; E2 `inversion_puff` 12.50, 0.52, 0.97 ± 0.16, 323 s; E5a `pinn_plume` 12.49, 0.42, 1.09 ± 0.33, 16 s; E6 `rf_deweather` 14.61, 0.53, 0.97 ± 0.09. Pisos de concentración: IDW 11.57, kriging 10.33.
