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
- [x] **Diagnósticos del BASELINE (Avance 3).** `nox_ml.validation.diagnostics` y `nox-ml diagnose <config>`: reducción de varianza posterior y grados de libertad para la señal por fuente (estaciones, TEMPO, ambas), ablación (sin TEMPO, 24/15/9 estaciones con 5 semillas, viento +15° y +30°) y curvas de aprendizaje (días y estaciones; RMSE en la muestra frente a LOO). Escribe CSV en `runs/<nombre>/diagnostics/` (2026-10-25, PR #15).
- [x] **Notebook del Avance 3 (baseline).** `notebooks/Avance3.39.ipynb`: problema, algoritmo, corrida del baseline, métricas, características (información y ablación), sub/sobreajuste y conclusiones. Solo llama funciones de `nox_ml`; las tablas y gráficas están en `nox_ml.validation.report_baseline` (2026-10-25, PR #26).
- [ ] **Mejora candidata: horas TEMPO sin estaciones.** Incluir las horas TEMPO sin estaciones (17 h locales, 13 % de los píxeles de feb–may 2024); comparar contra la base con el arnés de evaluación. No cambia la base hasta que la comparación lo justifique.
- [ ] **Perfil Infovial desde los datos crudos.** `data/traffic.py` solo lee `perfil_infovial.json`; falta migrar su derivación desde `infovial_201701_clasificacion.csv` (`puffs_cdmx.infovial_profile`).



## Modelos alternativos (avance 4)

- [x] **PINN como modelo (E5, `pinn_plume`).** `nox_ml.models.pinn`: la red aprende el núcleo de advección–difusión 2D con física solamente (Adam + L-BFGS, CPU, ~3 min) y es la matriz fuente–receptor de la misma inversión bayesiana; se registra como `pinn_plume` (subclase de `InversionPlume` que cambia solo `transport()`), con `PinnParams` como parámetros. La red de los parámetros por defecto viene incluida. Error de la red contra la solución exacta: mediana 1.7–4.7 % (la investigación: 3.5–6.6 %). Nov–dic 2023: domingo ÷ hábil 0.42 (0.33–0.54) frente a 0.43 de la investigación, error con estación retenida 12.5 ppb, r con TEMPO 0.78, placebo del modelo 1.09 ± 0.33 (elegible) (2026-10-25, PR #13). Ver ADR 0004.
- [x] **PINN con puffs (E5b, `pinn_puff`).** El núcleo de la PINN aplicado a la pluma de la última hora y a los puffs de hasta 24 h (`nox_ml.models.pinn.puff`), con `transport_key()` propia y `HistoryTransport` para pasar el viento horario del periodo. Implementado y probado (2026-10-25, PR #19); **falta correr `nox-ml run configs/experiments/pinn_puff.yaml` en local** (~15–25 min) y pegar su fila de `compare`. Ver ADR 0005.
- [x] **Frente B: E3 `regularized_ls`, E4 `lognormal_map`, R1 `idw`, R2 `kriging`.** NNLS con ridge y MAP log-normal con Laplace sobre los sistemas por hora del baseline; IDW y kriging espacial hora por hora como referencias (`role: reference`). En nov–dic 2023: E3 13.57 ppb, E4 13.59, IDW 11.57, kriging 10.33 (2026-10-26, PR #40).
- [x] **Difusividad `kappa` de la PINN como parámetro.** `PinnParams.kappa` (m, por defecto 1500, el valor de la investigación) entra en la ecuación como `eps = kappa / L` y en la clave de entrenamiento y de `transport_key()`; cada valor entrena (y guarda en caché) su propia red, porque el núcleo no se puede reescalar de forma exacta (ver ADR 0004). Con el valor por defecto nada cambia (misma red incluida). Falta la rejilla local `kappa` ∈ {500, 1000, 1500, 3000} con `pinn_puff` (comandos en el PR) (2026-10-25, PR #25).
- [x] **Notebook del avance 4, partes del frente C.** E5a, E5b y E6, ajuste de `pinn_puff` (búsquedas de transporte y de red), `kappa`, ajuste no anidado y E5c fuera, en `notebooks/Avance4.39.ipynb`. **Faltan** los números de las corridas finales y la rejilla `runs/pinn_puff_k*` (2026-10-25, PR 27).
- [x] **Notebook del avance 4 terminado.** `notebooks/Avance4.39.ipynb` lee solo `results/runs/`: tabla comparativa (8 modelos y 2 referencias), los dos mejores (E5b y E2), ajuste fino, modelo final E5b y limitaciones; la declaración de IA queda como marcador para el equipo. La carpeta `deliverables/` pasó a `notebooks/` y los HTML están en `docs/entregables/html/` (2026-10-26, PR #42).
- [ ] **Ajustar `pinn_plume` con `nox-ml tune`.** Falta la búsqueda sobre `PinnParams` (capas, ancho, peso de la física, τ). La investigación ya mostró que el nivel absoluto depende de la física (+50 % de emisión vial frente a la pluma) y que los cocientes no.
- [ ] **Estimar parámetros físicos con la PINN (κ, τ, factor de capa límite).** El entrenamiento conjunto de la investigación no mejoró el ajuste con la física fija; su caso de uso es estimar esos parámetros, no las emisiones. No se migró.

## Descartadas

- Exigir cobertura mínima por paquete (`fail_under`): no se aplica por ahora (decisión del usuario, 2026-10-24).

## Preparación del avance 5

- [x] **Artefactos de corrida para ensambles.** `nox-ml run` guarda `oof.parquet` (predicciones fuera de muestra de la estación oculta) y `emissions.parquet` (`docs/models.md`, sección 4) (2026-10-25, PR #12).
- [x] **Periodo de prueba reservado.** Feb–may 2024 solo se usa para evaluar el modelo final; `nox-ml tune` rechaza configuraciones que lo incluyan (2026-10-25, PR #12).
- [ ] **Eventos con respuesta conocida.** Migrar desde `research-archive` los datos y el cálculo del confinamiento 2020 frente a 2019 (`val2020_data.py`, `val2020_ratio.py`) y de las contingencias 2024 con CO (`contingencias_2024.py`, `contingencias_co.py`).

- [x] **Cuadernos de experimentos.** `notebooks/experimentos/` (01 transporte, 02 emisión frente a clima, 03 ajuste de `pinn_puff`, 04 ablación, 05 viento y objetivo), con las funciones en `nox_ml.validation.report_experiments`. Ejecutados con los datos reales; el 03 tolera las corridas que solo existen en la máquina del dueño (2026-10-25, PR #31). **Falta** correr en local `pinn_puff`, sus búsquedas y la rejilla de `kappa` para que el 03 muestre resultados.

## Después del avance 5 (1 de noviembre)

- [x] **Notebook "Exploración y preparación de datos".** Entregado como los dos cuadernos del curso: `notebooks/Avance1.39.ipynb` (estructura y tipos, estadísticos, faltantes y sus patrones, atípicos, univariadas, bivariado y multivariado, tendencias y decisiones de preprocesamiento: viento 2024 en mph, sensores atascados, capa límite con MERRA-2, filtros de TEMPO) y `notebooks/Avance2.39.ipynb` (características con justificación de dominio, transformaciones, selección y extracción, información por tipo de observación y conclusiones CRISP-ML(Q)). Solo llaman a `nox_ml.validation.report_eda`, con pruebas; ninguna decisión de modelado sale de feb–may 2024, que aparece solo en revisiones de calidad (2026-10-25, PR #29).
- [ ] **Ablación de `doy_*` y `ventilation_6h` en E6.** En nov–dic 2023 `doy_sin` y `doy_cos` tienen correlación 1.00 (son un contador de días, con información mutua alta y correlación baja con el NOₓ) y en feb–may 2024 quedan fuera del rango de ajuste; `ventilation_3h` y `ventilation_6h` correlacionan 0.985. Correr E6 sin ellas con la validación con estación oculta antes de decidir (Avance 2, 5.1 y 5.4).
- [ ] **Proxy vial de OSM como característica de sitio.** Spearman de 0.71 a 3 km con el nivel de 24 estaciones (Avance 2, 2.5); falta probar si baja el error con estación oculta de E6.
- [ ] **Sensibilidad del periodo de prueba a la capa límite.** La capa límite de 2024 es MERRA-2 corregido y su corrección no mejora el error mediano fuera de muestra (376 m frente a 338 m sin corregir; Avance 1, 4.4). Junto con la tarea del desfase de MERRA-2, medir cuánto cambian los resultados de feb–may 2024 con otra capa límite (por ejemplo los topes de 1000 y 1500 m de la investigación).
- [ ] **Corrección de mph por año de la etiqueta.** `simat.fix_wind_speed` decide por el año de `local`: la hora 24 del 31 de diciembre de 2024 (etiqueta 2025-01-01 00:00, 19 filas) queda sin corregir. Fuera de los periodos de estudio; corregir por archivo de origen.
- [x] **Características de E6 justificadas.** Se hacen en la sesión de E6 (hora y día cíclicos, ventilación y su acumulado, dirección del viento con seno y coseno, tipo de día), con la justificación de cada transformación y codificación (2026-10-25, PR #20).

## Ventajas del proyecto

- [ ] Estudiar las ventajas posibles y comparar con modelos químicos completos (GEOS-CF, CAMS, AQFS-Mex): ver `plan_ventajas.md`.
