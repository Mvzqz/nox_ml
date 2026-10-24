# Prueba rápida: química NO–NO₂–O₃ y la caída de primavera de TEMPO

Tardes 12–17 h, 15 feb–31 may 2024. Medianas por mes de todas las estaciones de SIMAT con NO, NO₂, NOₓ y O₃; columna TEMPO en píxeles válidos a < ~3 km de cada estación, emparejada por hora con el NO₂ de superficie. Onda corta: ERA5 (Open-Meteo) en el centro. j(NO₂) implícito por el estado fotoestacionario j = k[O₃][NO]/[NO₂] (k a 780 hPa). Script: `scripts/multifisica_leighton.py`.

## Valores por mes

|    |   NO2/NOx sup |   O3 (ppb) |   NOx sup (ppb) |   j(NO2) impl (1/s) |   onda corta (W/m²) |   capa límite (m) |   columna/sup (1e14) |   columna TEMPO (1e15) |
|---:|--------------:|-----------:|----------------:|--------------------:|--------------------:|------------------:|---------------------:|-----------------------:|
|  2 |         0.877 |       72.5 |              20 |               0.003 |             778.822 |           2162.41 |                7.467 |                 13.72  |
|  3 |         0.9   |       72   |              15 |               0.003 |             844.435 |           2403.79 |                6.705 |                  8.508 |
|  4 |         0.909 |       80   |              14 |               0.003 |             797.361 |           2643.14 |                6.462 |                  8.021 |
|  5 |         0.929 |       97   |              14 |               0.003 |             798.065 |           2934.31 |                6.958 |                  8.889 |

## Relativo a febrero

|    |   NO2/NOx sup |   O3 (ppb) |   NOx sup (ppb) |   j(NO2) impl (1/s) |   onda corta (W/m²) |   capa límite (m) |   columna/sup (1e14) |   columna TEMPO (1e15) |
|---:|--------------:|-----------:|----------------:|--------------------:|--------------------:|------------------:|---------------------:|-----------------------:|
|  2 |          1    |       1    |            1    |                1    |                1    |              1    |                 1    |                   1    |
|  3 |          1.03 |       0.99 |            0.75 |                0.84 |                1.08 |              1.11 |                 0.9  |                   0.62 |
|  4 |          1.04 |       1.1  |            0.7  |                0.8  |                1.02 |              1.22 |                 0.87 |                   0.58 |
|  5 |          1.06 |       1.34 |            0.7  |                0.79 |                1.02 |              1.36 |                 0.93 |                   0.65 |

Caída del exceso de columna TEMPO respecto a febrero (de `placebo_tempo.md`): marzo 0.81, abril 0.70, mayo 0.67; el modelo inerte da 0.98–1.07.
## Lectura

- **La partición NO₂/NOₓ no explica la caída: va al revés.** En superficie el cociente sube 3–6 % de febrero a mayo (más O₃: 72 → 97 ppb). Una química de Leighton con O₃ medido haría que TEMPO viera *más* NO₂, no menos.
- **La caída también está en superficie.** El NOₓ de las estaciones por la tarde baja a 0.70–0.75 de febrero, igual que la columna. El modelo inerte con emisión fija no la reproduce. Así que comparar estaciones entre temporadas tiene el mismo problema; el estimador que pasó el placebo 2019 lo evita porque compara el mismo periodo de dos años.
- **No es dilución vertical.** Si el NOₓ solo se mezclara en una capa más alta (la capa límite crece 36 %), la superficie bajaría pero la columna no, y el cociente columna/superficie subiría ~1.36. Se queda en 0.87–0.93. Lo que baja es la **masa** de NOₓ en la columna.
- **La explicación más probable es una vida química más corta** (más OH en la temporada de ozono). El j(NO₂) implícito por el estado fotoestacionario baja 20 % con la radiación de onda corta constante. Eso indica más radicales peróxido convirtiendo NO en NO₂, señal de química oxidante más activa. Una caída real de emisiones de 30 % sostenida de marzo a mayo es poco plausible, pero no está descartada (Semana Santa cae en marzo–abril).
- **Límites:** febrero solo tiene la segunda quincena; la radiación es ERA5 en un punto (la radiación UV de SIMAT es un conjunto aparte y el servidor no respondió); no se separan días festivos.
