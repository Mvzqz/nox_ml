# Diseños alternados: ¿intercalar días con y sin medida cancela la deriva?

Fecha: 2026-11-14. Frente F1 de [exploraciones_valor.md](../management/exploraciones_valor.md). Rama `explore/switchback`.

**Respuesta corta:** sí cancela la mayor parte de la deriva, pero no alcanza para medir medidas de 5–10 % en una sola temporada. Con media temporada de días con medida intercalados, el mínimo detectable baja a 14–16 % en la temporada más tranquila (feb–may 2026) y queda en 20–54 % en las demás. Si la gente no vuelve de inmediato a su hábito (arrastre del 50 % a la semana siguiente), ningún diseño baja de 21 %. Sumando seis temporadas, las semanas alternas llegan a ~10 % y los días alternos a ~8 %.

## Qué se hizo

- **Estimador:** E7 (`normalized_ratio`), igual que las fichas. Su cambio es un cociente de sumas diarias (NOₓ observado sobre NOₓ modelado, de los días con medida sobre los días sin medida). La inyección de las fichas (`events.inject_drop`) también es lineal por día. Por eso cada diseño se evalúa con las sumas diarias, sin volver a ajustar E7. Ese atajo reproduce a E7 exactamente: 0.811645 contra 0.811645 en nov–dic 2024 con semanas alternas y una baja de 15 % (`simulate.py --verify`).
- **Días:** los días hábiles normales (sin periodos atípicos ni contingencias, `products.reference_exclusions`) de seis temporadas: nov–dic 2023, feb–may 2024, nov–dic 2024, feb–may 2025, nov–dic 2025 y feb–may 2026. Son 28, 48, 28, 58, 28 y 63 días. En cada temporada, la medida cae en la mitad de los días (14 a 31) y la referencia es la otra mitad. feb–may 2024 solo se usa para medir; no se eligió nada con ella.
- **Diseños** (con el mismo número de días con medida, en promedio):
  - (a) días seguidos: un solo bloque que empieza en un día al azar;
  - (b) días alternos: los días en pares consecutivos, y uno de cada par, sorteado, lleva la medida;
  - (c) semanas alternas: lo mismo con semanas de calendario, con el día de corte también al azar;
  - (d) bloques de 2 semanas, en pares sorteados;
  - (e) días al azar: la mitad de los días;
  - (f) semanas al azar, como diseño extra.

  Alternar con un sorteo dentro de cada par (en vez de un patrón fijo) es lo que da un placebo válido. Con un patrón fijo solo hay 2 asignaciones posibles por temporada.
- **Incertidumbre:** el placebo del mismo diseño. Se toman 4,000 asignaciones al azar del diseño sin inyección; su intervalo del 90 %, ensanchado 5 % como en las fichas, da el rango. Una baja se detecta cuando el cociente queda debajo del límite inferior. El mínimo detectable es la menor baja (en pasos de 1 %) que se detecta el 80 % de las veces, en otras 4,000 asignaciones con la baja inyectada.
- **Arrastre:** los días sin medida que caen en los 7 días siguientes a un día con medida reciben el 50 % de la baja. En semanas alternas, eso es toda la semana sin medida que sigue. En días alternos, casi todos los días sin medida.

## Mínimo detectable por diseño (80 % de potencia, 90 % de confianza)

Sin arrastre:

| Diseño | nov–dic 2023 | feb–may 2024 | nov–dic 2024 | feb–may 2025 | nov–dic 2025 | feb–may 2026 | Seis temporadas juntas |
|---|---|---|---|---|---|---|---|
| (a) Días seguidos | 35 %* | 17 %* | 44 %* | 23 %* | 46 %* | 25 %* | 12 %* |
| (b) Días alternos | 34 % | 16 % | 20 % | 20 % | 26 % | **14 %** | 8 % |
| (c) Semanas alternas | 28 % | 25 % | 26 % | 22 % | 54 % | **15 %** | 10 % |
| (d) Bloques de 2 semanas | 42 % | 24 % | 44 % | 24 % | 49 % | 25 % | 13 % |
| (e) Días al azar | 36 % | 20 % | 24 % | 21 % | 34 % | 17 % | 10 % |
| (f) Semanas al azar | 38 % | 28 % | 37 % | 25 % | 46 % | 23 % | 13 % |
| Días con medida | 14 | 24 | 14 | 29 | 14 | 31 | |

Con arrastre del 50 % a la semana siguiente:

| Diseño | nov–dic 2023 | feb–may 2024 | nov–dic 2024 | feb–may 2025 | nov–dic 2025 | feb–may 2026 |
|---|---|---|---|---|---|---|
| (a) Días seguidos | 39 %* | 18 %* | 49 %* | 24 %* | 51 %* | 26 %* |
| (b) Días alternos | 49 % | 26 % | 32 % | 32 % | 40 % | 24 % |
| (c) Semanas alternas | 38 % | 32 % | 35 % | 29 % | 64 % | **21 %** |
| (d) Bloques de 2 semanas | 49 % | 27 % | 52 % | 27 % | 52 % | 28 % |
| (e) Días al azar | 50 % | 30 % | 37 % | 32 % | 49 % | 27 % |
| (f) Semanas al azar | 54 % | 29 % | 46 % | 28 % | 54 % | 28 % |

\* Las cifras de días seguidos son optimistas y no se deben usar. Con media temporada en un solo bloque solo hay 15–32 posiciones distintas, y se traslapan casi todas. Además, el centro del placebo no está en 1: va de 0.88 a 1.27 según la temporada (en invierno, diciembre sube frente a noviembre). En la práctica, quien mide una medida de días seguidos no conoce ese centro. La referencia honesta para días seguidos es la del artículo (Tabla 9): 39–47 % con 9 días y 32–34 % con 60, con la deriva de 0.15.

- **Robustez:** con otras tres semillas, feb–may 2026 da 14–15 % para días alternos, 15–16 % para semanas alternas y 16–17 % para días al azar.
- **Seis temporadas juntas:** combinación por inverso de la varianza en escala logarítmica, con aproximación normal. Supone que la deriva es independiente entre años; aplica solo a una medida que se repita en las seis temporadas.

## Falsas alarmas, cobertura y bootstrap

| Diseño | Falsa alarma con 0 % (baja detectada) | Cobertura sin arrastre (0–20 %) | Cobertura con arrastre, baja de 20 % | Cobertura del bootstrap de días (nominal 90 %) |
|---|---|---|---|---|
| (b) Días alternos | 4.3 % | 91 % | 70 % | 88–97 % |
| (c) Semanas alternas | 3.2 % | 92–93 % | 83 % | 59–95 % |
| (d) Bloques de 2 semanas | 2.5 % | 95 % | 92 % | 54–82 % |
| (e) Días al azar | 4.2 % | 91 % | 77 % | 85–90 % |
| (f) Semanas al azar | 3.6 % | 92 % | 90 % | 63–82 % |
| (a) Días seguidos | 1.7 % | 97 % | 85 % | 26–66 % |

Las falsas alarmas son promedios de las seis temporadas. Con 0 % de baja, el arrastre no cambia nada, así que la falsa alarma es la misma con y sin arrastre.

- **El placebo del mismo diseño está calibrado:** cubre la verdad el 91–95 % de las veces, con 2–4 % de falsas alarmas (esperado: ≤ 5 %).
- **El bootstrap de días que trae E7 solo sirve con días sueltos o alternos.** Con semanas o bloques, el bootstrap remuestrea días que no son independientes y sale demasiado angosto (54–82 % de cobertura). Con días seguidos cubre solo 26–66 %. Confirma la advertencia del plan: en un diseño alternado hay que usar el placebo del mismo diseño.
- **El arrastre hace que el rango no cubra la verdad:** con días alternos y una baja de 20 %, el rango solo contiene la baja real el 70 % de las veces. El diseño ya no mide la baja de la medida, sino la diferencia entre días con medida y días sin medida que también recibieron parte del efecto. Cuanto más corto el ciclo, más pesa el arrastre: con días alternos el mínimo pasa de 14–34 % a 24–49 %; con bloques de 2 semanas, apenas de 24–49 % a 27–52 %.

## Lectura

- **La deriva sí se cancela en buena parte.** Con la misma mitad de días con medida, la desviación del logaritmo del cociente promedia 0.094 con días alternos, 0.111 con días al azar y 0.127 con semanas alternas, contra 0.15–0.16 con bloques de 2 semanas o semanas al azar. Las semanas alternas le dejan a la deriva ~0.06, frente al ±0.15–0.25 que mueve el centro de los días seguidos.
- **Alternar en pares es mejor que sortear libremente.** Los días alternos (sorteo por par) le ganan a los días al azar en todas las temporadas. Los pares equilibran la deriva entre los dos grupos; el sorteo libre solo la equilibra en promedio.
- **El ruido de un día a otro sigue ahí.** Aunque la deriva se cancelara del todo, con la variación diaria de E7 (cv 0.27–0.44) y 14–31 días por grupo el piso sería de ~14 % en la mejor temporada y de ~30 % en invierno. Para 5–10 % hacen falta varias temporadas con la misma medida alternada, o un estimador con menos ruido diario.
- **Comparado con el artículo** (Tabla 9; días seguidos: 39–47 % con 9 días y 32–34 % con 60): con 14–31 días por grupo, las semanas alternas dan 15–28 % en cinco temporadas (54 % en nov–dic 2025, la de más deriva). Es una mejora clara frente a los días seguidos, con menos de la mitad de los días.

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
| **¿Funciona?** | 0 no se probó · 1 no funciona · 2 funciona con condiciones · 3 funciona y está validado de forma independiente | **2**, en el límite. Las semanas alternas llegan a 15–16 % (criterio: ≤ 15 %) y los días alternos a 14–15 %, solo en feb–may 2026 y sin arrastre. En las demás temporadas quedan en 16–54 %, y con arrastre del 50 % en ≥ 21 %. |
| **Evidencia** | La prueba decisiva y su cifra | 4,000 asignaciones por diseño, temporada y baja, con E7 reproducido exactamente. Mínimo detectable con semanas alternas: 15–28 % en cinco temporadas y 54 % en nov–dic 2025; 10 % con las seis juntas. Placebo calibrado: cobertura de 91–95 % y 2–4 % de falsas alarmas. |
| **Usuario** | Quién lo usaría | Autoridad y planeadores (CU3), al diseñar el piloto de una medida; financiadores (CU8), al exigir una evaluación con un diseño medible. |
| **Frecuencia** | Usos esperados al año | 1–3: un piloto alternado por temporada. Supone una autoridad dispuesta a encender y apagar una medida durante 2–3 meses. |
| **Alternativa** | Ninguna · peor · igual · mejor | Mejor que los días seguidos (32–47 % en el artículo, con más días). Igual que repetir la misma medida en varias temporadas, que también pide coordinar con la autoridad. |
| **Decisión que cambia** | Qué haría distinto el usuario | Se diseña el piloto como semanas alternas sorteadas por par, en feb–may, de 2–3 meses, en vez de "encender y comparar con el antes". Además, se exige que la medida baje ≥ 20 % en una temporada, o se repite en varias temporadas. |
| **Costo de llevarlo a producto** | Días de desarrollo y costo de operación | ~2 días: que `ficha-medida` acepte un patrón de días alternado y use el placebo de ese diseño (el sorteo por par). No tiene costo de operación. El costo real es institucional: coordinar el piloto. |
| **Veredicto** | Adoptar · seguir con condiciones · descartar | **Seguir con condiciones.** Vale para medidas de ≥ 15–20 % que se puedan alternar por semana con poco arrastre, en feb–may, o repetidas en varias temporadas. No resuelve las medidas de 5–10 % en una temporada. |

## Reproducir

```bash
# desde la raíz del repo, con data/{raw,interim,processed} disponibles
uv run python notebooks/exploraciones/switchback/daily_sums.py OUT/sums            # ~2 min, sumas diarias de E7
uv run python notebooks/exploraciones/switchback/simulate.py OUT/sums OUT/out --verify  # atajo frente a E7
uv run python notebooks/exploraciones/switchback/simulate.py OUT/sums OUT/out      # ~1 min, semilla 11
uv run python notebooks/exploraciones/switchback/summarize.py OUT/out              # tablas de esta nota
```

## Lo que no se probó

- **Menos días con medida:** por ejemplo, 9 días alternados dentro de un periodo de 18. Solo se probó media temporada.
- **Arrastres distintos de 50 % por 7 días.** Tampoco se probó el diseño con días de lavado (descartar la semana después de cada bloque con medida), que elimina el arrastre a costa de días.
- **Una medida localizada:** la inyección es de toda la ciudad. Una medida en una zona permitiría usar las otras zonas como control (otra forma de cancelar la deriva), pero E7 no separa zonas.
- **El satélite** (`flux-divergence`) con los mismos diseños.
- **La correlación de la deriva entre años**, que afecta la combinación de seis temporadas. El artículo da 22–26 % para días seguidos si se repite; para los diseños alternados se espera menos efecto, porque la deriva ya se cancela dentro de la temporada.
- **Observación al margen:** `products.measure_result` escribe el rango como `ratio * center / hi - 1`. Si el placebo está centrado en 1 (días al azar, como en las fichas) es lo mismo que `ratio / hi - 1`, que es lo que se usa aquí. No sería lo mismo con un placebo descentrado, como el de los días seguidos. Vale revisarlo si las fichas llegan a usar placebos con el mismo diseño.
