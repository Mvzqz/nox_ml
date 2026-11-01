# El sesgo del domingo: qué lo explica y qué no

Fecha: 2026-10-29; actualizado el 2026-11-01 (ver «La referencia del tráfico estaba alta», abajo). Todos los modelos daban domingo ÷ hábil de 0.42–0.56 en nov–dic 2023, por debajo de la referencia de tráfico (0.65–0.73). Esta nota junta la evidencia de [verificaciones_nivel1.md](verificaciones_nivel1.md), [controles_de_verdad.md](controles_de_verdad.md) y dos pruebas nuevas: el peso de TEMPO y la referencia de Infovial.

## Resumen

| Causa candidata | Veredicto | Evidencia |
|---|---|---|
| El método (inversión o estimador) | **No** | Con gemelos de verdad conocida (0.69), los modelos recuperan 0.66–0.77 |
| Días hábiles de fin de año en la referencia (acumulación que los modelos atribuyen a la emisión; el tráfico de esas fechas es normal) | **Sí, en parte** | Sin el 18–29 de diciembre: E7 0.56 → 0.63–0.65, E6 0.53 → 0.75, E2 0.52 → 0.59, E5b 0.48 → 0.53 |
| Peso de TEMPO | No como causa principal | Bajarlo de ×1 a ×10 no sube el domingo; solo quitarlo casi del todo, y entonces la inversión queda mal condicionada |
| Referencia de tráfico mal ponderada | No | Con cualquier ponderación de los pesados, Infovial da ≥ 0.64 en el día completo y ≥ 0.72 en la tarde |
| **Infovial como referencia de la emisión** (2026-11-01) | **Sí, en parte** | El satélite da 0.58 (0.54–0.61) con las 6 temporadas juntas, igual con o sin corrección por viento y capa de mezcla; el CO como trazador, 0.56–0.74. Las dos excluyen 0.76–0.81, pero son métodos de concentración o columna: no se descarta un sesgo común (ver «Revisión adversarial») |
| NO₂/NOₓ fijo, fondo, perfil horario, piso de viento (2026-11-01) | No | Ninguno sube el domingo de E2 o E5b; los cuatro lo dejan igual o lo bajan |
| Transporte equivocado | Sí, para la pluma | En gemelos generados con puffs, la pluma da 0.51–0.65; los puffs, no |

Con fin de año fuera y los intervalos honestos (bootstrap por bloques de 7 días), E7 (0.63–0.65) y E6 (0.75) quedan en el rango de enero de 2017 (0.65–0.73) o cerca del de noviembre–diciembre de 2018 (0.76–0.81). Las inversiones con puffs (E2 0.59, E5b 0.53, 0.44–0.67) quedan 0.1–0.25 por debajo.

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

Sin la primera semana de enero (vacaciones escolares) las cifras cambian en ±0.01.

**Noviembre–diciembre de 2018** (la misma temporada que nuestros datos; ponderado 1, 2, 5, 10, 15, 20):

| | Tarde (12–17 h) | Día completo |
|---|---|---|
| Domingo ÷ hábil (hasta el 11 de diciembre) | 0.81 | 0.76 |
| Días hábiles del 12 al 14 de diciembre ÷ normales | 1.02 | 1.01 |
| Días hábiles del 17 al 21 de diciembre ÷ normales | 1.02 | 1.01 |
| Días hábiles del 26 al 28 de diciembre ÷ normales | 0.97 | 0.91 |

- En noviembre–diciembre la referencia del domingo es más alta que en enero: 0.76–0.81. La brecha de las inversiones es mayor de lo que creíamos (E5b sin fin de año, 0.53).
- **El tráfico de fin de año no sube.** El NOₓ alto de los días hábiles del 18 al 22 de diciembre de 2023 no es más tráfico: es acumulación que los modelos no separan de la emisión. El fin de año se excluye de la referencia porque ahí los modelos fallan, no porque haya más autos. Aun suponiendo que solo los pesados emiten NOₓ, el domingo del tráfico no baja de 0.64. La referencia de 0.65–0.73 es la del día completo, la que corresponde a modelos con memoria del transporte (puffs de 24 h).

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

## Mejoras de modelo probadas sin efecto (2026-10-29)

Con E2 en nov–dic 2023:

| Cambio | Error con estación oculta | Domingo | Sin fin de año | Fin de año ÷ normal |
|---|---|---|---|---|
| Ninguno (viento del dominio, puffs de 24 h) | 12.50 | 0.52 | 0.59 | 1.23 |
| Campo de viento: cada fuente con el viento de las 20 estaciones interpolado en su ubicación (`wind_field`) | 12.62 | 0.49 | 0.52 | — |
| Puffs de 48 h | 12.49 | 0.52 | 0.59 | 1.23 |
| Puffs de 72 h | 12.49 | 0.52 | 0.59 | 1.23 |
| Viento de los aeropuertos en lugar del de la red | 12.53 | 0.52 | — | — |

- El campo de viento no mejora: el viento de cada estación es local (calles, edificios) y moverse con él agrega ruido. Queda como opción apagada.
- La memoria de varios días no cambia nada: con la química de OH el NOₓ vive pocas horas y lo emitido hace más de un día casi no aporta. El exceso de fin de año no es NOₓ viejo; es algo que el modelo no representa (capa de mezcla, fuentes de diciembre o fondo regional).
- Las inversiones dependen poco del detalle del viento: con el de los aeropuertos dan lo mismo. Los estadísticos sí cambian (E7 16.75 → 18.04 ppb; el domingo de E6, 0.53 → 0.44).

## Noviembre–diciembre de 2024: una temporada nueva

Con los modelos congelados (`configs/seasons/`), en un año que no se usó para elegir nada. Primera corrida, con el 18 de noviembre y el 25 de diciembre contados por error como hábiles (se repite con los festivos corregidos):

| Modelo | Error con estación oculta 2024 (2023) | Domingo ÷ hábil 2024 | Placebo |
|---|---|---|---|
| E7 | 15.3 (16.75) | 0.59 (0.46–0.75) | 1.04 ± 0.22 |
| E6 | 13.8 (14.6) | 0.72 (0.62–0.92) | 1.02 ± 0.10 |
| X4 | 13.6 (14.3) | 0.67 (0.60–0.79) | 1.01 ± 0.13 |
| E2 | 12.1 (12.5) | 0.64 (0.54–0.72) | 0.98 ± 0.16 |
| E5b | 11.5 (11.87) | 0.61 (0.42–0.80) | 0.93 ± 0.25 |

**Corrección (2026-11-01):** esa primera corrida contaba dos festivos como días hábiles. Con los festivos corregidos y sin periodos atípicos (`results/runs/*.nd2024/`), E5b da 0.50 y E2 0.61, y en las temporadas de 2025–2026 E5b da 0.36–0.49: el sesgo de las inversiones **no** era propio de 2023. La conclusión «buena parte del sesgo de 2023 era de esa temporada» no se sostiene.

## La referencia del tráfico estaba alta (2026-11-01)

La referencia de 0.76–0.81 es el tráfico contado en vialidades primarias (Infovial). Dos pruebas con los datos de SIMAT, que no usan Infovial ni el modelo de NOₓ:

**1. NOₓ frente a CO.** El CO sale casi todo de vehículos a gasolina (inventario 2018 de la ZMVM); el NOₓ, en buena parte del diésel. La pendiente ΔNOₓ/ΔCO de cada tipo de día (anomalías por estación) cancela la meteorología y los fondos:

| Temporada | Horario | ΔNOₓ/ΔCO, domingo ÷ hábil |
|---|---|---|
| nov–dic 2023 | mañana / tarde | 0.97 (0.93–1.07) / 0.84 (0.74–1.01) |
| feb–may 2024 | mañana / tarde | 0.88 (0.81–0.93) / 0.65 (0.51–0.81) |
| nov–dic 2024 | tarde | 0.94 (0.86–1.06) |

El NOₓ cae solo ~5–15 % más que el CO en domingo: el diésel baja más que los autos (en Infovial, las clases pesadas C5–C6 caen a 0.44–0.52 y C1 a 0.89), pero no alcanza para una caída de ~50 %. Con el reparto del inventario 2018 (pesados ~22 % del NOₓ), la ponderación por clase deja la referencia en ~0.8.

**2. El CO como trazador de la actividad.** El estimador normalizado (E7: observado ÷ modelado con emisión fija) aplicado al CO, con el mismo transporte y sin periodos atípicos:

| Temporada | CO, fondo 0 | CO, fondo = p5 | NOₓ, fondo 0 | NOₓ, fondo = p5 |
|---|---|---|---|---|
| nov–dic 2023 (7 domingos) | 0.82 (0.64–1.04) | 0.76 | 0.71 | 0.59 |
| feb–may 2024 | 0.80 (0.68–0.90) | 0.71 | 0.70 | 0.51 |
| nov–dic 2024 | 0.70 (0.59–0.84) | 0.62 | 0.66 | 0.54 |

La emisión de CO cae a 0.70–0.82 en domingo ya descontado el clima, contra 0.89–0.96 de los autos contados en Infovial: la actividad de toda la zona metropolitana cae más que la de las vialidades primarias. Con el factor del diésel (×0.9), la emisión de NOₓ del domingo queda en **0.56–0.74**, según el fondo que se suponga (el factor mismo varía de 0.65 a 0.97 entre temporadas y horarios). Es independiente de Infovial y del modelo de NOₓ, pero usa el mismo transporte y un fondo supuesto. Es de la misma magnitud que la caída de las concentraciones matutinas del domingo en la ciudad durante 1986–2007 (0.53–0.72; promedio de los tres valores más altos de 7 a 12 h, Stephens et al., 2008, ACP 8:5313); aquellas son concentraciones, no emisiones.

**Lectura:**

| Estimador | Domingo ÷ hábil (2023–2026) | Frente a 0.56–0.74 |
|---|---|---|
| X4 | 0.57–0.58 | En el borde inferior |
| E7 | 0.47–0.64 (0.47 en feb–may 2026, por una corrección excesiva del clima) | Casi siempre dentro o en el borde |
| E2 | 0.47–0.61 | Borde inferior |
| E5b | 0.36–0.53 | Debajo, en todas las temporadas |

Parte del «sesgo del domingo» era la referencia. El de las inversiones con puffs es real pero menor de lo que se creía: ~0.1–0.25, no ~0.3. El estimador estadístico más estable (X4) queda en el borde inferior (0.57–0.58) en las cuatro temporadas.

## El satélite solo: divergencia de flujo de TEMPO (2026-11-01)

`nox-ml flux-divergence` (`nox_ml.validation.divergence`, método de Beirle et al. 2019). Cada escaneo de la tarde se pasa a una malla de 5 km. La emisión de cada celda es lo que sale (divergencia del flujo de NO₂ con el viento de la hora) más lo que quita la química (columna sobre el fondo ÷ τ), con la columna convertida a NOₓ con el cociente NO₂/NOₓ medido en esa hora. No usa el NOₓ de las estaciones (salvo ese cociente, que mueve el resultado ~0.02), ni Infovial, ni el modelo de transporte. Escribe la serie diaria (CSV) con el viento, la capa de mezcla y los dos términos por separado, y el placebo con el límite de detección.

| Temporada | Domingo ÷ hábil, τ 2 h | τ 4 h | Sábado ÷ hábil, τ 2 h | Placebo (9 días) | Límite de detección, 9 días |
|---|---|---|---|---|---|
| nov–dic 2023 | 0.56 (0.47–0.68) | 0.55 (0.44–0.68) | 0.74 | 1.00 (0.79–1.28) | 31 % |
| feb–may 2024 | 0.51 (0.45–0.58) | 0.51 (0.43–0.59) | 0.76 | 1.00 (0.82–1.23) | 26 % |
| nov–dic 2024 | 0.60 (0.49–0.72) | 0.60 (0.48–0.72) | 0.80 | 1.00 (0.86–1.17) | 20 % |
| feb–may 2025 | 0.61 (0.54–0.69) | 0.61 (0.53–0.71) | 0.90 | 0.99 (0.85–1.18) | 22 % |
| nov–dic 2025 | 0.57 (0.46–0.69) | 0.58 (0.46–0.71) | 1.00 | 1.00 (0.91–1.10) | 14 % |
| feb–may 2026 | 0.53 (0.46–0.60) | 0.49 (0.41–0.60) | 0.85 | 0.99 (0.85–1.15) | 21 % |

**Qué mide en realidad.** El término químico pesa 77–91 % del total con τ = 2 h, así que el cociente es casi el de la columna de NO₂ sobre el fondo: por eso no cambia con τ (escala igual a todos los días) ni con la altura del viento (×1 o ×2.5). No es una prueba de robustez del flujo. Dos pruebas de que aun así refleja la emisión y no el clima:

- **Corrección por clima:** con log(columna) ~ temporada + log(viento) + log(capa de mezcla) ajustado en los días hábiles, el domingo queda igual: 0.58 (0.54–0.61) sin corregir y 0.58 (0.54–0.61) corregido, con las 6 temporadas juntas (47 domingos, bootstrap por semanas); por temporada, 0.55–0.67 corregido. En promedio el domingo tiene el mismo viento (0.99 del hábil) y la misma capa de mezcla (1.02).
- **La divergencia sola** (τ = ∞, la parte que sí usa el viento) es ruidosa por temporada (0.29–0.72), pero junta da 0.54 (0.39–0.70): también excluye 0.76–0.81.

**Lo que no se probó:** una vida media distinta por tipo de día. La química del OH no es lineal; si el NOₓ del domingo vive menos, la emisión sería mayor que la columna (con τ del domingo 0.8 del hábil, 0.58 pasaría a ~0.73), y al revés si vive más. El signo no se conoce con estos datos.

**La magnitud no valida nada.** 79–132 kt/año con τ de 2–4 h frente a 144 kt/año del inventario 2018 es el mismo orden de magnitud, pero el valor cambia ×1.9 con τ y ×1.7 con el fondo, y extrapola la tarde a todo el día.

**Referencia del domingo: 0.58 (0.54–0.61) por el satélite y 0.56–0.74 por el CO.** Las dos excluyen el tráfico contado (0.76–0.81): Infovial (26 vialidades primarias de 2017–2018) no se ajusta a la emisión total de NOₓ en domingo. Las tres referencias que lo excluyen (satélite, CO y los estimadores) son métodos de concentración o columna, así que no se descarta del todo un sesgo común; separarlo pide un ancla de emisión que no sea concentración (ventas de combustible, aforos recientes). Frente al satélite, temporada por temporada:

| Temporada | TEMPO | E5b | E2 | E7 | X4 |
|---|---|---|---|---|---|
| nov–dic 2023 | 0.55–0.56 | 0.49 | 0.59 | 0.64 | 0.68 |
| feb–may 2024 | 0.51 | 0.49 (prueba) | — | — | — |
| nov–dic 2024 | 0.60 | 0.50 | 0.61 | 0.57 | 0.57 |
| feb–may 2025 | 0.61 | 0.49 | 0.57 | 0.64 | 0.57 |
| nov–dic 2025 | 0.57–0.58 | 0.36 | 0.47 | 0.57 | 0.57 |
| feb–may 2026 | 0.49–0.53 | 0.49 | 0.56 | 0.47 | 0.58 |

- Todas las cifras sin periodos atípicos. E2, E7 y X4 son compatibles con el satélite dentro de intervalos de ±0.1–0.2. E2 y E5b además usan TEMPO, así que su comparación no es independiente.
- E5b queda en promedio ~0.07 por debajo del satélite y es inestable entre temporadas (0.36 en nov–dic 2025).
- Una parte importante del «sesgo del domingo» del avance 4 se explica porque la referencia de tráfico mide otra cosa. La brecha restante de E5b sigue sin explicación.
- Sábado: con las 6 temporadas juntas, 0.86 (0.81–0.92; 42 sábados), igual en invierno (0.86) y en feb–may (0.87). Con una sola temporada no se estima.
- Combinar el satélite con E7 (pesos de mínima varianza, elegidos con los mismos datos) baja el límite de detección de 9 días de 23–31 % (E7) a 15–25 %. Las dos series diarias se correlacionan (+0.3 a +0.6), por variación real de la emisión o por clima compartido. Antes de usarlo en las fichas hay que fijar los pesos de antemano.
- El satélite también ve el aumento antes de Navidad (18–22 de diciembre: +26 % en 2023, +27 % en 2025). Como el cociente es casi el de la columna, no separa más emisión de acumulación: no confirma ni descarta la explicación de la acumulación.

### Revisión adversarial (2026-11-01)

Una revisión independiente encontró que el cociente del satélite es casi el de la columna (arriba), que el rango del CO estaba recortado (0.60 → 0.56), que Stephens et al. mide concentraciones de la mañana y no emisiones, y que E5b sí queda ~0.07 por debajo. Todo eso está corregido arriba. La corrección por clima y la divergencia sola se hicieron después, para responderla.

## Causas del modelo probadas sin efecto (2026-11-01)

Nov–dic 2023, sin cambiar nada más; ninguna sube el domingo:

| Cambio | Modelo | Error con estación oculta | Domingo | Placebo |
|---|---|---|---|---|
| Ninguno | E5b / E2 | 11.87 / 12.50 | 0.48 / 0.52 | 1.01 ± 0.12 / 0.97 ± 0.16 |
| NO₂/NOₓ de cada hora (0.78 hábil, 0.85 domingo; 0.69 a las 11 h, 0.85 a las 16 h) en lugar del fijo 0.774 (`hourly_no2_nox`) | E5b / E2 | 11.9 / 12.5 | 0.45 / 0.49 | 1.02 ± 0.14 / 0.99 ± 0.17 |
| Fondo de cada hora más rígido (desviación a priori × 0.3) | E2 | 15.8 | 0.48 | 1.00 ± 0.14 |
| Fondo más libre (× 3) | E2 | 12.4 | 0.52 | 0.96 ± 0.16 |
| Perfil horario de Infovial de cada tipo de día también de 6 a 17 h (el domingo sin hora pico de la mañana) | E2 | 12.6 | 0.49 | 0.96 ± 0.16 |
| Piso de viento 1 m/s | E5b | 12.0 | 0.50 | 1.02 ± 0.12 |
| Piso de viento 3 m/s | E5b | 11.9 | 0.45 | 1.00 ± 0.13 |

- El NO₂/NOₓ de cada hora es físicamente más correcto (queda como opción, apagada por defecto), pero baja el domingo: la conversión fija sobreestimaba el NOₓ del domingo que ve TEMPO.
- El piso de viento mueve el domingo de forma sistemática (0.50 → 0.48 → 0.45 con 1, 2 y 3 m/s), pero solo ±0.03.
- Queda sin probar: fuentes no viales con ciclo semanal (industria), gemelos con un fondo que tenga ciclo semanal, y la ventaja de E5b concentrada en la estación SAG.
