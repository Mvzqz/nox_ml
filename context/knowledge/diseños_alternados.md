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

## Reproducir

Desde la raíz del repo, con `data/{raw,interim,processed}` disponibles:

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
- **Observación al margen:** `products.measure_result` escribe el rango como `ratio * center / hi - 1`.
  - Si el placebo está centrado en 1, como el de días al azar de las fichas, es lo mismo que `ratio / hi - 1`, que es lo que se usa aquí.
  - Con un placebo descentrado, como el de días seguidos (0.88–1.27), no es lo mismo.
  - Vale revisarlo si las fichas llegan a usar el placebo del mismo diseño.
