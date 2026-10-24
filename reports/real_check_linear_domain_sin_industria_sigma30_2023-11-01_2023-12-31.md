# Prueba con datos reales: inversión lineal, viento 'domain' (2023-11-01 a 2023-12-31)

- Horas: 366; observaciones de estación: 7,537; píxeles TEMPO: 78,227; σ obs: estaciones 15.0 ppb, TEMPO 5e+15; σθ viento 30°
- Festivos tratados como domingo: 2023-11-20, 2023-12-25

## 1. Ajuste en muestra

- Estaciones NOₓ: r = 0.78, RMSE = 12.8 ppb (media observada 31.2, desv. est. 20.0)
- TEMPO NO₂: r = 0.75

## 2. Emisión vial por tipo de día

IC 90 % por bootstrap de 61 días completos (200 réplicas).

| Tipo de día | Horas | Total vial (t/año equivalente) | IC 90 % |
|---|---|---|---|
| hábil | 246 | 40,494 | 35,293–46,217 |
| sábado | 54 | 31,390 | 27,389–37,798 |
| domingo/festivo | 66 | 16,606 | 13,852–19,607 |
| a priori (igual para todos) | | 99,292 | |

- sábado / hábil = **0.78** (IC 90 % 0.64–0.98)

- domingo/festivo / hábil = **0.41** (IC 90 % 0.34–0.51)

| Región | hábil | sábado | domingo/festivo |
|---|---|---|---|
| SO | -0.02 | -0.06 | -0.07 |
| S | 0.41 | 0.43 | 0.25 |
| SE | 0.22 | 0.13 | 0.13 |
| O | 0.50 | 0.49 | 0.13 |
| Centro | 0.73 | 0.34 | 0.28 |
| E | 0.16 | 0.51 | 0.03 |
| NO | 0.62 | 0.52 | 0.24 |
| N | 0.49 | 0.25 | 0.28 |
| NE | 0.44 | 0.26 | 0.16 |

(factor α respecto al a priori de la región; a priori 1 ± 0.5)

## 3. Fuentes puntuales

| Fuente | A priori t/año | A posteriori t/año |
|---|---|---|
| Nonoalco | 277 | 325 ± 46 |
| Valle de México (CC) + Valle de México (Vapor) | 2,615 | 296 ± 45 |
| AIFA (NLU) | 500 | -194 ± 41 |
| AICM (MEX) | 500 | 74 ± 49 |

## 4. Estación retenida (LOO)

Híbrido = modelo LOO + IDW de los residuos de las demás estaciones en la misma hora.

| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido | r modelo | r IDW | r híbrido |
|---|---|---|---|---|---|---|---|
| ACO | 141 | 9.1 | 13.2 | 8.1 | 0.60 | 0.60 | 0.65 |
| AJM | 361 | 11.4 | 9.2 | 9.0 | 0.73 | 0.85 | 0.84 |
| ATI | 290 | 12.3 | 13.7 | 11.5 | 0.76 | 0.79 | 0.83 |
| CAM | 362 | 12.2 | 8.4 | 8.5 | 0.89 | 0.90 | 0.90 |
| CCA | 359 | 10.3 | 5.4 | 5.5 | 0.81 | 0.95 | 0.95 |
| CHO | 303 | 10.7 | 12.8 | 10.7 | 0.66 | 0.80 | 0.72 |
| CUA | 360 | 12.7 | 14.5 | 12.6 | 0.65 | 0.74 | 0.72 |
| CUT | 336 | 15.1 | 12.1 | 13.4 | 0.54 | 0.70 | 0.66 |
| FAC | 357 | 13.8 | 12.4 | 10.7 | 0.80 | 0.80 | 0.84 |
| HGM | 356 | 11.1 | 6.7 | 6.7 | 0.90 | 0.95 | 0.95 |
| IZT | 351 | 11.6 | 7.4 | 7.7 | 0.88 | 0.94 | 0.93 |
| MER | 361 | 18.4 | 15.8 | 13.4 | 0.82 | 0.92 | 0.89 |
| MGH | 344 | 14.3 | 9.5 | 10.6 | 0.83 | 0.88 | 0.87 |
| MON | 96 | 13.1 | 18.3 | 12.6 | 0.49 | 0.59 | 0.52 |
| NEZ | 359 | 11.0 | 9.8 | 9.2 | 0.77 | 0.88 | 0.89 |
| PED | 349 | 10.9 | 5.5 | 5.4 | 0.80 | 0.96 | 0.96 |
| SAC | 350 | 12.7 | 10.0 | 9.7 | 0.73 | 0.87 | 0.86 |
| SAG | 358 | 17.8 | 13.4 | 21.3 | 0.72 | 0.86 | 0.78 |
| TLA | 312 | 18.7 | 14.8 | 14.4 | 0.84 | 0.89 | 0.88 |
| TLI | 354 | 10.2 | 10.7 | 9.8 | 0.80 | 0.86 | 0.87 |
| UAX | 200 | 10.5 | 10.4 | 10.1 | 0.72 | 0.79 | 0.81 |
| UIZ | 262 | 13.5 | 10.1 | 9.7 | 0.82 | 0.91 | 0.91 |
| VIF | 264 | 13.3 | 16.7 | 13.5 | 0.67 | 0.75 | 0.78 |
| XAL | 352 | 16.9 | 14.2 | 17.1 | 0.73 | 0.86 | 0.74 |

- RMSE ponderado: modelo 13.4, IDW 11.6, híbrido 11.5 ppb
- Parte constante (sesgo medio por estación, RMS): modelo 6.6, IDW 6.6, híbrido 5.9 ppb
- Parte que varía hora a hora (RMSE sin el sesgo): modelo 11.7, IDW 9.5, híbrido 9.9 ppb
- Modelo < IDW en 7 de 24 estaciones; híbrido < IDW en 16 de 24
