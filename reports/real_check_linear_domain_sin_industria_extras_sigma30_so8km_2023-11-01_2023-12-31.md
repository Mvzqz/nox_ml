# Prueba con datos reales: inversión lineal, viento 'domain' (2023-11-01 a 2023-12-31)

- Horas: 366; observaciones de estación: 8,564; píxeles TEMPO: 11,349; σ obs: estaciones 15.0 ppb, TEMPO 1.5e+16 (×3) — no aplica: superobservaciones de 8 km con σ² = (2.6e+15)² + (5e+15)²/n; σθ viento 30°
- Festivos tratados como domingo: 2023-11-20, 2023-12-25

## 1. Ajuste en muestra

- Estaciones NOₓ: r = 0.78, RMSE = 12.5 ppb (media observada 30.8, desv. est. 19.9)
- TEMPO NO₂: r = 0.76

## 2. Emisión vial por tipo de día

IC 90 % por bootstrap de 61 días completos (100 réplicas).

| Tipo de día | Horas | Total vial (t/año equivalente) | IC 90 % |
|---|---|---|---|
| hábil | 246 | 39,594 | 34,773–44,291 |
| sábado | 54 | 30,701 | 27,107–38,360 |
| domingo/festivo | 66 | 16,258 | 13,122–19,275 |
| a priori (igual para todos) | | 99,292 | |

- sábado / hábil = **0.78** (IC 90 % 0.64–0.99)

- domingo/festivo / hábil = **0.41** (IC 90 % 0.32–0.51)

| Región | hábil | sábado | domingo/festivo |
|---|---|---|---|
| SO | -0.05 | -0.06 | -0.09 |
| S | 0.40 | 0.46 | 0.27 |
| SE | 0.23 | 0.15 | 0.12 |
| O | 0.55 | 0.53 | 0.16 |
| Centro | 0.64 | 0.24 | 0.21 |
| E | 0.20 | 0.47 | 0.04 |
| NO | 0.60 | 0.47 | 0.20 |
| N | 0.52 | 0.29 | 0.29 |
| NE | 0.42 | 0.20 | 0.22 |

(factor α respecto al a priori de la región; a priori 1 ± 0.5)

## 3. Fuentes puntuales

| Fuente | A priori t/año | A posteriori t/año |
|---|---|---|
| Nonoalco | 277 | 769 ± 99 |
| Valle de México (CC) + Valle de México (Vapor) | 2,615 | 269 ± 118 |
| AIFA (NLU) | 500 | -212 ± 97 |
| AICM (MEX) | 500 | 261 ± 132 |

## 4. Estación retenida (LOO)

Híbrido = modelo LOO + IDW de los residuos de las demás estaciones en la misma hora.

| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido | r modelo | r IDW | r híbrido |
|---|---|---|---|---|---|---|---|
| ACO | 141 | 9.2 | 13.0 | 8.2 | 0.59 | 0.57 | 0.63 |
| AJM | 361 | 11.5 | 9.3 | 9.2 | 0.73 | 0.85 | 0.83 |
| ATI | 290 | 12.4 | 13.6 | 11.5 | 0.76 | 0.78 | 0.82 |
| CAM | 362 | 12.3 | 9.0 | 9.1 | 0.89 | 0.90 | 0.90 |
| CCA | 359 | 10.3 | 5.5 | 5.4 | 0.81 | 0.95 | 0.95 |
| CHO | 303 | 10.6 | 12.5 | 10.6 | 0.67 | 0.80 | 0.72 |
| CUA | 360 | 12.9 | 14.3 | 12.7 | 0.64 | 0.73 | 0.71 |
| CUT | 336 | 15.1 | 12.3 | 13.6 | 0.54 | 0.69 | 0.65 |
| FAC | 357 | 13.9 | 12.9 | 11.2 | 0.78 | 0.79 | 0.83 |
| HGM | 356 | 11.1 | 6.5 | 6.4 | 0.90 | 0.95 | 0.95 |
| IZT | 351 | 11.5 | 7.3 | 7.5 | 0.89 | 0.95 | 0.94 |
| MER | 361 | 18.6 | 16.7 | 14.1 | 0.84 | 0.92 | 0.89 |
| MGH | 344 | 14.6 | 9.8 | 11.1 | 0.83 | 0.88 | 0.87 |
| MON | 96 | 13.3 | 17.7 | 12.4 | 0.52 | 0.61 | 0.55 |
| NEZ | 359 | 11.0 | 9.0 | 8.7 | 0.77 | 0.89 | 0.88 |
| PED | 349 | 11.0 | 5.7 | 5.6 | 0.80 | 0.96 | 0.95 |
| SAC | 350 | 12.6 | 10.0 | 9.8 | 0.73 | 0.87 | 0.85 |
| SAG | 358 | 16.8 | 10.7 | 17.5 | 0.73 | 0.87 | 0.79 |
| TLA | 312 | 18.5 | 15.4 | 14.7 | 0.83 | 0.88 | 0.88 |
| TLI | 354 | 10.3 | 10.6 | 9.8 | 0.79 | 0.85 | 0.86 |
| UAX | 200 | 10.5 | 10.5 | 10.1 | 0.72 | 0.78 | 0.80 |
| UIZ | 262 | 13.6 | 10.3 | 10.0 | 0.82 | 0.90 | 0.91 |
| VIF | 264 | 13.7 | 16.6 | 13.9 | 0.65 | 0.73 | 0.76 |
| XAL | 352 | 16.8 | 14.0 | 15.7 | 0.77 | 0.91 | 0.85 |

- RMSE ponderado: modelo 13.4, IDW 11.5, híbrido 11.2 ppb
- Parte constante (sesgo medio por estación, RMS): modelo 6.6, IDW 6.5, híbrido 5.6 ppb
- Parte que varía hora a hora (RMSE sin el sesgo): modelo 11.6, IDW 9.5, híbrido 9.7 ppb
- Modelo < IDW en 7 de 24 estaciones; híbrido < IDW en 18 de 24
