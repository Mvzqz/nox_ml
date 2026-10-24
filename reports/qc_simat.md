# QC SIMAT 2023–2024

## NO / NO₂ / NOₓ (RAMA)

- ✅ Códigos de estación en catálogo (desconocidos: ninguno)
- ✅ Unidades NO/NO₂/NOₓ: ['ppb']
- ✅ Filas duplicadas estación-parámetro-hora: 0
- ✅ Valores negativos: 0
- ℹ️ Horas > 250 ppb (se marcan, no se borran): NO=299, NO₂=0, NOₓ=810
- ✅ NOₓ ≈ NO + NO₂: mediana dif. 0.0%, 7.1% de horas con dif > 5 %
- ❌ Horas NOₓ en rachas > 6 h con valor idéntico: 59 (ACO:9, MON:14, PED:7, TAH:29)
- ✅ Pico matutino de NOₓ entre 07 y 09 h en todos los meses (fuera: ninguno)
- ✅ Domingo (27.5 ppb) < hábiles (38.5 ppb)
- ✅ Tráfico {'MER': np.float64(55.0), 'CAM': np.float64(50.6)} > periféricas {'AJM': np.float64(19.1), 'CUA': np.float64(23.1)}
- ℹ️ Estaciones del catálogo dentro del dominio: 65

### Estaciones NOₓ válidas (≥ 75 % de horas 12–17 h) por mes de temporada seca

| Mes | Estaciones válidas | Estaciones con datos |
|---|---|---|
| 2023-01 | 20 | 23 |
| 2023-02 | 20 | 23 |
| 2023-03 | 16 | 22 |
| 2023-04 | 14 | 20 |
| 2023-05 | 12 | 20 |
| 2023-11 | 20 | 24 |
| 2023-12 | 19 | 22 |
| 2024-01 | 18 | 20 |
| 2024-02 | 19 | 22 |
| 2024-03 | 17 | 22 |
| 2024-04 | 16 | 22 |
| 2024-05 | 18 | 21 |
| 2024-11 | 19 | 22 |
| 2024-12 | 18 | 22 |

## Viento (REDMET)

- ✅ Unidades: WSP ['m/s'], WDR ['°']
- ⚠️ Corrección aplicada: WSP de 2024 ÷ 2.237 (142,690 filas; original en WSP_raw)
- ✅ Dirección en [0, 360]: rango 0.0–360.0
- ✅ Mediana horaria WSP entre 1 y 4 m/s en 86% de las horas (mediana global 1.75)
- ℹ️ Calmas (< 0.5 m/s): 4.5% de las horas válidas

### Horas 12–17 h con ≥ 10 estaciones de viento válidas (dominio)

| Mes | % horas OK | Mediana estaciones |
|---|---|---|
| 2023-01 | 100% | 20 |
| 2023-02 | 100% | 22 |
| 2023-03 | 100% | 22 |
| 2023-04 | 100% | 20 |
| 2023-05 | 100% | 20 |
| 2023-11 | 100% | 18 |
| 2023-12 | 100% | 17 |
| 2024-01 | 95% | 13 |
| 2024-02 | 96% | 12 |
| 2024-03 | 98% | 13 |
| 2024-04 | 98% | 13 |
| 2024-05 | 91% | 12 |
| 2024-11 | 100% | 16 |
| 2024-12 | 100% | 15 |

- ℹ️ Dirección vectorial media de la tarde (de dónde viene): 51° — contrastar con ERA5
