# Prueba con datos reales: inversión lineal, viento 'field' (2023-11-01 a 2023-12-31)

- Horas: 366; observaciones de estación: 8,564; píxeles TEMPO: 78,227; σ obs: estaciones 15.0 ppb, TEMPO 5e+15; σθ viento 30°
- Festivos tratados como domingo: 2023-11-20, 2023-12-25

## 1. Ajuste en muestra

- Estaciones NOₓ: r = 0.76, RMSE = 12.9 ppb (media observada 30.8, desv. est. 19.9)
- TEMPO NO₂: r = 0.75

## 2. Emisión vial por tipo de día

IC 90 % por bootstrap de 61 días completos (200 réplicas).

| Tipo de día | Horas | Total vial (t/año equivalente) | IC 90 % |
|---|---|---|---|
| hábil | 246 | 35,333 | 30,522–41,654 |
| sábado | 54 | 26,131 | 21,302–33,629 |
| domingo/festivo | 66 | 10,602 | 8,116–14,425 |
| a priori (igual para todos) | | 99,292 | |

- sábado / hábil = **0.74** (IC 90 % 0.57–0.99)

- domingo/festivo / hábil = **0.30** (IC 90 % 0.23–0.42)

| Región | hábil | sábado | domingo/festivo |
|---|---|---|---|
| SO | -0.24 | -0.19 | -0.22 |
| S | 0.58 | 0.58 | 0.26 |
| SE | 0.08 | 0.15 | 0.04 |
| O | 0.49 | 0.35 | 0.17 |
| Centro | 0.66 | 0.40 | 0.25 |
| E | 0.04 | 0.11 | -0.14 |
| NO | 0.60 | 0.62 | 0.23 |
| N | 0.51 | 0.23 | 0.26 |
| NE | -0.09 | -0.57 | -0.45 |

(factor α respecto al a priori de la región; a priori 1 ± 0.5)

## 3. Fuentes puntuales

| Fuente | A priori t/año | A posteriori t/año |
|---|---|---|
| Nonoalco | 277 | 271 ± 44 |
| Valle de México (CC) + Valle de México (Vapor) | 2,615 | 324 ± 45 |
| AIFA (NLU) | 500 | -365 ± 60 |
| AICM (MEX) | 500 | 698 ± 51 |

## 4. Estación retenida (LOO)

Híbrido = modelo LOO + IDW de los residuos de las demás estaciones en la misma hora.

| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido | r modelo | r IDW | r híbrido |
|---|---|---|---|---|---|---|---|
| ACO | 141 | 9.6 | 13.0 | 8.2 | 0.57 | 0.57 | 0.62 |
| AJM | 361 | 11.1 | 9.3 | 8.9 | 0.74 | 0.85 | 0.84 |
| ATI | 290 | 12.4 | 13.6 | 11.7 | 0.76 | 0.78 | 0.82 |
| CAM | 362 | 12.3 | 9.0 | 9.1 | 0.87 | 0.90 | 0.89 |
| CCA | 359 | 10.8 | 5.5 | 5.5 | 0.80 | 0.95 | 0.95 |
| CHO | 303 | 10.6 | 12.5 | 10.6 | 0.66 | 0.80 | 0.72 |
| CUA | 360 | 13.1 | 14.3 | 13.2 | 0.63 | 0.73 | 0.71 |
| CUT | 336 | 14.9 | 12.3 | 13.4 | 0.55 | 0.69 | 0.66 |
| FAC | 357 | 15.7 | 12.9 | 11.8 | 0.82 | 0.79 | 0.85 |
| HGM | 356 | 11.4 | 6.5 | 7.0 | 0.88 | 0.95 | 0.94 |
| IZT | 351 | 11.4 | 7.3 | 8.0 | 0.89 | 0.95 | 0.93 |
| MER | 361 | 19.5 | 16.7 | 15.2 | 0.81 | 0.92 | 0.87 |
| MGH | 344 | 15.9 | 9.8 | 12.0 | 0.79 | 0.88 | 0.85 |
| MON | 96 | 13.7 | 17.7 | 12.7 | 0.48 | 0.61 | 0.53 |
| NEZ | 359 | 11.6 | 9.0 | 9.5 | 0.75 | 0.89 | 0.86 |
| PED | 349 | 11.5 | 5.7 | 5.9 | 0.79 | 0.96 | 0.95 |
| SAC | 350 | 11.7 | 10.0 | 9.2 | 0.77 | 0.87 | 0.88 |
| SAG | 358 | 18.0 | 10.7 | 18.1 | 0.69 | 0.87 | 0.77 |
| TLA | 312 | 18.3 | 15.4 | 14.1 | 0.83 | 0.88 | 0.88 |
| TLI | 354 | 10.8 | 10.6 | 10.3 | 0.78 | 0.85 | 0.85 |
| UAX | 200 | 10.7 | 10.5 | 10.2 | 0.70 | 0.78 | 0.80 |
| UIZ | 262 | 14.0 | 10.3 | 10.5 | 0.81 | 0.90 | 0.90 |
| VIF | 264 | 13.4 | 16.6 | 13.4 | 0.65 | 0.73 | 0.76 |
| XAL | 352 | 16.3 | 14.0 | 15.3 | 0.76 | 0.91 | 0.84 |

- RMSE ponderado: modelo 13.7, IDW 11.5, híbrido 11.4 ppb
- Parte constante (sesgo medio por estación, RMS): modelo 6.9, IDW 6.5, híbrido 5.7 ppb
- Parte que varía hora a hora (RMSE sin el sesgo): modelo 11.8, IDW 9.5, híbrido 9.9 ppb
- Modelo < IDW en 6 de 24 estaciones; híbrido < IDW en 14 de 24
