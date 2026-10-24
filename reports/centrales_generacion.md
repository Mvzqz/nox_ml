# Centrales eléctricas: a priori con datos de generación

Objetivo: revisar el a priori de la central Valle de México (en Acolman) y de Nonoalco con datos reales de generación. Después, volver a correr la inversión real de nov–dic 2023 para ver si cambia el resultado.

## Resumen

- **El a priori original de Valle de México (2,615 t/año) estaba mal construido.** Repartía el 2 % del NOₓ total según la capacidad de la base WRI GPPD, y esa base tiene dos errores:
  - cuenta 450 MW de unidades de vapor que se retiraron en 2021–2022;
  - le falta el ciclo combinado Valle de México II (615 MW, 2018).
- **A priori corregido para Valle de México: 1,600 ± 650 t/año.**
  - Climate TRACE estima 1,600 t de NOₓ en 2023, con 5.6 TWh generados.
  - Un cálculo propio con el factor de turbina de gas de bajo NOₓ de la EPA (AP-42) da lo mismo.
- **A priori corregido para Nonoalco: 100 ± 100 t/año.** Es una central de turbogás de respaldo de 74 MW que opera pocas horas, no una planta de carga base de 106 MW.
- **La inversión casi no cambia: Valle de México sale en unas 300 t/año con cualquier a priori.** El resultado lo fijan los datos (TEMPO), no el a priori. Por eso la diferencia de unas 5 veces contra la estimación de abajo hacia arriba es un problema del modelo, no del a priori (ver "Qué explica la diferencia").
- **CENACE no publica la generación por central.** Solo publica la generación agregada por tecnología. La única serie pública por planta es Climate TRACE: anual y modelada, con la generación en confianza "media" y el factor de emisión en confianza "muy baja".

## 1. Qué hay realmente en Valle de México

| Unidad | Tecnología | MW | Estado (Global Energy Monitor) |
|---|---|---|---|
| I-1, I-2, I-3 | Vapor, gas natural (1963–1971) | 3 × 150 | **Retiradas** en 2021–2022 |
| I-4-5-6-7 | Ciclo combinado (2002) | 549 | En operación |
| II | Ciclo combinado Siemens SGT6-8000H (2018) | 615 | En operación |
| III | Ciclo combinado | 397 | Proyecto detenido |

- **WRI GPPD (2016)** registra "Valle de México (CC)" con 549 MW y "Valle de México (Vapor)" con 450 MW, es decir, el estado de antes de 2018.
- **Hoy operan unos 1,164 MW**, todos de ciclo combinado. Climate TRACE usa 1,333 MW.

Fuentes:
- Global Energy Monitor: https://www.gem.wiki/Valle_de_M%C3%A9xico_power_station (cita el Informe Anual 2021 y 2023 de CFE y el PRODESEN)
- WRI GPPD v1.3: `data/raw/powerplants/`

## 2. Generación y NOₓ

**Climate TRACE v5.10**, activo 447723:
- Paquete de país: `data/raw/cenace/climatetrace/`
- API: https://api.climatetrace.org/v6/assets/emissions?assetIds=447723&years=2023&gas=nox

| Año | Generación (TWh) | Factor de planta (sobre 1,164 MW) | NOₓ (t) | CO₂ (Mt) |
|---|---|---|---|---|
| 2021 | 7.29 | 72 %* | 2,646 | 3.60 |
| 2022 | 4.90 | 48 % | 1,402 | 1.97 |
| **2023** | **5.60** | **55 %** | **1,600** | **2.26** |
| 2024 | 5.61 | 55 % | 1,612 | 2.26 |

\* En 2021 aún operaban unidades de vapor (Climate TRACE usa 1,633 MW).

- **Nov–dic 2023:** 131 y 138 t/mes, unas 1,600 t/año. La serie mensual es casi plana, así que es el total anual repartido por mes. No informa si la planta operaba más o menos en las tardes de ese periodo.
- **Factor de emisión de Climate TRACE:** 0.29 kg de NOₓ/MWh.

**Comprobación independiente con AP-42** (EPA, Tabla 3.1-1, turbinas de gas): https://www.epa.gov/sites/default/files/2020-10/documents/c03s01.pdf

| Supuesto | NOₓ resultante |
|---|---|
| Combustión de premezcla pobre, 0.099 lb/MMBtu × consumo de un ciclo combinado de ~7 MMBtu/MWh | 0.31 kg/MWh → **1,600–1,750 t/año** con 5.6 TWh |
| Inyección de agua (0.13 lb/MMBtu), posible en la unidad de 2002 | ~2,100 t/año |
| Planta operando al 40 %, factor bajo | ~800 t/año |
| Escenario alto: 6.5 TWh, inyección de agua | ~3,000 t/año |

**Recomendación:** media 1,600 t/año, σ 650 (≈ 40 %).

## 3. Nonoalco

- **Qué es:** una central de turbogás de Luz y Fuerza, hoy de CFE, de turbinas aeroderivadas. Global Energy Monitor la lista con 74 MW en operación; una unidad de 32 MW (de 1972) está retirada. Fue rehabilitada en 2019 para respaldar el suministro del Metro.
- **Por qué el a priori viejo (277 t/año) era inflado:** WRI GPPD le asigna 106 MW y una generación estimada de 831 GWh en 2017, lo que implica un factor de planta del 90 %. Eso no es realista para una planta de picos.
- **Climate TRACE no la incluye.**
- **Estimación de abajo hacia arriba:**
  - factor de planta del 5–25 %, o sea 32–160 GWh;
  - factor de emisión sin control de 0.32 lb/MMBtu × ~10 MMBtu/MWh ≈ 1.45 kg/MWh;
  - resultado: **50–235 t/año. Recomendación: 100 ± 100 t/año.**

Fuentes:
- https://gem.wiki/Nonoalco_power_station
- https://forbes.com.mx/?p=581489 (rehabilitación de 2019)

**Otra fuente en el dominio:** Climate TRACE lista la "Subestación Coapa" (19.27 N, 99.13 O): una turbina de 32 MW con unas 137 t/año, aunque con un factor de planta poco creíble (71 %). No está entre los candidatos. Es pequeña frente a las regiones viales, así que no hace falta agregarla.

## 4. Inversión real con los a priori corregidos

Script: `scripts/centrales_prior_real.py`, sin cambios a los scripts compartidos. Tabla completa: `reports/centrales_prior_real_2023-11-01_2023-12-31.md`.

Base: industria agrupada más estaciones extra, nov–dic 2023. Se usan tres a priori:
- original;
- corregido;
- débil, con σ diez veces mayor, para ver qué dicen solo los datos.

Valores en t/año (posterior ± σ posterior):

| Configuración | A priori | Valle de México | Nonoalco | AICM | AIFA |
|---|---|---|---|---|---|
| σθ = 30° | original (2,615 / 277) | 316 ± 45 | 326 ± 46 | 123 ± 51 | −154 ± 42 |
| σθ = 30° | **corregido (1,600 / 100)** | **320 ± 45** | **287 ± 42** | 117 ± 51 | −153 ± 42 |
| σθ = 30° | débil | 316 ± 45 | 326 ± 46 | 123 ± 51 | −154 ± 42 |
| σθ = 30° + viento ponderado + Acolman a 200 m | original | 294 ± 46 | 333 ± 47 | 183 ± 51 | −141 ± 43 |
| σθ = 30° + viento ponderado + Acolman a 200 m | **corregido** | **298 ± 46** | **292 ± 43** | 178 ± 51 | −139 ± 43 |
| σθ = 30° + viento ponderado + Acolman a 200 m | débil | 294 ± 46 | 334 ± 48 | 183 ± 51 | −141 ± 43 |

Lo que no cambia en ninguna variante:
- el error de validación por estación retenida: 13.4 ppb con el modelo y 11.2 con el híbrido;
- la emisión vial respecto al inventario: 41–42 %;
- el cociente domingo/hábil: 0.41–0.42.

Las centrales no afectan las estaciones.

**Lectura:**
- **El a priori casi no pesa.** Original, corregido y débil dan lo mismo: ~300 ± 45 t/año para Valle de México. Ninguna estación queda viento abajo de la planta, así que el resultado lo fija TEMPO.
- **El ± 45 es la incertidumbre formal.** No incluye el error del modelo de transporte.
- **Valle de México: el modelo con TEMPO ve unas 5 veces menos de lo que debería emitir** (300 frente a 1,600, con un rango de abajo hacia arriba de 800–3,000). Corregir el a priori no cierra la brecha.
- **Nonoalco: los datos le asignan ~330 t/año**, más que su estimación de 50–235. Está en el centro, junto a Tlatelolco y vías de mucho tráfico. Lo más probable es que absorba emisión vial de la región Centro (confusión entre fuentes cercanas), no que la planta emita eso. No se debe interpretar como emisión de la planta.

## 5. Qué explica la diferencia en Valle de México (hipótesis por probar)

1. **Cociente NO₂/NOₓ cerca de la fuente.** TEMPO ve NO₂. En una pluma fresca de central casi todo es NO al principio, así que el cociente puede estar en 0.2–0.5, no en el ~0.6–0.7 urbano que usa el modelo. Si el modelo supone un cociente más alto que el real, interpreta un aumento de NO₂ pequeño como poca emisión de NOₓ y la subestima entre 1.5 y 3 veces. Es la hipótesis más probable.
2. **Factor de masa de aire de TEMPO.** Sobre plumas concentradas está sesgado hacia abajo. Goldberg et al. (2019) encontraron diferencias del orden de decenas de por ciento al reprocesar el NO₂ satelital con un mejor factor de masa de aire. Ver `otras_ciudades.md`.
3. **Fondo por hora de TEMPO.** Es libre (σ 5e15) y puede absorber parte de la pluma, porque la planta está a 5–7 km del borde del dominio y el gradiente urbano de Ecatepec domina la zona.
4. **Operación real en las tardes de nov–dic 2023.** Se desconoce, porque CENACE no la publica. Una planta que sigue la demanda podría operar menos en la tarde que en el pico nocturno. Esto explica cuando mucho una fracción, no 5 veces.

**Prueba rápida sugerida:** repetir la inversión con un cociente NO₂/NOₓ de 0.3 solo para la columna de la central en el jacobiano de TEMPO. Si el resultado sube a ~600–1,000 t/año, la hipótesis 1 explica la mayor parte.

## 6. Recomendación

- **Actualizar los a priori** en `point_candidates`:
  - Valle de México: 1,600 t/año, σ 650;
  - Nonoalco: 100 t/año, σ 100.
  - Ninguno cambia los resultados actuales; los documentos quedan correctos.
- **No usar Valle de México como "fuente conocida" para validar** mientras no se resuelva el cociente NO₂/NOₓ de la pluma. Hoy la inversión la subestima unas 5 veces, sin importar el a priori.
- **Reportar Nonoalco dentro de la región vial Centro**, no como fuente propia.
- **Pedir a CFE o CENACE la generación horaria de Valle de México y Nonoalco en nov–dic 2023.** Es la única forma de validar de verdad. Conviene agregarla a `solicitudes_datos.md`, como solicitud de transparencia a CFE (PNT).

Datos: `data/raw/cenace/MANIFEST.md`.

## Prueba de la hipótesis de pluma fresca (2026-10-21)

**Pregunta.** ¿La inversión subestima Valle de México (~300 frente a 1,600 t/año) porque convierte NOₓ → NO₂ con el cociente urbano (0.77 en la tarde de nov–dic 2023) también en la pluma de la central, que sale casi toda como NO?

**Cómo se probó** (`scripts/centrales_pluma_fresca.py`, tablas en `centrales_pluma_fresca_2023-11-01_2023-12-31.md`). Solo cambian las columnas de TEMPO de las dos centrales; las estaciones miden NOₓ y no se tocan. Nov–dic 2023, viento del dominio, σθ = 30°, industria agrupada y estaciones extra, a priori corregidos (1,600 ± 650 y 100 ± 100) y débiles.

| Variante del cociente de la pluma | Supuesto | Cociente efectivo en los píxeles (Valle) |
|---|---|---|
| Uniforme (actual) | 0.77 en todas partes | 0.77 |
| Ozono limitante (OLM de EPA) | NO₂ en chimenea 10 %; el resto solo se convierte con el O₃ de fondo que entra (mediana 48 ppb). Concentración de la pluma instantánea, sin meandro: cota alta | 0.76 |
| OLM + conversión lenta | además, la mezcla con aire ambiente tarda τ = 20 min | 0.73 |
| Extrema (no física) | 0.25 en todo el dominio | 0.25 |

**Resultados con datos reales (a priori corregido).**

| Variante | Valle de México | Nonoalco | AICM / AIFA | Vial / inventario | LOO híbrido | Domingo/hábil |
|---|---|---|---|---|---|---|
| Uniforme | 320 ± 45 | 287 ± 42 | 117 / −153 | 41 % | 11.2 ppb | 0.42 |
| Ozono limitante | 313 ± 51 | 285 ± 42 | 117 / −155 | 41 % | 11.2 ppb | 0.42 |
| OLM + lenta | 326 ± 57 | −89 ± 51 | 70 / −147 | 41 % | 11.2 ppb | 0.43 |
| Extrema | 981 ± 136 | 534 ± 79 | 105 / −151 | 41 % | 11.2 ppb | 0.42 |

Con a priori débil los resultados son casi iguales (Valle 307–326 con química física; 989 con la extrema).

**Gemelo** (verdad: Valle 1,600 y Nonoalco 100, generada con la pluma fresca; 20 realizaciones de ruido; a priori corregido).

| Verdad generada con | Invertida con cociente uniforme | Invertida con el cociente correcto |
|---|---|---|
| Ozono limitante | 1,313 (−18 %) | 1,571 |
| OLM + lenta | 1,146 (−28 %) | 1,581 |
| Extrema | 508 (−68 %) | 1,652 |

**Conclusiones.**

- **La hipótesis no explica la brecha.** Con química realista, la pluma ya está casi en equilibrio cuando llega a los píxeles TEMPO. El O₃ de fondo (~48 ppb) supera la concentración de la pluma diluida a pocos kilómetros de la chimenea, y el píxel (~2 × 4.5 km) promedia la zona cercana. El efecto posible es un sesgo de −18 a −28 % (gemelo), no un factor de 5. Con datos reales, Valle no se mueve (313–326).
- **TEMPO sí fija la central.** Con el cociente extremo, Valle sube a ~980, en proporción a 0.77/0.25. Para llegar a 1,600 haría falta un cociente medio de ~0.15 en todos los píxeles, lo que no es físico de tarde.
- **Si se conociera el cociente, la central sería identificable** (gemelo: 1,570–1,650 recuperados con σ ≈ 50–140). El problema con datos reales es otro.
- **Nonoalco es inestable.** Con la conversión lenta pasa a negativo (−89), así que se confirma que debe reportarse dentro de la región vial Centro.
- **El resto no cambia.** Vial, domingo/hábil, AICM, AIFA y el LOO de estaciones quedan igual en todas las variantes.

**Hipótesis que quedan, sin probar.**

1. **El fondo de TEMPO absorbe la pluma.** Con σθ = 30° y mezcla en la capa límite, la pluma de la central es ancha y suave, y el fondo por hora de TEMPO se la puede quedar. Prueba: fondo con gradiente espacial, o sin σθ solo para la central.
2. **Error de posición del viento.** Si la pluma cae fuera de los píxeles donde se modela, la inversión la ve como ruido.
3. **Climate TRACE sobreestima la central en nov–dic 2023.** Es un dato anual y modelado; la generación real de esos meses pudo ser menor (mantenimiento, despacho). Solo la generación horaria de CFE o CENACE lo resuelve.

**Recomendación.** Mantener el cociente urbano (el ajuste a la química no cambia nada con datos reales) y seguir sin usar las centrales como fuente de validación. La siguiente prueba barata es la hipótesis 1.
