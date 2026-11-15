# Validación del diagnóstico de episodios (F3)

Fecha: 2026-11-14. Frente F3 de [exploraciones_valor.md](../management/exploraciones_valor.md). Pregunta: ¿qué tan seguido acierta `nox-ml episode` (`nox_ml.validation.episodes`) en episodios de causa conocida? Hasta ahora solo se había probado en tres semanas de diciembre de 2023 ([verificaciones_nivel1.md](verificaciones_nivel1.md), sección 2).

## Qué se hizo

- **Ocho ventanas:** nov–dic 2023, feb–may 2024 (solo se mide, no se elige nada con ella), nov–dic 2024, feb–may 2025, nov–dic 2025, feb–may 2026 (con TEMPO) y feb–may de 2019 y 2020 (solo estaciones; sin TEMPO el fondo regional y la parte urbana quedan vacíos). Las fuentes son las de cada temporada (`configs/seasons/`): SIMAT hasta 2024, OpenAQ con el viento de los aeropuertos después, las tablas de la investigación en 2019–2020.
- **El mismo cálculo que el comando:** `diagnose_episode` con la pluma del baseline, 500 episodios falsos y el intervalo del 95 %. Comprobado: 18–22 dic 2023 da con el guion las mismas cifras que `nox-ml episode` con el código actual (concentración 1.59, emisión 1.42, fondo 2.09, veredicto emisión con fondo arriba). Las cifras de la sección 2 de verificaciones_nivel1.md (1.36, 1.34, 1.78) son de una versión anterior del código; el veredicto es el mismo.
- **Referencias limpias:** ningún episodio usa como referencia días atípicos (fin de año, Semana Santa), contingencias, festivos ni el confinamiento de 2020.
- **65 episodios elegidos sin mirar el NOₓ** (`notebooks/exploraciones/episodes/episodios.csv`, con el criterio de cada uno):

| Tipo | n | Criterio | Causa esperada |
|---|---|---|---|
| Estancada | 11 | Semanas hábiles (lun–vie, sin días atípicos) con el coeficiente de ventilación de la tarde más bajo (capa de mezcla × viento): 1 por temporada de invierno, 2 por temporada de primavera | Clima, sube |
| Ventilada | 11 | Las de coeficiente más alto, mismo número | Clima, baja |
| Festivo | 12 | Festivos oficiales en día hábil fuera de los periodos atípicos; se comparan con días normales de su mismo día de la semana (en el paquete un festivo cuenta como domingo) | Emisión, baja |
| Semana Santa | 4 | Días hábiles de Semana Santa y Pascua (vacaciones escolares), 2019, 2024–2026 | Emisión, baja |
| Confinamiento | 2 | 23–27 mar y 30 mar–3 abr 2020; las referencias son de antes del 23 de marzo | Emisión, baja |
| Placebo 2019 | 2 | Las mismas semanas de 2019 | Nada |
| Fin de año | 6 | Días hábiles 16–23 y 24–31 dic de 2023, 2024 y 2025 | Acumulación |
| Fondo alto | 6 | La semana hábil con el fondo regional de TEMPO más alto de cada temporada (percentil 10 de las columnas, no el NOₓ de las estaciones), que no sea semana de clima | Acumulación |
| Contingencia | 11 | Las contingencias de ozono de 2024, de la activación a la suspensión (no hay archivo de 2023 ni de 2025–2026 en `data/raw/contingencias/`) | Sin causa conocida |

- **Puntuación** (fijada antes de correr):
  - *Clima acierta:* en las semanas estancadas o ventiladas, el veredicto es `weather` o `both` con el clima en la dirección esperada. En los episodios de emisión o acumulación, el veredicto no le atribuye el episodio al clima (`weather`).
  - *Falso positivo de emisión:* un veredicto `emission`, `both` o `emission_or_accumulation` en un episodio sin cambio de emisión conocido (clima, acumulación, placebo), o una subida de emisión en uno de emisión baja.
  - *No evaluable:* el comando falla o el intervalo nulo tiene menos de 100 episodios falsos.
- **Veredicto prudente** (postproceso en `validate.py`, fijado antes de ver los resultados), sin afirmar emisión:
  - *normal:* la concentración está dentro del intervalo;
  - *el clima lo explica:* el cociente del clima sale del intervalo en la dirección de la concentración;
  - *lo explica en parte:* además, la emisión sale en la misma dirección;
  - *no lo explica:* en cualquier otro caso, con la nota "fondo regional alto" si el fondo sale arriba.

  Con este veredicto, el falso positivo es un "no lo explica" en un episodio de clima o placebo, o en uno de acumulación sin la nota del fondo. En los episodios de emisión baja, "no lo explica" es el resultado correcto.

## Resultados

Aciertos por tipo de episodio (`aciertos.csv`; ningún episodio quedó no evaluable):

| Tipo | n | Clima acierta | Falso positivo de emisión | Clima acierta (prudente) | Falso positivo (prudente) |
|---|---|---|---|---|---|
| Estancada | 11 | 36 % | 0 % | 18 % | 9 % |
| Ventilada | 11 | 27 % | 18 % | 9 % | 0 % |
| Festivo | 12 | 42 % | 0 % | 100 % | 0 % |
| Semana Santa | 4 | 100 % | 0 % | 100 % | 0 % |
| Confinamiento | 2 | 100 % | 0 % | 100 % | 0 % |
| Fin de año | 6 | 100 % | 33 % | 100 % | 0 % |
| Fondo alto | 6 | 83 % | 33 % | 100 % | 33 % |
| Placebo 2019 | 2 | 100 % | 0 % | 100 % | 0 % |
| **Clima (22)** | | **32 %** | **9 %** | **14 %** | **5 %** |
| **Emisión baja (18)** | | 61 % | 0 % | 100 % | 0 % |
| **Acumulación (12)** | | 92 % | 33 % | 100 % | 17 % |
| **Todos con causa conocida (52)** | | **56 %** | **12 %** | **63 %** | **6 %** |
| **Sin cambio de emisión (34: clima y acumulación)** | | | **18 %** | | **9 %** |

Veredictos (`resultados.csv`):

| Tipo | Clima | Emisión | Acumulación | Normal |
|---|---|---|---|---|
| Estancada | 4 | 0 | 1 | 6 |
| Ventilada | 3 | 2 | 1 | 5 |
| Festivo | 7 | 2 | 0 | 3 |
| Semana Santa | 0 | 0 | 1 | 3 |
| Confinamiento | 0 | 1 (0.63) | 0 | 1 |
| Fin de año | 0 | 2 | 0 | 4 |
| Fondo alto | 1 | 2 | 0 | 3 |
| Contingencia | 1 | 0 | 0 | 10 |

Lectura:

1. **Las semanas más estancadas o ventiladas de una temporada casi nunca salen inusuales.** En las 22 semanas de clima, el cociente del clima sale del intervalo en el 36 % y la concentración solo en el 18 %. La semana más estancada de una temporada tiene el clima entre 0.97 y 1.74 del normal; el intervalo de una semana de días normales va de ~0.7 a ~1.5. Por eso la mitad de las semanas salen "normal". Si "normal" en una semana cuya concentración fue normal no cuenta como error, la parte de clima acierta en el 82 % de las semanas de clima con el veredicto original y en el 95 % con el prudente. El criterio estricto, que pide que diga "clima", da 32 % y 14 %.
2. **El veredicto original le atribuye al clima lo que no es clima.** Cuando la concentración es inusual y la emisión no, el código devuelve `weather` sin mirar el cociente del clima (`verdict`, rama final). De los 12 festivos, 7 salen "clima" con el clima normal (por ejemplo, 18 mar 2024: concentración 0.56, clima 0.84 dentro del intervalo, emisión 0.67 fuera del intervalo de un día). El veredicto prudente los manda a "el clima no lo explica", que es lo correcto: la parte de clima pasa del 61 % al 100 % en los episodios de emisión baja.
3. **Los falsos positivos de emisión en semanas sin cambio de emisión son del 18 %**, casi cuatro veces el 5 % nominal. Lo explican dos causas ya conocidas:
   - **La deriva semanal** ([deriva.md](deriva.md), ±15 %): los episodios falsos del intervalo nulo son días sueltos tomados al azar, no semanas seguidas, así que el intervalo no contiene la deriva. Con la anchura típica del intervalo de emisión de una semana (logaritmo ±0.29, desviación ~0.15) más una deriva de 0.15, la tasa esperada de falsas alarmas es P(|z| > 1.38) ≈ **17 %**, la que se observa.
   - **La sobrecorrección del estimador cuando el clima está desbalanceado** ([temporadas.md](temporadas.md): en feb–may 2026, E7 baja el domingo de 0.64 a 0.47): en las semanas ventiladas la emisión sale alta (1.36, 1.29, 1.41, 1.63) y en las estancadas baja (0.70, 0.80, 0.82). Las dos semanas ventiladas con "emisión" (13 nov 2023, 23 feb 2026) son este sesgo.
4. **Con el veredicto prudente, los falsos positivos bajan a 9 % (3 de 34)**: la semana estancada del 4 dic 2023 (concentración 1.24 inusual, clima 1.28 dentro de su intervalo) y dos semanas de fondo alto (25 nov 2024, 10 nov 2025) cuyo fondo no salió del intervalo. El veredicto prudente no inventa emisión donde hubo acumulación en los fines de año (18–22 dic 2023: "no lo explica, fondo regional alto").
5. **El veredicto prudente no detecta las bajas de emisión.** Con el veredicto original, 3 de 18 bajas se nombran (festivo del 18 nov 2024: 0.55; 16 mar 2020: 0.67; confinamiento del 30 mar 2020: 0.63). Con el prudente, 8 de 18 quedan en "el clima no lo explica", que es una pista, no una detección. La Semana Santa no sale en ningún año (emisión 0.83–0.98): las vacaciones escolares bajan el NOₓ de la tarde menos de lo que el intervalo de una semana puede ver. La primera semana del confinamiento (23–27 mar, medidas parciales) tampoco.
6. **Fin de año 24–31 dic 2024** sale "emisión" a la baja (0.65). Cuenta como falso positivo con la regla fijada, pero es plausible que sea real: son vacaciones.
7. **Contingencias de ozono de 2024:** 10 de 11 salen "normal" en NOₓ. La del 22–25 feb sale "clima", con el fondo regional casi al doble (1.94). Para la pregunta "¿por qué hubo contingencia?", la herramienta casi siempre responde que el NOₓ de la tarde no fue inusual. Es coherente con un episodio de ozono, pero no responde la pregunta del usuario.

## Veredicto

| Criterio | Escala | Resultado |
|---|---|---|
| **¿Funciona?** | 0–3 | **1 con el criterio fijado** (clima acierta en 56 % y 63 % de los casos con causa conocida, contra ≥ 80 %), aunque los falsos positivos del prudente sí quedan en 9 % (≤ 10 %). **2 si "normal" cuenta como acierto** en las semanas de clima sin concentración inusual: el prudente no se equivoca de causa en 49 de 52 episodios con causa conocida |
| **Evidencia** | Prueba decisiva y cifra | 52 episodios con causa conocida en 8 ventanas: falsos positivos de emisión de 18 % → 9 % con el veredicto prudente; clima mal atribuido en 7 de 12 festivos con el original, 0 con el prudente; semanas de clima extremo casi siempre normales (concentración inusual en 18 %) |
| **Usuario** | Rol (CU1) | Autoridad y medios: "¿por qué esta semana estuvo tan alta?" |
| **Frecuencia** | Usos al año | ~5–10 preguntas al año (contingencias y semanas altas de invierno; ~11 contingencias en feb–may 2024), pero 10 de 11 contingencias salen "normal" en NOₓ |
| **Alternativa** | Ninguna · peor · igual · mejor | Igual que mirar la capa de mezcla y el viento de la semana con la concentración; mejor solo por el intervalo nulo y el fondo de TEMPO |
| **Decisión que cambia** | Qué haría distinto el usuario | Ninguna sobre medidas. Sirve para no atribuir a una medida o a "más emisión" lo que fue clima o acumulación: el veredicto prudente evita esa afirmación falsa |
| **Costo de llevarlo a producto** | Días y operación | ~1 día: cambiar el veredicto y el intervalo nulo, más pruebas (abajo); costo de operación nulo (segundos por episodio) |
| **Veredicto** | Adoptar · seguir con condiciones · descartar | **Seguir con condiciones:** adoptar el veredicto prudente y el nulo con semanas seguidas antes de ofrecer la herramienta; no presentarla como detector de emisión |

## Cambio recomendado a la herramienta (PR posterior, con pruebas)

Estado (15 nov 2026): los puntos 1 y 2 ya están en `nox_ml.validation.episodes` (`prudent_verdict` es el veredicto principal de `nox-ml episode`; el anterior queda en `detail`, con la rama final corregida a `unexplained`). Faltan los puntos 3 y 4.

1. **Veredicto prudente** en `episodes.verdict` (o junto a él): `normal` / `weather_explains` / `weather_explains_part` / `weather_does_not_explain`, más la nota `background_up`, con las reglas de `prudent()` en `notebooks/exploraciones/episodes/validate.py`. La etiqueta de emisión queda solo en las notas, como "sin explicación del clima", hasta tener un dato de actividad.
2. **Corregir la rama final:** con la concentración inusual y la emisión normal, el veredicto debe ser `weather` solo si el cociente del clima también sale del intervalo en la misma dirección; si no, es "el clima no lo explica". Prueba: un caso con concentración 0.56 inusual, clima 0.84 normal y emisión 0.67 normal no debe dar `weather`.
3. **Intervalo nulo con la deriva:** para episodios de días seguidos, tomar los episodios falsos como bloques de días seguidos de la temporada (o sumar 0.15 de deriva en logaritmo, como las fichas). Así la tasa de falsas alarmas vuelve a ~5 %. Prueba: con datos sintéticos con deriva semanal, la tasa nominal se respeta.
4. **Festivos:** ofrecer la opción de comparar un festivo con su propio día de la semana (como `as_weekday` del guion), que es la pregunta de "¿bajó el tráfico en el festivo?".

## Lo que faltó

- **Contingencias 2023 y 2025–2026:** no hay archivo en `data/raw/contingencias/` (solo 2024).
- **Vacaciones de verano** (jul–ago): no están en las temporadas congeladas; las ventanas de lluvias de 2024–2026 tienen TEMPO y se podrían agregar.
- **Recorte amplio de TEMPO:** se usó el fondo del recorte estándar (percentil 10 de los píxeles de la ciudad); con ~27 km desde el centro ese fondo todavía es ciudad ([deriva.md](deriva.md)).
- **Verdad de los episodios de clima:** la "causa conocida" es el coeficiente de ventilación, el mismo dato con el que la herramienta calcula el clima. Por eso la prueba mide si la ventilación extrema mueve la concentración más allá del ruido, no si el modelo de transporte acierta.
- **Pocas semanas por temporada de invierno** (4–5 semanas elegibles antes del 12 de diciembre): la semana "más estancada" de nov–dic es poco extrema.
- **No se probó el nulo con bloques** (recomendación 3); el 17 % esperado es un cálculo, no una corrida.

## Reproducir

```bash
# los datos de DVC (data/raw, data/interim) del repositorio principal
uv run python notebooks/exploraciones/episodes/prepare.py    # tablas diarias por ventana (~2 min), en runs/episode_validation/
uv run python notebooks/exploraciones/episodes/validate.py   # episodios, diagnóstico y veredicto prudente (~6 min)
uv run python notebooks/exploraciones/episodes/summary.py    # tasas por grupo
uv run nox-ml episode --days 2023-12-18:2023-12-22 --data 2023-11-01:2023-12-31   # control: mismas cifras que el guion
```

Salidas versionadas: `notebooks/exploraciones/episodes/episodios.csv` (episodios y criterio), `resultados.csv` (cocientes, intervalos, veredictos y puntuación) y `aciertos.csv` (tasas por tipo).
