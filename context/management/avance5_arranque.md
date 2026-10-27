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

Nadie empieza el paso 2 sobre `main` sin el contrato fusionado. Mientras tanto se puede leer el código y preparar las pruebas.

## El contrato de ensambles (paso 1)

Lo implementa coordinación; al fusionarse queda descrito en `docs/models.md` (sección de ensambles) y en un ADR nuevo. **Si esta guía y `docs/models.md` no coinciden, manda `docs/models.md`.** Lo que se espera:

- Un ensamble es un `Model` del registro (`role: model`) que envuelve a sus modelos base, declarados en sus parámetros como configuraciones de experimento. Pasa la prueba de contrato como cualquier modelo.
- Debe estimar emisión: una combinación convexa (pesos ≥ 0 que suman 1) de las emisiones de sus bases. Si mezcla modelos con transportes distintos (E5b, E2 y E5a difieren hasta en un factor de 2 en emisión absoluta), se reporta como relativo (cocientes por tipo de día).
- Una utilidad de stacking convexo anidado por estación sobre los `oof.parquet` de las corridas: los pesos con que se evalúa la estación `s` se aprenden sin `s`.
- `nox-ml evaluate <config> --period test`: corre una configuración congelada en el periodo de prueba y guarda en `runs/<name>.test/`. `nox-ml tune` sigue rechazando ese periodo.

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

Los nombres de los ensambles son los que esperan las pruebas: `bagged_inversion`, `wind_ensemble`, `stacking`, `bayes_average`, `gb_deweather` y, opcional, `pinn_seeds`. Si hace falta otro nombre, se cambia también en la prueba.

## Cómo se leen los resultados

- El ruido del error con estación oculta es de ~±0.5 ppb: una mejora menor no es una mejora. Un ensamble que no mejora el error pero estrecha el placebo o acerca el domingo/hábil al tráfico (0.65–0.73) sí aporta, y hay que decirlo.
- Elegibilidad: placebo con centro en 1 ± 0.15. Un ensamble que no la cumple no compite.
- Referencias del avance 4 (nov–dic 2023): E5b `pinn_puff` 11.87 ppb, domingo 0.48 (0.36–0.62), placebo 1.01 ± 0.12, 529 s; E2 `inversion_puff` 12.50, 0.52, 0.97 ± 0.16, 323 s; E5a `pinn_plume` 12.49, 0.42, 1.09 ± 0.33, 16 s; E6 `rf_deweather` 14.61, 0.53, 0.97 ± 0.09. Pisos de concentración: IDW 11.57, kriging 10.33.
