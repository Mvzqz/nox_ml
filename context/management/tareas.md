# Tareas

Tareas abiertas para las siguientes sesiones (nube o local). Al terminar una, se marca con la fecha y el PR.

## Seguimiento de la migración (revisión de los PR #1–#3, 2026-10-24)

- [ ] **Cuartiles de estancamiento.** Migrar la clasificación de días por cuartil de ventilación (`pd.qcut(viento·pbl, 4)`) y el grupo "estancado" del placebo (`estancamiento_evaluar.py:76` y `:100` en `research-archive`) a `nox_ml.validation.stagnation`.
- [x] **Hora local en un solo lugar.** UTC−6 estaba definido en 4 sitios (`data/domain.py`, `inversion/normalized.py`, `physics/chemistry.py`, `physics/puff.py`), y `local_day`/`utc_to_local` estaban duplicados. Unificado en `nox_ml/time.py` (2026-10-24, PR #5).
- [ ] **Desfase de MERRA-2.** `data/pbl.py` (~línea 70) conserva el desfase de una hora de MERRA-2 frente a ERA5 que traía la investigación. Revisar si es correcto y, si no, corregirlo y medir el efecto.
- [x] **Sensores atascados.** `simat.mask_stuck` pone en NaN NO, NO₂ y NOₓ de las 59 horas atascadas (TAH 29, MON 14, ACO 9, PED 7) y es el comportamiento por defecto de `run_qc` y `nox-ml qc-simat` (`--no-mask` las conserva). Ninguna cae en nov–dic 2023 ni feb–may 2024: efecto nulo en domingo/hábil y placebos (2026-10-24, PR #4).
- [x] **Migrar `jacobian_hour_puff`.** Es la pieza que conecta el transporte con la inversión. Ahora en `nox_ml.inversion.jacobian`, con la configuración estándar; reproduce la salida de la investigación (`puffs_cdmx.jacobian_puff_mx`) con diferencia relativa máxima de 3e-15 en datos reales (2026-10-24, PR #5).
- [ ] **Ensamblar el sistema de la inversión.** Falta lo que rodea al Jacobiano en `real_check_linear.build` y `load_inputs`: celdas viales, estaciones y píxeles, σ de TEMPO ×3, `EST_FACTOR`, ecuaciones normales y restricción de cociente.
- [ ] **Perfil Infovial desde los datos crudos.** `data/traffic.py` solo lee `perfil_infovial.json`; falta migrar su derivación desde `infovial_201701_clasificacion.csv` (`puffs_cdmx.infovial_profile`).



## Descartadas

- Exigir cobertura mínima por paquete (`fail_under`): no se aplica por ahora (decisión del usuario, 2026-10-24).
