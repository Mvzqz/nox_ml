# Centrales: hipótesis de pluma fresca (nov–dic 2023, σθ = 30°)

Cociente urbano NO₂/NOₓ de la tarde: 0.77; O₃ mediano 12–17 h: 48 ppb; r0 = 0.1.

## Cociente NO₂/NOₓ efectivo de la pluma en los píxeles TEMPO (promedio ponderado por sensibilidad)

| Variante | Valle de México | Nonoalco |
|---|---|---|
| uniforme | 0.77 | 0.77 |
| olm | 0.76 | 0.77 |
| lenta | 0.73 | 0.73 |
| extrema | 0.25 | 0.25 |

## Datos reales

| Variante | A priori | Valle de México | Nonoalco | AICM | AIFA | Vial / inventario | RMSE LOO modelo / híbrido (ppb) | TEMPO r | Domingo/hábil |
|---|---|---|---|---|---|---|---|---|---|
| cociente urbano también para las centrales (actual) | corregido | 320 ± 45 | 287 ± 42 | 117 ± 51 | -153 ± 42 | 41% | 13.4 / 11.2 | 0.75 | 0.42 (0.33–0.53) |
| cociente urbano también para las centrales (actual) | débil (solo datos) | 316 ± 45 | 326 ± 46 | 123 ± 51 | -154 ± 42 | 41% | 13.4 / 11.2 | 0.75 | 0.42 (0.33–0.53) |
| ozono limitante, pluma instantánea | corregido | 313 ± 51 | 285 ± 42 | 117 ± 51 | -155 ± 42 | 41% | 13.4 / 11.2 | 0.75 | 0.42 (0.33–0.53) |
| ozono limitante, pluma instantánea | débil (solo datos) | 307 ± 51 | 324 ± 46 | 123 ± 51 | -156 ± 42 | 41% | 13.4 / 11.2 | 0.75 | 0.42 (0.33–0.53) |
| ozono limitante + conversión lenta (τ = 20 min) | corregido | 326 ± 57 | -89 ± 51 | 70 ± 51 | -147 ± 42 | 41% | 13.4 / 11.2 | 0.75 | 0.43 (0.34–0.54) |
| ozono limitante + conversión lenta (τ = 20 min) | débil (solo datos) | 312 ± 57 | -155 ± 59 | 62 ± 51 | -147 ± 42 | 42% | 13.4 / 11.3 | 0.75 | 0.43 (0.34–0.54) |
| 0.25 fijo (cota no física) | corregido | 981 ± 136 | 534 ± 79 | 105 ± 51 | -151 ± 42 | 41% | 13.4 / 11.2 | 0.75 | 0.42 (0.34–0.53) |
| 0.25 fijo (cota no física) | débil (solo datos) | 989 ± 139 | 1,233 ± 128 | 138 ± 51 | -156 ± 42 | 41% | 13.4 / 11.2 | 0.75 | 0.42 (0.33–0.53) |

## Gemelo (verdad: a posteriori real con Valle 1,600 y Nonoalco 100 t/año; 20 realizaciones de ruido)

| Verdad generada con | Invertida con | A priori | Valle de México (mediana, P5–P95) | σ posterior | Nonoalco | Vial / verdad |
|---|---|---|---|---|---|---|
| olm | uniforme | corregido | 1,313 (1,231–1,358) | 45 | 71 | 1.03 |
| olm | uniforme | débil (solo datos) | 1,283 (1,197–1,393) | 45 | 64 | 1.03 |
| olm | olm | corregido | 1,571 (1,498–1,654) | 51 | 79 | 1.01 |
| olm | olm | débil (solo datos) | 1,560 (1,504–1,697) | 51 | 96 | 1.01 |
| lenta | uniforme | corregido | 1,146 (1,089–1,204) | 45 | 46 | 1.04 |
| lenta | uniforme | débil (solo datos) | 1,114 (1,040–1,182) | 45 | 25 | 1.04 |
| lenta | lenta | corregido | 1,581 (1,457–1,610) | 57 | 73 | 1.01 |
| lenta | lenta | débil (solo datos) | 1,582 (1,485–1,660) | 57 | 57 | 1.02 |
| extrema | uniforme | corregido | 508 (453–549) | 45 | 34 | 1.01 |
| extrema | uniforme | débil (solo datos) | 498 (453–569) | 45 | 27 | 1.01 |
| extrema | extrema | corregido | 1,652 (1,411–1,871) | 136 | 153 | 1.01 |
| extrema | extrema | débil (solo datos) | 1,599 (1,418–1,787) | 139 | 238 | 1.01 |

Valores en t/año (a posteriori ± σ). Ver reports/centrales_generacion.md.
