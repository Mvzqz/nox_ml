# El sesgo del domingo: qué lo explica y qué no

Fecha: 2026-10-29. Todos los modelos daban domingo ÷ hábil de 0.42–0.56 en nov–dic 2023, por debajo de la referencia de tráfico (0.65–0.73). Esta nota junta la evidencia de [verificaciones_nivel1.md](verificaciones_nivel1.md), [controles_de_verdad.md](controles_de_verdad.md) y dos pruebas nuevas: el peso de TEMPO y la referencia de Infovial.

## Resumen

| Causa candidata | Veredicto | Evidencia |
|---|---|---|
| El método (inversión o estimador) | **No** | Con gemelos de verdad conocida (0.69), los modelos recuperan 0.66–0.77 |
| Días hábiles de fin de año en la referencia | **Sí, en parte** | Sin el 18–29 de diciembre: E7 0.56 → 0.63–0.65, E6 0.53 → 0.75, E2 0.52 → 0.59, E5b 0.48 → 0.53 |
| Peso de TEMPO | No como causa principal | Bajarlo de ×1 a ×10 no sube el domingo; solo quitarlo casi del todo, y entonces la inversión queda mal condicionada |
| Referencia de tráfico mal ponderada | No | Con cualquier ponderación de los pesados, Infovial da ≥ 0.64 en el día completo y ≥ 0.72 en la tarde |
| Transporte equivocado | Sí, para la pluma | En gemelos generados con puffs, la pluma da 0.51–0.65; los puffs, no |

Con fin de año fuera y los intervalos honestos (bootstrap por bloques de 7 días), E7 y E6 quedan dentro del rango del tráfico y las inversiones con puffs (E2 0.59, E5b 0.53, 0.44–0.67) quedan 0.05–0.10 por debajo, con el límite superior del intervalo de E5b tocando la referencia.

## Peso de TEMPO

E2 y E5b ajustados a los datos reales con el error de cada píxel multiplicado (`tempo_sigma_mult`):

| Peso de TEMPO | E2, todos los días | E2, sin fin de año | E5b, todos los días | E5b, sin fin de año |
|---|---|---|---|---|
| ×1 (nominal) | 0.52 | 0.59 | 0.48 | 0.53 |
| ×3 | 0.49 | 0.59 | 0.46 | 0.54 |
| ×10 | 0.45 | 0.60 | 0.40 | 0.56 |
| ×1000 (casi sin TEMPO) | 0.74 (0.56–0.99) | 0.89 (0.64–1.20) | 0.71 (0.52–0.90) | 0.92 (0.71–1.24) |

- Entre ×1 y ×10 el domingo casi no se mueve; sin fin de año, nada.
- Sin TEMPO el domingo salta, pero con intervalos enormes. La inversión solo con estaciones no es confiable: en el confinamiento inventó una caída de 42 % en 2019, el año sin cambio, porque el fondo por hora y la emisión se intercambian.
- La investigación (`reports/fondo_tempo.md`) atribuía el domingo bajo a TEMPO con la pluma y σθ = 30°; con los puffs y el peso nominal, la evidencia no lo sostiene.

## Referencia de Infovial

Infovial, enero de 2017 (sin el 1 y el 2 de enero), 26 vialidades primarias. Clases C1…C6 sin definición oficial; se suponen ordenadas por tamaño. Proporción de los conteos: C1 63 %, C2 25 %, C3 6 %, C4–C6 5 %.

| Ponderación de las clases | Tarde (12–17 h): domingo / sábado | Día completo: domingo / sábado |
|---|---|---|
| Conteos | 0.91 / 0.99 | 0.84 / 0.96 |
| Pesos 1, 2, 5, 10, 15, 20 (la de la investigación) | 0.80 / 0.95 | 0.73 / 0.89 |
| Pesados × 3 (1, 2, 15, 30, 45, 60) | 0.74 / 0.93 | 0.67 / 0.85 |
| Solo C3–C6 | 0.73 / 0.92 | 0.65 / 0.84 |

Sin la primera semana de enero (vacaciones escolares) las cifras cambian en ±0.01. Aun suponiendo que solo los pesados emiten NOₓ, el domingo del tráfico no baja de 0.64. La referencia de 0.65–0.73 es la del día completo, la que corresponde a modelos con memoria del transporte (puffs de 24 h).

Limitaciones de la referencia: son vialidades primarias de 2017. Después de 2020 el trabajo desde casa bajó el tráfico de los días hábiles, lo que subiría el domingo/hábil, no lo bajaría.

## Qué queda sin explicar

Las inversiones con puffs quedan 0.05–0.10 por debajo del tráfico aun sin fin de año. Candidatas, sin probar:
- **Fuentes no viales con ciclo semanal** (industria y comercio que bajan en domingo): el modelo carga toda la emisión de las regiones a las vialidades. Si fueran ~20 % del NOₓ con un domingo de 0.5, el total bajaría solo a ~0.65: alcanzaría para una parte.
- **Otros periodos atípicos** además del fin de año (puentes, quincenas), que la sensibilidad de festivos no cubre.
- **El a priori:** la investigación encontró que, sin TEMPO, el 0.42 de la pluma lo fijaban los a priori y no los datos.

## Consecuencias

- Para el producto, la referencia de día hábil debe excluir periodos atípicos de forma automática: el fin de año explica la mayor parte del sesgo de E6 y E7.
- Los cocientes de las inversiones se reportan con intervalos por bloques de 7 días; con ellos, E5b sin fin de año es compatible con el tráfico en el límite superior.
- La brecha restante (0.05–0.10) es del orden del límite de detección de una temporada: no invalida los cambios grandes (como el confinamiento), pero sí pide cautela con cambios de 5–10 %.
