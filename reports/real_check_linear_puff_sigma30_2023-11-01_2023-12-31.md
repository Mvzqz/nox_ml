# Prueba con datos reales: inversión lineal, viento 'puff' (2023-11-01 a 2023-12-31)

- Horas: 366; observaciones de estación: 7,537; píxeles TEMPO: 78,227; σ obs: estaciones 15.0 ppb, TEMPO 5e+15; σθ viento 30°
- Festivos tratados como domingo: 2023-11-20, 2023-12-25

## 1. Ajuste en muestra

- Estaciones NOₓ: r = 0.78, RMSE = 12.7 ppb (media observada 31.2, desv. est. 20.0)
- TEMPO NO₂: r = 0.84

## 2. Emisión vial por tipo de día

IC 90 % por bootstrap de 61 días completos (200 réplicas).

| Tipo de día | Horas | Total vial (t/año equivalente) | IC 90 % |
|---|---|---|---|
| hábil | 246 | 76,956 | 70,599–83,255 |
| sábado | 54 | 58,001 | 45,608–67,452 |
| domingo/festivo | 66 | 36,243 | 30,963–40,782 |
| a priori (igual para todos) | | 99,292 | |

- sábado / hábil = **0.75** (IC 90 % 0.60–0.90)

- domingo/festivo / hábil = **0.47** (IC 90 % 0.39–0.56)

| Región | hábil | sábado | domingo/festivo |
|---|---|---|---|
| SO | 0.53 | 0.40 | 0.22 |
| S | 0.82 | 0.64 | 0.44 |
| SE | 0.46 | 0.17 | 0.24 |
| O | 0.90 | 0.73 | 0.35 |
| Centro | 1.09 | 0.57 | 0.43 |
| E | 0.56 | 0.54 | 0.32 |
| NO | 0.96 | 0.81 | 0.48 |
| N | 0.70 | 0.65 | 0.39 |
| NE | 0.66 | 0.85 | 0.39 |

(factor α respecto al a priori de la región; a priori 1 ± 0.5)

## 3. Fuentes puntuales

| Fuente | A priori t/año | A posteriori t/año |
|---|---|---|
| Nonoalco | 277 | 276 ± 45 |
| Valle de México (CC) + Valle de México (Vapor) | 2,615 | 299 ± 44 |
| AIFA (NLU) | 500 | 70 ± 41 |
| AICM (MEX) | 500 | 441 ± 47 |
| Industria Naucalpan de Juárez (minerales no metálicos) | 231 | -111 ± 49 |
| Industria Tlalnepantla de Baz (minerales no metálicos) | 212 | 135 ± 52 |
| Industria Ecatepec de Morelos (minerales no metálicos) | 170 | 318 ± 61 |
| Industria Iztacalco (minerales no metálicos) | 156 | 146 ± 47 |
| Industria Tlalnepantla de Baz (minerales no metálicos) | 143 | 25 ± 17 |
| Industria Azcapotzalco (minerales no metálicos) | 126 | 769 ± 43 |
| Industria Iztapalapa (minerales no metálicos) | 119 | 385 ± 29 |
| Industria Gustavo A. Madero (minerales no metálicos) | 117 | 1,105 ± 45 |
| Industria Ecatepec de Morelos (química) | 106 | 33 ± 38 |
| Industria Ecatepec de Morelos (minerales no metálicos) | 102 | 124 ± 52 |
| Industria Tlalnepantla de Baz (equipo de transporte) | 95 | 541 ± 44 |
| Industria Cuautitlán Izcalli (papel) | 94 | -22 ± 45 |

## 4. Estación retenida (LOO)

Híbrido = modelo LOO + IDW de los residuos de las demás estaciones en la misma hora.

| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido | r modelo | r IDW | r híbrido |
|---|---|---|---|---|---|---|---|
| ACO | 141 | 6.9 | 13.2 | 6.5 | 0.60 | 0.60 | 0.64 |
| AJM | 361 | 12.0 | 9.2 | 10.5 | 0.78 | 0.85 | 0.85 |
| ATI | 290 | 12.3 | 13.7 | 10.8 | 0.77 | 0.79 | 0.83 |
| CAM | 362 | 10.9 | 8.4 | 9.0 | 0.87 | 0.90 | 0.89 |
| CCA | 359 | 9.8 | 5.4 | 6.0 | 0.83 | 0.95 | 0.95 |
| CHO | 303 | 10.1 | 12.8 | 10.0 | 0.66 | 0.80 | 0.71 |
| CUA | 360 | 12.5 | 14.5 | 11.7 | 0.65 | 0.74 | 0.71 |
| CUT | 336 | 16.9 | 12.1 | 15.8 | 0.54 | 0.70 | 0.65 |
| FAC | 357 | 12.2 | 12.4 | 10.5 | 0.80 | 0.80 | 0.85 |
| HGM | 356 | 10.9 | 6.7 | 8.5 | 0.87 | 0.95 | 0.91 |
| IZT | 351 | 11.5 | 7.4 | 8.6 | 0.87 | 0.94 | 0.92 |
| MER | 361 | 17.2 | 15.8 | 15.3 | 0.74 | 0.92 | 0.80 |
| MGH | 344 | 11.7 | 9.5 | 9.8 | 0.85 | 0.88 | 0.88 |
| MON | 96 | 9.3 | 18.3 | 8.8 | 0.49 | 0.59 | 0.46 |
| NEZ | 359 | 9.1 | 9.8 | 7.4 | 0.83 | 0.88 | 0.90 |
| PED | 349 | 9.6 | 5.5 | 5.3 | 0.85 | 0.96 | 0.96 |
| SAC | 350 | 11.0 | 10.0 | 8.6 | 0.79 | 0.87 | 0.88 |
| SAG | 358 | 25.7 | 13.4 | 29.1 | 0.61 | 0.86 | 0.66 |
| TLA | 312 | 23.7 | 14.8 | 22.4 | 0.40 | 0.89 | 0.50 |
| TLI | 354 | 10.8 | 10.7 | 9.6 | 0.77 | 0.86 | 0.85 |
| UAX | 200 | 9.9 | 10.4 | 8.7 | 0.73 | 0.79 | 0.81 |
| UIZ | 262 | 16.5 | 10.1 | 15.4 | 0.77 | 0.91 | 0.84 |
| VIF | 264 | 12.5 | 16.7 | 11.8 | 0.64 | 0.75 | 0.77 |
| XAL | 352 | 21.7 | 14.2 | 23.9 | 0.50 | 0.86 | 0.48 |

- RMSE ponderado: modelo 14.2, IDW 11.6, híbrido 13.4 ppb
- Parte constante (sesgo medio por estación, RMS): modelo 5.8, IDW 6.6, híbrido 6.0 ppb
- Parte que varía hora a hora (RMSE sin el sesgo): modelo 13.0, IDW 9.5, híbrido 12.0 ppb
- Modelo < IDW en 9 de 24 estaciones; híbrido < IDW en 13 de 24
