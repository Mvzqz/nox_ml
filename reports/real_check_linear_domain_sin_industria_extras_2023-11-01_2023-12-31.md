# Prueba con datos reales: inversión lineal, viento 'domain' (2023-11-01 a 2023-12-31)

- Horas: 366; observaciones de estación: 8,564; píxeles TEMPO: 78,227; σ obs: estaciones 15.0 ppb, TEMPO 5e+15
- Festivos tratados como domingo: 2023-11-20, 2023-12-25

## 1. Ajuste en muestra

- Estaciones NOₓ: r = 0.77, RMSE = 12.8 ppb (media observada 30.8, desv. est. 19.9)
- TEMPO NO₂: r = 0.74

## 2. Emisión vial por tipo de día

IC 90 % por bootstrap de 61 días completos (200 réplicas).

| Tipo de día | Horas | Total vial (t/año equivalente) | IC 90 % |
|---|---|---|---|
| hábil | 246 | 37,596 | 32,978–42,626 |
| sábado | 54 | 29,527 | 25,656–35,814 |
| domingo/festivo | 66 | 16,331 | 13,804–19,165 |
| a priori (igual para todos) | | 99,292 | |

- sábado / hábil = **0.79** (IC 90 % 0.65–0.99)

- domingo/festivo / hábil = **0.43** (IC 90 % 0.36–0.54)

| Región | hábil | sábado | domingo/festivo |
|---|---|---|---|
| SO | 0.04 | 0.06 | -0.01 |
| S | 0.34 | 0.36 | 0.20 |
| SE | 0.26 | 0.18 | 0.16 |
| O | 0.45 | 0.39 | 0.13 |
| Centro | 0.57 | 0.31 | 0.21 |
| E | 0.34 | 0.46 | 0.15 |
| NO | 0.58 | 0.53 | 0.23 |
| N | 0.54 | 0.26 | 0.29 |
| NE | 0.26 | 0.16 | 0.14 |

(factor α respecto al a priori de la región; a priori 1 ± 0.5)

## 3. Fuentes puntuales

| Fuente | A priori t/año | A posteriori t/año |
|---|---|---|
| Nonoalco | 277 | 55 ± 36 |
| Valle de México (CC) + Valle de México (Vapor) | 2,615 | 223 ± 35 |
| AIFA (NLU) | 500 | -11 ± 33 |
| AICM (MEX) | 500 | 46 ± 40 |

## 4. Estación retenida (LOO)

Híbrido = modelo LOO + IDW de los residuos de las demás estaciones en la misma hora.

| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido | r modelo | r IDW | r híbrido |
|---|---|---|---|---|---|---|---|
| ACO | 141 | 9.0 | 13.0 | 8.0 | 0.59 | 0.57 | 0.63 |
| AJM | 361 | 11.5 | 9.3 | 9.2 | 0.72 | 0.85 | 0.83 |
| ATI | 290 | 12.5 | 13.6 | 11.5 | 0.76 | 0.78 | 0.82 |
| CAM | 362 | 12.7 | 9.0 | 9.2 | 0.89 | 0.90 | 0.90 |
| CCA | 359 | 10.3 | 5.5 | 5.6 | 0.80 | 0.95 | 0.95 |
| CHO | 303 | 10.9 | 12.5 | 10.8 | 0.66 | 0.80 | 0.72 |
| CUA | 360 | 13.0 | 14.3 | 12.9 | 0.64 | 0.73 | 0.71 |
| CUT | 336 | 15.0 | 12.3 | 13.6 | 0.54 | 0.69 | 0.65 |
| FAC | 357 | 14.7 | 12.9 | 11.7 | 0.77 | 0.79 | 0.82 |
| HGM | 356 | 11.6 | 6.5 | 6.5 | 0.91 | 0.95 | 0.95 |
| IZT | 351 | 11.6 | 7.3 | 7.6 | 0.89 | 0.95 | 0.94 |
| MER | 361 | 19.9 | 16.7 | 15.1 | 0.82 | 0.92 | 0.88 |
| MGH | 344 | 13.9 | 9.8 | 10.4 | 0.83 | 0.88 | 0.87 |
| MON | 96 | 13.7 | 17.7 | 12.9 | 0.54 | 0.61 | 0.58 |
| NEZ | 359 | 10.9 | 9.0 | 8.7 | 0.77 | 0.89 | 0.88 |
| PED | 349 | 10.9 | 5.7 | 5.7 | 0.80 | 0.96 | 0.95 |
| SAC | 350 | 12.7 | 10.0 | 9.9 | 0.72 | 0.87 | 0.85 |
| SAG | 358 | 16.8 | 10.7 | 18.0 | 0.71 | 0.87 | 0.77 |
| TLA | 312 | 18.9 | 15.4 | 14.8 | 0.83 | 0.88 | 0.88 |
| TLI | 354 | 10.4 | 10.6 | 10.0 | 0.79 | 0.85 | 0.86 |
| UAX | 200 | 10.5 | 10.5 | 10.0 | 0.71 | 0.78 | 0.80 |
| UIZ | 262 | 13.8 | 10.3 | 10.2 | 0.82 | 0.90 | 0.90 |
| VIF | 264 | 13.8 | 16.6 | 14.1 | 0.65 | 0.73 | 0.75 |
| XAL | 352 | 17.4 | 14.0 | 16.6 | 0.76 | 0.91 | 0.83 |

- RMSE ponderado: modelo 13.6, IDW 11.5, híbrido 11.4 ppb
- Parte constante (sesgo medio por estación, RMS): modelo 6.9, IDW 6.5, híbrido 5.8 ppb
- Parte que varía hora a hora (RMSE sin el sesgo): modelo 11.7, IDW 9.5, híbrido 9.8 ppb
- Modelo < IDW en 7 de 24 estaciones; híbrido < IDW en 16 de 24
