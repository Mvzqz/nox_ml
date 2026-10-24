# Factor de dilución por hora (transporte 'domain', 2023-11-01 a 2023-12-31)

- s_h por hora con a priori 1 ± 0.5, acotado a [0.2, 5]; 6 iteraciones alternadas.
- Ajuste en muestra, estaciones: r = 0.80
- s_h: mediana 1.18, percentiles 10–90 0.87–1.68
- Domingo-festivo / hábil = 0.39; sábado / hábil = 0.77; total vial hábil = 34,854 t/año (35% del a priori)
- Correlación de log s_h con capa límite ERA5: -0.01; con velocidad del viento ERA5: -0.11 (se esperan negativas: más mezcla o más viento = menos concentración)

## Estación retenida (LOO)

| | Modelo con s_h | IDW | Híbrido |
|---|---|---|---|
| RMSE total (ppb) | 14.0 | 11.6 | 12.6 |
| Sesgo por estación (RMS) | 5.8 | 6.6 | 5.3 |
| Error hora a hora | 12.8 | 9.5 | 11.5 |
| Estaciones donde gana a IDW | 8 de 24 | — | 14 de 24 |

| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido |
|---|---|---|---|---|
| ACO | 141 | 7.5 | 13.2 | 6.8 |
| AJM | 361 | 11.7 | 9.2 | 9.0 |
| ATI | 290 | 11.6 | 13.7 | 10.6 |
| CAM | 362 | 11.8 | 8.4 | 8.6 |
| CCA | 359 | 10.3 | 5.4 | 5.9 |
| CHO | 303 | 10.0 | 12.8 | 9.7 |
| CUA | 360 | 12.3 | 14.5 | 12.0 |
| CUT | 336 | 15.2 | 12.1 | 13.6 |
| FAC | 357 | 13.8 | 12.4 | 11.1 |
| HGM | 356 | 10.6 | 6.7 | 7.0 |
| IZT | 351 | 10.9 | 7.4 | 7.9 |
| MER | 361 | 19.4 | 15.8 | 15.0 |
| MGH | 344 | 13.0 | 9.5 | 9.8 |
| MON | 96 | 12.5 | 18.3 | 12.5 |
| NEZ | 359 | 10.0 | 9.8 | 8.1 |
| PED | 349 | 10.6 | 5.5 | 5.4 |
| SAC | 350 | 11.9 | 10.0 | 9.0 |
| SAG | 358 | 16.7 | 13.4 | 21.2 |
| TLA | 312 | 27.8 | 14.8 | 26.7 |
| TLI | 354 | 10.2 | 10.7 | 9.7 |
| UAX | 200 | 10.3 | 10.4 | 9.9 |
| UIZ | 262 | 13.5 | 10.1 | 11.3 |
| VIF | 264 | 13.1 | 16.7 | 13.5 |
| XAL | 352 | 21.1 | 14.2 | 21.6 |
