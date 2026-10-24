# Prueba con datos reales: inversión lineal, viento 'domain' (2023-11-01 a 2023-12-31)

- Horas: 366; observaciones de estación: 8,564; píxeles TEMPO: 78,227; σ obs: estaciones 15.0 ppb, TEMPO 5e+15; σθ viento 30°
- Festivos tratados como domingo: 2023-11-20, 2023-12-25

## 1. Ajuste en muestra

- Estaciones NOₓ: r = 0.78, RMSE = 12.6 ppb (media observada 30.8, desv. est. 19.9)
- TEMPO NO₂: r = 0.75

## 2. Emisión vial por tipo de día

IC 90 % por bootstrap de 61 días completos (200 réplicas).

| Tipo de día | Horas | Total vial (t/año equivalente) | IC 90 % |
|---|---|---|---|
| hábil | 246 | 40,627 | 35,253–46,475 |
| sábado | 54 | 31,991 | 28,468–39,195 |
| domingo/festivo | 66 | 17,094 | 14,214–20,084 |
| a priori (igual para todos) | | 99,292 | |

- sábado / hábil = **0.79** (IC 90 % 0.66–1.01)

- domingo/festivo / hábil = **0.42** (IC 90 % 0.34–0.53)

| Región | hábil | sábado | domingo/festivo |
|---|---|---|---|
| SO | -0.04 | -0.04 | -0.07 |
| S | 0.39 | 0.45 | 0.24 |
| SE | 0.23 | 0.16 | 0.14 |
| O | 0.54 | 0.50 | 0.15 |
| Centro | 0.73 | 0.32 | 0.27 |
| E | 0.15 | 0.42 | 0.03 |
| NO | 0.65 | 0.53 | 0.25 |
| N | 0.50 | 0.27 | 0.29 |
| NE | 0.39 | 0.21 | 0.21 |

(factor α respecto al a priori de la región; a priori 1 ± 0.5)

## 3. Fuentes puntuales

| Fuente | A priori t/año | A posteriori t/año |
|---|---|---|
| Nonoalco | 277 | 326 ± 46 |
| Valle de México (CC) + Valle de México (Vapor) | 2,615 | 316 ± 45 |
| AIFA (NLU) | 500 | -154 ± 42 |
| AICM (MEX) | 500 | 123 ± 51 |

## 4. Estación retenida (LOO)

Híbrido = modelo LOO + IDW de los residuos de las demás estaciones en la misma hora.

| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido | r modelo | r IDW | r híbrido |
|---|---|---|---|---|---|---|---|
| ACO | 141 | 9.0 | 13.0 | 7.8 | 0.59 | 0.57 | 0.64 |
| AJM | 361 | 11.5 | 9.3 | 9.2 | 0.73 | 0.85 | 0.84 |
| ATI | 290 | 12.4 | 13.6 | 11.5 | 0.76 | 0.78 | 0.82 |
| CAM | 362 | 12.2 | 9.0 | 9.0 | 0.89 | 0.90 | 0.90 |
| CCA | 359 | 10.3 | 5.5 | 5.4 | 0.81 | 0.95 | 0.95 |
| CHO | 303 | 10.6 | 12.5 | 10.6 | 0.66 | 0.80 | 0.72 |
| CUA | 360 | 12.9 | 14.3 | 12.6 | 0.64 | 0.73 | 0.71 |
| CUT | 336 | 15.2 | 12.3 | 13.7 | 0.53 | 0.69 | 0.65 |
| FAC | 357 | 14.0 | 12.9 | 11.2 | 0.78 | 0.79 | 0.83 |
| HGM | 356 | 11.2 | 6.5 | 6.4 | 0.90 | 0.95 | 0.95 |
| IZT | 351 | 11.5 | 7.3 | 7.5 | 0.89 | 0.95 | 0.94 |
| MER | 361 | 18.6 | 16.7 | 14.1 | 0.83 | 0.92 | 0.89 |
| MGH | 344 | 14.5 | 9.8 | 10.9 | 0.83 | 0.88 | 0.87 |
| MON | 96 | 13.0 | 17.7 | 11.9 | 0.51 | 0.61 | 0.55 |
| NEZ | 359 | 11.0 | 9.0 | 8.7 | 0.77 | 0.89 | 0.88 |
| PED | 349 | 11.0 | 5.7 | 5.6 | 0.80 | 0.96 | 0.95 |
| SAC | 350 | 12.7 | 10.0 | 9.8 | 0.72 | 0.87 | 0.85 |
| SAG | 358 | 17.2 | 10.7 | 17.8 | 0.73 | 0.87 | 0.79 |
| TLA | 312 | 18.6 | 15.4 | 14.8 | 0.84 | 0.88 | 0.88 |
| TLI | 354 | 10.3 | 10.6 | 9.8 | 0.79 | 0.85 | 0.86 |
| UAX | 200 | 10.5 | 10.5 | 10.0 | 0.72 | 0.78 | 0.80 |
| UIZ | 262 | 13.6 | 10.3 | 10.0 | 0.82 | 0.90 | 0.91 |
| VIF | 264 | 13.3 | 16.6 | 13.3 | 0.66 | 0.73 | 0.76 |
| XAL | 352 | 16.7 | 14.0 | 15.9 | 0.76 | 0.91 | 0.83 |

- RMSE ponderado: modelo 13.4, IDW 11.5, híbrido 11.2 ppb
- Parte constante (sesgo medio por estación, RMS): modelo 6.6, IDW 6.5, híbrido 5.6 ppb
- Parte que varía hora a hora (RMSE sin el sesgo): modelo 11.6, IDW 9.5, híbrido 9.7 ppb
- Modelo < IDW en 8 de 24 estaciones; híbrido < IDW en 18 de 24
