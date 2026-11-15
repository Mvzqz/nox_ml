# Ciudad de control con el satélite (frente F9)

Fecha: 2026-11-15. Pregunta: la deriva lenta de la ZMVM (semanas enteras ±15 % arriba o abajo, que ven E7 y el satélite solo; [deriva.md](deriva.md)) ¿la comparte otra ciudad? Si sí, una diferencia en diferencias (ZMVM con medida frente a una ciudad de control) la cancela y baja el límite de detección sin datos de tráfico. Rama `explore/control-city`.

**Alcance real:** una temporada (nov–dic 2024) y tres ciudades en el mismo granulo de TEMPO que la ZMVM (Monterrey, Puebla y Toluca como contraste). La descarga de feb–may 2025 se cortó al quinto día (la sesión se cerró por falta de memoria de la máquina) y Guadalajara, que cae en otro granulo, no se descargó. El criterio pedía dos temporadas: **esto es un indicio, no un veredicto.**

## Método

- **Emisión diaria con TEMPO solo**, con la misma función `divergence.scan_emission` de `nox-ml flux-divergence` (cuadrícula de 5 km, vida media de 2 h, fondo = percentil 10 del escaneo). Cambia solo la entrada, igual para todas las ciudades: una caja del tamaño del dominio de la ZMVM (0.54° × 0.52°) alrededor de cada centro, el viento de ERA5 a 10 m en el centro (Open-Meteo, hora más cercana) y un cociente NO₂/NOₓ constante (escala todos los días por igual y se cancela en logaritmo).
- **La ZMVM se calcula dos veces:** con ese mismo método (serie "ZMVM, mismo método") y con la serie oficial de `results/runs/flux_divergence` (viento de aeropuertos y cociente de las estaciones). La réplica correlaciona 0.87 día a día con la oficial; el viento de ERA5 es 1.6 veces el de los aeropuertos.
- **Días normales:** hábiles, sin periodo atípico (`calendar.atypical_days`); en la ZMVM, además, sin contingencia (`products.reference_exclusions`). Anomalía = logaritmo de la emisión menos la media de la temporada.
- **Deriva**, con las dos definiciones de [deriva.md](deriva.md): semanal (dispersión de las medias de semanas con ≥ 3 días menos la del ruido diario) y de bloques (dispersión de 9 días seguidos contra el resto, menos la de 9 días al azar). Para la diferencia ZMVM − control se usan los días en que las dos tienen dato.
- **Mínimo detectable de una medida de una temporada** (90 %, potencia 80 %, la regla de `products`): 1 − exp(−2.49 · √(deriva² + 2·cv²/k)), con k los días normales de la temporada y cv la variación diaria. En la diferencia, cv es el de la serie diferencia: incluye el ruido de la ciudad de control.

## Cobertura y validación fuera de la ZMVM (nov–dic 2024, vida media de 2 h)

| Serie | Días normales | Semanas | Deriva semanal | Deriva 9 días | CV diario | Domingo ÷ hábil | Placebo 9 días |
|---|---|---|---|---|---|---|---|
| ZMVM oficial | 26 | 6 | 0.15 | 0.18 | 0.17 | 0.60 | 1.00 |
| ZMVM, mismo método | 26 | 6 | 0.16 | 0.24 | 0.22 | 0.52 | 1.00 |
| Monterrey | 17 | 4 | 0.00 | — | 0.37 | 0.63 | 1.01 |
| Puebla | 25 | 6 | 0.28 | 0.27 | 0.22 | 0.62 | 1.00 |
| Toluca | 20 | 4 | 0.11 | 0.25 | 0.29 | 0.57 | 1.00 |

- **El método funciona fuera de la ZMVM:** placebo en 1.00–1.01 y domingo de 0.57–0.63 en las tres ciudades, el mismo rango que la ZMVM (0.52–0.60) y que la literatura.
- **Monterrey tiene poca cobertura en invierno** (17 días normales de 37 hábiles, por nubes): no alcanza para la deriva de bloques. Puebla tiene la misma cobertura que la ZMVM.

## La prueba decisiva: ¿la diferencia deriva menos?

| Control | Serie ZMVM | r semanal | r diario | Días pareados | Deriva semanal: ZMVM → diferencia | Deriva 9 días: ZMVM → diferencia | Mínimo detectable de una temporada: ZMVM → diferencia |
|---|---|---|---|---|---|---|---|
| Puebla | mismo método | **0.95** | 0.78 | 25 | 0.18 → **0.03** | 0.25 → **0.00** | 35 % → **14 %** |
| Puebla | oficial | **0.96** | 0.78 | 25 | 0.15 → 0.11 | 0.16 → **0.09** | 32 % → 19 % |
| Toluca (contraste) | mismo método | 0.95 | 0.79 | 20 | 0.13 → 0.00 | 0.19 → 0.02 | → 14 % |
| Toluca (contraste) | oficial | 0.86 | 0.77 | 20 | 0.12 → 0.00 | 0.11 → 0.14 | → 14 % |
| Monterrey | mismo método | 0.52 | 0.11 | 16 | 0.16 → 0.19 | — | → 24 % |
| Monterrey | oficial | 0.79 | 0.42 | 16 | 0.18 → 0.10 | — | → 19 % |

(Las derivas "ZMVM" de esta tabla son las de los días pareados, por eso difieren un poco de la tabla anterior.)

- **Puebla comparte la deriva de la ZMVM:** sus semanas altas y bajas son las mismas (r = 0.95–0.96) y también sus días (0.78). Con el mismo método en las dos ciudades, la diferencia no deriva y el mínimo detectable de una medida de una temporada baja de ~35 % a ~14 %, aun con el ruido de Puebla sumado.
- **Con la serie oficial de la ZMVM la mejora es menor:** la deriva de bloques baja a la mitad (0.16 → 0.09), la semanal solo de 0.15 a 0.11. Con la vida media de 4 h la diferencia con la serie oficial no mejora (bloques 0.14 → 0.21) y con el mismo método sí (0.27 → 0.00). La cancelación es más limpia cuando las dos ciudades usan el mismo viento y el mismo cociente: parte de lo que se cancela puede ser error común del método (viento de ERA5, química), no solo deriva física.
- **No es aire de la ZMVM llegando a Puebla:** en nov–dic 2024 ninguna tarde tuvo viento en Puebla desde la ZMVM (rumbo 299° ± 45°; `transport_check.py`). En Toluca, que sí recibe aire de la ZMVM (6 de 20 días), la correlación es menor esos días (0.34 contra 0.82): la señal común no viene del transporte.
- **Monterrey no comparte la deriva** con el mismo método (r diario 0.11, la diferencia deriva igual o más). Con la serie oficial la correlación semanal es 0.79, pero con solo 4 semanas.
- **Lectura física (hipótesis):** que una ciudad a 100 km, sin intercambio de aire esos días, suba y baje con la ZMVM y una a 700 km no, apunta a algo regional y sinóptico (química, vida media del NOₓ, capa de mezcla, fondo regional) más que a la actividad de la ZMVM. Encaja con lo que encontró [deriva.md](deriva.md): la afluencia del transporte público no la sigue y la diferencia oriente − poniente de la ZMVM no deriva.

**Cuidado con las cifras:** seis semanas por temporada. La deriva estimada con 6 semanas tiene un error del orden de su propio valor; una deriva de 0.00 significa "no se distingue del ruido diario", no "cero". Por eso el criterio pedía dos temporadas.

## Frente al criterio fijado

- **Funciona** si la deriva de la diferencia baja a ≤ la mitad de la de la ZMVM sola en al menos dos temporadas (criterio ajustado a la escala de bloques de 9 días). En nov–dic 2024 Puebla lo cumple con el mismo método (0.25 → 0.00) y justo con la serie oficial (0.16 → 0.09); falta la segunda temporada.
- **No funciona** si la correlación semanal es < 0.3 o la diferencia no deriva menos: no pasa con Puebla; Monterrey queda en el límite (0.52 con el mismo método, la diferencia no deriva menos).

## Valor de cada ciudad por sí misma

- **Puebla–Tlaxcala:** buena cobertura de TEMPO en invierno, domingo y placebo razonables. Es el mejor control y una ciudad sin un sistema de este tipo; su propia deriva es mayor que la de la ZMVM (0.27), así que por sí sola tendría un límite peor (~50 % por temporada).
- **Monterrey:** el método da un domingo de 0.63 y placebo en 1, pero en invierno solo hay 17 días normales sin nubes; con eso su límite por temporada sería ~23 % (con 4 semanas no se mide su deriva). Para el Hub del Campus Monterrey es un punto de partida barato (satélite + ERA5, sin estaciones), pero conviene probar feb–may, más despejado, y su peso industrial, antes de ofrecerlo (frente F8).
- **Toluca:** sirve solo de contraste: recibe aire de la ZMVM algunos días.

## Veredicto

| Criterio | Resultado |
|---|---|
| **¿Funciona?** | 2: funciona con condiciones, en una temporada. Puebla comparte la deriva (r semanal 0.95) y la diferencia baja de 0.25 a 0.00 (9 días, mismo método) o de 0.16 a 0.09 (serie oficial). Falta la segunda temporada que pide el criterio |
| **Evidencia** | nov–dic 2024: mínimo detectable de una medida de una temporada de ~35 % a ~14 % (mismo método) o de 32 % a 19 % (serie oficial), con placebo de Puebla en 1.00 y domingo 0.62 |
| **Usuario** | Evaluadores de medidas y SEDEMA/CAMe (CU2, CU7, CU8): medidas sostenidas de la ZMVM que no se aplican en Puebla |
| **Frecuencia** | 1–3 evaluaciones al año (medidas de temporada: programas de verificación, Hoy No Circula, contingencias extendidas), si se valida |
| **Alternativa** | Mejor que lo que existe: la deriva no la quitaba ninguna corrección (clima, columna lejana, afluencia, zonas) y no requiere datos de tráfico |
| **Decisión que cambia** | Medidas de 15–20 % por temporada pasan a ser evaluables (hoy solo ≥ 30 %); una medida que cubra también Puebla (p. ej., megalopolitana de la CAMe) no se puede evaluar así |
| **Costo de llevarlo a producto** | 3–5 días: generalizar el dominio de `divergence` y la descarga de `tempo` a una caja por ciudad, agregar el control a las fichas y validar con inyecciones. Operación: ~25 GB de descarga por temporada (granulos completos, recorte local), sin costo de cómputo relevante |
| **Veredicto** | **Seguir con condiciones:** (1) repetir en feb–may 2025 y nov–dic 2025 con Puebla (y Guadalajara como control lejano); (2) calibrar con inyecciones de bloques de 9 y 20 días en la ZMVM con la diferencia; (3) usar la serie oficial y el mismo método y adoptar solo si las dos bajan la deriva a la mitad |

## Reproducir

Scripts en `notebooks/exploraciones/control_city/` (corren con `.venv/bin/python`, desde la raíz):

```sh
nice -n 15 .venv/bin/python notebooks/exploraciones/control_city/download_tempo.py 2024-11-01 2024-12-31 monterrey puebla toluca --workers 1
.venv/bin/python notebooks/exploraciones/control_city/download_wind.py
nice -n 15 .venv/bin/python notebooks/exploraciones/control_city/flux.py 2024-11-01 2024-12-31 zmvm monterrey puebla toluca
.venv/bin/python notebooks/exploraciones/control_city/compare.py 2024-11-01 2024-12-31 monterrey puebla toluca           # vida media de 2 h
.venv/bin/python notebooks/exploraciones/control_city/compare.py 2024-11-01 2024-12-31 monterrey puebla toluca --column tau_4h
.venv/bin/python notebooks/exploraciones/control_city/summary.py
cd notebooks/exploraciones/control_city && ../../../.venv/bin/python transport_check.py puebla 2024-11-01:2024-12-31
```

Las series diarias y las comparaciones quedan en `notebooks/exploraciones/control_city/out/`. Datos nuevos (anotados en `data/raw/MANIFEST.md`): `data/raw/tempo_{monterrey,puebla,toluca}/` y `data/raw/era5_openmeteo_cities/`. La descarga de 2024 usó una primera versión propia del recorte (sin `latitude_bounds`); la actual reutiliza `nox_ml.data.tempo` (`list_granules`, `download_granule`, `subset_granule`) con la caja de cada ciudad y descarga cada granulo una sola vez para todas las ciudades que cubre.

## Lo que faltó

- **Segunda y tercera temporada** (feb–may 2025: 5 días descargados de 106; nov–dic 2025). Es lo que decide el criterio.
- **Guadalajara** (granulo G07, otra descarga): el control lejano que más limpio separaría una deriva regional de una sinóptica.
- **Comparación con E7:** no hay serie diaria de E7 guardada en `results/runs/`; con la correlación E7–satélite de 0.95 en esta temporada ([deriva.md](deriva.md)), se espera lo mismo.
- **Inyecciones** de bajas en la ZMVM con la diferencia, para calibrar falsas alarmas y cobertura como en la segunda opinión del satélite ([fichas.md](fichas.md)).
- Probar el viento a 100 m y si la cancelación sobrevive con el viento de aeropuerto también en Puebla (aeropuerto MMPB, IEM).
