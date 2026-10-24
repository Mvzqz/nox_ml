# Prueba con datos reales: inversión lineal, viento 'puff' (2023-11-01 a 2023-12-31)

- Horas: 366; observaciones de estación: 7,537; píxeles TEMPO: 78,227; σ obs: estaciones 15.0 ppb, TEMPO 5e+15
- Festivos tratados como domingo: 2023-11-20, 2023-12-25

## 1. Ajuste en muestra

- Estaciones NOₓ: r = 0.74, RMSE = 13.7 ppb (media observada 31.2, desv. est. 20.0)
- TEMPO NO₂: r = 0.83

## 2. Emisión vial por tipo de día

IC 90 % por bootstrap de 61 días completos (200 réplicas).

| Tipo de día | Horas | Total vial (t/año equivalente) | IC 90 % |
|---|---|---|---|
| hábil | 246 | 68,781 | 63,100–74,693 |
| sábado | 54 | 52,990 | 43,492–60,964 |
| domingo/festivo | 66 | 33,570 | 29,199–37,745 |
| a priori (igual para todos) | | 99,292 | |

- sábado / hábil = **0.77** (IC 90 % 0.63–0.92)

- domingo/festivo / hábil = **0.49** (IC 90 % 0.41–0.58)

| Región | hábil | sábado | domingo/festivo |
|---|---|---|---|
| SO | 0.39 | 0.28 | 0.16 |
| S | 0.68 | 0.55 | 0.38 |
| SE | 0.39 | 0.14 | 0.20 |
| O | 0.83 | 0.71 | 0.35 |
| Centro | 1.14 | 0.66 | 0.52 |
| E | 0.52 | 0.50 | 0.28 |
| NO | 0.78 | 0.72 | 0.38 |
| N | 0.65 | 0.56 | 0.35 |
| NE | 0.44 | 0.69 | 0.27 |

(factor α respecto al a priori de la región; a priori 1 ± 0.5)

## 3. Fuentes puntuales

| Fuente | A priori t/año | A posteriori t/año |
|---|---|---|
| Nonoalco | 277 | 47 ± 37 |
| Valle de México (CC) + Valle de México (Vapor) | 2,615 | 251 ± 37 |
| AIFA (NLU) | 500 | -76 ± 34 |
| AICM (MEX) | 500 | 238 ± 38 |

## 4. Estación retenida (LOO)

Híbrido = modelo LOO + IDW de los residuos de las demás estaciones en la misma hora.

| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido | r modelo | r IDW | r híbrido |
|---|---|---|---|---|---|---|---|
| ACO | 141 | 7.2 | 13.2 | 7.0 | 0.58 | 0.60 | 0.61 |
| AJM | 361 | 11.4 | 9.2 | 9.7 | 0.78 | 0.85 | 0.85 |
| ATI | 290 | 12.1 | 13.7 | 10.8 | 0.78 | 0.79 | 0.83 |
| CAM | 362 | 12.1 | 8.4 | 9.7 | 0.86 | 0.90 | 0.88 |
| CCA | 359 | 9.8 | 5.4 | 6.0 | 0.83 | 0.95 | 0.95 |
| CHO | 303 | 9.7 | 12.8 | 9.6 | 0.68 | 0.80 | 0.73 |
| CUA | 360 | 12.5 | 14.5 | 11.7 | 0.65 | 0.74 | 0.71 |
| CUT | 336 | 16.6 | 12.1 | 15.3 | 0.54 | 0.70 | 0.66 |
| FAC | 357 | 13.1 | 12.4 | 12.1 | 0.77 | 0.80 | 0.82 |
| HGM | 356 | 10.7 | 6.7 | 8.5 | 0.88 | 0.95 | 0.91 |
| IZT | 351 | 11.2 | 7.4 | 8.9 | 0.87 | 0.94 | 0.91 |
| MER | 361 | 19.0 | 15.8 | 16.8 | 0.71 | 0.92 | 0.77 |
| MGH | 344 | 12.0 | 9.5 | 10.2 | 0.84 | 0.88 | 0.86 |
| MON | 96 | 10.0 | 18.3 | 9.3 | 0.49 | 0.59 | 0.48 |
| NEZ | 359 | 9.2 | 9.8 | 7.9 | 0.82 | 0.88 | 0.90 |
| PED | 349 | 9.8 | 5.5 | 5.5 | 0.84 | 0.96 | 0.96 |
| SAC | 350 | 11.0 | 10.0 | 8.6 | 0.79 | 0.87 | 0.87 |
| SAG | 358 | 32.9 | 13.4 | 37.3 | 0.52 | 0.86 | 0.56 |
| TLA | 312 | 17.0 | 14.8 | 13.8 | 0.79 | 0.89 | 0.86 |
| TLI | 354 | 10.8 | 10.7 | 9.6 | 0.77 | 0.86 | 0.85 |
| UAX | 200 | 9.7 | 10.4 | 8.7 | 0.75 | 0.79 | 0.83 |
| UIZ | 262 | 13.0 | 10.1 | 9.7 | 0.86 | 0.91 | 0.92 |
| VIF | 264 | 12.7 | 16.7 | 12.0 | 0.65 | 0.75 | 0.77 |
| XAL | 352 | 20.9 | 14.2 | 25.5 | 0.56 | 0.86 | 0.49 |

- RMSE ponderado: modelo 14.5, IDW 11.6, híbrido 14.0 ppb
- Parte constante (sesgo medio por estación, RMS): modelo 7.0, IDW 6.6, híbrido 7.2 ppb
- Parte que varía hora a hora (RMSE sin el sesgo): modelo 12.7, IDW 9.5, híbrido 12.1 ppb
- Modelo < IDW en 8 de 24 estaciones; híbrido < IDW en 13 de 24
