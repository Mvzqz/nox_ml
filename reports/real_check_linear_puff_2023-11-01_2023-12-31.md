# Prueba con datos reales: inversión lineal, viento 'puff' (2023-11-01 a 2023-12-31)

- Horas: 366; observaciones de estación: 7,537; píxeles TEMPO: 78,227; σ obs: estaciones 15.0 ppb, TEMPO 5e+15
- Festivos tratados como domingo: 2023-11-20, 2023-12-25

## 1. Ajuste en muestra

- Estaciones NOₓ: r = 0.75, RMSE = 13.3 ppb (media observada 31.2, desv. est. 20.0)
- TEMPO NO₂: r = 0.83

## 2. Emisión vial por tipo de día

IC 90 % por bootstrap de 61 días completos (200 réplicas).

| Tipo de día | Horas | Total vial (t/año equivalente) | IC 90 % |
|---|---|---|---|
| hábil | 246 | 66,160 | 60,694–71,794 |
| sábado | 54 | 50,243 | 40,003–58,201 |
| domingo/festivo | 66 | 30,944 | 26,648–35,090 |
| a priori (igual para todos) | | 99,292 | |

- sábado / hábil = **0.76** (IC 90 % 0.61–0.91)

- domingo/festivo / hábil = **0.47** (IC 90 % 0.39–0.56)

| Región | hábil | sábado | domingo/festivo |
|---|---|---|---|
| SO | 0.40 | 0.30 | 0.18 |
| S | 0.66 | 0.53 | 0.37 |
| SE | 0.39 | 0.15 | 0.20 |
| O | 0.78 | 0.65 | 0.30 |
| Centro | 1.01 | 0.52 | 0.39 |
| E | 0.54 | 0.52 | 0.30 |
| NO | 0.79 | 0.72 | 0.40 |
| N | 0.65 | 0.57 | 0.36 |
| NE | 0.45 | 0.68 | 0.27 |

(factor α respecto al a priori de la región; a priori 1 ± 0.5)

## 3. Fuentes puntuales

| Fuente | A priori t/año | A posteriori t/año |
|---|---|---|
| Nonoalco | 277 | 102 ± 38 |
| Valle de México (CC) + Valle de México (Vapor) | 2,615 | 321 ± 37 |
| AIFA (NLU) | 500 | -74 ± 34 |
| AICM (MEX) | 500 | 506 ± 39 |
| Industria Naucalpan de Juárez (minerales no metálicos) | 231 | -169 ± 42 |
| Industria Tlalnepantla de Baz (minerales no metálicos) | 212 | 71 ± 45 |
| Industria Ecatepec de Morelos (minerales no metálicos) | 170 | 333 ± 56 |
| Industria Iztacalco (minerales no metálicos) | 156 | 84 ± 39 |
| Industria Tlalnepantla de Baz (minerales no metálicos) | 143 | 18 ± 16 |
| Industria Azcapotzalco (minerales no metálicos) | 126 | 688 ± 36 |
| Industria Iztapalapa (minerales no metálicos) | 119 | 335 ± 25 |
| Industria Gustavo A. Madero (minerales no metálicos) | 117 | 1,223 ± 38 |
| Industria Ecatepec de Morelos (química) | 106 | -4 ± 33 |
| Industria Ecatepec de Morelos (minerales no metálicos) | 102 | 29 ± 48 |
| Industria Tlalnepantla de Baz (equipo de transporte) | 95 | 494 ± 39 |
| Industria Cuautitlán Izcalli (papel) | 94 | -54 ± 40 |

## 4. Estación retenida (LOO)

Híbrido = modelo LOO + IDW de los residuos de las demás estaciones en la misma hora.

| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido | r modelo | r IDW | r híbrido |
|---|---|---|---|---|---|---|---|
| ACO | 141 | 7.2 | 13.2 | 6.9 | 0.58 | 0.60 | 0.61 |
| AJM | 361 | 11.4 | 9.2 | 9.8 | 0.78 | 0.85 | 0.85 |
| ATI | 290 | 12.1 | 13.7 | 10.6 | 0.78 | 0.79 | 0.83 |
| CAM | 362 | 11.0 | 8.4 | 8.9 | 0.87 | 0.90 | 0.89 |
| CCA | 359 | 9.9 | 5.4 | 6.0 | 0.82 | 0.95 | 0.95 |
| CHO | 303 | 9.8 | 12.8 | 9.6 | 0.67 | 0.80 | 0.72 |
| CUA | 360 | 12.5 | 14.5 | 11.7 | 0.65 | 0.74 | 0.71 |
| CUT | 336 | 16.6 | 12.1 | 15.3 | 0.54 | 0.70 | 0.65 |
| FAC | 357 | 13.1 | 12.4 | 11.4 | 0.77 | 0.80 | 0.83 |
| HGM | 356 | 10.8 | 6.7 | 8.5 | 0.88 | 0.95 | 0.91 |
| IZT | 351 | 11.2 | 7.4 | 8.5 | 0.88 | 0.94 | 0.92 |
| MER | 361 | 19.0 | 15.8 | 16.6 | 0.72 | 0.92 | 0.78 |
| MGH | 344 | 11.9 | 9.5 | 10.0 | 0.84 | 0.88 | 0.87 |
| MON | 96 | 10.1 | 18.3 | 9.6 | 0.50 | 0.59 | 0.48 |
| NEZ | 359 | 9.2 | 9.8 | 7.4 | 0.82 | 0.88 | 0.90 |
| PED | 349 | 9.9 | 5.5 | 5.6 | 0.84 | 0.96 | 0.95 |
| SAC | 350 | 11.1 | 10.0 | 8.7 | 0.78 | 0.87 | 0.87 |
| SAG | 358 | 29.4 | 13.4 | 33.9 | 0.55 | 0.86 | 0.59 |
| TLA | 312 | 24.8 | 14.8 | 23.4 | 0.39 | 0.89 | 0.48 |
| TLI | 354 | 10.8 | 10.7 | 9.6 | 0.77 | 0.86 | 0.85 |
| UAX | 200 | 9.8 | 10.4 | 8.7 | 0.75 | 0.79 | 0.82 |
| UIZ | 262 | 18.5 | 10.1 | 17.5 | 0.71 | 0.91 | 0.79 |
| VIF | 264 | 12.6 | 16.7 | 12.2 | 0.65 | 0.75 | 0.77 |
| XAL | 352 | 25.0 | 14.2 | 28.3 | 0.44 | 0.86 | 0.40 |

- RMSE ponderado: modelo 15.1, IDW 11.6, híbrido 14.6 ppb
- Parte constante (sesgo medio por estación, RMS): modelo 6.2, IDW 6.6, híbrido 6.5 ppb
- Parte que varía hora a hora (RMSE sin el sesgo): modelo 13.7, IDW 9.5, híbrido 13.0 ppb
- Modelo < IDW en 8 de 24 estaciones; híbrido < IDW en 11 de 24
