# Tareas

Tareas abiertas. Al terminar una, se marca con la fecha y el PR.

## Seguimiento de la migración (revisión de los PR #1–#3, 2026-10-24)

- [x] **Cuartiles de estancamiento.** `nox_ml.validation.stagnation`: `ventilation_quartile` (`pd.qcut(viento·pbl, 4)`, 0 = más estancado), `index_by_quartile`, `stagnant_index` y `poorly_ventilated_mask`, el grupo «días poco ventilados» del placebo (`pool_mask` de `placebo.placebo`; umbral = cuantil 25 de la estancación modelada de los días de contingencia). Con los datos de la investigación reproducen los cuartiles (0.856, 0.956, 0.996, 1.205) y el cuartil estancado (0.856, IC 0.800–0.913, 22 días; 0.887 en días hábiles) (2026-10-27, PR #52).
- [x] **Hora local en un solo lugar.** UTC−6 estaba definido en 4 sitios (`data/domain.py`, `inversion/normalized.py`, `physics/chemistry.py`, `physics/puff.py`), y `local_day`/`utc_to_local` estaban duplicados. Unificado en `nox_ml/time.py` (2026-10-24, PR #5).
- [x] **Desfase de MERRA-2.** Era incorrecto: la correlación cruzada con ERA5 en 2023 tiene su máximo en −1 h. Corregido en `data/pbl.py` y `pbl_2023_2024.parquet` regenerado; efecto despreciable en `baseline` y `pinn_puff` de nov–dic 2023 (ver `context/knowledge/desfase_merra2.md`). Los cuadernos Avance1/Avance2 aún citan las cifras anteriores y hay que volver a ejecutarlos (2026-10-27, PR #52).
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
- [x] **Contingencias 2024.** Migrar desde `research-archive` los datos y el cálculo de las contingencias 2024 con CO (`contingencias_2024.py`, `contingencias_co.py`); caen dentro del periodo de prueba y se usan para evaluar el modelo final en el avance 5. Código y pruebas hechos (`nox_ml.data.contingencies`, `nox_ml.validation.events`, `nox-ml contingencies`); falta la corrida con E7 y con el modelo final (C2) (2026-10-28, PR #57).
- [ ] **Contrato de ensambles y evaluación en el periodo de prueba.** Un ensamble es un `Model` del registro que envuelve a sus modelos base (stacking anidado por estación sobre `oof.parquet`); modo de `nox-ml` para correr una configuración congelada en feb–may 2024.
- [ ] **Ensambles X1–X6** (`plan_avances.md`, avance 5). Mínimo para la rúbrica: X1, X4, X5 y X6.

- [x] **Cuadernos de experimentos.** `notebooks/experimentos/` (01 transporte, 02 emisión frente a clima, 03 ajuste de `pinn_puff`, 04 ablación, 05 viento y objetivo), con las funciones en `nox_ml.validation.report_experiments`. Ejecutados con los datos reales; el 03 tolera las corridas que solo existen en la máquina del dueño (2026-10-25, PR #31). **Falta** correr en local `pinn_puff`, sus búsquedas y la rejilla de `kappa` para que el 03 muestre resultados.

## Después del avance 5 (1 de noviembre)

- [x] **Avance 1 con la capa límite corregida.** Celdas 33 y 77 de `notebooks/Avance1.39.ipynb` con las cifras tras el PR #52 (340 frente a 383 m fuera de muestra, sin desfase) y una nota de corrección posterior a la entrega; HTML exportado de nuevo (2026-10-27, PR #54). El avance 4 no cambia: nov–dic 2023 usa ERA5 en todas las horas de los modelos.

- [x] **Notebook "Exploración y preparación de datos".** Entregado como los dos cuadernos del curso: `notebooks/Avance1.39.ipynb` (estructura y tipos, estadísticos, faltantes y sus patrones, atípicos, univariadas, bivariado y multivariado, tendencias y decisiones de preprocesamiento: viento 2024 en mph, sensores atascados, capa límite con MERRA-2, filtros de TEMPO) y `notebooks/Avance2.39.ipynb` (características con justificación de dominio, transformaciones, selección y extracción, información por tipo de observación y conclusiones CRISP-ML(Q)). Solo llaman a `nox_ml.validation.report_eda`, con pruebas; ninguna decisión de modelado sale de feb–may 2024, que aparece solo en revisiones de calidad (2026-10-25, PR #29).
- [ ] **Ablación de `doy_*` y `ventilation_6h` en E6.** En nov–dic 2023 `doy_sin` y `doy_cos` tienen correlación 1.00 (son un contador de días, con información mutua alta y correlación baja con el NOₓ) y en feb–may 2024 quedan fuera del rango de ajuste; `ventilation_3h` y `ventilation_6h` correlacionan 0.985. Correr E6 sin ellas con la validación con estación oculta antes de decidir (Avance 2, 5.1 y 5.4).
- [ ] **Proxy vial de OSM como característica de sitio.** Spearman de 0.71 a 3 km con el nivel de 24 estaciones (Avance 2, 2.5); falta probar si baja el error con estación oculta de E6.
- [ ] **Sensibilidad del periodo de prueba a la capa límite.** *Parcial (2026-10-27, PR #52): construcción, error de 2023 y sensibilidad ±20 % en nov–dic 2023 en `context/knowledge/capa_limite_2024.md`; falta medir feb–may 2024 con otra capa (topes de 1000 y 1500 m), que solo puede hacerse con la corrida única.* La capa límite de 2024 es MERRA-2 corregido y su corrección no mejora el error mediano fuera de muestra (376 m frente a 338 m sin corregir; Avance 1, 4.4). Junto con la tarea del desfase de MERRA-2, medir cuánto cambian los resultados de feb–may 2024 con otra capa límite (por ejemplo los topes de 1000 y 1500 m de la investigación).
- [ ] **Corrección de mph por año de la etiqueta.** `simat.fix_wind_speed` decide por el año de `local`: la hora 24 del 31 de diciembre de 2024 (etiqueta 2025-01-01 00:00, 19 filas) queda sin corregir. Fuera de los periodos de estudio; corregir por archivo de origen.
- [x] **Características de E6 justificadas.** Se hacen en la sesión de E6 (hora y día cíclicos, ventilación y su acumulado, dirección del viento con seno y coseno, tipo de día), con la justificación de cada transformación y codificación (2026-10-25, PR #20).

- [ ] **Temporadas de ozono 2025 y 2026 (después del avance 5).** Con 2024 solo 9 días hábiles con medidas de contingencia: el límite de detección es de ~±13 % con E7 y ~±27 % con E5b. 2025 tuvo 5 contingencias (26 feb, 18 mar, 1, 23 y 25 abr) y 2026 ya pasó; juntas podrían duplicar o triplicar los días y probar el modelo en años completamente nuevos. Trabajo estimado de 2 a 4 días:
  - Datos: TEMPO feb–may de cada año (revisar la versión del producto), SIMAT 2025–2026 (2026 puede venir sin validar; repetir los controles de mph, sensores atascados y estaciones nuevas o dadas de baja), capa límite ERA5 de Open-Meteo (cubre 2025–2026; confirmar que no hace falta el relleno con MERRA-2) y las fechas de las contingencias verificadas con la CAMe.
  - Código fijo en 2023–2024: `HOLIDAYS` (sin festivos de 2025–2026 se contarían como hábiles), `pbl_2023_2024.parquet` y el rango de `fill-pbl`, los nombres de los archivos de píxeles de TEMPO, `WIND_FIX_YEAR` de la corrección de mph, el módulo de contingencias (un solo archivo de 2024) y la referencia de OH (abril de 2023).
  - Supuestos que envejecen: el perfil horario de Infovial es de 2017; revisar centrales nuevas o retiradas en las fuentes puntuales.
  - Cómputo: cada temporada cuesta como feb–may 2024 (2 a 4 h por modelo).
  - Alternativa menor sin datos nuevos: medir también los 7 días con medidas en fin de semana contra su mismo tipo de día (+7 días en grupos chicos; ~2 h de código).
- [ ] **Confinamiento 2020 frente a 2019 (fuera del avance 5).** Migrar `val2020_data.py` y `val2020_ratio.py` de `research-archive` y correr E7 y E6, que no necesitan TEMPO. El modelo final no aplica: necesita TEMPO (desde 2023) y MERRA-2 (no descargado para 2019–2020), y sin TEMPO la inversión no pasa el placebo de 2019 (`reports/validacion_2020.md`).

## Ventajas del proyecto

- [ ] Estudiar las ventajas posibles y comparar con modelos químicos completos (GEOS-CF, CAMS, AQFS-Mex): ver `plan_ventajas.md`.

## M1 (peso de TEMPO y restricción de tráfico): pendientes después del avance 4

Revisión del PR #30 con datos reales: con `traffic_sd` 0.04 la restricción casi no mueve el domingo (0.42 → 0.43); con una restricción fuerte (0.01–0.002) el domingo sube a 0.54–0.68, pero el placebo deja de ser válido (centro 0.70–0.84) porque los domingos falsos también quedan restringidos.

- [x] **(Necesaria antes de usar la restricción) No aplicar la restricción en los reajustes del placebo.** Hecho: `InversionPlume.constraints` no la aplica cuando el reajuste es del placebo (`data.day_kinds`).
- [ ] (Opcional) Restricción por región, como en la investigación (σ ≈ 0.02 por región).
- [ ] (Opcional) Marcar en `compare` las corridas con restricción de tráfico, para no validar el domingo contra el tráfico cuando se impuso (circular).
- [ ] (Opcional) Documentar que con `traffic_sd` ≥ 0.04 el efecto de la restricción es mínimo.
