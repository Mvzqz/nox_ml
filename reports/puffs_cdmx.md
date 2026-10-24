# Puffs en la CDMX con la configuración actual

**Pregunta.** En Los Ángeles lo que mejoró la inversión con datos reales fue el transporte dependiente del tiempo (puffs), no un viento mejor (`otras_ciudades.md`, «Puffs + HRRR»). En la CDMX los puffs se habían probado con otra configuración (σθ = 15°, TEMPO con peso completo, sin restricción) y empeoraban las estaciones (LOO 14.1 → 15.1) aunque mejoraban TEMPO (0.74 → 0.83). ¿Qué pasa con la configuración actual?

**Configuración (igual en todas las variantes).** σθ = 30°; σ de TEMPO ×3; restricción de cociente de Infovial de día completo (sábado 0.87, domingo 0.69, σ 0.02); a priori de centrales de Climate TRACE (Valle de México 1,600 ± 650, Nonoalco 100 ± 100 t/año); capa límite ERA5 + MERRA-2; sin clústeres industriales; estaciones extra (solo NO₂) y viento METAR de los aeropuertos. Periodos: nov–dic 2023 (366 h) y feb–may 2024 (642 h).

## Resumen

- **Los puffs mejoran todo lo que no es la validación con estaciones**, en los dos periodos:
  - El modelo con emisión fija explica mejor a TEMPO (r 0.50 → 0.65 en nov–dic; 0.50 → 0.58 en primavera) y, tras invertir, r con TEMPO sube de 0.75 a 0.83 (nov–dic) y de 0.73 a 0.80 (primavera).
  - La emisión vial deja de quedar muy por debajo del inventario: 42 % → 75 % (nov–dic) y 25 % → 45 % (primavera).
  - **El estimador normalizado se vuelve más estable**: CV de los días hábiles 0.35 → 0.26 (nov–dic) y 0.27 → 0.23 (primavera); placebo ±0.26 → ±0.19 en nov–dic (±0.12 → ±0.11 en primavera). El domingo normalizado casi no cambia (0.65 → 0.61; 0.70 → 0.68).
  - El domingo **libre** (sin restricción) se acerca al tráfico: 0.42 → 0.49 (nov–dic) y 0.43 → 0.53 (primavera). Con restricción queda igual (0.62–0.65).
  - El AICM sube hacia su a priori (69 → 646 t/año en nov–dic; 63 → 334 en primavera); Valle de México sube algo (313 → 425), lejos aún de 1,600.
- **Estaciones: empate, salvo Ecatepec.** En nov–dic el LOO del híbrido empeora (11.2 → 12.3 ppb; gana a IDW en 15 de 24 estaciones frente a 17). **Toda la pérdida viene de dos estaciones de Ecatepec, SAG y XAL**: sin ellas, el modelo mejora con puffs (13.0 → 12.2 ppb) y el híbrido empata (10.52 frente a 10.52). En primavera el modelo mejora (8.0 → 7.8) y el híbrido empata (6.7 → 6.8).
- **El viento IDW dentro de los puffs no aporta** frente al vector medio del dominio, como en LA.
- **Los ajustes baratos no arreglan Ecatepec**: el perfil horario de Infovial y quitar el perfil dejan el LOO igual; acortar la vida química a 2 h lo empeora (LOO del modelo 14.5).

**Veredicto:** los puffs ganan con claridad en TEMPO, en los totales y en la estabilidad del estimador normalizado, y empatan en estaciones fuera de Ecatepec. No ganan con claridad en la validación con estaciones, así que **no cambié el estándar**: quedan como opción en `scripts/puffs_cdmx.py`. La decisión depende de qué pese más: si el producto es el estimador normalizado y los mapas, los puffs son mejores; si es el mapa híbrido en estaciones, la pluma estacionaria sigue un poco mejor por Ecatepec.

## Por qué los puffs fallan en SAG y XAL

Descompuse la predicción media de cada estación por fuente (nov–dic, con restricción):

| Estación | Observado | Pluma: fondo + vial local (región) = modelo | Puffs: fondo + vial local = modelo |
|---|---|---|---|
| SAG (Ecatepec) | 25.1 | 20.9 + 10.5 (Centro) = 34.9 | 15.8 + 22.2 (Centro) = 40.6 |
| XAL (Ecatepec) | 38.4 | 20.9 + 5.9 (Centro) = 30.5 | 15.9 + 12.7 (Centro) = 31.4 |
| TLA (Tlalnepantla) | 44.9 | 21.8 + 7.5 (O) = 33.3 | 16.5 + 17.1 (O) = 37.4 |

- Ecatepec cae dentro de la región «Centro» de la malla 3×3. Con puffs, el factor vial de Centro casi se duplica (0.58 → 0.97) porque los puffs reparten más señal a las calles y menos al fondo (fondo 21 → 16 ppb).
- SAG está junto a vialidades con mucho peso en el proxy de OSM pero mide poco NOₓ. El factor regional, fijado sobre todo por las estaciones del centro real (MER, CAM, HGM, IZT), le asigna demasiada emisión local. Es un problema de **representatividad del proxy vial dentro de una región grande**, no del transporte: los puffs solo lo amplifican al darle más peso a las calles.
- No es la mañana, el perfil horario ni la capa límite nocturna: el modelo con puffs mejora la correlación día a día en todas las horas de la tarde (tabla por hora), y cambiar el perfil no mueve el LOO.

**Arreglo posible (no probado):** separar Ecatepec/Tlalnepantla de la región Centro (regiones por municipio o una malla 4×4) o revisar el peso del proxy vial cerca de SAG.

## Tablas completas

### nov–dic 2023

| Transporte | LOO modelo / IDW / híbrido (ppb) | Sesgo / hora a hora del modelo | Híbrido < IDW | r fija estaciones (hora / espacial) | r fija TEMPO (global / por escaneo) | r TEMPO invertido | Vial hábil / inventario |
|---|---|---|---|---|---|---|---|
| Pluma estacionaria (estándar) | 13.4 / 11.5 / 11.2 | 6.7 / 11.6 | 17 de 24 | 0.39 / 0.33 | 0.50 / 0.69 | 0.75 | 42% |
| Puffs, viento del dominio | 13.6 / 11.5 / 12.3 | 6.5 / 12.0 | 15 de 24 | 0.41 / 0.36 | 0.65 / 0.77 | 0.83 | 75% |
| Puffs, viento IDW | 13.6 / 11.5 / 12.0 | 6.3 / 12.1 | 14 de 24 | 0.40 / 0.34 | 0.65 / 0.77 | 0.83 | 75% |
| Puffs + perfil Infovial | 13.6 / 11.5 / 12.3 | 6.5 / 12.0 | 15 de 24 | 0.38 / 0.35 | 0.63 / 0.77 | 0.83 | 67% |
| Puffs sin perfil horario | 13.6 / 11.5 / 12.3 | 6.5 / 12.0 | 15 de 24 | 0.42 / 0.36 | 0.65 / 0.76 | 0.83 | 95% |
| Puffs, vida química 2 h | 14.5 / 11.5 / 13.4 | 7.1 / 12.7 | 11 de 24 | 0.37 / 0.32 | 0.62 / 0.74 | 0.81 | 93% |

| Transporte | Domingo/hábil libre (IC 90 %) | Con restricción | Normalizado (IC 90 %) | Placebo ± | CV hábiles normalizado / crudo | Valle | Nonoalco | AICM | AIFA |
|---|---|---|---|---|---|---|---|---|---|
| Pluma estacionaria (estándar) | 0.42 (0.34–0.54) | 0.62 | 0.65 (0.56–0.76) | 0.26 | 0.35 / 0.33 | 313 ± 130 | 235 ± 78 | 69 ± 141 | -36 ± 123 |
| Puffs, viento del dominio | 0.49 (0.42–0.57) | 0.63 | 0.61 (0.53–0.69) | 0.19 | 0.26 / 0.33 | 425 ± 128 | 430 ± 77 | 646 ± 135 | 53 ± 121 |
| Puffs, viento IDW | 0.48 (0.38–0.57) | 0.63 | 0.63 (0.54–0.73) | 0.19 | 0.24 / 0.33 | 469 ± 131 | 371 ± 77 | 758 ± 163 | -35 ± 176 |
| Puffs + perfil Infovial | 0.45 (0.39–0.53) | 0.62 | 0.58 (0.51–0.67) | 0.19 | 0.26 / 0.33 | 463 ± 128 | 460 ± 77 | 710 ± 135 | 36 ± 121 |
| Puffs sin perfil horario | 0.49 (0.40–0.58) | 0.63 | 0.61 (0.54–0.70) | 0.19 | 0.26 / 0.33 | 445 ± 127 | 434 ± 77 | 653 ± 135 | 57 ± 121 |
| Puffs, vida química 2 h | 0.51 (0.44–0.59) | 0.64 | 0.60 (0.52–0.68) | 0.19 | 0.26 / 0.33 | 592 ± 135 | 559 ± 79 | 857 ± 142 | -27 ± 130 |

Por hora local (ppb; media en estaciones con NOₓ medido): observado, modelo con emisión fija (a priori), modelo invertido, y r día a día del modelo fijo.

| Transporte | 11–12 h | 12–13 h | 13–14 h | 14–15 h | 15–16 h | 16–17 h |
|---|---|---|---|---|---|---|
| Pluma estacionaria (estándar) | 45 / 28 / 42 / r 0.54 | 36 / 22 / 33 / r 0.50 | 29 / 19 / 28 / r 0.37 | 26 / 19 / 25 / r 0.35 | 25 / 18 / 24 / r 0.42 | 26 / 22 / 25 / r 0.52 |
| Puffs, viento del dominio | 45 / 23 / 42 / r 0.58 | 36 / 19 / 34 / r 0.59 | 29 / 17 / 28 / r 0.52 | 26 / 17 / 25 / r 0.43 | 25 / 17 / 24 / r 0.53 | 26 / 21 / 26 / r 0.58 |
| Puffs, viento IDW | 45 / 21 / 42 / r 0.51 | 36 / 17 / 34 / r 0.60 | 29 / 15 / 28 / r 0.57 | 26 / 15 / 25 / r 0.49 | 25 / 16 / 24 / r 0.55 | 26 / 20 / 26 / r 0.59 |
| Puffs + perfil Infovial | 45 / 24 / 42 / r 0.61 | 36 / 21 / 34 / r 0.56 | 29 / 19 / 28 / r 0.47 | 26 / 19 / 25 / r 0.35 | 25 / 20 / 24 / r 0.48 | 26 / 23 / 26 / r 0.56 |
| Puffs sin perfil horario | 45 / 18 / 42 / r 0.58 | 36 / 15 / 34 / r 0.58 | 29 / 14 / 28 / r 0.52 | 26 / 13 / 25 / r 0.43 | 25 / 13 / 24 / r 0.53 | 26 / 16 / 26 / r 0.58 |
| Puffs, vida química 2 h | 45 / 18 / 42 / r 0.56 | 36 / 15 / 34 / r 0.55 | 29 / 14 / 28 / r 0.47 | 26 / 14 / 25 / r 0.36 | 25 / 14 / 24 / r 0.49 | 26 / 17 / 26 / r 0.59 |

### feb–may 2024

| Transporte | LOO modelo / IDW / híbrido (ppb) | Sesgo / hora a hora del modelo | Híbrido < IDW | r fija estaciones (hora / espacial) | r fija TEMPO (global / por escaneo) | r TEMPO invertido | Vial hábil / inventario |
|---|---|---|---|---|---|---|---|
| Pluma estacionaria (estándar) | 8.0 / 7.1 / 6.7 | 4.5 / 6.6 | 14 de 22 | 0.44 / 0.37 | 0.50 / 0.64 | 0.73 | 25% |
| Puffs, viento del dominio | 7.8 / 7.1 / 6.8 | 3.9 / 6.8 | 13 de 22 | 0.41 / 0.38 | 0.58 / 0.69 | 0.80 | 45% |
| Puffs, viento IDW | 8.0 / 7.1 / 6.9 | 4.2 / 6.8 | 14 de 22 | 0.40 / 0.34 | 0.58 / 0.69 | 0.79 | 45% |

| Transporte | Domingo/hábil libre (IC 90 %) | Con restricción | Normalizado (IC 90 %) | Placebo ± | CV hábiles normalizado / crudo | Valle | Nonoalco | AICM | AIFA |
|---|---|---|---|---|---|---|---|---|---|
| Pluma estacionaria (estándar) | 0.43 (0.32–0.59) | 0.65 | 0.70 (0.61–0.79) | 0.12 | 0.27 / 0.30 | 272 ± 89 | -27 ± 68 | 63 ± 99 | 123 ± 88 |
| Puffs, viento del dominio | 0.53 (0.47–0.63) | 0.65 | 0.68 (0.61–0.76) | 0.11 | 0.23 / 0.30 | 321 ± 87 | 7 ± 67 | 334 ± 94 | 130 ± 86 |
| Puffs, viento IDW | 0.50 (0.44–0.61) | 0.65 | 0.68 (0.62–0.75) | 0.09 | 0.20 / 0.30 | 299 ± 85 | 56 ± 70 | 434 ± 130 | 18 ± 138 |

Por hora local (ppb; media en estaciones con NOₓ medido): observado, modelo con emisión fija (a priori), modelo invertido, y r día a día del modelo fijo.

| Transporte | 11–12 h | 12–13 h | 13–14 h | 14–15 h | 15–16 h | 16–17 h |
|---|---|---|---|---|---|---|
| Pluma estacionaria (estándar) | 27 / 15 / 25 / r 0.56 | 19 / 13 / 17 / r 0.29 | 15 / 11 / 14 / r 0.36 | 14 / 10 / 13 / r 0.38 | 14 / 8 / 13 / r 0.21 | 14 / 7 / 13 / r 0.29 |
| Puffs, viento del dominio | 27 / 15 / 25 / r 0.61 | 19 / 13 / 18 / r 0.37 | 15 / 12 / 14 / r 0.36 | 14 / 11 / 13 / r 0.40 | 14 / 9 / 13 / r 0.26 | 14 / 9 / 14 / r 0.30 |
| Puffs, viento IDW | 27 / 12 / 25 / r 0.67 | 19 / 10 / 18 / r 0.54 | 15 / 9 / 14 / r 0.53 | 14 / 9 / 13 / r 0.49 | 14 / 8 / 13 / r 0.33 | 14 / 8 / 14 / r 0.31 |

Notas:
- «r fija»: correlación del modelo con emisión del a priori (sin invertir) con las observaciones; mide el transporte, no el ajuste.
- El estimador normalizado y el placebo son los de `la_real.metrics` (incluyen estaciones extra y fuentes puntuales en el modelo fijo), así que pueden diferir en ±0.01–0.02 de los de `scripts/pinn/invert.py`.
- Las corridas de Valle de México y Nonoalco usan los a priori de Climate TRACE; la app y `invert.py` siguen con los del inventario.
- Tiempo de cómputo del Jacobiano con puffs del dominio: 1.5–4 min por periodo en CPU (pluma: 15–30 s). Los tiempos de los modos IDW no son confiables (la máquina estuvo suspendida durante la corrida).

## Archivos

- `scripts/puffs_cdmx.py`: corrida (`--period nov23|prim24 --modes plume puff puff_idw puff_infovial puff_plano puff_tau2 puff_tau8`) y tablas (`--report`). No modifica scripts compartidos: parchea `real_check_linear` en memoria.
- `data/interim/puffs_cdmx/{periodo}_{modo}.json`: métricas completas, incluidas LOO por estación y diagnóstico por hora.
- `data/interim/puffs_cdmx/perfil_infovial.json`: perfil horario de emisión vial por tipo de día (Infovial ene-2017, ponderado por clase C1…C6 = 1, 2, 5, 10, 15, 20; media diaria = 1).
