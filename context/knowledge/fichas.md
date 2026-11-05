# Fichas: cada pregunta con su estimador, y su validación

Fecha: 2026-10-29 (actualizado con las temporadas 2024–2026 y la calibración del rango). Las capacidades únicas del sistema ([capacidades.md](capacidades.md), filas 1–3) ya existían en la línea de comandos; las fichas las presentan en una página en español, para alguien fuera del equipo. Código: `nox_ml.validation.products`.

## Qué estimador responde cada pregunta

| Pregunta | Estimador | Por qué |
|---|---|---|
| ¿Cambió la emisión entre periodos? (una medida, un anuncio) | E7, normalizado por meteorología | Midió el confinamiento de 2020 (−50 %, esperado −40 a −60 %) con el placebo de 2019 en 1; las inversiones sin TEMPO fallan ese placebo y con TEMPO tienen el sesgo del domingo ([sesgo_domingo.md](sesgo_domingo.md)). Solo usa estaciones: corre también donde falta TEMPO |
| Ciclo semanal (domingo ÷ hábil) | X4, boosting | 0.57–0.58 en las cuatro temporadas de 2024–2026; el bosque (E6) varió entre 0.56 y 0.67 y las inversiones exageran el domingo ([temporadas.md](temporadas.md)) |
| Concentración donde no hay estación | Regresión-kriging sobre E5b | 10.2 ppb, la mejor de la tabla |

## Las fichas

- `nox-ml ficha-medida --days INICIO:FIN --data INICIO:FIN --title "..." [--claim -0.2]`: ¿cambió la emisión en esos días?, con el cambio, su rango, el cambio mínimo detectable con esos días, el veredicto (baja, aumento o no detectable) y, si se da, si el cambio anunciado cabe en el rango. Advierte cuando los días caen en un periodo atípico.
- `nox-ml ficha-dias --data INICIO:FIN [--drops 0.1 ...] [--days-per-season 20]`: cuántos días hábiles seguidos necesita una medida para mostrar una baja dada en una temporada, con la variación de un día a otro y la deriva lenta, y cuántas temporadas cuando una no alcanza. Con la deriva (0.15), ninguna baja menor a ~31 % se ve en una sola temporada; en feb–may 2025, con 20 días por temporada, una baja de 30 % pide 2 temporadas, 20 % 5, 10 % 20 y 5 % 84.

El rango sale de eventos falsos de la misma duración sacados de días normales (placebo). Cuando la medida dura tanto como la referencia o más (una medida sostenida de meses), no hay suficientes días para el placebo: el rango y el mínimo detectable se extrapolan con la variación de un día a otro de la temporada, con la regla que siguen los placebos cortos (desviación ∝ √(1/k + 1/n), con k días de la medida y n de referencia). La ficha dice cuál de los dos usó.

## Validación

| Lo que afirma la ficha | Prueba | Resultado | ¿Pasa? |
|---|---|---|---|
| El rango contiene el cambio real | 200 conjuntos de 9 días normales de nov–dic 2023, con bajas inyectadas de 0, 10, 20, 30 y 36 % | Lo contenía 84–87 % de las veces (nominal 90 %) | Corregido: ver la calibración abajo |
| El cambio mínimo detectable | Las mismas inyecciones, con la baja igual al mínimo que reporta la ficha (36 % con 9 días) | Se detecta 78 % de las veces (prometido: 80 %) | Sí |
| Falsas alarmas | Inyección de 0 % | 4 % de "baja detectada" (esperado ~5 %) | Sí |
| Veredicto en un cambio real | Confinamiento de 2020 (fases 2 y 3 frente a la base; 42 días contra 29, modo extrapolado) | Baja detectada: −50 % (−62 a −33 %, con la deriva) | Sí |
| Veredicto sin cambio | Mismas fechas de 2019 | No detectable: −7 % (−29 a +21 %, con la deriva) | Sí |
| ¿El anuncio cabe? | Confinamiento con anuncios de −50 % y −10 % | −50 % cabe; −10 % no | Sí |
| Periodos atípicos | Vacaciones de fin de año de 2023 | La ficha mide +40 % y advierte que es un periodo donde el método confunde acumulación con emisión | Sí, con la advertencia |
| Pruebas automáticas | Datos sintéticos con baja impuesta y sin cambio; modo extrapolado; advertencia; inversión de la calculadora | 9 pruebas | Sí |

### Calibración del rango

En 960 inyecciones (4 temporadas: nov–dic 2023, nov–dic 2024, feb–may 2025 y nov–dic 2025; 120 conjuntos de 9 días por temporada con bajas de 0 y 20 %), el rango del placebo contenía la verdad el 88 % de las veces, con 6.5 % de falsas alarmas. Ensanchado 5 % en escala logarítmica alrededor de su centro (`products.RANGE_WIDENING`):

| Ensanchamiento | Contiene la verdad | Falsas alarmas | Detecta una baja de 20 % |
|---|---|---|---|
| Ninguno | 88 % | 6.5 % | 48 % |
| **5 % (el de la ficha)** | **91 %** (89–92 % por temporada) | **5.0 %** | 46 % |
| 10 % | 92 % | 4.0 % | 44 % |

Esta calibración usa eventos falsos de días sueltos al azar; para medidas de días seguidos, ver la deriva lenta abajo.

### La deriva lenta: medidas de días seguidos

Una medida real ocupa días seguidos (semanas o meses), no días sueltos. Dentro de cada temporada, E7 tiene una deriva lenta: semanas más altas o más bajas que el clima no explica (noviembre frente a diciembre, febrero frente a mayo). Los eventos falsos de días sueltos la promedian y no la ven.

| Prueba (sin cambio real, salvo la inyectada) | Sin la deriva | Con la deriva (`DRIFT_SD` = 0.15) |
|---|---|---|
| Media temporada contra la otra media (6 temporadas, 72 casos, modo extrapolado) | Contiene la verdad 50 %, falsas alarmas 50 % | 92 %, 8 % |
| Bloques de 9 y 20 días seguidos (feb–may 2025, lluvias 2025, feb–may 2026; 96 casos) | 65 %, 35 % | 98 %, 2 % |

- La dispersión real de media temporada contra la otra media es 0.19 (escala logarítmica); la ficha decía 0.09.
- Las lluvias (junio–octubre) casi no tienen deriva (0.05); feb–may y nov–dic, sí (0.12–0.23).
- Un placebo de bloques continuos de la misma temporada no la corrige (50–78 %): los extremos de la temporada, donde la deriva es mayor, no tienen bloques de referencia.
- La ficha ahora detecta si los días de la medida son seguidos (modo `drift`) y suma la deriva al rango; con días sueltos (contingencias) usa el placebo de siempre. El costo: el mínimo detectable de una medida de días seguidos sube a 39–47 % con 9 días y 32–34 % con 60, en una temporada.
- El confinamiento sigue siendo detectado (−50 %, mucho mayor que la deriva) y su placebo de 2019 (−7 %) cabe en el rango.
- Las dos calibraciones salen de los mismos datos que validan (no hay temporadas aparte): son estimaciones dentro de la muestra.

### Varias temporadas

`ficha-medida` acepta varias temporadas (`--data` repetido): cada una se compara con sus propios días normales y los cambios se combinan pesando cada temporada por su precisión (inverso de la varianza en escala logarítmica). Validación con inyecciones en nov–dic 2023 y nov–dic 2024 (150 repeticiones, 9 días por temporada):

| Baja inyectada | El rango combinado contiene la verdad | Se detecta la baja |
|---|---|---|
| 0 % | 87 % | 6 % (falsa alarma) |
| 10 % | 88 % | 37 % |
| 20 % (el mínimo que reporta la ficha combinada) | 89 % | 78 % |
| 30 % | 87 % | 99 % |

Con dos temporadas, el mínimo detectable con 9 días por temporada baja de 36 % y 26 % (cada una sola) a 20 %; con las seis de 2023–2026 y la deriva incluida, a 20 % ([temporadas.md](temporadas.md)). La combinación supone que la deriva de cada temporada es independiente: lo es entre feb–may 2025 y 2026, pero los inviernos de 2023 y 2025 se parecen. Las temporadas desde 2025 leen las estaciones de OpenAQ y el viento de los aeropuertos (`sources_for`).

Pendiente: la prueba de comprensión con tres personas fuera del equipo; protocolo, fichas y registro en `context/management/prueba_fichas/`.

## Lo que muestran las fichas de ejemplo

- **Días necesarios en invierno (nov–dic 2023):** 19 días hábiles para una baja de 30 %, 48 para 20 %, 214 para 10 % y ~900 para 5 %. Con la variación del invierno, las medidas de 5–10 % no se pueden evaluar en una temporada; en feb–may la variación es menor. Es el argumento cuantitativo para sumar temporadas (2024–2026).
- La cobertura de las medidas de días seguidos se validó con bloques continuos de días reales (ver la deriva lenta): sin la deriva, la ficha prometía 90 % y cumplía 50–65 %.

## Reproducir

```bash
uv run nox-ml ficha-dias --data 2023-11-01:2023-12-31
uv run nox-ml ficha-medida --days 2023-12-18:2023-12-29 --data 2023-11-01:2023-12-31 --title "Vacaciones de fin de año 2023"
```

## Segunda opinión del satélite (2026-11-05)

`ficha-medida` lee, en las temporadas con píxeles de TEMPO, la emisión de la ciudad del satélite solo (divergencia de flujo, vida media de 2 h; [sesgo_domingo.md](sesgo_domingo.md)) en los mismos días de la medida, con el mismo placebo, deriva y extrapolación que E7, y dice si coincide con las estaciones (mismo veredicto y rangos que se cruzan). Con varias temporadas, combina también las del satélite.

- No se combina con E7: los dos ven la misma deriva, así que la combinación no baja el mínimo detectable de medidas de días seguidos (0.164 frente a 0.163 en bloques de 9 días; [deriva.md](deriva.md)). Su valor es ser independiente de las estaciones y del modelo de transporte.
- Prueba con datos reales, días sin ninguna medida: 4 semanas de marzo de 2025 (E7 +23 %, satélite +15 %, coinciden, no detectable); 4 semanas en 3 temporadas (+9 % y +6 %, coinciden); 5 días sueltos de feb–may 2025, donde E7 dio una falsa alarma (+34 %, "aumento") y el satélite no (−17 %, no detectable): la ficha avisa que no coinciden.
- Sin píxeles de TEMPO, o con menos de 2 días de la medida sin nubes, la ficha lo dice y no da segunda opinión.
- Ambas fichas escriben también un JSON con los números (`medida_*.json`, `dias_*.json`), para que otros programas (la interfaz) no lean el texto.

### Calibración de la segunda opinión

Inyecciones de bajas de 0 y 20 % en el satélite, en 6 temporadas (sin feb–may 2024), con bloques de 5, 9 y 20 días seguidos y conjuntos de días al azar (1,100 casos por baja):

| | Días al azar (5 / 9 / 20) | Días seguidos (5 / 9 / 20) |
|---|---|---|
| El rango contiene la verdad (nominal 90 %) | 92 / 92 / 98 % | 94 / 87 / 95 % |
| Falsas alarmas (sin cambio) | 8 / 8 / 2 % | 4 / 13 / 5 % |
| Detecta una baja de 20 % | 54 / 71 / 51 % | 32 / 29 / 33 % |
| El veredicto no coincide con E7, sin cambio | 14 / 11 / 6 % | 13 / 21 / 7 % |
| El veredicto no coincide con E7, baja de 20 % | 35 / 39 / 33 % | 23 / 20 / 29 % |

- Los rangos de E7 y del satélite nunca dejaron de cruzarse: los desacuerdos son siempre de veredicto (uno detecta y el otro no), sobre todo con cambios cerca del mínimo detectable. La ficha distingue tres casos: coinciden, el veredicto no coincide (indicio, no resultado firme) y se contradicen (rangos que no se cruzan; no se vio en las inyecciones).
- E7 en esta prueba es su serie diaria (la media de cada día, como el satélite), no el ajuste completo de la ficha: aproxima su ruido, no lo reproduce.
