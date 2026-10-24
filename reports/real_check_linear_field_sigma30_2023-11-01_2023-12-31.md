# Prueba con datos reales: inversión lineal, viento 'field' (2023-11-01 a 2023-12-31)

- Horas: 366; observaciones de estación: 7,537; píxeles TEMPO: 78,227; σ obs: estaciones 15.0 ppb, TEMPO 5e+15; σθ viento 30°
- Festivos tratados como domingo: 2023-11-20, 2023-12-25

## 1. Ajuste en muestra

- Estaciones NOₓ: r = 0.77, RMSE = 13.0 ppb (media observada 31.2, desv. est. 20.0)
- TEMPO NO₂: r = 0.75

## 2. Emisión vial por tipo de día

IC 90 % por bootstrap de 61 días completos (200 réplicas).

| Tipo de día | Horas | Total vial (t/año equivalente) | IC 90 % |
|---|---|---|---|
| hábil | 246 | 33,339 | 28,886–38,657 |
| sábado | 54 | 26,414 | 21,343–32,725 |
| domingo/festivo | 66 | 8,973 | 6,060–12,545 |
| a priori (igual para todos) | | 99,292 | |

- sábado / hábil = **0.79** (IC 90 % 0.60–1.03)

- domingo/festivo / hábil = **0.27** (IC 90 % 0.17–0.40)

| Región | hábil | sábado | domingo/festivo |
|---|---|---|---|
| SO | -0.21 | -0.19 | -0.21 |
| S | 0.58 | 0.61 | 0.28 |
| SE | 0.04 | 0.15 | 0.01 |
| O | 0.48 | 0.34 | 0.19 |
| Centro | 0.62 | 0.27 | 0.17 |
| E | -0.05 | 0.10 | -0.20 |
| NO | 0.52 | 0.64 | 0.16 |
| N | 0.46 | 0.19 | 0.24 |
| NE | -0.02 | -0.02 | -0.39 |

(factor α respecto al a priori de la región; a priori 1 ± 0.5)

## 3. Fuentes puntuales

| Fuente | A priori t/año | A posteriori t/año |
|---|---|---|
| Nonoalco | 277 | 523 ± 46 |
| Valle de México (CC) + Valle de México (Vapor) | 2,615 | 374 ± 44 |
| AIFA (NLU) | 500 | -340 ± 43 |
| AICM (MEX) | 500 | 620 ± 51 |
| Industria Naucalpan de Juárez (minerales no metálicos) | 231 | -136 ± 56 |
| Industria Tlalnepantla de Baz (minerales no metálicos) | 212 | 41 ± 57 |
| Industria Ecatepec de Morelos (minerales no metálicos) | 170 | 247 ± 65 |
| Industria Iztacalco (minerales no metálicos) | 156 | -377 ± 52 |
| Industria Tlalnepantla de Baz (minerales no metálicos) | 143 | 47 ± 16 |
| Industria Azcapotzalco (minerales no metálicos) | 126 | -30 ± 49 |
| Industria Iztapalapa (minerales no metálicos) | 119 | 251 ± 36 |
| Industria Gustavo A. Madero (minerales no metálicos) | 117 | 253 ± 49 |
| Industria Ecatepec de Morelos (química) | 106 | 165 ± 41 |
| Industria Ecatepec de Morelos (minerales no metálicos) | 102 | 32 ± 57 |
| Industria Tlalnepantla de Baz (equipo de transporte) | 95 | 292 ± 46 |
| Industria Cuautitlán Izcalli (papel) | 94 | 233 ± 51 |

## 4. Estación retenida (LOO)

Híbrido = modelo LOO + IDW de los residuos de las demás estaciones en la misma hora.

| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido | r modelo | r IDW | r híbrido |
|---|---|---|---|---|---|---|---|
| ACO | 141 | 9.7 | 13.2 | 8.5 | 0.57 | 0.60 | 0.64 |
| AJM | 361 | 11.1 | 9.2 | 8.9 | 0.74 | 0.85 | 0.85 |
| ATI | 290 | 12.3 | 13.7 | 11.8 | 0.76 | 0.79 | 0.82 |
| CAM | 362 | 12.1 | 8.4 | 8.5 | 0.88 | 0.90 | 0.90 |
| CCA | 359 | 10.9 | 5.4 | 5.6 | 0.79 | 0.95 | 0.95 |
| CHO | 303 | 10.5 | 12.8 | 10.7 | 0.66 | 0.80 | 0.71 |
| CUA | 360 | 13.0 | 14.5 | 13.4 | 0.63 | 0.74 | 0.71 |
| CUT | 336 | 14.8 | 12.1 | 13.2 | 0.55 | 0.70 | 0.67 |
| FAC | 357 | 15.7 | 12.4 | 11.6 | 0.82 | 0.80 | 0.85 |
| HGM | 356 | 11.5 | 6.7 | 7.5 | 0.87 | 0.95 | 0.93 |
| IZT | 351 | 12.1 | 7.4 | 8.3 | 0.88 | 0.94 | 0.92 |
| MER | 361 | 19.7 | 15.8 | 14.7 | 0.81 | 0.92 | 0.87 |
| MGH | 344 | 15.8 | 9.5 | 11.7 | 0.80 | 0.88 | 0.85 |
| MON | 96 | 13.7 | 18.3 | 13.3 | 0.46 | 0.59 | 0.51 |
| NEZ | 359 | 10.8 | 9.8 | 9.1 | 0.77 | 0.88 | 0.88 |
| PED | 349 | 11.5 | 5.5 | 5.7 | 0.78 | 0.96 | 0.95 |
| SAC | 350 | 11.6 | 10.0 | 9.0 | 0.78 | 0.87 | 0.89 |
| SAG | 358 | 17.8 | 13.4 | 20.3 | 0.69 | 0.86 | 0.77 |
| TLA | 312 | 18.2 | 14.8 | 14.5 | 0.72 | 0.89 | 0.80 |
| TLI | 354 | 10.7 | 10.7 | 10.3 | 0.78 | 0.86 | 0.86 |
| UAX | 200 | 10.7 | 10.4 | 10.1 | 0.70 | 0.79 | 0.80 |
| UIZ | 262 | 14.7 | 10.1 | 12.0 | 0.78 | 0.91 | 0.88 |
| VIF | 264 | 13.2 | 16.7 | 13.4 | 0.66 | 0.75 | 0.78 |
| XAL | 352 | 17.9 | 14.2 | 17.2 | 0.65 | 0.86 | 0.69 |

- RMSE ponderado: modelo 13.8, IDW 11.6, híbrido 11.7 ppb
- Parte constante (sesgo medio por estación, RMS): modelo 6.5, IDW 6.6, híbrido 5.6 ppb
- Parte que varía hora a hora (RMSE sin el sesgo): modelo 12.1, IDW 9.5, híbrido 10.3 ppb
- Modelo < IDW en 6 de 24 estaciones; híbrido < IDW en 14 de 24
