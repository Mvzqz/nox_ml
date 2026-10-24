# Prueba con datos reales: inversión lineal, viento 'domain' (2023-11-01 a 2023-12-31)

- Horas: 366; observaciones de estación: 7,537; píxeles TEMPO: 78,227; σ obs: estaciones 15.0 ppb, TEMPO 5e+15; σθ viento 30°
- Festivos tratados como domingo: 2023-11-20, 2023-12-25

## 1. Ajuste en muestra

- Estaciones NOₓ: r = 0.78, RMSE = 12.6 ppb (media observada 31.2, desv. est. 20.0)
- TEMPO NO₂: r = 0.75

## 2. Emisión vial por tipo de día

IC 90 % por bootstrap de 61 días completos (200 réplicas).

| Tipo de día | Horas | Total vial (t/año equivalente) | IC 90 % |
|---|---|---|---|
| hábil | 246 | 36,939 | 32,018–42,259 |
| sábado | 54 | 27,855 | 23,524–34,341 |
| domingo/festivo | 66 | 13,090 | 10,048–16,357 |
| a priori (igual para todos) | | 99,292 | |

- sábado / hábil = **0.75** (IC 90 % 0.60–0.97)

- domingo/festivo / hábil = **0.35** (IC 90 % 0.27–0.47)

| Región | hábil | sábado | domingo/festivo |
|---|---|---|---|
| SO | 0.00 | -0.03 | -0.05 |
| S | 0.40 | 0.41 | 0.24 |
| SE | 0.23 | 0.14 | 0.13 |
| O | 0.40 | 0.39 | 0.04 |
| Centro | 0.58 | 0.19 | 0.13 |
| E | 0.19 | 0.54 | 0.06 |
| NO | 0.61 | 0.50 | 0.24 |
| N | 0.49 | 0.26 | 0.27 |
| NE | 0.43 | 0.24 | 0.16 |

(factor α respecto al a priori de la región; a priori 1 ± 0.5)

## 3. Fuentes puntuales

| Fuente | A priori t/año | A posteriori t/año |
|---|---|---|
| Nonoalco | 277 | 359 ± 49 |
| Valle de México (CC) + Valle de México (Vapor) | 2,615 | 391 ± 45 |
| AIFA (NLU) | 500 | -201 ± 41 |
| AICM (MEX) | 500 | 351 ± 52 |
| Industria Naucalpan de Juárez (minerales no metálicos) | 231 | 32 ± 55 |
| Industria Tlalnepantla de Baz (minerales no metálicos) | 212 | 86 ± 59 |
| Industria Ecatepec de Morelos (minerales no metálicos) | 170 | 157 ± 66 |
| Industria Iztacalco (minerales no metálicos) | 156 | 99 ± 50 |
| Industria Tlalnepantla de Baz (minerales no metálicos) | 143 | 70 ± 17 |
| Industria Azcapotzalco (minerales no metálicos) | 126 | 482 ± 47 |
| Industria Iztapalapa (minerales no metálicos) | 119 | 131 ± 31 |
| Industria Gustavo A. Madero (minerales no metálicos) | 117 | 957 ± 48 |
| Industria Ecatepec de Morelos (química) | 106 | 110 ± 40 |
| Industria Ecatepec de Morelos (minerales no metálicos) | 102 | 116 ± 57 |
| Industria Tlalnepantla de Baz (equipo de transporte) | 95 | 655 ± 48 |
| Industria Cuautitlán Izcalli (papel) | 94 | 52 ± 49 |

## 4. Estación retenida (LOO)

Híbrido = modelo LOO + IDW de los residuos de las demás estaciones en la misma hora.

| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido | r modelo | r IDW | r híbrido |
|---|---|---|---|---|---|---|---|
| ACO | 141 | 9.2 | 13.2 | 8.4 | 0.59 | 0.60 | 0.65 |
| AJM | 361 | 11.4 | 9.2 | 9.0 | 0.73 | 0.85 | 0.84 |
| ATI | 290 | 12.4 | 13.7 | 11.3 | 0.76 | 0.79 | 0.83 |
| CAM | 362 | 11.9 | 8.4 | 8.4 | 0.89 | 0.90 | 0.90 |
| CCA | 359 | 10.3 | 5.4 | 5.5 | 0.81 | 0.95 | 0.95 |
| CHO | 303 | 10.7 | 12.8 | 10.7 | 0.66 | 0.80 | 0.72 |
| CUA | 360 | 12.7 | 14.5 | 12.6 | 0.65 | 0.74 | 0.72 |
| CUT | 336 | 15.1 | 12.1 | 13.4 | 0.54 | 0.70 | 0.66 |
| FAC | 357 | 14.6 | 12.4 | 11.1 | 0.79 | 0.80 | 0.84 |
| HGM | 356 | 11.2 | 6.7 | 6.7 | 0.90 | 0.95 | 0.95 |
| IZT | 351 | 11.5 | 7.4 | 7.5 | 0.88 | 0.94 | 0.94 |
| MER | 361 | 18.7 | 15.8 | 13.6 | 0.83 | 0.92 | 0.89 |
| MGH | 344 | 14.2 | 9.5 | 10.5 | 0.83 | 0.88 | 0.88 |
| MON | 96 | 13.3 | 18.3 | 13.0 | 0.50 | 0.59 | 0.52 |
| NEZ | 359 | 11.0 | 9.8 | 9.0 | 0.77 | 0.88 | 0.89 |
| PED | 349 | 10.9 | 5.5 | 5.4 | 0.80 | 0.96 | 0.96 |
| SAC | 350 | 12.7 | 10.0 | 9.5 | 0.73 | 0.87 | 0.86 |
| SAG | 358 | 15.7 | 13.4 | 19.1 | 0.73 | 0.86 | 0.79 |
| TLA | 312 | 28.9 | 14.8 | 27.9 | 0.24 | 0.89 | 0.34 |
| TLI | 354 | 10.2 | 10.7 | 9.7 | 0.80 | 0.86 | 0.87 |
| UAX | 200 | 10.5 | 10.4 | 10.0 | 0.72 | 0.79 | 0.81 |
| UIZ | 262 | 13.9 | 10.1 | 10.6 | 0.80 | 0.91 | 0.90 |
| VIF | 264 | 13.4 | 16.7 | 13.7 | 0.66 | 0.75 | 0.78 |
| XAL | 352 | 18.0 | 14.2 | 17.7 | 0.66 | 0.86 | 0.69 |

- RMSE ponderado: modelo 14.1, IDW 11.6, híbrido 12.4 ppb
- Parte constante (sesgo medio por estación, RMS): modelo 5.9, IDW 6.6, híbrido 5.3 ppb
- Parte que varía hora a hora (RMSE sin el sesgo): modelo 12.8, IDW 9.5, híbrido 11.2 ppb
- Modelo < IDW en 7 de 24 estaciones; híbrido < IDW en 15 de 24
