# Prueba con datos reales: inversión lineal, viento 'domain' (2023-11-01 a 2023-12-31)

- Horas: 366; observaciones de estación: 8,564; píxeles TEMPO: 78,227; σ obs: estaciones 15.0 ppb, TEMPO 2e+16 (×3); σθ viento 30°
- Festivos tratados como domingo: 2023-11-20, 2023-12-25

## 1. Ajuste en muestra

- Estaciones NOₓ: r = 0.78, RMSE = 12.5 ppb (media observada 30.8, desv. est. 19.9)
- TEMPO NO₂: r = 0.75

## 2. Emisión vial por tipo de día

IC 90 % por bootstrap de 61 días completos (100 réplicas).

| Tipo de día | Horas | Total vial (t/año equivalente) | IC 90 % |
|---|---|---|---|
| hábil | 246 | 43,227 | 37,623–47,505 |
| sábado | 54 | 34,313 | 30,065–41,423 |
| domingo/festivo | 66 | 17,799 | 15,044–20,348 |
| a priori (igual para todos) | | 99,292 | |

- sábado / hábil = **0.79** (IC 90 % 0.67–1.00)

- domingo/festivo / hábil = **0.41** (IC 90 % 0.34–0.50)

| Región | hábil | sábado | domingo/festivo |
|---|---|---|---|
| SO | 0.01 | 0.01 | -0.07 |
| S | 0.43 | 0.44 | 0.26 |
| SE | 0.26 | 0.20 | 0.14 |
| O | 0.62 | 0.54 | 0.18 |
| Centro | 0.61 | 0.29 | 0.23 |
| E | 0.24 | 0.50 | 0.07 |
| NO | 0.66 | 0.61 | 0.25 |
| N | 0.54 | 0.27 | 0.30 |
| NE | 0.50 | 0.34 | 0.26 |

(factor α respecto al a priori de la región; a priori 1 ± 0.5)

## 3. Fuentes puntuales

| Fuente | A priori t/año | A posteriori t/año |
|---|---|---|
| Nonoalco | 277 | 582 ± 115 |
| Valle de México (CC) + Valle de México (Vapor) | 2,615 | 322 ± 134 |
| AIFA (NLU) | 500 | -56 ± 124 |
| AICM (MEX) | 500 | 279 ± 142 |

## 4. Estación retenida (LOO)

Híbrido = modelo LOO + IDW de los residuos de las demás estaciones en la misma hora.

| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido | r modelo | r IDW | r híbrido |
|---|---|---|---|---|---|---|---|
| ACO | 141 | 9.2 | 13.0 | 8.2 | 0.59 | 0.57 | 0.63 |
| AJM | 361 | 11.4 | 9.3 | 9.2 | 0.73 | 0.85 | 0.84 |
| ATI | 290 | 12.4 | 13.6 | 11.5 | 0.76 | 0.78 | 0.82 |
| CAM | 362 | 12.3 | 9.0 | 9.2 | 0.89 | 0.90 | 0.90 |
| CCA | 359 | 10.2 | 5.5 | 5.4 | 0.81 | 0.95 | 0.95 |
| CHO | 303 | 10.6 | 12.5 | 10.6 | 0.66 | 0.80 | 0.72 |
| CUA | 360 | 13.0 | 14.3 | 12.7 | 0.64 | 0.73 | 0.71 |
| CUT | 336 | 15.3 | 12.3 | 13.9 | 0.53 | 0.69 | 0.65 |
| FAC | 357 | 13.7 | 12.9 | 11.2 | 0.78 | 0.79 | 0.83 |
| HGM | 356 | 11.2 | 6.5 | 6.5 | 0.90 | 0.95 | 0.95 |
| IZT | 351 | 11.6 | 7.3 | 7.6 | 0.89 | 0.95 | 0.94 |
| MER | 361 | 18.8 | 16.7 | 14.3 | 0.84 | 0.92 | 0.89 |
| MGH | 344 | 14.3 | 9.8 | 10.9 | 0.82 | 0.88 | 0.87 |
| MON | 96 | 13.2 | 17.7 | 12.4 | 0.52 | 0.61 | 0.55 |
| NEZ | 359 | 11.0 | 9.0 | 8.7 | 0.77 | 0.89 | 0.88 |
| PED | 349 | 10.9 | 5.7 | 5.6 | 0.80 | 0.96 | 0.95 |
| SAC | 350 | 12.6 | 10.0 | 9.8 | 0.73 | 0.87 | 0.85 |
| SAG | 358 | 17.0 | 10.7 | 17.7 | 0.73 | 0.87 | 0.79 |
| TLA | 312 | 18.3 | 15.4 | 14.5 | 0.83 | 0.88 | 0.88 |
| TLI | 354 | 10.4 | 10.6 | 9.9 | 0.79 | 0.85 | 0.86 |
| UAX | 200 | 10.4 | 10.5 | 10.0 | 0.72 | 0.78 | 0.81 |
| UIZ | 262 | 13.6 | 10.3 | 10.0 | 0.83 | 0.90 | 0.91 |
| VIF | 264 | 13.6 | 16.6 | 13.9 | 0.65 | 0.73 | 0.76 |
| XAL | 352 | 17.0 | 14.0 | 15.8 | 0.77 | 0.91 | 0.85 |

- RMSE ponderado: modelo 13.4, IDW 11.5, híbrido 11.3 ppb
- Parte constante (sesgo medio por estación, RMS): modelo 6.6, IDW 6.5, híbrido 5.7 ppb
- Parte que varía hora a hora (RMSE sin el sesgo): modelo 11.6, IDW 9.5, híbrido 9.7 ppb
- Modelo < IDW en 8 de 24 estaciones; híbrido < IDW en 18 de 24
