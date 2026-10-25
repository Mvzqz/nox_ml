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



## Descartadas

- Exigir cobertura mínima por paquete (`fail_under`): no se aplica por ahora (decisión del usuario, 2026-10-24).

## Preparación del avance 5

- [x] **Artefactos de corrida para ensambles.** `nox-ml run` guarda `oof.parquet` (predicciones fuera de muestra de la estación oculta) y `emissions.parquet` (`docs/models.md`, sección 4) (2026-10-25, PR #12).
- [x] **Periodo de prueba reservado.** Feb–may 2024 solo se usa para evaluar el modelo final; `nox-ml tune` rechaza configuraciones que lo incluyan (2026-10-25, PR #12).
- [ ] **Eventos con respuesta conocida.** Migrar desde `research-archive` los datos y el cálculo del confinamiento 2020 frente a 2019 (`val2020_data.py`, `val2020_ratio.py`) y de las contingencias 2024 con CO (`contingencias_2024.py`, `contingencias_co.py`).
