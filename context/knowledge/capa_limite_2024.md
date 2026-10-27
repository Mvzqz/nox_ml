# Capa límite de 2024 y sensibilidad (para las limitaciones del avance 5)

Fecha: 2026-10-27. Todo lo medido aquí usa 2023; no se corrió ningún modelo en feb–may 2024.

## Cómo se construye la capa límite de 2024

- ERA5 de Open-Meteo (`boundary_layer_height`, horaria, 19.5 N 99.25 O) existe en 2023 pero **no de enero a junio de 2024**, que incluye todo el periodo de prueba (15 feb–31 may).
- Ese hueco se rellena con **MERRA-2** (`M2T1NXFLX`, celda 19.5 N 99.375 O): se pasa a valores en punto (promedio de las lecturas de hh−1:30 y hh:30; ver [desfase_merra2.md](desfase_merra2.md)) y se multiplica por un factor por hora local, la mediana de ERA5 ÷ MERRA-2 de ene–jun 2023 (0.81–0.95 por la tarde). Son 4,368 horas de MERRA-2 corregido y 1,464 de ERA5 entre nov 2023 y jun 2024.
- Los modelos la usan promediada con la hora siguiente y con un piso de 200 m (`nox_ml.data.inputs.hourly_pbl`). En la inversión solo limita la dispersión vertical: `min(√(π/2)·σz, capa límite)`.

## Error medido en 2023

Contra ERA5, tarde (12–17 h locales), ene–jun 2023, con el desfase corregido:

| Hora local | ERA5 mediana (m) | MERRA-2 mediana (m) | Sesgo (m) | r | Factor |
|---|---|---|---|---|---|
| 12 | 2,025 | 2,509 | +448 | 0.79 | 0.81 |
| 13 | 2,345 | 2,795 | +395 | 0.77 | 0.86 |
| 14 | 2,600 | 2,970 | +372 | 0.79 | 0.89 |
| 15 | 2,655 | 2,970 | +298 | 0.73 | 0.90 |
| 16 | 2,650 | 2,817 | +220 | 0.74 | 0.92 |
| 17 | 2,290 | 2,493 | +125 | 0.69 | 0.95 |

- **Error fuera de muestra** (factor ajustado con ene–mar, evaluado en abr–jun 2023): mediana de 340 m (12 %) con la corrección y 383 m (13 %) sin ella.
- **En nov–dic 2023**: MERRA-2 corregido frente a ERA5 tiene error mediano de 297 m y r = 0.67.
- **Contra radiosondeos** (AICM 76679, 00 UTC = 18 h locales, 303 lanzamientos en 2023): el archivo solo trae temperatura en superficie y a 700 hPa (~900 m sobre el suelo), así que da la estabilidad Δθ = θ700 − θsuperficie, no la altura. Δθ > 0 (estable, capa menor a ~900 m) ocurre en 27 % de las tardes de 2023. En esas tardes ERA5 da una mediana de 405 m y solo 7 % supera 1,500 m; en ene–jun (16 tardes estables) ERA5 supera 1,500 m en 19 % de ellas y MERRA-2 corregido en otro 19 %, con correlaciones de rango entre Δθ y la capa de −0.30 (ERA5) y −0.32 (MERRA-2 corregido). Es decir, ERA5 y MERRA-2 coinciden entre sí en las tardes de capa baja que el radiosondeo detecta, y ambos fallan en una minoría de ellas. Limitaciones: la hora de las 18 h es cuando la capa ya colapsa, no el 12–17 h del modelo, y la muestra es pequeña. La investigación (`estancamiento.md`, rama `research-archive`) encontró lo mismo con los radiosondeos de 2024: ~10 % de las tardes con capa real menor a ~900 m y modelada de ~2,650 m.

## Sensibilidad a escalar la capa límite ±20 % (nov–dic 2023)

Se multiplicó toda la serie `pbl_m` por 0.8 y 1.2 y se corrieron `baseline` y `pinn_puff` con la configuración de siempre:

| Modelo | Escala | Error con estación oculta (ppb) | Cambio | Sesgo (ppb) | Domingo ÷ hábil | Placebo (centro ± semiancho) |
|---|---|---|---|---|---|---|
| `baseline` | 0.8 | 13.58 | −0.1 % | 6.58 | 0.424 | 1.076 ± 0.349 |
| `baseline` | 1.0 | 13.59 | — | 6.83 | 0.423 | 1.077 ± 0.350 |
| `baseline` | 1.2 | 13.64 | +0.4 % | 7.00 | 0.423 | 1.077 ± 0.350 |
| `pinn_puff` | 0.8 | 11.71 | −1.3 % | 5.06 | 0.477 | 1.011 ± 0.124 |
| `pinn_puff` | 1.0 | 11.87 | — | 5.22 | 0.477 | 1.011 ± 0.124 |
| `pinn_puff` | 1.2 | 12.05 | +1.5 % | 5.40 | 0.477 | 1.011 ± 0.124 |

El error con estación oculta cambia como máximo 1.5 % y las emisiones por tipo de día (y con ellas domingo ÷ hábil y el placebo) casi no se mueven: los totales viales cambian menos de 0.1 %. Una explicación probable, no verificada con una ablación, es que el nivel de emisión lo fijan sobre todo las columnas de TEMPO, que no dependen de la altura de la capa, mientras las estaciones llevan un fondo horario libre; la capa solo entra en las concentraciones en superficie, como tope de la dispersión vertical.

## Para la sección de limitaciones

1. La capa límite de todo el periodo de prueba es MERRA-2 corregido, con error típico de ~340 m (12 %) frente a ERA5 y sesgo residual dependiente de la hora; no hay medida independiente de su altura (los radiosondeos solo distinguen capas menores a ~900 m).
2. Un error sistemático de ±20 % en la capa mueve el error con estación oculta menos de 1.5 % y no mueve el cociente domingo ÷ hábil ni el placebo en nov–dic 2023. Sustituir ERA5 por MERRA-2 corregido en esos meses cuesta +0.26 ppb en `pinn_puff` y casi nada en `baseline`.
3. Lo que no se pudo cubrir: errores no uniformes (días con capa muy baja que ERA5/MERRA-2 no ven) y el comportamiento de la capa en feb–may, que no se miró para no usar el periodo de prueba.
