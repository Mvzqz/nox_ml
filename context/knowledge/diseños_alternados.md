# Diseños alternados: ¿intercalar días con y sin medida cancela la deriva?

Fecha: 2026-11-14. Frente F1 de [exploraciones_valor.md](../management/exploraciones_valor.md). Rama `explore/switchback`.

**Respuesta corta:** sí. Alternar días o semanas cancela casi toda la deriva lenta. Aun así, no alcanza para medir medidas de 5–10 % en una sola temporada.

- **Con E7 solo:** con media temporada de días con medida intercalados, el mínimo detectable baja a 15–16 % en la temporada más tranquila (feb–may 2026). En las demás queda en 16–54 %.
- **Con E7 y el satélite (0.5/0.5):** baja a 11 % con días alternos y a 14 % con semanas alternas en feb–may 2026.
- **Con arrastre:** si la gente no vuelve de inmediato a su hábito (50 % del efecto en la semana siguiente sin medida), ningún diseño baja de 19 %.
- **Con las seis temporadas juntas:** las semanas alternas llegan a ~9–10 % y los días alternos a ~6–8 %.

## Qué se hizo

- **Estimador:** E7 (`normalized_ratio`), igual que las fichas. Su cambio es un cociente de sumas diarias: el NOₓ observado sobre el modelado, de los días con medida contra los días sin medida.
  - La inyección de las fichas (`events.inject_drop`) también es lineal por día. Por eso cada diseño se evalúa con las sumas diarias, sin volver a ajustar E7.
  - El atajo reproduce a E7 exactamente: 0.811645 contra 0.811645, en nov–dic 2024 con semanas alternas y una baja de 15 % (`simulate.py --verify`).
- **Satélite:** como variante, la combinación 0.5/0.5 de E7 con el satélite solo (divergencia de flujo, `products.satellite_daily`, vida media de 2 h). Es la media geométrica de los dos cocientes. La baja se inyecta en el satélite como factor (1 − d) sobre la emisión del día; es una aproximación, no la inyección en las columnas. El satélite falta en 2–14 días por temporada.
- **Días:** los días hábiles normales (sin periodos atípicos ni contingencias, `products.reference_exclusions`) de seis temporadas:

  | Temporada | Días hábiles normales | Días con medida |
  |---|---|---|
  | nov–dic 2023 | 28 | 14 |
  | feb–may 2024 | 48 | 24 |
  | nov–dic 2024 | 28 | 14 |
  | feb–may 2025 | 58 | 29 |
  | nov–dic 2025 | 28 | 14 |
  | feb–may 2026 | 63 | 31 |

  En cada temporada, la medida cae en la mitad de los días y la referencia es la otra mitad. feb–may 2024 solo se usa para medir; no se eligió nada con ella.
- **Diseños** (con el mismo número de días con medida, en promedio):
  - (a) días seguidos: un solo bloque que empieza en un día al azar;
  - (b) días alternos: los días en pares consecutivos, y uno de cada par, sorteado, lleva la medida;
  - (c) semanas alternas: lo mismo con semanas de calendario, con el día de corte también al azar;
  - (d) bloques de 2 semanas, en pares sorteados;
  - (e) días al azar: la mitad de los días;
  - (f) semanas al azar, como diseño extra.

  Para medir la deriva como en [deriva.md](deriva.md), también se corrieron bloques de 9 días seguidos y 9 días al azar contra el resto. Alternar con un sorteo dentro de cada par, en vez de un patrón fijo, es lo que da un placebo válido: con un patrón fijo solo hay 2 asignaciones posibles por temporada.
- **Incertidumbre:** el placebo del mismo diseño.
  - Se toman 4,000 asignaciones al azar del diseño, sin inyección. Su intervalo del 90 %, ensanchado 5 % como en las fichas, da el rango.
  - Una baja se detecta cuando el cociente queda debajo del límite inferior.
  - El mínimo detectable es la menor baja (en pasos de 1 %) que se detecta el 80 % de las veces, en otras 4,000 asignaciones con la baja inyectada.
- **Arrastre:** los días sin medida que caen en los 7 días siguientes a un día con medida reciben el 50 % de la baja. En semanas alternas, eso es toda la semana sin medida que sigue; en días alternos, casi todos los días sin medida.

## La deriva que deja cada diseño

La deriva se mide como en [deriva.md](deriva.md): la dispersión del logaritmo del cociente alrededor de "sin cambio", menos, en cuadratura, la de días al azar de la misma temporada. La media es la de las seis temporadas.

| Diseño | Deriva con E7 | Deriva con E7 y el satélite |
|---|---|---|
| Referencia: 9 días seguidos frente a 9 al azar | 0.137 (0.11–0.17) | 0.134 |
| (a) Media temporada seguida | 0.154 | 0.141 |
| (b) Días alternos | 0 (6 de 6 temporadas) | 0.004 |
| (c) Semanas alternas | 0.054: 0 en 4 temporadas, 0.06 en nov–dic 2023 y 0.19 en nov–dic 2025 | 0.047 |
| (d) Bloques de 2 semanas | 0.114 | 0.092 |
| (f) Semanas al azar | 0.100 | 0.089 |

La referencia de 9 días (0.137) se parece a la de [deriva.md](deriva.md), que da 0.125 sin feb–may 2024. Los días alternos la cancelan del todo. Las semanas alternas la cancelan en cuatro de seis temporadas. Los bloques de 2 semanas y las semanas al azar conservan la mayor parte.

## Mínimo detectable (80 % de potencia, 90 % de confianza)

E7, sin arrastre:

| Diseño | nov–dic 2023 | feb–may 2024 | nov–dic 2024 | feb–may 2025 | nov–dic 2025 | feb–may 2026 | Seis juntas |
|---|---|---|---|---|---|---|---|
| (a) Días seguidos | 34 %* | 17 %* | 43 %* | 23 %* | 46 %* | 25 %* | 12 %* |
| (b) Días alternos | 33 % | 16 % | 20 % | 20 % | 26 % | **15 %** | 8 % |
| (c) Semanas alternas | 28 % | 25 % | 26 % | 21 % | 54 % | 16 % | 10 % |
| (d) Bloques de 2 semanas | 42 % | 24 % | 44 % | 23 % | 46 % | 24 % | 13 % |
| (e) Días al azar | 35 % | 20 % | 24 % | 21 % | 34 % | 16 % | 10 % |
| (f) Semanas al azar | 38 % | 28 % | 36 % | 24 % | 46 % | 23 % | 13 % |
| Días con medida | 14 | 24 | 14 | 29 | 14 | 31 | |

E7 con arrastre del 50 % a la semana siguiente:

| Diseño | nov–dic 2023 | feb–may 2024 | nov–dic 2024 | feb–may 2025 | nov–dic 2025 | feb–may 2026 |
|---|---|---|---|---|---|---|
| (a) Días seguidos | 38 %* | 18 %* | 49 %* | 24 %* | 50 %* | 26 %* |
| (b) Días alternos | 49 % | 26 % | 33 % | 32 % | 40 % | 25 % |
| (c) Semanas alternas | 38 % | 32 % | 35 % | 28 % | 64 % | 22 % |
| (d) Bloques de 2 semanas | 49 % | 27 % | 52 % | 25 % | 49 % | 28 % |
| (e) Días al azar | 50 % | 30 % | 36 % | 32 % | 49 % | 26 % |
| (f) Semanas al azar | 45 % | 34 % | 45 % | 29 % | 54 % | 28 % |

E7 y el satélite (0.5/0.5), sin arrastre (entre paréntesis, con arrastre):

| Diseño | nov–dic 2023 | feb–may 2024 | nov–dic 2024 | feb–may 2025 | nov–dic 2025 | feb–may 2026 | Seis juntas |
|---|---|---|---|---|---|---|---|
| (b) Días alternos | 28 % (42) | 13 % (22) | 15 % (26) | 16 % (26) | 16 % (26) | **11 %** (19) | 6 % |
| (c) Semanas alternas | 25 % (36) | 23 % (30) | 24 % (35) | 19 % (26) | 37 % (50) | **14 %** (20) | 9 % |
| (d) Bloques de 2 semanas | 30 % | 27 % | 42 % | 18 % | 35 % | 24 % | 11 % |
| (e) Días al azar | 28 % | 20 % | 20 % | 17 % | 21 % | 15 % | 8 % |

\* Las cifras de días seguidos son optimistas y no se deben usar.

- Con media temporada en un solo bloque solo hay 15–32 posiciones distintas, y casi todas se traslapan.
- El centro de su placebo no está en 1: va de 0.88 a 1.27 según la temporada (en invierno, diciembre sube frente a noviembre). Quien evalúa una medida de días seguidos no conoce ese centro.
- La referencia honesta para días seguidos es la del artículo (Tabla 9): 39–47 % con 9 días y 32–34 % con 60, con la deriva de 0.15.

Notas:

- **Robustez:** con otras tres semillas, E7 en feb–may 2026 da 14–15 % con días alternos, 15–16 % con semanas alternas y 16–17 % con días al azar.
- **Seis temporadas juntas:** combinación por inverso de la varianza en escala logarítmica, con aproximación normal. Supone que cada temporada es independiente y solo aplica a una medida que se repita en las seis.

## Falsas alarmas, cobertura y bootstrap (E7)

| Diseño | Falsa alarma con 0 % | Cobertura sin arrastre (0–20 %) | Cobertura con arrastre, baja de 20 % | Cobertura del bootstrap de días (nominal 90 %) |
|---|---|---|---|---|
| (b) Días alternos | 4.2 % | 91 % | 70 % | 88–97 % |
| (c) Semanas alternas | 3.3 % | 94 % | 84 % | 55–94 % |
| (d) Bloques de 2 semanas | 3.9 % | 94 % | 92 % | 54–80 % |
| (e) Días al azar | 4.3 % | 91–92 % | 78 % | 83–90 % |
| (f) Semanas al azar | 3.5 % | 92 % | 90 % | 59–81 % |
| (a) Días seguidos | 1.7 % | 97 % | 85 % | 25–64 % |

La falsa alarma es la de "baja detectada", en promedio de las seis temporadas.

- **El placebo del mismo diseño está calibrado.** Cubre la verdad el 91–94 % de las veces, con 2–4 % de falsas alarmas (esperado: ≤ 5 %).
- **El bootstrap de días que trae E7 solo sirve con días sueltos o alternos.** Con semanas o bloques sale demasiado angosto (54–94 % de cobertura); con días seguidos cubre solo 25–64 %. Confirma la advertencia del plan: en un diseño alternado hay que usar el placebo del mismo diseño.
- **La ficha actual tampoco sirve tal cual.** Desde el PR #86, `ficha-medida` usa el modo `drift` (días seguidos) o el placebo de días al azar. Un diseño de semanas alternas caería en el placebo de días al azar, que no ve la deriva que queda (0.05). Si la medida ocupa la mitad de la temporada, caería en el modo extrapolado más `DRIFT_SD`, que ya no corresponde porque la deriva se canceló. Hace falta el placebo del mismo diseño.
- **El arrastre hace que el rango no cubra la verdad.** El diseño ya no mide la baja de la medida, sino la diferencia contra días sin medida que también recibieron parte del efecto. Cuanto más corto el ciclo, más pesa:

  | Diseño | Mínimo sin arrastre | Con arrastre |
  |---|---|---|
  | Días alternos | 15–33 % | 25–49 % |
  | Semanas alternas | 16–54 % | 22–64 % |
  | Bloques de 2 semanas | 23–46 % | 25–52 % |

## Lectura

- **La deriva se cancela, y el mínimo queda en el ruido de un día a otro.** Aunque la deriva se cancele, la variación diaria de E7 (cv 0.27–0.44) pone el piso. Con 14–31 días por grupo, ese piso es ~15 % en la mejor temporada y ~25–35 % en invierno. Para medidas de 5–10 % hacen falta varias temporadas con la misma medida alternada, o menos ruido diario.
- **El satélite ayuda justo aquí.** Combinar E7 con el satélite no quita la deriva de días seguidos ([deriva.md](deriva.md)): 0.137 frente a 0.134. En cambio, sí baja el ruido diario. Con un diseño alternado, que ya canceló la deriva, la combinación baja el mínimo 2–17 puntos según la temporada y el diseño.
- **Alternar en pares es mejor que sortear libremente.** Los días alternos (sorteo por par) le ganan a los días al azar en todas las temporadas, porque los pares equilibran la deriva entre los dos grupos. Lo mismo pasa con las semanas alternas frente a las semanas al azar.
- **Comparado con el artículo** (Tabla 9; días seguidos: 39–47 % con 9 días y 32–34 % con 60), con 14–31 días por grupo:
  - semanas alternas con E7: 16–28 % en cinco temporadas y 54 % en nov–dic 2025, la de más deriva;
  - semanas alternas con E7 y el satélite: 14–25 % en cinco temporadas y 37 % en nov–dic 2025.

  Es una mejora clara, con menos de la mitad de los días.

## Qué medidas de la ZMVM se podrían alternar

- **Se pueden alternar** (se encienden y apagan por decreto, y el hábito vuelve rápido, con poco arrastre):
  - restricciones extra de circulación por día, como las de la Fase 1 de contingencia: un Hoy No Circula adicional en días sorteados;
  - restricción horaria a la carga pesada por semanas;
  - teletrabajo obligatorio del gobierno en semanas alternas;
  - horarios escalonados de entrada;
  - gratuidad o descuento del transporte público por días o semanas;
  - carriles exclusivos o confinados temporales (con conos).
- **Con reservas:**
  - el Hoy No Circula sabatino: cae en fin de semana, y este análisis es de días hábiles; además, el sábado no se estima en invierno con una temporada ([temporadas.md](temporadas.md));
  - las tarifas o descuentos que cambian decisiones de compra o de ruta: tienen arrastre alto, así que conviene usar bloques de 2 semanas, que pierden poco con el arrastre pero detectan peor.
- **No se pueden alternar:**
  - la verificación vehicular y los cambios de norma o de combustible;
  - la renovación de flotas;
  - las líneas nuevas de Metrobús o de Metro y la infraestructura;
  - cualquier medida permanente que cambie la compra de vehículos o el lugar de residencia.

  Para estas medidas solo queda el diseño de días seguidos, con la Tabla 9.

## Veredicto

| Criterio | Escala | Resultado |
|---|---|---|
| **¿Funciona?** | 0 no se probó · 1 no funciona · 2 funciona con condiciones · 3 funciona y está validado de forma independiente | **2.** El criterio (≤ 15 % en una temporada) se cumple solo en feb–may 2026 y sin arrastre: 14 % con semanas alternas y E7 más el satélite; 15–16 % con E7 solo. En las demás temporadas, el mínimo queda en 16–54 %. Con arrastre del 50 %, en ≥ 19 %. |
| **Evidencia** | La prueba decisiva y su cifra | 4,000 asignaciones por diseño, temporada y baja, con E7 reproducido exactamente. Semanas alternas: la deriva baja de 0.137 a 0.054 y el mínimo queda en 16–28 % en cinco temporadas (54 % en nov–dic 2025); 10 % con las seis juntas (9 % con el satélite). Placebo calibrado: 91–94 % de cobertura, 2–4 % de falsas alarmas. |
| **Usuario** | Quién lo usaría | Autoridad y planeadores (CU3), al diseñar el piloto de una medida; financiadores (CU8), al exigir una evaluación con un diseño medible. |
| **Frecuencia** | Usos esperados al año | 1–3: un piloto alternado por temporada. Supone una autoridad dispuesta a encender y apagar una medida durante 2–3 meses. |
| **Alternativa** | Ninguna · peor · igual · mejor | Mejor que los días seguidos (32–47 % en el artículo, con más días). Igual que repetir la misma medida en varias temporadas, que también pide coordinar con la autoridad. |
| **Decisión que cambia** | Qué haría distinto el usuario | El piloto se diseña como semanas alternas, sorteadas por par, en feb–may y de 2–3 meses, en vez de "encender y comparar con el antes". Se exige que la medida baje ≥ 15–20 % en una temporada, o se repite en varias temporadas. |
| **Costo de llevarlo a producto** | Días de desarrollo y costo de operación | ~2–3 días: que `ficha-medida` acepte un diseño alternado y use su propio placebo (el sorteo por par, con E7 y el satélite), y que `ficha-dias` calcule los días que pide. No tiene costo de operación. El costo real es institucional: coordinar el piloto. |
| **Veredicto** | Adoptar · seguir con condiciones · descartar | **Seguir con condiciones.** Vale para medidas de ≥ 15–20 % que se puedan alternar por semana con poco arrastre, en feb–may, o repetidas en varias temporadas. No resuelve las medidas de 5–10 % en una temporada. |

## Más confianza (2026-11-15)

Rama `explore/switchback-confidence`. Mismos días y sumas diarias que arriba; script nuevo `confidence.py` (y `summarize_confidence.py`). Criterio fijado de antemano: **aumenta la confianza** si la combinación E7 y satélite queda calibrada (cobertura ≥ 88 %, falsas alarmas ≤ 10 %) y algún diseño con lavado mantiene el mínimo de una temporada ≤ 20 % con arrastre del 50 %.

**Resultado:** la calibración pasa con holgura. El criterio del lavado se queda en el límite (20–21 %), así que **no se cumple de forma robusta**: la confianza sube en la incertidumbre del diseño, no en el piso con arrastre.

### 1. E7 y satélite con su propio placebo

El placebo del mismo diseño (3,000 asignaciones sin inyección, intervalo del 90 % ensanchado 5 %) se calcula con la combinación 0.5/0.5; la inyección se evalúa con baja de 0 a 20 %.

| Diseño | Falsa alarma con 0 % (media, máx. de seis) | Cobertura 5–20 % (media, mín.) | Cobertura con arrastre 50 %, baja 20 % (media) |
|---|---|---|---|
| (b) Días alternos | 4.2 % (5.2) | 91.6 % (89.6) | 54 % |
| (c) Semanas alternas | 3.4 % (5.1) | 93.1 % (90.5) | 81 % |
| (d) Bloques de 2 semanas | 3.4 % (5.4) | 93.4 % (90.1) | 92 % |
| (e) Días al azar | 4.4 % (5.2) | 91.2 % (90.0) | 72 % |

- **Calibrada:** cobertura 90–100 % por temporada (baja de 10 %) y falsas alarmas ≤ 5.4 %. Igual que con E7 solo (4.0–4.5 %, cobertura 91.6–94.9 %).
- **El mínimo se confirma.** Con otra semilla, E7 y satélite con semanas alternas en feb–may 2026 da 14 % y con días alternos 11 %; en feb–may 2025, 20 % y 16 %.
- **Con arrastre, el rango no cubre** (como con E7): días alternos baja a 35–82 % de cobertura. Solo los bloques de 2 semanas aguantan (88–96 %).

### 2. Arrastre y lavado

Mínimo detectable de E7 y satélite (entre paréntesis, E7 solo) en las dos temporadas más tranquilas, y las seis juntas, con distintos arrastres durante 7 días:

| Diseño | Sin arrastre | 25 % | 50 % | 75 % |
|---|---|---|---|---|
| (b) Días alternos, feb–may 2026 | 11 % (15) | 14 % (18) | 20 % (25) | 31 % (37) |
| (b) Días alternos, feb–may 2025 | 16 % (20) | 19 % (25) | 25 % (32) | 39 % (46) |
| (c) Semanas alternas, feb–may 2026 | 14 % (15) | 16 % (18) | 19 % (22) | 25 % (27) |
| (c) Semanas alternas, feb–may 2025 | 19 % (22) | 22 % (24) | 26 % (28) | 32 % (36) |
| (d) Bloques de 2 semanas, feb–may 2026 | 23 % (24) | 24 % (26) | 26 % (28) | 30 % (29) |

Cada 25 % de arrastre cuesta ~3–6 puntos en días alternos y ~2–3 en semanas. Los bloques de 2 semanas casi no se mueven, pero parten de 23–24 %.

**Lavado:** descartar de los días sin medida los 7 días (o 14) siguientes a un día con medida. Con semanas alternas al azar por par, el lavado deja ~10 días de control de ~31 y falla: el placebo mezcla asignaciones sin días de control, la cobertura cae a 46 % y varias temporadas no alcanzan potencia. Por eso se probó un diseño de **tríos de semanas**: en cada trío, una semana (al azar) lleva la medida, la siguiente se lava y el resto es control; ~1/3 de las semanas con medida (`g_triple_weeks`).

| Con E7 y satélite (E7 solo) | feb–may 2025 | feb–may 2026 | nov–dic 2025 | Seis juntas (sin arrastre) | Cobertura, arrastre 50 % |
|---|---|---|---|---|---|
| Tríos, sin arrastre | 17 % (21) | 16 % (17) | 32 % (48) | 9.5 % | 91 % |
| Tríos, arrastre 50 %, sin lavado | 21 % (24) | 18 % (21) | 40 % (55) | | 89 % |
| **Tríos, arrastre 50 %, lavado 7 días** | **20–21 % (25–26)** | **21–22 % (23)** | 33 % (50) | 11.4 % | **94 %** |
| Tríos, cola de 25 % hasta el día 14, lavado 7 | 22 % (27) | 23 % (25) | 38 % (53) | | 91 % |
| Tríos, cola de 25 %, lavado 14 | 27 % | 28 % | 33 % | 17 % | 47 % |

- **El lavado no baja el mínimo; devuelve la cobertura.** Contra los tríos con arrastre sin lavado, el mínimo no mejora (20–21 % frente a 21 % en 2025; 21–22 % frente a 18 % en 2026, con 4 semillas), pero el rango vuelve a cubrir (94 % frente a 89 %) y ya no depende de adivinar el arrastre exacto.
- **Cuesta ~2 puntos en las seis juntas** (11.4 % frente a 9.5 %) y 30 % de las semanas como control.
- **El criterio de 20 % queda en el límite:** 20 % en la semilla del barrido y 20–21 % en otras cuatro (feb–may 2025, E7 y satélite); en feb–may 2026, 21–22 %. Con E7 solo, 23–26 %. Si la cola del arrastre pasa de la primera semana, el lavado de 7 días ya no alcanza (22–23 %) y uno de 14 días deja pocos días de control (47 % de cobertura).

### 3. Menos días con medida

Piloto de N días hábiles normales (la mitad con la medida; ~1.4 N días de calendario), en ventanas repartidas en cada temporada. Mediana de las ventanas y temporadas. Con N de 30 y 40 solo hay feb–may (3 temporadas); de 14 a 24 entran las seis.

**Tabla para un planeador:** mínimo detectable (80 % de potencia, 90 % de confianza) con E7 y satélite. Entre paréntesis, con arrastre del 50 % a la semana siguiente.

| Días con medida (de N) | Días alternos | Semanas alternas | Días al azar | Rango entre temporadas (días alternos, sin arrastre) |
|---|---|---|---|---|
| 7 de 14 | 23 % (36) | 30 % (38) | 26 % (37) | 12–39 % |
| 9 de 18 | 20 % (32) | 28 % (36) | 24 % (35) | 14–36 % |
| 12 de 24 | 18 % (29) | 29 % (36) | 21 % (32) | 14–29 % |
| 15 de 30 | 18 % (29) | 22 % (30) | 20 % (29) | 13–22 % |
| 20 de 40 | 16 % (26) | 19 % (25) | 18 % (28) | 13–19 % |

Con E7 solo, 3–7 puntos más: días alternos 29, 26, 24, 21 y 18 % (sin arrastre) y 42, 40, 37, 33 y 30 % (con arrastre).

- **Cada 10 días hábiles más de piloto bajan el mínimo ~3 puntos** (de 14 a 40 días, de 23 a 16 %), con rendimientos decrecientes. Un piloto de 9 de 18 detecta ~20 % en una temporada típica y 14 % en la mejor ventana; no sirve para medidas de ≤ 10 %.
- **Con arrastre del 50 %, ningún tamaño probado baja de ~25 %.** Un piloto corto solo sirve si se lava o si la medida tiene poco arrastre.
- **La variación entre temporadas es mayor que la del tamaño:** nov–dic 2023 y 2025 quedan 5–10 puntos arriba de feb–may 2026 con el mismo N.

### 4. Correlación de la deriva entre años

Se aplicó la misma asignación de calendario (unidades contadas desde el inicio de la temporada) a todas las temporadas y se correlacionó el logaritmo del cociente sin inyección entre años de la misma ventana (3,000 asignaciones).

| Diseño | nov–dic 2023–24 | 2023–25 | 2024–25 | feb–may 2024–25 | 2024–26 | 2025–26 | Error de seis juntas: independiente / misma asignación |
|---|---|---|---|---|---|---|---|
| E7, días alternos | +0.36 | +0.29 | −0.12 | +0.05 | −0.07 | +0.10 | 0.035 / 0.035 |
| E7, semanas alternas | +0.09 | +0.43 | +0.22 | −0.23 | +0.09 | −0.40 | 0.042 / 0.035 |
| E7, bloques de 2 semanas | +0.83 | +0.68 | +0.64 | −0.39 | +0.22 | −0.41 | 0.054 / 0.056 |
| E7 y satélite, días alternos | +0.28 | +0.45 | −0.07 | −0.23 | 0.00 | +0.05 | 0.026 / 0.025 |
| E7 y satélite, semanas alternas | −0.17 | −0.07 | +0.02 | +0.06 | +0.02 | −0.33 | 0.036 / 0.028 |
| E7 y satélite, bloques de 2 semanas | +0.81 | +0.38 | +0.50 | +0.05 | −0.12 | −0.26 | 0.046 / 0.058 |

- **Con días o semanas alternos, la deriva que queda no se repite de un año a otro.** Las correlaciones van de −0.40 a +0.45 sin patrón (como en las anomalías semanales de [deriva.md](deriva.md), de −0.57 a +0.49) y el error de las seis juntas con la misma asignación es igual o menor que suponiendo independencia (0.035 frente a 0.035 y 0.042; 0.025 frente a 0.026 y 0.036 con el satélite). **La combinación por inverso de la varianza sigue siendo válida.**
- **Excepción: bloques de 2 semanas en nov–dic** (+0.64 a +0.83, de 4–5 bloques por temporada, así que mide sobre todo el calendario: diciembre contra noviembre). Con la misma asignación el error de las seis juntas sube 26 % con el satélite (0.058 frente a 0.046). Para ese diseño, el sorteo debe ser distinto cada año.
- **Recomendación:** sortear la asignación de forma independiente cada año; así la correlación entre años no entra, aunque exista. No es necesario ajustar el error de las seis juntas.

### Veredicto actualizado

| Criterio | Escala | Resultado |
|---|---|---|
| **¿Funciona?** | 0 no se probó · 1 no funciona · 2 funciona con condiciones · 3 funciona y está validado de forma independiente | **2.** Sigue en 2: el rango de E7 y satélite está calibrado (cobertura 90–100 % por temporada, falsas alarmas ≤ 5.4 %), pero con arrastre del 50 % el mínimo de una temporada queda en 19–26 % sin lavado y en 20–22 % con lavado (tríos de semanas, feb–may). |
| **Evidencia** | La prueba decisiva y su cifra | Calibración con placebo propio (4 diseños, 6 temporadas, 3,000 asignaciones): cobertura media 91–93 %, falsas alarmas 3.4–4.4 %. Lavado de 7 días en tríos: 20–21 % (E7 y satélite) o 25–26 % (E7) en feb–may 2025, con 94 % de cobertura bajo arrastre. Piloto de 9 de 18 días: 20 % con días alternos. |
| **Usuario** | Quién lo usaría | Planeadores y autoridad (CU3) y financiadores (CU8), igual que antes; ahora con una tabla de días con medida frente al mínimo detectable. |
| **Frecuencia** | Usos esperados al año | 1–3, igual que antes. |
| **Alternativa** | Ninguna · peor · igual · mejor | Mejor que días seguidos (32–47 %, Tabla 9), con ≤ 40 días hábiles; igual de caro en coordinación. |
| **Decisión que cambia** | Qué haría distinto el usuario | Para un piloto de ~30 días hábiles en feb–may: días alternos (si el arrastre es ≤ 25 %), o tríos de semanas con lavado (si puede ser mayor). Con menos de ~24 días con medida o en nov–dic, no esperar menos de 20–30 %. Sortear cada año de forma independiente. |
| **Costo de llevarlo a producto** | Días de desarrollo y costo de operación | ~3–4 días (2–3 de antes, más el lavado y los tríos en el placebo de la ficha). Sin costo de operación. |
| **Veredicto** | Adoptar · seguir con condiciones · descartar | **Seguir con condiciones**, con más confianza en el rango y la combinación de años, y la misma limitación: no baja de ~20 % en una temporada con arrastre del 50 %. |

### Lo que sigue sin probar

- Una medida localizada (contraste entre zonas) y la inyección del satélite en sus columnas.
- Otros patrones de lavado (por ejemplo, ciclos de 4 semanas con dos de control) y un perfil de arrastre medido de una medida real.
- Tamaños de piloto con ventanas contiguas en nov–dic más largas de 28 días: no existen en los datos.
- Las cifras de la tabla de planeador usan 1,500 asignaciones por ventana y 3 ventanas por temporada: dan ±2 puntos.

## Reproducir

Desde la raíz del repo, con `data/{raw,interim,processed}` disponibles. Las pruebas de esta sección (después de `daily_sums.py`):

```bash
for t in calibration carry fewer years; do
  uv run python notebooks/exploraciones/switchback/confidence.py OUT/sums OUT/conf $t   # 2–10 min cada una
done
uv run python notebooks/exploraciones/switchback/summarize_confidence.py OUT/conf
```

Las de la primera parte:

```bash
uv run python notebooks/exploraciones/switchback/daily_sums.py OUT/sums                 # ~2 min: sumas diarias de E7 y satélite
uv run python notebooks/exploraciones/switchback/simulate.py OUT/sums OUT/out --verify  # atajo frente a E7
uv run python notebooks/exploraciones/switchback/simulate.py OUT/sums OUT/out           # ~5 min, semilla 11
uv run python notebooks/exploraciones/switchback/summarize.py OUT/out                   # tablas de esta nota
```

## Lo que no se probó

- **Menos días con medida:** por ejemplo, 9 días alternados dentro de un periodo de 18. Solo se probó media temporada.
- **Otros arrastres** distintos de 50 % por 7 días. Tampoco se probó el diseño con días de lavado (descartar la semana después de cada bloque con medida), que quita el arrastre a costa de días.
- **Una medida localizada.** La inyección es de toda la ciudad. El contraste entre zonas también cancela la deriva, pero es ruidoso ([deriva.md](deriva.md)); no se repitió.
- **La inyección del satélite en sus columnas.** Se aplicó como factor sobre la emisión diaria. Tampoco se validó la cobertura de la combinación E7–satélite con su propio placebo; las cifras de falsas alarmas y cobertura son las de E7.
- **La correlación de la deriva entre años,** que afecta la combinación de seis temporadas. Con los diseños alternados pesa menos, porque la deriva ya se canceló dentro de la temporada.
- **Observación al margen (resuelta en el PR #94):** `products.measure_result` escribía el rango como `ratio * center / hi - 1`, distinto de `ratio / hi - 1` con un placebo descentrado. El PR #94 lo cambió a `ratio/hi − 1` a `ratio/lo − 1`, lo que usa esta nota. Ese PR también suma la deriva solo cuando ≥ 80 % de los días hábiles del periodo son de la medida, así que un diseño alternado ya no la recibe por error.
