# Validación con un cambio conocido: el confinamiento de 2020

Fecha: 2026-10-21. Scripts: `scripts/val2020_data.py`, `scripts/val2020_linear.py`, `scripts/val2020_ratio.py`. Resultados en `data/interim/val2020_*.json` y `val2020_hourly_*.parquet`.

## Resumen

- **La dirección del cambio se detecta sin ambigüedad.** Las dos formas de estimarlo dan una caída clara de la emisión vial en el confinamiento.
- **La inversión completa no mide bien el tamaño.** El placebo de 2019, mismas fechas y sin confinamiento, muestra una caída **falsa** de 44 % en días hábiles entre febrero–marzo y abril–mayo. Sin TEMPO, el fondo por hora y la emisión vial se intercambian, y el cociente entre periodos queda sesgado.
- **Un estimador simple, normalizado por meteorología, pasa el placebo** (2019: 1.00 y 1.03). En 2020 da una caída de 33–38 % (diferencia de diferencias: −35 %, IC 90 % −21 a −46 %). Concuerda en orden de magnitud con el NO₂ ajustado por meteorología de la literatura (−43 % en la fase 3), aunque es conservador.
- **Implicación:** el sesgo de magnitud que vimos en el domingo de 2023 tiene una explicación concreta y una corrección viable. Para evaluar contingencias hay que usar siempre un control placebo de la misma temporada, y reportar el estimador normalizado junto a la inversión.

## Qué se comparó

| Periodo | 2020 (confinamiento) | 2019 (placebo) |
|---|---|---|
| Base | 15 feb–15 mar | 15 feb–15 mar |
| Fase 2 (medidas parciales desde 24–30 mar) | 30 mar–20 abr | 30 mar–20 abr |
| Fase 3 (confinamiento total desde 21 abr) | 21 abr–31 may | 21 abr–31 may |

- Tardes de 12 a 17 h, estaciones de NOₓ de SIMAT dentro del dominio, viento REDMET y capa límite ERA5 (Open-Meteo, sin huecos en 2019–2020).
- Días hábiles por separado de fines de semana y festivos (incluye Semana Santa).
- Fechas de las fases según Hernández-Paniagua et al. (2021).
- **Solo estaciones:** TEMPO no existía, y TROPOMI se descartó por costo (113 archivos de ~570 MB, ~63 GB solo para 2020).

**Control de calidad.** Los archivos de 2019–2020 son gzip reales (no ZIP como 2023–2024), con fechas día/mes/año y horas 01–24. El viento REDMET de 2019–2020 está en m/s: el cociente REDMET central ÷ METAR del aeropuerto por trimestre es 0.60–0.71, igual que en 2023. No hay error de unidades como el de 2024.

## Dos estimadores

1. **Inversión completa** (la usada en el resto del proyecto: estacionaria, industria agrupada): factor vial por región × periodo × tipo de día, todos con el mismo a priori, un fondo por hora, IC 90 % por bootstrap de días (300 réplicas).
2. **Estimador normalizado por meteorología:** para cada periodo, NOₓ observado ÷ NOₓ que predice el modelo con la emisión vial fija del a priori. El cociente entre periodos estima el cambio de emisión una vez descontado el cambio de ventilación. IC 90 % por bootstrap de días (1,000 réplicas).

## Resultados (días hábiles; cociente fase ÷ base)

| | Fase 2 | Fase 3 |
|---|---|---|
| Concentración observada, 2020 | 0.56 | 0.52 |
| Concentración observada, 2019 (placebo) | 0.89 | 0.83 |
| Lo que la meteorología explica sola (modelo con emisión fija), 2020 / 2019 | 0.90 / 0.89 | 0.78 / 0.81 |
| **Inversión completa, 2020** | 0.53 (0.46–0.69) | 0.40 (0.30–0.54) |
| **Inversión completa, 2019 placebo** (debería ser ≈ 1) | 0.80 (0.64–1.03) | **0.56 (0.39–0.77)** ❌ |
| Inversión completa, 2020 ÷ 2019 | 0.66 (0.50–0.92) | 0.71 (0.45–1.13) |
| **Estimador normalizado, 2020** | 0.62 (0.54–0.75) | 0.67 (0.58–0.78) |
| **Estimador normalizado, 2019 placebo** | 1.00 (0.86–1.16) ✅ | 1.03 (0.90–1.18) ✅ |
| **Estimador normalizado, 2020 ÷ 2019** | 0.63 (0.50–0.78) | 0.65 (0.54–0.79) |

Fines de semana y festivos: el estimador normalizado da 0.77 (fase 2) y 0.78 (fase 3) en 2020. En 2019 da 1.21 y 1.18, mayores que 1, así que el control sí tiene sesgo de temporada en fin de semana. La diferencia de diferencias da 0.64 (0.49–0.84) y 0.66 (0.50–0.88), en línea con los hábiles.

### Por qué falla la inversión completa

Con emisión fija, el modelo predice que la meteorología de abril–mayo baja la concentración a 0.81 (2019). La concentración observada bajó a 0.83, así que en 2019 la meteorología explica todo y la emisión no cambió. Aun así, la inversión infiere 0.56.

La razón es el **fondo por hora**: absorbe 6–11 ppb de un NOₓ observado de 10–23 ppb y se intercambia con la emisión vial. En 2019 el fondo inferido sube de 9.9 a 10.9 ppb entre la base y la fase 3, mientras la emisión vial baja. Solo con estaciones, el modelo no distingue entre "subió el fondo regional" y "bajó el tráfico". El total vial queda mal condicionado aunque el ajuste a las concentraciones sea bueno.

### Por qué el estimador normalizado es conservador

Su numerador incluye el fondo, que cambia poco. Por eso diluye el cambio y lo acerca a 1: la caída real de la emisión vial debe ser **al menos** la que estima (−35 %), probablemente mayor.

## Referencias independientes del tamaño del cambio

| Referencia | Fase 2 | Fase 3 | Comentario |
|---|---|---|---|
| NO₂ de superficie ajustado por meteorología y tendencia (Hernández-Paniagua et al., 2021) | −10 a −23 % (≈ −20 %) | ≈ −43 % | Excluye días estancados y de lluvia; señalan que sin ajuste meteorológico el cambio se sobreestima ~2 veces |
| Columna de NO₂ de OMI, zona norte (mismo estudio) | ≈ −30 % | ≈ −50 % | Satélite |
| Movilidad de Google, CDMX, días hábiles (lugares de trabajo / transporte) | −59 % / −61 % | −61 % / −65 % | Personas, no vehículos |
| Índice de manejo de Apple, CDMX, días hábiles | −68 % | −66 % | Solicitudes de rutas de automovilistas; sobrestima la caída del tránsito total |
| Movimientos vehiculares (Vega Rangel et al., 2021) | hasta −59 % en la fase inicial | — | Sin desglose por fase |

**Rango esperado para la emisión vial de NOₓ en la fase 3: −40 a −60 %** (cociente 0.4–0.6). Los autos bajaron ~60 %, pero los vehículos pesados a diésel, que pesan mucho en el NOₓ, siguieron circulando más. El NO₂ ajustado por meteorología (−43 %) cae dentro de ese rango.

## Veredicto

| Pregunta | Respuesta |
|---|---|
| ¿Detecta la dirección? | **Sí**, con ambos estimadores y con IC lejos de 1 |
| ¿La inversión completa mide bien el tamaño? | **No.** El placebo muestra un sesgo de temporada de hasta −44 %. En 2020 da −60 % (fase 3), dentro del rango esperado, pero en parte por ese mismo sesgo; corregida con el placebo da −29 % con un IC muy ancho (−55 a +13 %) |
| ¿El estimador normalizado mide bien el tamaño? | **Pasa el placebo** en días hábiles y da −35 % (−21 a −46 %): la dirección y el orden de magnitud son correctos. Es conservador frente al rango esperado de −40 a −60 %, porque incluye el fondo |
| ¿Exagera o subestima? | La inversión completa **exagera** los cambios entre periodos, igual que con el domingo de 2023 frente a Infovial. El estimador normalizado los **subestima** algo. La verdad queda entre ambos |

## Qué implica para el caso de uso (evaluar contingencias)

1. **Siempre con control placebo** de la misma temporada (año previo, o días sin contingencia comparables) y reportando la diferencia de diferencias. Sin control, la inversión completa puede inventar cambios de ±40 % entre meses distintos.
2. **Reportar el estimador normalizado junto a la inversión.** Es simple, transparente y pasó el placebo; da una cota conservadora del efecto.
3. **Separar mejor el fondo de la emisión vial:** TEMPO (disponible desde 2023) debería ayudar, porque ve el fondo regional fuera de la ciudad. Conviene repetir esta prueba con TEMPO en Semana Santa 2024, que requiere antes la capa límite de ene–jun 2024. También ayudaría un a priori más estrecho del fondo, o fondos por día en lugar de por hora.
4. **Precisión alcanzable hoy:** cambios de ≥ 30–40 % se detectan con ambos estimadores. Para cuantificarlos con ±10 % hacen falta las mejoras anteriores y repetir la validación.
5. `val2020_linear.run()` acepta otra función de jacobiano (`jac_fn`), así que la prueba se puede repetir con las mejoras de la tarea B (perfil de Infovial, ensamble de vientos) sin cambiar el resto.

## Datos usados (nuevos)

| Archivo | Origen |
|---|---|
| `data/raw/simat/contaminantes_{2019,2020}.csv.gz`, `meteorologia_{2019,2020}.csv.gz` | http://datosabiertos.aire.cdmx.gob.mx:8080/opendata/anuales_horarios_gz/ (gzip, encabezado en la línea 11) |
| `data/raw/metar/MMMX_2019-2020.csv` | Iowa Environmental Mesonet, ASOS MMMX |
| `data/raw/era5_openmeteo/pbl_wind_center_2019-2020.json` | Open-Meteo, archivo ERA5 |
| `data/raw/movilidad_2020/2020_MX_Region_Mobility_Report.csv` | https://www.gstatic.com/covid19/mobility/Region_Mobility_Report_CSVs.zip |
| `data/raw/movilidad_2020/apple_mobility_report.csv` | Espejo de los reportes de Apple: https://github.com/ActiveConclusion/COVID19_mobility |

## Fuentes (páginas abiertas)

- [Hernández-Paniagua et al. (2021), "Impact of the COVID-19 Lockdown on Air Quality and Resulting Public Health Benefits in the Mexico City Metropolitan Area", Frontiers in Public Health 9:642630](https://www.frontiersin.org/journals/public-health/articles/10.3389/fpubh.2021.642630/full)
- [Vega Rangel et al. (2021), "Changes in air quality in Mexico City, London and Delhi in response to various stages and levels of lockdowns and easing of restrictions during COVID-19 pandemic", Environmental Pollution 285:117664](https://researchportal.northumbria.ac.uk/en/publications/changes-in-air-quality-in-mexico-city-london-and-delhi-in-respons/)
- [Google COVID-19 Community Mobility Reports](https://www.gstatic.com/covid19/mobility/Region_Mobility_Report_CSVs.zip)
- [Apple Mobility Trends (espejo ActiveConclusion)](https://github.com/ActiveConclusion/COVID19_mobility)
