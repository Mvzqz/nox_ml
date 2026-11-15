# Ciudad de control con el satélite (frente F9)

Fecha: 2026-11-15. Pregunta: la deriva lenta de la ZMVM (semanas enteras ±15 % arriba o abajo, que ven E7 y el satélite solo; [deriva.md](deriva.md)) ¿la comparte otra ciudad? Si sí, una diferencia en diferencias (ZMVM con medida frente a una ciudad de control) la cancela y baja el límite de detección sin datos de tráfico. Rama `explore/control-city`.

**Resultado: no.** Puebla comparte la deriva de la ZMVM en nov–dic 2024 (r semanal 0.95), pero no en feb–may 2025 (0.19) ni en nov–dic 2025 (0.24–0.43). En una temporada de tres la diferencia deriva menos; en las otras dos, igual o más, y restar Puebla agrega su propio ruido. Se descarta como forma de bajar el límite de detección.

**Alcance:** Puebla en tres temporadas (nov–dic 2024, feb–may 2025, nov–dic 2025); Monterrey solo en nov–dic 2024 y Toluca, como contraste, en nov–dic 2024 y feb–may 2025. Guadalajara no se descargó (cae en otro granulo de TEMPO).

## Método

- **Emisión diaria con TEMPO solo**, con la misma función `divergence.scan_emission` de `nox-ml flux-divergence` (cuadrícula de 5 km, vida media de 2 h, fondo = percentil 10 del escaneo). Solo cambia la entrada, que es igual para todas las ciudades: una caja del tamaño del dominio de la ZMVM (0.54° × 0.52°) alrededor de cada centro, el viento de ERA5 a 10 m en el centro (Open-Meteo, hora más cercana) y un cociente NO₂/NOₓ constante (escala todos los días por igual y se cancela en logaritmo).
- **La ZMVM se calcula dos veces:** con ese mismo método ("mismo método") y con la serie oficial de `results/runs/flux_divergence` (viento de aeropuertos y cociente de las estaciones). En nov–dic 2024 la réplica correlaciona 0.87 día a día con la oficial; el viento de ERA5 es 1.6 veces el de los aeropuertos.
- **Días normales:** hábiles y sin periodo atípico (`calendar.atypical_days`). En la ZMVM, además, sin contingencia (`products.reference_exclusions`). Anomalía = logaritmo de la emisión menos la media de la temporada.
- **Deriva**, con las dos definiciones de [deriva.md](deriva.md):
  - semanal: la dispersión de las medias de las semanas con ≥ 3 días, menos la que pone el ruido diario;
  - de bloques: la dispersión de 9 días seguidos contra el resto de la temporada, menos la de 9 días al azar.

  La diferencia ZMVM − Puebla se calcula en los días en que las dos tienen dato.
- **Criterio** (ajustado a la escala de bloques): funciona si la deriva de la diferencia baja a la mitad o menos de la de la ZMVM sola en al menos dos temporadas. No funciona si la correlación semanal es < 0.3 o si la diferencia no deriva menos.

## Validación del método fuera de la ZMVM

| Temporada | Ciudad | Días normales | Domingo ÷ hábil | Placebo 9 días | Deriva 9 días |
|---|---|---|---|---|---|
| nov–dic 2024 | Puebla | 25 | 0.62 | 1.00 | 0.27 |
| nov–dic 2024 | Monterrey | 17 | 0.63 | 1.01 | — (4 semanas) |
| nov–dic 2024 | Toluca | 20 | 0.57 | 1.00 | 0.25 |
| feb–may 2025 | Puebla | 54 | 0.71 | 1.00 | 0.11 |
| feb–may 2025 | Toluca | 37 | 0.74 | 1.00 | 0.00 |
| nov–dic 2025 | Puebla | 25 | 0.63 | 1.00 | 0.11 |

En las tres ciudades el método da el placebo en 1.00 y un domingo ÷ hábil de 0.57–0.74, el rango de la ZMVM (0.52–0.62). Monterrey tiene poca cobertura en invierno por las nubes: 17 de 37 días hábiles.

## La prueba decisiva: Puebla como control, tres temporadas

| Temporada | Serie ZMVM | r semanal | r diario | Días pareados | Deriva semanal: ZMVM → diferencia | Deriva 9 días: ZMVM → diferencia | ¿Pasa? |
|---|---|---|---|---|---|---|---|
| nov–dic 2024 | mismo método | **0.95** | 0.78 | 25 | 0.18 → 0.03 | 0.25 → **0.00** | sí |
| nov–dic 2024 | oficial | **0.96** | 0.78 | 25 | 0.15 → 0.11 | 0.16 → **0.09** | justo |
| feb–may 2025 | mismo método | 0.19 | 0.18 | 49 | 0.13 → 0.14 | 0.08 → 0.16 | no |
| feb–may 2025 | oficial | 0.20 | 0.29 | 43 | 0.13 → 0.12 | 0.09 → 0.08 | no |
| nov–dic 2025 | mismo método | 0.43 | 0.24 | 24 | 0.17 → 0.15 | 0.22 → 0.16 | no |
| nov–dic 2025 | oficial | 0.24 | 0.18 | 24 | 0.00 → 0.09 | 0.02 → 0.05 | no |

(Las derivas de la ZMVM en esta tabla son las de los días pareados.)

- **Solo nov–dic 2024 pasa.** En feb–may 2025 la correlación semanal (0.19–0.20) queda bajo el umbral de 0.3 y la diferencia no deriva menos. En nov–dic 2025 la deriva de la serie oficial ya es casi nula (0.02–0.05, como en [deriva.md](deriva.md)) y restar Puebla la sube.
- **No es aire de la ZMVM llegando a Puebla:** en nov–dic 2024 ninguna tarde tuvo viento en Puebla desde la ZMVM (rumbo 299° ± 45°), y en feb–may 2025 solo una (`transport_check.py`). En Toluca, que sí recibe aire de la ZMVM (6 de 20 días en nov–dic 2024), la correlación es menor esos días (0.34 contra 0.82).
- **Lectura:** en nov–dic 2024 algo regional movió a las dos ciudades juntas (química, capa de mezcla o fondo de un episodio sinóptico). Es la temporada en que E7 y el satélite también coinciden más (0.95, [deriva.md](deriva.md)). Pero no es un rasgo estable: la deriva de la ZMVM es casi toda propia en las otras dos temporadas. Encaja con [deriva.md](deriva.md): no hay un control externo que la quite de forma sistemática.
- **Monterrey** (solo nov–dic 2024): r semanal 0.52 con el mismo método, r diario 0.11, y la diferencia deriva igual o más (0.16 → 0.19). Tampoco sirve.

## Inyecciones de bajas con diferencia en diferencias

`inject.py`: en los días pareados, una medida es un bloque de k días seguidos. Se inyecta una baja solo en la ZMVM y se estima con la ZMVM sola (bloque − resto) y con la diferencia (lo mismo sobre ZMVM − Puebla). El rango sale del placebo del mismo estimador: los bloques de la temporada que no se traslapan con el probado. El mínimo detectable "por dispersión" es 1 − exp(−2.49 · σ), con σ la desviación de los bloques sin inyección; es la regla de `products`.

Dispersión de bloques de 9 días (σ) y mínimo detectable por dispersión, ZMVM sola → diferencia:

| Temporada | Mismo método | Serie oficial |
|---|---|---|
| nov–dic 2024 | 0.27 → 0.09 (49 % → 19 %) | 0.19 → 0.13 (37 % → 27 %) |
| feb–may 2025 | 0.13 → 0.20 (28 % → 40 %) | 0.14 → 0.14 (29 % → 30 %) |
| nov–dic 2025 | 0.24 → 0.19 (45 % → 38 %) | 0.07 → 0.10 (15 % → 23 %) |

Las tres temporadas juntas, bloques de 9 días (74 bloques con el mismo método, 68 con la serie oficial):

| | Falsas alarmas | Detecta −10 / −15 / −20 % | Cobertura del rango de 90 % | Mínimo detectable (80 % de las veces) |
|---|---|---|---|---|
| ZMVM sola, mismo método | 38 % | 34 / 49 / 54 % | 62 % | 40 % |
| Diferencia, mismo método | 32 % | 35 / 53 / 62 % | 68 % | 34 % |
| ZMVM sola, serie oficial | 51 % | 32 / 43 / 47 % | 49 % | 35 % |
| Diferencia, serie oficial | 41 % | 32 / 38 / 47 % | 59 % | 29 % |

- **El placebo dentro de la temporada está mal calibrado para los dos estimadores** (falsas alarmas de 32–51 %, cobertura de 49–68 % frente al 90 % nominal). Con 24–54 días pareados, los bloques que no se traslapan son pocos y no recogen toda la deriva. Por eso las fichas suman la deriva aparte (`products.DRIFT_SD`). Las tasas sirven para comparar los dos estimadores entre sí, no como calibración absoluta.
- **La diferencia mejora poco y solo por nov–dic 2024:** el mínimo detectable con 9 días baja de 40 % a 34 % (mismo método) o de 35 % a 29 % (oficial). Fuera de esa temporada, la dispersión sube o se queda igual.
- Con bloques de 20 días (solo feb–may 2025 tiene días suficientes), la diferencia empeora con el mismo método (15 % → 32 %) y mejora con la serie oficial (28 % → 19 %): no hay una dirección estable.

## Valor de cada ciudad por sí misma

- **Puebla–Tlaxcala:** buena cobertura de TEMPO, domingo y placebo razonables. Su deriva de bloques (0.11–0.27) es parecida a la de la ZMVM. El mismo método satelital le daría un límite parecido al de la ZMVM: ~25–50 % por temporada con 9 días seguidos. Es una ciudad sin un sistema de este tipo, pero no un control.
- **Monterrey:** el método da un domingo de 0.63 y el placebo en 1, pero en invierno solo hay 17 días normales sin nubes. Para el Hub del Campus Monterrey es un punto de partida barato (satélite + ERA5, sin estaciones). Antes de ofrecerlo conviene probar feb–may, más despejado, y el peso de su industria (frente F8).
- **Toluca:** solo sirve de contraste, porque recibe aire de la ZMVM algunos días.

## Veredicto

| Criterio | Resultado |
|---|---|
| **¿Funciona?** | 1: no funciona. Pasa en 1 de 3 temporadas (nov–dic 2024: r semanal 0.95, deriva de 9 días 0.25 → 0.00); en feb–may 2025 r = 0.19 y en nov–dic 2025 la diferencia no deriva menos |
| **Evidencia** | Deriva de bloques de 9 días, ZMVM → ZMVM − Puebla: 0.25 → 0.00, 0.08 → 0.16 y 0.22 → 0.16 (mismo método); con inyecciones en las tres temporadas, el mínimo detectable con 9 días baja solo de 40 % a 34 % (de 35 % a 29 % con la serie oficial), todo por nov–dic 2024 |
| **Usuario** | Habría sido el evaluador de medidas (CU2, CU7, CU8) |
| **Frecuencia** | — |
| **Alternativa** | Igual que lo que existe: la ZMVM sola con la deriva sumada (`products.DRIFT_SD`) |
| **Decisión que cambia** | Ninguna. Confirma que la deriva es sobre todo propia de la ZMVM (emisión real o meteorología local), no regional, y que sin un dato de actividad no se baja el límite de ~30 % por temporada |
| **Costo de llevarlo a producto** | No aplica (habrían sido 3–5 días y ~25 GB de descarga por temporada) |
| **Veredicto** | **Descartar** como control. Queda la herramienta de divergencia de flujo para cualquier caja (`flux.py`), útil para el frente de Monterrey y para otras ciudades con TEMPO |

## Reproducir

Scripts en `notebooks/exploraciones/control_city/`, desde la raíz, con `.venv/bin/python` (todo con `nice -n 15`):

```sh
python notebooks/exploraciones/control_city/download_tempo.py 2024-11-01 2024-12-31 monterrey puebla toluca --workers 1
python notebooks/exploraciones/control_city/download_tempo.py 2025-02-15 2025-05-31 puebla toluca --workers 1
python notebooks/exploraciones/control_city/download_tempo.py 2025-11-01 2025-12-31 puebla --workers 1
python notebooks/exploraciones/control_city/download_wind.py
python notebooks/exploraciones/control_city/flux.py 2024-11-01 2024-12-31 zmvm monterrey puebla toluca      # y 2025-02-15 2025-05-31, 2025-11-01 2025-12-31
python notebooks/exploraciones/control_city/compare.py 2024-11-01 2024-12-31 monterrey puebla toluca        # una por temporada; --column tau_4h
python notebooks/exploraciones/control_city/summary.py
python notebooks/exploraciones/control_city/inject.py puebla 2024-11-01:2024-12-31 2025-02-15:2025-05-31 2025-11-01:2025-12-31 [--zmvm zmvm_official]
cd notebooks/exploraciones/control_city && ../../../.venv/bin/python transport_check.py puebla 2024-11-01:2024-12-31
```

Las series diarias, las comparaciones y las inyecciones quedan en `notebooks/exploraciones/control_city/out/`. Los datos nuevos están anotados en `data/raw/MANIFEST.md`: `data/raw/tempo_{monterrey,puebla,toluca}/` y `data/raw/era5_openmeteo_cities/`. La descarga reutiliza `nox_ml.data.tempo` (`list_granules`, `download_granule`, `subset_granule`) con la caja de cada ciudad, y baja cada granulo una sola vez para todas las ciudades que cubre. Los recortes de nov–dic 2024 salieron de una primera versión propia, sin `latitude_bounds`.

## Lo que faltó

- **Guadalajara** (granulo G07), el control lejano. Con Puebla, una ciudad vecina con el mismo clima sinóptico, la correlación ya falla en 2 de 3 temporadas. Es poco probable que una ciudad lejana correlacione más.
- **Comparación con E7:** no hay serie diaria de E7 guardada en `results/runs/`.
- **feb–may 2026** y el viento de aeropuerto también en Puebla (MMPB, IEM): no cambiarían el veredicto con 2 de 3 temporadas en contra.
