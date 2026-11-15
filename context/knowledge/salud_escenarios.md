# Simulador de salud: muertes y asma evitadas (frente F5)

Fecha: 2026-11-15. Rama `explore/health-scenarios`. Pregunta: si la emisión vial de NOₓ bajara 5, 10, 20 o 30 %, ¿cuántas muertes de adultos y casos nuevos de asma infantil se evitarían al año en la ZMVM? Plan: [exploraciones_valor.md](../management/exploraciones_valor.md), sección F5.

## Resumen

Con el NO₂ promedio anual de las estaciones (22 ppb) y una elasticidad empírica de 0.40 (el domingo la emisión baja ~50 % y el NO₂ de 24 h baja 19 %), una baja de 10 % de la emisión vial baja el NO₂ ~0.8 ppb y evita **~430 muertes al año (rango 90 %: 180–760) y ~155 casos nuevos de asma infantil (70–295)**. Los resultados escalan casi linealmente. El control con la literatura es **parcial**: no se encontró una estimación publicada de carga de NO₂ en la Ciudad de México; la fracción atribuible de asma que sale aquí (18 %, 10–26 %) coincide con la publicada para ciudades (16 % urbano en 2019, Anenberg et al., 2022), y las muertes atribuibles totales (~10 000 sin umbral, ~7 300 sobre la guía de la OMS) quedan en el orden de la carga publicada de PM₂.₅ en la ciudad (~6 700, C40), no más allá. La incertidumbre mayor está en la función de riesgo y en el supuesto de que el recorte vial mueve el NO₂ como lo mueve el domingo.

## Método

1. **Concentración de partida.** SIMAT, NO₂ horario en ppb de estaciones a ≤ 45 km del Zócalo; media diaria con ≥ 18 horas; media anual de estaciones con ≥ 75 % de días (`results/annual_no2_by_station.csv`): 2019 21.3 ppb (23 estaciones), 2023 21.2 (19), 2024 23.2 (18). Base: 22.2 ppb (2023–2024). Es un promedio simple de estaciones, no ponderado por población; en el Monte Carlo se multiplica por U(0.8, 1.0) porque las estaciones sobrerrepresentan zonas viales.
2. **De emisión a concentración (elasticidad del domingo).** No se invirtió con la matriz de transporte (no hay corrida del modelo final para esta pregunta y el plan pedía lo simple). Cociente domingo/entre semana del NO₂ de 24 h, normalizado por estación y año, sin festivos ni días atípicos (Semana Santa, fin de año), 2019, 2023 y 2024: **0.814 (0.790–0.842)**, bootstrap de semanas. La emisión baja el domingo ~50 % (triangular 30–50–60 %); elasticidad = (1 − cociente) / baja de emisión = **0.40 (0.31–0.54)**. Sin emparejar por clima (F2 mostró que emparejarlo cambia poco). Caveats: (a) el domingo baja toda la actividad, no solo la vial, así que la elasticidad respecto a la emisión vial sola está algo sobreestimada; (b) es una respuesta de un día, y una baja sostenida arrastra también el fondo, que responde más lento.
3. **Conversión NO₂/NOₓ.** No hace falta: la elasticidad se mide directo sobre NO₂, que es lo que usan las funciones de riesgo.
4. **Unidades.** SIMAT da ppb; Huangfu y Atkinson usan µg/m³. Se convierte con 1 ppb = U(1.47, 1.88) µg/m³ (1.88 a 25 °C y 1 atm; 1.47 a la presión y temperatura de la ZMVM). Stieb usa ppb y no necesita conversión.
5. **Monte Carlo** (20 000 realizaciones, semilla fija): coeficiente de riesgo normal en log con el IC 95 % publicado; elasticidad; concentración base; conversión de unidades; muertes de línea base ±10 %; incidencia de asma triangular. Mortalidad: mitad de las realizaciones con Huangfu y Atkinson, mitad con Stieb (se reportan también por separado). Muertes evitadas = D · (1 − exp(−β · ΔNO₂)); sin umbral.

## Funciones de riesgo (fuentes verificadas en la web)

| Fuente | Resultado | Unidad | IC 95 % | Estado |
|---|---|---|---|---|
| Huangfu y Atkinson (2020), NO₂ de largo plazo, mortalidad por todas las causas | RR 1.02 | por 10 µg/m³ | 1.01–1.04 | Verificado (resumen en Europe PMC). Revisión que sustenta las guías OMS 2021. |
| Stieb et al. (2021), 79 estudios de 47 cohortes, mortalidad por causas naturales | HR 1.047 | por 10 ppb | 1.023–1.072 | Verificado (resumen en Europe PMC). |
| Achakulwisut et al. (2019), asma infantil | coeficiente **no verificado** | | | Se confirmó el artículo y sus cifras globales (4.0 millones de casos, 13 %, 6–16 %); el texto completo dio 403 y no se pudo leer el coeficiente. Se usó RR 1.05 por 4 ppb (IC 1.02–1.07) de memoria (Khreis et al., 2017) como una mitad de las realizaciones. |
| Burkart et al. (2025), GBD 2023, asma infantil | RR 1.05 | por 5 ppb | no leído (se supuso 1.02–1.08) | Cifra central verificada en el resumen; es la otra mitad. |

Pendiente: leer el coeficiente exacto, el contrafactual y la cifra de la Ciudad de México en el texto de Achakulwisut et al.

## Tasas base

- **Población:** 21 804 515 (Censo 2020, ZMVM; DataMéxico/INEGI). `data/raw/inegi/` solo trae los polígonos de municipios, sin población, así que no se pondera por municipio. Menores de 18 años: 27 % (supuesto).
- **Muertes:** INEGI, defunciones registradas 2023: CDMX 78 598 y Estado de México 87 572 (nota periodística que cita a INEGI, sin confirmar el criterio de residencia). ZMVM ≈ CDMX + 73 % del Estado de México (59 municipios, 12.4 de 17.0 millones) ≈ 143 000; adultos (≥ 25) 97 %, ±10 % en el Monte Carlo. No se obtuvo la tabla por municipio.
- **Incidencia de asma infantil:** 0.15–0.3–0.5 % por niño-año (triangular). **Es un supuesto de orden de magnitud**, no una cifra de la Secretaría de Salud (no se encontró); es el supuesto más débil de los casos de asma.

## Resultados por escenario (rango del 90 %)

| Baja de la emisión vial | Baja del NO₂ (ppb) | Muertes evitadas al año | Con Huangfu | Con Stieb | Casos de asma infantil evitados al año |
|---|---|---|---|---|---|
| 5 % | 0.39 (0.30–0.54) | 214 (88–380) | 179 (67–330) | 248 (134–409) | 78 (35–148) |
| 10 % | 0.79 (0.61–1.09) | 428 (176–760) | 358 (133–659) | 496 (268–816) | 155 (69–295) |
| 20 % | 1.58 (1.21–2.17) | 854 (351–1515) | 715 (266–1315) | 989 (536–1628) | 309 (138–586) |
| 30 % | 2.37 (1.82–3.26) | 1279 (526–2267) | 1071 (399–1968) | 1481 (803–2435) | 461 (207–873) |

(`results/scenarios.csv`). Como referencia, 428 muertes son ~0.3 % de las defunciones de la ZMVM.

## Control con la literatura

Carga atribuible total con el mismo modelo (`results/attributable_burden.csv`): todo el NO₂ sobre cero, 10 400 muertes al año (4 400–16 500); solo lo que excede la guía OMS de 10 µg/m³, 7 300 (3 000–12 000); asma: 17.8 % de los casos nuevos (9.6–25.6 %), ~3 200 casos (1 600–5 400).

- **Asma:** Achakulwisut et al. (2019) dan 13 % global y hasta 20 % o más en 92 de 125 ciudades; Anenberg et al. (2022) dan 16 % urbano en 2019. Nuestro 18 % queda en el mismo orden. No se obtuvo el valor de la Ciudad de México.
- **Muertes:** no se encontró una estimación publicada de muertes por NO₂ en la ZMVM. Contexto, no control directo: C40 cita ~6 700 muertes anuales por PM₂.₅ en la Ciudad de México. Que el NO₂ solo (con un RR de 2–5 % por 10 unidades, bien por debajo del de PM₂.₅) dé 7 000–10 000 es plausible pero **no está controlado**, y debe leerse con cautela: los estudios multicontaminante dan coeficientes menores y casi todos no significativos (Stieb), y NO₂ y PM₂.₅ comparten parte del efecto.
- Veredicto del control: **orden de magnitud consistente en asma; sin control para muertes**.

## Ozono (F2), solo cualitativo

El centro está limitado por COV en la temporada de ozono (regimen_ozono.md: el ozono máximo de 8 h sube 3 % en domingo en el centro, aunque el NOₓ baja ~30 %). Una baja de NOₓ en el centro puede dejar igual o subir algo el ozono, y el ozono tiene sus propios efectos de salud y activa contingencias. Esta nota no lo resta: no hay base para cuantificarlo, y su dirección es reducir los beneficios del NO₂ en el centro, no en la periferia. Los beneficios aquí son solo los del NO₂.

## Supuestos y límites

- La función de riesgo es lineal sin umbral y de efecto causal único del NO₂ (la evidencia multicontaminante es más débil); el NO₂ puede ser un indicador de la mezcla del tráfico (en ese caso la reducción de la mezcla sí evita muertes, pero la causa no es el NO₂ solo).
- Concentración promedio de estaciones, sin ponderar por población ni capturar gradientes cerca de vialidades (que subestiman la exposición de quien vive junto a una avenida).
- Elasticidad del domingo, no de la inversión; la inversión daría la respuesta por zona, pero su incertidumbre es mayor que la de este rango.
- Efecto en 1 año; no hay retardo de la mortalidad ni cohortes.
- Las unidades de las funciones de riesgo están en su referencia de condiciones estándar; la conversión ppb–µg/m³ cubre 1.47–1.88.

## Cómo reproducir

```
nice -n 10 uv run python notebooks/exploraciones/health/health_scenarios.py
```

Usa `data/raw/simat/` (2019, 2023, 2024). Escribe `notebooks/exploraciones/health/results/*.csv`. Semilla fija; segundos de cómputo.

## Lo que faltó

Coeficiente verificado de Achakulwisut et al.; incidencia de asma de la Secretaría de Salud; defunciones y población por municipio (INEGI); una estimación publicada de carga de NO₂ en la ZMVM; ponderar por población; probar la elasticidad con la inversión del modelo final.

## Veredicto

| Criterio | Escala | Resultado |
|---|---|---|
| **¿Funciona?** | 0 no se probó · 1 no funciona · 2 funciona con condiciones · 3 funciona y está validado de forma independiente | **2.** Corre y da rangos; el control es parcial (asma sí, muertes no). |
| **Evidencia** | La prueba decisiva y su cifra | 10 % menos de emisión vial: ~430 muertes (180–760) y ~155 casos de asma (70–295) al año; carga total de asma 18 % frente a 16 % urbano publicado. |
| **Usuario** | Quién lo usaría | Autoridad ambiental y de salud pública, financiadores (CU9). |
| **Frecuencia** | Usos al año | ~2–4 (evaluación de medidas y programas, informes anuales); supuesto: una corrida por propuesta. |
| **Alternativa** | Ninguna · peor · igual · mejor | Igual: es la evaluación de impacto en salud estándar (OMS/GBD); lo nuevo es ligar la elasticidad al dato propio de la ciudad. |
| **Decisión que cambia** | | Priorizar medidas viales por beneficio en salud y dimensionar lo que está en juego antes de decidir; no decide por sí solo por el rango amplio. |
| **Costo de llevarlo a producto** | | ~3–5 días (tasas por municipio, ponderación por población, leer las fuentes faltantes); costo de operación casi nulo. |
| **Veredicto** | Adoptar · seguir con condiciones · descartar | **Seguir con condiciones:** cerrar las tasas base de INEGI y Secretaría de Salud, el coeficiente de Achakulwisut y la ponderación por población, y reportar siempre el rango y la penalización por ozono del centro. |

## Referencias

- Achakulwisut, P., Brauer, M., Hystad, P. y Anenberg, S. C. (2019). Global, national, and urban burdens of paediatric asthma incidence attributable to ambient NO₂ pollution: Estimates from global datasets. *The Lancet Planetary Health, 3*(4), e166–e178. https://doi.org/10.1016/S2542-5196(19)30046-4
- Anenberg, S. C., et al. (2022). Long-term trends in urban NO₂ concentrations and associated paediatric asthma incidence: Estimates from global datasets. *The Lancet Planetary Health, 6*(1), e49–e58. (DOI no verificado.)
- Burkart, K., et al. (2025). Global, regional and national estimates of the burden of childhood asthma attributable to NO₂ exposure for 204 countries and territories from 1990 to 2023. *eClinicalMedicine, 90*, 103580. https://doi.org/10.1016/j.eclinm.2025.103580
- Huangfu, P. y Atkinson, R. (2020). Long-term exposure to NO₂ and O₃ and all-cause and respiratory mortality: A systematic review and meta-analysis. *Environment International, 144*, 105998. https://doi.org/10.1016/j.envint.2020.105998
- Organización Mundial de la Salud. (2021). *WHO global air quality guidelines: Particulate matter (PM2.5 and PM10), ozone, nitrogen dioxide, sulfur dioxide and carbon monoxide.* OMS.
- Stieb, D. M., Berjawi, R., Emode, M., Zheng, C., Salama, D., Hocking, R., Lyrette, N., Matz, C., Lavigne, E. y Shin, H. H. (2021). Systematic review and meta-analysis of cohort studies of long term outdoor nitrogen dioxide exposure and mortality. *PLoS ONE, 16*(2), e0246451. https://doi.org/10.1371/journal.pone.0246451
- C40 Cities. (2022). *Mexico City: Regulating industrial emissions.* (Cifra de ~6 700 muertes anuales por PM₂.₅.)
- INEGI. (2024). *Estadísticas de defunciones registradas 2023 (preliminar).* https://www.inegi.org.mx/contenidos/saladeprensa/boletines/2024/EDR/EDR2023_ene-dic.pdf
