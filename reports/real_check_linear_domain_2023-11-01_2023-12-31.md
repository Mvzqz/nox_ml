# Prueba con datos reales: inversión lineal, viento 'domain' (2023-11-01 a 2023-12-31)

- Horas: 366; observaciones de estación: 7,537; píxeles TEMPO: 78,227; σ obs: estaciones 15.0 ppb, TEMPO 5e+15
- Festivos tratados como domingo: 2023-11-20, 2023-12-25

## 1. Ajuste en muestra

- Estaciones NOₓ: r = 0.77, RMSE = 12.9 ppb (media observada 31.2, desv. est. 20.0)
- TEMPO NO₂: r = 0.74

## 2. Emisión vial por tipo de día

IC 90 % por bootstrap de 61 días completos (200 réplicas).

| Tipo de día | Horas | Total vial (t/año equivalente) | IC 90 % |
|---|---|---|---|
| hábil | 246 | 34,902 | 30,304–40,084 |
| sábado | 54 | 26,675 | 21,957–32,753 |
| domingo/festivo | 66 | 13,540 | 10,920–16,440 |
| a priori (igual para todos) | | 99,292 | |

- sábado / hábil = **0.76** (IC 90 % 0.60–0.96)

- domingo/festivo / hábil = **0.39** (IC 90 % 0.31–0.50)

| Región | hábil | sábado | domingo/festivo |
|---|---|---|---|
| SO | 0.06 | 0.01 | -0.02 |
| S | 0.35 | 0.35 | 0.22 |
| SE | 0.23 | 0.16 | 0.15 |
| O | 0.38 | 0.37 | 0.09 |
| Centro | 0.44 | 0.18 | 0.08 |
| E | 0.39 | 0.56 | 0.17 |
| NO | 0.54 | 0.52 | 0.22 |
| N | 0.54 | 0.24 | 0.28 |
| NE | 0.26 | 0.19 | 0.08 |

(factor α respecto al a priori de la región; a priori 1 ± 0.5)

## 3. Fuentes puntuales

| Fuente | A priori t/año | A posteriori t/año |
|---|---|---|
| Nonoalco | 277 | 90 ± 40 |
| Valle de México (CC) + Valle de México (Vapor) | 2,615 | 300 ± 35 |
| AIFA (NLU) | 500 | -11 ± 32 |
| AICM (MEX) | 500 | 293 ± 41 |
| Industria Naucalpan de Juárez (minerales no metálicos) | 231 | -103 ± 46 |
| Industria Tlalnepantla de Baz (minerales no metálicos) | 212 | -91 ± 50 |
| Industria Ecatepec de Morelos (minerales no metálicos) | 170 | 155 ± 62 |
| Industria Iztacalco (minerales no metálicos) | 156 | -114 ± 41 |
| Industria Tlalnepantla de Baz (minerales no metálicos) | 143 | 50 ± 16 |
| Industria Azcapotzalco (minerales no metálicos) | 126 | 306 ± 38 |
| Industria Iztapalapa (minerales no metálicos) | 119 | 123 ± 26 |
| Industria Gustavo A. Madero (minerales no metálicos) | 117 | 903 ± 39 |
| Industria Ecatepec de Morelos (química) | 106 | 112 ± 35 |
| Industria Ecatepec de Morelos (minerales no metálicos) | 102 | 113 ± 53 |
| Industria Tlalnepantla de Baz (equipo de transporte) | 95 | 366 ± 41 |
| Industria Cuautitlán Izcalli (papel) | 94 | -47 ± 42 |

## 4. Estación retenida (LOO)

Híbrido = modelo LOO + IDW de los residuos de las demás estaciones en la misma hora.

| Estación | n | RMSE modelo | RMSE IDW | RMSE híbrido | r modelo | r IDW | r híbrido |
|---|---|---|---|---|---|---|---|
| ACO | 141 | 9.1 | 13.2 | 8.4 | 0.59 | 0.60 | 0.64 |
| AJM | 361 | 11.5 | 9.2 | 9.1 | 0.72 | 0.85 | 0.84 |
| ATI | 290 | 12.3 | 13.7 | 11.4 | 0.76 | 0.79 | 0.83 |
| CAM | 362 | 12.4 | 8.4 | 8.6 | 0.88 | 0.90 | 0.90 |
| CCA | 359 | 10.4 | 5.4 | 5.6 | 0.80 | 0.95 | 0.95 |
| CHO | 303 | 10.9 | 12.8 | 10.9 | 0.65 | 0.80 | 0.72 |
| CUA | 360 | 12.8 | 14.5 | 12.8 | 0.64 | 0.74 | 0.72 |
| CUT | 336 | 14.9 | 12.1 | 13.2 | 0.55 | 0.70 | 0.67 |
| FAC | 357 | 14.7 | 12.4 | 11.2 | 0.78 | 0.80 | 0.84 |
| HGM | 356 | 11.6 | 6.7 | 6.8 | 0.90 | 0.95 | 0.94 |
| IZT | 351 | 12.0 | 7.4 | 7.8 | 0.88 | 0.94 | 0.93 |
| MER | 361 | 19.9 | 15.8 | 14.6 | 0.82 | 0.92 | 0.88 |
| MGH | 344 | 13.6 | 9.5 | 10.0 | 0.84 | 0.88 | 0.88 |
| MON | 96 | 14.0 | 18.3 | 14.0 | 0.53 | 0.59 | 0.56 |
| NEZ | 359 | 11.0 | 9.8 | 9.0 | 0.77 | 0.88 | 0.89 |
| PED | 349 | 10.9 | 5.5 | 5.5 | 0.80 | 0.96 | 0.96 |
| SAC | 350 | 12.7 | 10.0 | 9.6 | 0.73 | 0.87 | 0.86 |
| SAG | 358 | 15.1 | 13.4 | 19.0 | 0.72 | 0.86 | 0.79 |
| TLA | 312 | 26.0 | 14.8 | 24.0 | 0.35 | 0.89 | 0.45 |
| TLI | 354 | 10.3 | 10.7 | 9.9 | 0.80 | 0.86 | 0.87 |
| UAX | 200 | 10.6 | 10.4 | 10.0 | 0.72 | 0.79 | 0.81 |
| UIZ | 262 | 14.9 | 10.1 | 11.7 | 0.77 | 0.91 | 0.88 |
| VIF | 264 | 13.9 | 16.7 | 14.4 | 0.66 | 0.75 | 0.77 |
| XAL | 352 | 19.0 | 14.2 | 18.6 | 0.64 | 0.86 | 0.66 |

- RMSE ponderado: modelo 14.1, IDW 11.6, híbrido 12.2 ppb
- Parte constante (sesgo medio por estación, RMS): modelo 6.2, IDW 6.6, híbrido 5.5 ppb
- Parte que varía hora a hora (RMSE sin el sesgo): modelo 12.7, IDW 9.5, híbrido 11.0 ppb
- Modelo < IDW en 7 de 24 estaciones; híbrido < IDW en 13 de 24
