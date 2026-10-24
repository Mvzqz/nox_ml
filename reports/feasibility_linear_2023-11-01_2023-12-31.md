# Factibilidad: inversión lineal (2023-11-01 a 2023-12-31)

- Horas usadas: 366; cociente NO₂/NOₓ de la tarde: 0.77; σ obs nominal: estaciones 8.0 ppb, TEMPO 3e+15 molec/cm²
- Reducción = 1 − σ posterior / σ a priori (0 % = los datos no informan; 100 % = determinada). Error gemelo = mediana del error relativo de 50 gemelos.
- Pesimista: errores ×2 y verdad generada con viento perturbado (±20° y ±25 % de velocidad por hora).

| Fuente | A priori t/año | Solo estaciones: reducción / error gemelo | Estaciones + TEMPO: reducción / error gemelo | Estaciones + TEMPO, pesimista: reducción / error gemelo |
|---|---|---|---|---|
| Nonoalco | 277 | 62% / 17% | 91% / 4% | 83% / 82% |
| Valle de México (CC) + Valle de México (Vapor) | 2,615 | 84% / 14% | 99% / 1% | 98% / 17% |
| AIFA (NLU) | 500 | 57% / 46% | 98% / 3% | 96% / 13% |
| AICM (MEX) | 500 | 81% / 22% | 98% / 3% | 95% / 28% |
| Industria Naucalpan de Juárez (minerales no metálicos) | 231 | 39% / 41% | 88% / 8% | 77% / 202% |
| Industria Tlalnepantla de Baz (minerales no metálicos) | 212 | 37% / 36% | 86% / 12% | 73% / 175% |
| Industria Ecatepec de Morelos (minerales no metálicos) | 170 | 26% / 38% | 76% / 16% | 59% / 27% |
| Industria Iztacalco (minerales no metálicos) | 156 | 52% / 29% | 84% / 8% | 70% / 86% |
| Industria Tlalnepantla de Baz (minerales no metálicos) | 143 | 92% / 5% | 94% / 3% | 88% / 13% |
| Industria Azcapotzalco (minerales no metálicos) | 126 | 41% / 41% | 81% / 9% | 65% / 78% |
| Industria Iztapalapa (minerales no metálicos) | 119 | 84% / 8% | 88% / 7% | 76% / 16% |
| Industria Gustavo A. Madero (minerales no metálicos) | 117 | 17% / 38% | 79% / 15% | 61% / 193% |
| Industria Ecatepec de Morelos (química) | 106 | 74% / 22% | 81% / 11% | 64% / 33% |
| Industria Ecatepec de Morelos (minerales no metálicos) | 102 | 14% / 36% | 65% / 31% | 42% / 40% |
| Industria Tlalnepantla de Baz (equipo de transporte) | 95 | 34% / 33% | 73% / 15% | 51% / 352% |
| Industria Cuautitlán Izcalli (papel) | 94 | 4% / 30% | 71% / 13% | 49% / 112% |
| Vial región SO | 13,435 | 97% / 1% | 99% / 0% | 99% / 8% |
| Vial región S | 18,356 | 97% / 1% | 99% / 0% | 99% / 4% |
| Vial región SE | 9,290 | 91% / 3% | 99% / 0% | 98% / 9% |
| Vial región O | 16,167 | 96% / 1% | 99% / 0% | 98% / 4% |
| Vial región Centro | 14,969 | 97% / 1% | 99% / 0% | 98% / 8% |
| Vial región E | 5,360 | 82% / 6% | 99% / 0% | 98% / 10% |
| Vial región NO | 7,037 | 92% / 3% | 99% / 1% | 97% / 7% |
| Vial región N | 10,582 | 92% / 1% | 99% / 0% | 99% / 6% |
| Vial región NE | 4,096 | 71% / 14% | 98% / 1% | 96% / 14% |

| Escenario | Observaciones | DOFS de fuentes (de 25) |
|---|---|---|
| Solo estaciones | 7,537 | 19.7 |
| Estaciones + TEMPO | 85,764 | 24.5 |
| Estaciones + TEMPO, pesimista | 85,764 | 23.3 |

## Pares más confundidos (Estaciones + TEMPO; correlación a posteriori negativa = el modelo no sabe a cuál asignar)

| Fuente A | Fuente B | r |
|---|---|---|
| Industria Cuautitlán Izcalli (papel) | Vial región NO | -0.74 |
| Industria Ecatepec de Morelos (minerales no metálicos) | Industria Ecatepec de Morelos (minerales no metálicos) | -0.74 |
| Industria Naucalpan de Juárez (minerales no metálicos) | Vial región O | -0.61 |
| AICM (MEX) | Vial región Centro | -0.52 |
| Industria Iztacalco (minerales no metálicos) | Vial región S | -0.52 |
| Industria Gustavo A. Madero (minerales no metálicos) | Vial región Centro | -0.50 |
| Valle de México (CC) + Valle de México (Vapor) | Vial región NE | -0.47 |
| Industria Ecatepec de Morelos (minerales no metálicos) | Industria Ecatepec de Morelos (química) | -0.46 |
