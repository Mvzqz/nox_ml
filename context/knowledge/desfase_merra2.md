# Desfase de MERRA-2 frente a ERA5

Fecha: 2026-10-27. Solo se usó 2023 (ene–dic) y la serie de ERA5 de Open-Meteo; no se corrió ningún modelo en feb–may 2024.

## Conclusión

**El desfase de una hora heredado de la investigación era incorrecto y se corrigió** (`nox_ml.data.pbl.merra_to_hourly`). El efecto sobre las métricas de nov–dic 2023 es despreciable; el beneficio es que MERRA-2 queda alineado con ERA5 y que su corrección multiplicativa por hora ahora sí reduce el error fuera de muestra.

## Convención de tiempo

MERRA-2 `M2T1NXFLX` (tavg1) trae promedios de hora con marca hh:30: la lectura de hh:30 es el promedio de [hh:00, hh+1:00]. ERA5 (Open-Meteo) trae valores en punto. El promedio de dos lecturas consecutivas (hh−1:30 y hh:30) queda centrado en hh:00 y debe llevar esa marca. El código migrado lo marcaba una hora después (hh+1:00), de modo que MERRA-2 iba una hora atrasado.

## Correlación cruzada horaria (2023)

Correlación de la capa límite de ERA5 con la de MERRA-2 desplazada `lag` horas (`lag` negativo = MERRA-2 más temprano). Serie con la marca heredada:

| Periodo | −2 h | **−1 h** | 0 h (heredado) | +1 h | +2 h |
|---|---|---|---|---|---|
| Todas las horas, 2023 | 0.816 | **0.874** | 0.841 | 0.724 | 0.550 |
| Todas las horas, ene–jun 2023 | 0.832 | **0.889** | 0.851 | 0.727 | 0.545 |
| Todas las horas, nov–dic 2023 | 0.777 | **0.826** | 0.771 | 0.626 | 0.430 |
| Tarde (12–17 h locales), 2023 | 0.698 | **0.812** | 0.754 | 0.611 | 0.474 |
| Tarde, nov–dic 2023 | 0.541 | **0.665** | 0.564 | 0.388 | 0.251 |

El máximo está siempre en −1 h: la marca heredada va exactamente una hora tarde. Como comprobación, las lecturas sin promediar, marcadas al inicio de su hora, tienen su máximo entre 0 y +1 h (0.852 y 0.866), es decir, a media hora, como corresponde a un promedio centrado en hh:30.

## Efecto de la corrección

Ajuste de ene–jun 2023, tarde (12–17 h locales):

| | Heredado | Corregido |
|---|---|---|
| Correlación con ERA5 | 0.68 | 0.76 |
| Sesgo mediano MERRA-2 − ERA5 | +224 m | +337 m |
| Error mediano fuera de muestra (ajuste ene–mar, prueba abr–jun), sin corregir | 338 m (12 %) | 383 m (13 %) |
| Ídem, con la corrección por hora | 376 m (14 %) | **340 m (12 %)** |

Con la marca correcta la corrección multiplicativa por hora (factores 0.81–0.95 por la tarde) deja de empeorar el error mediano.

## Efecto en los modelos (nov–dic 2023)

Nov–dic 2023 usa ERA5 directamente, así que el cambio **no altera esos datos**: antes y después son idénticos. Para medir el efecto del desfase se sustituyó, solo en esos dos meses y solo para esta prueba, la capa límite de ERA5 por MERRA-2 corregido (con el factor de ene–jun 2023, como en la serie de 2024), con la marca heredada y con la corregida:

| Modelo | Capa límite | Error con estación oculta (ppb) | Sesgo (ppb) | Domingo ÷ hábil (IC 90 %) | Placebo del modelo (centro ± semiancho) | Placebo normalizado (± semiancho) |
|---|---|---|---|---|---|---|
| `baseline` | ERA5 (la de producción) | 13.59 | 6.83 | 0.423 (0.349–0.535) | 1.077 ± 0.350 | ± 0.255 |
| `baseline` | MERRA-2, marca heredada (antes) | 13.56 | 7.11 | 0.423 (0.349–0.536) | 1.080 ± 0.351 | ± 0.216 |
| `baseline` | MERRA-2, marca corregida (después) | 13.57 | 7.13 | 0.423 (0.349–0.536) | 1.080 ± 0.351 | ± 0.212 |
| `pinn_puff` | ERA5 (la de producción) | 11.87 | 5.22 | 0.477 (0.362–0.624) | 1.011 ± 0.124 | ± 0.255 |
| `pinn_puff` | MERRA-2, marca heredada (antes) | 12.13 | 5.57 | 0.477 (0.363–0.624) | 1.013 ± 0.123 | ± 0.216 |
| `pinn_puff` | MERRA-2, marca corregida (después) | 12.15 | 5.59 | 0.477 (0.363–0.624) | 1.013 ± 0.123 | ± 0.212 |

(El «leave-one-out» de la tabla es el error con estación oculta.) Lectura:

- El desfase no cambia las conclusiones: domingo ÷ hábil y placebo son iguales a tres decimales; el error con estación oculta cambia 0.01–0.02 ppb.
- La capa límite de MERRA-2 corregido sí cuesta algo frente a ERA5 en `pinn_puff` (+0.26 ppb) y casi nada en `baseline` (−0.03 ppb). Es un orden de magnitud de lo que cabe esperar en feb–may 2024, donde no hay ERA5.
- En nov–dic 2023 la capa límite de MERRA-2 corregido frente a ERA5 (tarde) tiene error absoluto mediano de 312 m y r = 0.60 con la marca heredada, y de 297 m y r = 0.67 con la corregida.

## Qué cambió

- `nox_ml.data.pbl.merra_to_hourly`: la marca es `hh:00` (antes `hh+1:00`), con una prueba de rampa lineal.
- `data/interim/pbl_2023_2024.parquet` y `pbl_merra2_vs_era5.csv` regenerados con `nox-ml fill-pbl` y versionados con DVC. Solo cambian las horas de ene–jun 2024 (las de MERRA-2).
- Pendiente: los cuadernos `Avance1.39` (sección 4.4) y `Avance2.39` y sus HTML citan las cifras anteriores (r = 0.68, 224 m, 338 frente a 376 m) y la nota del desfase; hay que volver a ejecutarlos para que reflejen las nuevas.
