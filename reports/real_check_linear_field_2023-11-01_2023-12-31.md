# Prueba con datos reales: inversión lineal, viento 'field' (2023-11-01 a 2023-12-31)

- Horas: 366; observaciones de estación: 7,537; píxeles TEMPO: 78,227; σ obs: estaciones 15.0 ppb, TEMPO 5e+15
- Festivos tratados como domingo: 2023-11-20, 2023-12-25

## 1. Ajuste en muestra

- Estaciones NOₓ: r = 0.76, RMSE = 13.2 ppb (media observada 31.2, desv. est. 20.0)
- TEMPO NO₂: r = 0.73

## 2. Emisión vial por tipo de día

IC 90 % por bootstrap de 61 días completos (200 réplicas).

| Tipo de día | Horas | Total vial (t/año equivalente) | IC 90 % |
|---|---|---|---|
| hábil | 246 | 30,279 | 26,278–35,301 |
| sábado | 54 | 25,106 | 19,972–31,009 |
| domingo/festivo | 66 | 9,403 | 7,371–13,083 |
| a priori (igual para todos) | | 99,292 | |

- sábado / hábil = **0.83** (IC 90 % 0.61–1.06)

- domingo/festivo / hábil = **0.31** (IC 90 % 0.23–0.43)

| Región | hábil | sábado | domingo/festivo |
|---|---|---|---|
| SO | -0.12 | -0.12 | -0.14 |
| S | 0.51 | 0.54 | 0.25 |
| SE | 0.04 | 0.21 | 0.03 |
| O | 0.43 | 0.30 | 0.19 |
| Centro | 0.46 | 0.22 | 0.12 |
| E | 0.14 | 0.23 | -0.10 |
| NO | 0.47 | 0.57 | 0.17 |
| N | 0.44 | 0.17 | 0.20 |
| NE | -0.13 | -0.08 | -0.32 |

(factor α respecto al a priori de la región; a priori 1 ± 0.5)

## 3. Fuentes puntuales

| Fuente | A priori t/año | A posteriori t/año |
|---|---|---|
| Nonoalco | 277 | 354 ± 36 |
| Valle de México (CC) + Valle de México (Vapor) | 2,615 | 280 ± 34 |
| AIFA (NLU) | 500 | -159 ± 33 |
| AICM (MEX) | 500 | 412 ± 39 |
| Industria Naucalpan de Juárez (minerales no metálicos) | 231 | -475 ± 46 |
| Industria Tlalnepantla de Baz (minerales no metálicos) | 212 | -107 ± 48 |
| Industria Ecatepec de Morelos (minerales no metálicos) | 170 | 232 ± 58 |
| Industria Iztacalco (minerales no metálicos) | 156 | -536 ± 42 |
| Industria Tlalnepantla de Baz (minerales no metálicos) | 143 | 43 ± 14 |
| Industria Azcapotzalco (minerales no metálicos) | 126 | -29 ± 39 |
| Industria Iztapalapa (minerales no metálicos) | 119 | 170 ± 30 |
| Industria Gustavo A. Madero (minerales no metálicos) | 117 | 196 ± 40 |
| Industria Ecatepec de Morelos (química) | 106 | 135 ± 35 |
| Industria Ecatepec de Morelos (minerales no metálicos) | 102 | 108 ± 50 |
| Industria Tlalnepantla de Baz (equipo de transporte) | 95 | 106 ± 39 |
| Industria Cuautitlán Izcalli (papel) | 94 | 47 ± 43 |

## 4. Estación retenida (LOO)

Híbrido = modelo LOO + IDW de los residuos de las demás estaciones en la misma hora.

| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido | r modelo | r IDW | r híbrido |
|---|---|---|---|---|---|---|---|
| ACO | 141 | 9.8 | 13.2 | 8.8 | 0.57 | 0.60 | 0.64 |
| AJM | 361 | 11.2 | 9.2 | 8.8 | 0.73 | 0.85 | 0.85 |
| ATI | 290 | 12.4 | 13.7 | 12.0 | 0.76 | 0.79 | 0.82 |
| CAM | 362 | 12.3 | 8.4 | 8.5 | 0.88 | 0.90 | 0.90 |
| CCA | 359 | 10.8 | 5.4 | 5.9 | 0.79 | 0.95 | 0.94 |
| CHO | 303 | 10.8 | 12.8 | 11.0 | 0.65 | 0.80 | 0.71 |
| CUA | 360 | 13.2 | 14.5 | 13.7 | 0.63 | 0.74 | 0.71 |
| CUT | 336 | 14.5 | 12.1 | 12.9 | 0.57 | 0.70 | 0.68 |
| FAC | 357 | 15.7 | 12.4 | 11.4 | 0.82 | 0.80 | 0.85 |
| HGM | 356 | 11.9 | 6.7 | 7.9 | 0.87 | 0.95 | 0.93 |
| IZT | 351 | 12.9 | 7.4 | 8.9 | 0.87 | 0.94 | 0.91 |
| MER | 361 | 20.6 | 15.8 | 15.3 | 0.80 | 0.92 | 0.86 |
| MGH | 344 | 15.3 | 9.5 | 11.3 | 0.80 | 0.88 | 0.85 |
| MON | 96 | 14.2 | 18.3 | 14.1 | 0.48 | 0.59 | 0.53 |
| NEZ | 359 | 10.7 | 9.8 | 9.1 | 0.77 | 0.88 | 0.88 |
| PED | 349 | 11.4 | 5.5 | 5.9 | 0.78 | 0.96 | 0.95 |
| SAC | 350 | 11.9 | 10.0 | 9.3 | 0.77 | 0.87 | 0.88 |
| SAG | 358 | 17.6 | 13.4 | 20.9 | 0.66 | 0.86 | 0.75 |
| TLA | 312 | 18.9 | 14.8 | 15.0 | 0.72 | 0.89 | 0.79 |
| TLI | 354 | 10.7 | 10.7 | 10.5 | 0.78 | 0.86 | 0.86 |
| UAX | 200 | 10.6 | 10.4 | 10.0 | 0.70 | 0.79 | 0.80 |
| UIZ | 262 | 14.5 | 10.1 | 11.3 | 0.78 | 0.91 | 0.88 |
| VIF | 264 | 13.7 | 16.7 | 14.1 | 0.65 | 0.75 | 0.77 |
| XAL | 352 | 18.6 | 14.2 | 18.1 | 0.65 | 0.86 | 0.68 |

- RMSE ponderado: modelo 14.0, IDW 11.6, híbrido 12.0 ppb
- Parte constante (sesgo medio por estación, RMS): modelo 6.8, IDW 6.6, híbrido 5.9 ppb
- Parte que varía hora a hora (RMSE sin el sesgo): modelo 12.2, IDW 9.5, híbrido 10.4 ppb
- Modelo < IDW en 6 de 24 estaciones; híbrido < IDW en 13 de 24
