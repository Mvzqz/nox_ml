# Prueba con datos reales: inversión lineal, viento 'field' (2023-11-01 a 2023-12-31)

- Horas: 366; observaciones de estación: 8,564; píxeles TEMPO: 78,227; σ obs: estaciones 15.0 ppb, TEMPO 5e+15
- Festivos tratados como domingo: 2023-11-20, 2023-12-25

## 1. Ajuste en muestra

- Estaciones NOₓ: r = 0.76, RMSE = 13.1 ppb (media observada 30.8, desv. est. 19.9)
- TEMPO NO₂: r = 0.73

## 2. Emisión vial por tipo de día

IC 90 % por bootstrap de 61 días completos (200 réplicas).

| Tipo de día | Horas | Total vial (t/año equivalente) | IC 90 % |
|---|---|---|---|
| hábil | 246 | 30,421 | 26,125–36,237 |
| sábado | 54 | 23,500 | 18,872–29,948 |
| domingo/festivo | 66 | 9,149 | 7,335–12,800 |
| a priori (igual para todos) | | 99,292 | |

- sábado / hábil = **0.77** (IC 90 % 0.59–1.02)

- domingo/festivo / hábil = **0.30** (IC 90 % 0.23–0.41)

| Región | hábil | sábado | domingo/festivo |
|---|---|---|---|
| SO | -0.15 | -0.10 | -0.15 |
| S | 0.49 | 0.48 | 0.21 |
| SE | 0.07 | 0.21 | 0.05 |
| O | 0.39 | 0.25 | 0.13 |
| Centro | 0.50 | 0.35 | 0.19 |
| E | 0.20 | 0.18 | -0.09 |
| NO | 0.53 | 0.55 | 0.22 |
| N | 0.47 | 0.19 | 0.22 |
| NE | -0.20 | -0.51 | -0.37 |

(factor α respecto al a priori de la región; a priori 1 ± 0.5)

## 3. Fuentes puntuales

| Fuente | A priori t/año | A posteriori t/año |
|---|---|---|
| Nonoalco | 277 | 122 ± 34 |
| Valle de México (CC) + Valle de México (Vapor) | 2,615 | 358 ± 35 |
| AIFA (NLU) | 500 | -316 ± 45 |
| AICM (MEX) | 500 | 453 ± 38 |

## 4. Estación retenida (LOO)

Híbrido = modelo LOO + IDW de los residuos de las demás estaciones en la misma hora.

| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido | r modelo | r IDW | r híbrido |
|---|---|---|---|---|---|---|---|
| ACO | 141 | 9.7 | 13.0 | 8.5 | 0.58 | 0.57 | 0.63 |
| AJM | 361 | 11.2 | 9.3 | 9.0 | 0.73 | 0.85 | 0.84 |
| ATI | 290 | 12.6 | 13.6 | 11.9 | 0.75 | 0.78 | 0.82 |
| CAM | 362 | 12.5 | 9.0 | 9.0 | 0.88 | 0.90 | 0.89 |
| CCA | 359 | 10.6 | 5.5 | 5.7 | 0.80 | 0.95 | 0.95 |
| CHO | 303 | 10.7 | 12.5 | 10.8 | 0.66 | 0.80 | 0.72 |
| CUA | 360 | 13.3 | 14.3 | 13.6 | 0.62 | 0.73 | 0.71 |
| CUT | 336 | 14.6 | 12.3 | 13.1 | 0.56 | 0.69 | 0.67 |
| FAC | 357 | 16.0 | 12.9 | 11.9 | 0.81 | 0.79 | 0.84 |
| HGM | 356 | 11.6 | 6.5 | 7.0 | 0.89 | 0.95 | 0.94 |
| IZT | 351 | 11.7 | 7.3 | 8.0 | 0.89 | 0.95 | 0.93 |
| MER | 361 | 20.5 | 16.7 | 15.9 | 0.81 | 0.92 | 0.87 |
| MGH | 344 | 15.3 | 9.8 | 11.4 | 0.80 | 0.88 | 0.85 |
| MON | 96 | 14.2 | 17.7 | 13.5 | 0.50 | 0.61 | 0.55 |
| NEZ | 359 | 11.7 | 9.0 | 9.8 | 0.74 | 0.89 | 0.86 |
| PED | 349 | 11.3 | 5.7 | 6.1 | 0.79 | 0.96 | 0.94 |
| SAC | 350 | 11.9 | 10.0 | 9.4 | 0.77 | 0.87 | 0.87 |
| SAG | 358 | 18.0 | 10.7 | 18.8 | 0.67 | 0.87 | 0.75 |
| TLA | 312 | 18.9 | 15.4 | 14.5 | 0.83 | 0.88 | 0.88 |
| TLI | 354 | 10.7 | 10.6 | 10.5 | 0.78 | 0.85 | 0.85 |
| UAX | 200 | 10.6 | 10.5 | 10.0 | 0.71 | 0.78 | 0.80 |
| UIZ | 262 | 14.2 | 10.3 | 10.7 | 0.80 | 0.90 | 0.89 |
| VIF | 264 | 13.8 | 16.6 | 14.0 | 0.65 | 0.73 | 0.75 |
| XAL | 352 | 17.1 | 14.0 | 16.1 | 0.76 | 0.91 | 0.84 |

- RMSE ponderado: modelo 13.9, IDW 11.5, híbrido 11.7 ppb
- Parte constante (sesgo medio por estación, RMS): modelo 7.1, IDW 6.5, híbrido 6.0 ppb
- Parte que varía hora a hora (RMSE sin el sesgo): modelo 11.9, IDW 9.5, híbrido 10.0 ppb
- Modelo < IDW en 6 de 24 estaciones; híbrido < IDW en 13 de 24
