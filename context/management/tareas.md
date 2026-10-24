# Tareas

Tareas abiertas para las siguientes sesiones (nube o local). Al terminar una, se marca con la fecha y el PR.

## Seguimiento de la migración (revisión de los PR #1–#3, 2026-10-24)

- [ ] **Cuartiles de estancamiento.** Migrar la clasificación de días por cuartil de ventilación (`pd.qcut(viento·pbl, 4)`) y el grupo "estancado" del placebo (`estancamiento_evaluar.py:76` y `:100` en `research-archive`) a `nox_ml.validation.stagnation`.
- [ ] **Hora local en un solo lugar.** UTC−6 está definido en 4 sitios (`data/domain.py`, `inversion/normalized.py`, `physics/chemistry.py`, `physics/puff.py`), y `local_day`/`utc_to_local` están duplicados. Unificar en `nox_ml/time.py`.
- [ ] **Desfase de MERRA-2.** `data/pbl.py` (~línea 70) conserva el desfase de una hora de MERRA-2 frente a ERA5 que traía la investigación. Revisar si es correcto y, si no, corregirlo y medir el efecto.
- [x] **Sensores atascados.** Hecho 2026-10-24 (PR #4). `simat.mask_stuck` pone en NaN NO, NO₂ y NOₓ de las 59 horas (TAH 29, MON 14, ACO 9, PED 7) y es el valor por defecto de `run_qc` y `nox-ml qc-simat` (`--no-mask` las conserva). Ninguna cae en nov–dic 2023 ni feb–may 2024: efecto nulo en domingo/hábil y en los placebos. Pendiente: regenerar `simat_nox.parquet` y hacer `dvc push`.
- [ ] **Migrar `jacobian_hour_puff`.** Es la pieza que conecta el transporte con la inversión.

## Descartadas

- Exigir cobertura mínima por paquete (`fail_under`): no se aplica por ahora (decisión del usuario, 2026-10-24).
