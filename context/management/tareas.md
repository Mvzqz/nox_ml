# Tareas

Tareas abiertas para las siguientes sesiones (nube o local). Al terminar una, se marca con la fecha y el PR.

## Seguimiento de la migración (revisión de los PR #1–#3, 2026-10-24)

- [ ] **Cuartiles de estancamiento.** Migrar la clasificación de días por cuartil de ventilación (`pd.qcut(viento·pbl, 4)`) y el grupo "estancado" del placebo (`estancamiento_evaluar.py:76` y `:100` en `research-archive`) a `nox_ml.validation.stagnation`.
- [x] **Hora local en un solo lugar.** UTC−6 estaba definido en 4 sitios (`data/domain.py`, `inversion/normalized.py`, `physics/chemistry.py`, `physics/puff.py`), y `local_day`/`utc_to_local` estaban duplicados. Unificado en `nox_ml/time.py` (2026-10-24, PR #5).
- [ ] **Desfase de MERRA-2.** `data/pbl.py` (~línea 70) conserva el desfase de una hora de MERRA-2 frente a ERA5 que traía la investigación. Revisar si es correcto y, si no, corregirlo y medir el efecto.
- [x] **Sensores atascados.** `simat.mask_stuck` pone en NaN NO, NO₂ y NOₓ de las 59 horas atascadas (TAH 29, MON 14, ACO 9, PED 7) y es el comportamiento por defecto de `run_qc` y `nox-ml qc-simat` (`--no-mask` las conserva). Ninguna cae en nov–dic 2023 ni feb–may 2024: efecto nulo en domingo/hábil y placebos (2026-10-24, PR #4).
- [x] **Migrar `jacobian_hour_puff`.** Es la pieza que conecta el transporte con la inversión. Ahora en `nox_ml.inversion.jacobian`, con la configuración estándar; reproduce la salida de la investigación (`puffs_cdmx.jacobian_puff_mx`) con diferencia relativa máxima de 3e-15 en datos reales (2026-10-24, PR #5).
- [x] **Inversión base (pluma estacionaria).** `jacobian_hour_plume` y `nox_ml.inversion.linear`: 4 fuentes puntuales, α por región × tipo de día, fondo horario marginalizado con Sherman–Morrison, TEMPO ×1, σθ 15°, `U_MIN` 1. Reproducen `jacobian_hour` y `real_check_linear.build`/`solve` con diferencia relativa máxima < 1e-9 en un fixture pequeño (2026-10-24, PR #7).
- [x] **Entradas de la inversión base y arnés de evaluación.** `nox_ml.data.inputs` arma los `HourData` (viento medio del dominio, capa límite, cociente NO₂/NOₓ, píxeles TEMPO; solo horas con filas de estación y viento) y `nox-ml run configs/experiments/baseline.yaml` corre la inversión y escribe `runs/baseline/` (config, `metrics.json`, hash del código). Reproduce la fila «Dominio, sin industria» 15° de `base_sigma30.md` en nov–dic 2023: r 0.77/0.74, LOO 13.6/11.6/11.7, domingo 0.42 (0.35–0.54) (2026-10-24, PR #10). **Sigue sin migrar:** `EST_FACTOR`, superobservaciones y la restricción de cociente.
- [ ] **Mejora candidata: horas TEMPO sin estaciones.** Incluir las horas TEMPO sin estaciones (17 h locales, 13 % de los píxeles de feb–may 2024); comparar contra la base con el arnés de evaluación. No cambia la base hasta que la comparación lo justifique.
- [ ] **Perfil Infovial desde los datos crudos.** `data/traffic.py` solo lee `perfil_infovial.json`; falta migrar su derivación desde `infovial_201701_clasificacion.csv` (`puffs_cdmx.infovial_profile`).



## Modelos alternativos (avance 4)

- [x] **PINN como modelo (E5, `pinn_plume`).** `nox_ml.models.pinn`: la red aprende el núcleo de advección–difusión 2D con física solamente (Adam + L-BFGS, CPU, ~3 min) y es la matriz fuente–receptor de la misma inversión bayesiana; se registra como `pinn_plume` (subclase de `InversionPlume` que cambia solo `transport()`), con `PinnParams` como parámetros. La red de los parámetros por defecto viene incluida. Error de la red contra la solución exacta: mediana 1.7–4.7 % (la investigación: 3.5–6.6 %). Nov–dic 2023: domingo ÷ hábil 0.42 (0.33–0.54) frente a 0.43 de la investigación, error con estación retenida 12.5 ppb, r con TEMPO 0.78, placebo del modelo 1.09 ± 0.33 (elegible) (2026-10-25, PR #13). Ver ADR 0004.
- [ ] **Ajustar `pinn_plume` con `nox-ml tune`.** Falta la búsqueda sobre `PinnParams` (capas, ancho, peso de la física, τ). La investigación ya mostró que el nivel absoluto depende de la física (+50 % de emisión vial frente a la pluma) y que los cocientes no.
- [ ] **Estimar parámetros físicos con la PINN (κ, τ, factor de capa límite).** El entrenamiento conjunto de la investigación no mejoró el ajuste con la física fija; su caso de uso es estimar esos parámetros, no las emisiones. No se migró.

## Descartadas

- Exigir cobertura mínima por paquete (`fail_under`): no se aplica por ahora (decisión del usuario, 2026-10-24).

## Preparación del avance 5

- [x] **Artefactos de corrida para ensambles.** `nox-ml run` guarda `oof.parquet` (predicciones fuera de muestra de la estación oculta) y `emissions.parquet` (`docs/models.md`, sección 4) (2026-10-25, PR #12).
- [x] **Periodo de prueba reservado.** Feb–may 2024 solo se usa para evaluar el modelo final; `nox-ml tune` rechaza configuraciones que lo incluyan (2026-10-25, PR #12).
- [ ] **Eventos con respuesta conocida.** Migrar desde `research-archive` los datos y el cálculo del confinamiento 2020 frente a 2019 (`val2020_data.py`, `val2020_ratio.py`) y de las contingencias 2024 con CO (`contingencias_2024.py`, `contingencias_co.py`).

## Después del avance 5 (1 de noviembre)

- [ ] **Notebook "Exploración y preparación de datos".** Uno solo, para el reporte final, reutilizando `nox_ml.data` y los hallazgos de la investigación: estructura y faltantes, viento 2024 en mph, sensores atascados, huecos de capa límite, control de calidad de TEMPO, ciclos horarios y semanales, relación con la ventilación. Puede incluir feb–may 2024 para revisar calidad, pero ninguna decisión de modelado sale de ese periodo (es el de prueba).
- [x] **Características de E6 justificadas.** Se hacen en la sesión de E6 (hora y día cíclicos, ventilación y su acumulado, dirección del viento con seno y coseno, tipo de día), con la justificación de cada transformación y codificación (2026-10-25, PR #20).
