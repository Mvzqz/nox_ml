# Resumen de datos: ¿sirven para el POC?

Fecha: 2026-10-19. Detalle en `qc_simat.md`, `qc_geo.md` y `qc_era5.md`.

## Veredicto por fuente

| Dato | Estado | Resultado |
|---|---|---|
| NO/NO₂/NOₓ RAMA 2023–2024 | ✅ Apto | ppb, sin duplicados ni negativos, NOₓ = NO + NO₂, pico 07–09 h todo el año, domingo < hábil, MER/CAM > AJM/CUA. 59 h con sensor pegado (TAH, MON, ACO, PED): se filtran. |
| Viento REDMET 2023 | ✅ Apto | m/s y °, dirección meteorológica (componente v vs ERA5 r ≈ 0.8), velocidad ≈ ERA5. |
| Viento REDMET 2024 | ⚠️ **Error de unidades** | La velocidad es ≈ 2.2× la de ERA5 en todas las estaciones y meses (en 2023 era ≈ 1.05×). El salto ocurre justo el 1 de enero de 2024. Contra el METAR del aeropuerto MMMX, la razón pasa de 0.62 en 2023 a 1.26–1.46 en 2024, otra vez ≈ 2.2×. Además, en 2024 faltan los valores 0.3 y 0.6, y 1.0 aparece una sola vez, huecos que deja un factor de conversión. El factor coincide con mph etiquetadas como m/s (2.237). La dirección está bien. |
| Catálogo de estaciones | ✅ Apto | 24 estaciones con NOₓ y 19 con viento en el dominio; todas caen en su municipio. ACO (2,198 m) y XAL (2,160 m) quedan apenas bajo el umbral de 2,200 m: hay que ajustar el umbral, no los datos. |
| INEGI 2022 | ✅ Apto | 16 alcaldías, EPSG:4326, 47 municipios tocan el dominio. |
| OSM (Overpass) | ✅ Apto | Clases motorway a tertiary presentes (8,840 km); están Periférico, Circuito Interior, Viaducto e Insurgentes. Se usó Overpass con la caja del dominio (27 MB) en lugar del PBF de México (617 MB). |
| Inventario 2018 | ✅ Totales / ❌ municipios | La Tabla 7 suma 144,597.8 t/año, con 85.8 / 7.3 / 6.6 / 0.2 %. El PDF **no trae NOₓ por municipio** (solo un mapa), así que la prueba de "mismos 5 municipios principales" necesita los anexos de SEDEMA o EDGAR. |
| ERA5 (vía Open-Meteo, sin cuenta) | ✅ Apto, umbral a ajustar | Máximo de la capa límite a las 15 h y < 100 m de noche. Entre 12 y 17 h va de 980 a 1,590 m: el piso de 1,000 m falla a las 17 h, así que el rango de la meta es demasiado alto. Para la malla completa hace falta el CDS. |
| TEMPO NO₂ L2 | ⏳ Cobertura confirmada | Según CMR hay entre 12 y 16 escaneos por día sobre el dominio, que cubren las 12–17 h locales. Conviene usar **V04** (V03 termina en 2025-09). Falta descargarlo, para lo que se necesita una cuenta de Earthdata, y revisar píxeles y nubes. |
| Contingencias 2024 | ⚠️ Fuente secundaria | 23 días entre febrero y mayo de 2024, tomados de la prensa; falta contrastar con CAMe. |
| OpenAQ, EDGAR, TROPOMI | ⏳ Pendiente | Necesitan una clave o son opcionales. |

## Hallazgos que afectan el diseño

1. **Densidad de estaciones.** Por mes hay solo entre 13 y 18 estaciones de NOₓ válidas, con una distancia mediana de 5.6 km entre vecinas (16.8 km la máxima). La meta del experimento gemelo (error de ubicación < 2 km) es ambiciosa con esta red, así que TEMPO y el proxy vial serán imprescindibles. Además, al retener el 20 % de las estaciones quedan unas 12 para entrenar.
2. **Contingencias.** Por la tarde, el NOₓ en días de contingencia es casi igual al de días hábiles (17.5 frente a 17.9 ppb), porque la atmósfera estancada compensa la menor emisión. Los domingos sí bajan un 33 %. La PINN tiene que separar emisión de meteorología; los domingos son la prueba más limpia.
3. **Periodo.** TEMPO empieza en agosto de 2023, el archivo anual de 2025 aún no está publicado y las contingencias ocurren entre febrero y mayo. Opciones:
   - **A (recomendada):** del 15 de febrero al 31 de mayo de 2024, con 14 a 17 estaciones, 9 o más episodios de contingencia y TEMPO. Requiere corregir la velocidad de REDMET 2024 (÷ 2.237) y documentar la corrección o confirmarla con SIMAT.
   - **B:** de noviembre a diciembre de 2023, con 18 estaciones, viento limpio y TEMPO, pero casi sin contingencias.

## Fuentes puntuales candidatas (ver `point_candidates.md`)

- Lista: 2 centrales (WRI GPPD), el aeropuerto (OSM) y 12 clústeres industriales del DENUE, todos con intensidad a priori (Tabla 5 del inventario repartida por personal ocupado).
- La central Valle de México en Acolman (≈ 2,600 t/año a priori, ≈ 1.8 % del NOₓ total) es la fuente puntual más grande. Ninguna estación queda viento abajo a ≤ 10 km en ningún periodo, así que **solo TEMPO puede restringirla**.
- Ecatepec (3 clústeres) se ve en apenas 7–8 % de las horas en feb–may 2024, porque XAL no tiene datos en abril–mayo de 2024 y ACO no tiene NOₓ desde diciembre de 2023. En nov–dic 2023 sube a 13–26 %.
- Pendiente: GPPD (2021) puede no incluir las unidades más nuevas de Valle de México, y hay que verificar si Nonoalco sigue operando.

## TEMPO NO₂ L2 V04 — nov–dic 2023 (ver `qc_tempo_2023-11-01_2023-12-31.md`, `observability_2023-11-01_2023-12-31.md`)

- Descarga por recorte: 396 granulos, ~120 KB cada uno (originales de ~150 MB descartados; URLs en `data/raw/tempo/manifest.csv`).
- ✅ Unidades molecules/cm²; centro urbano 2.0e16, 1.74× los alrededores.
- ✅ Concordancia con estaciones de NO₂: r = 0.76 (4,424 pares hora-estación), mediana r = 0.70 dentro de cada granulo (meta del plan: > 0.6) y r = 0.84 en promedios por estación.
- ⚠️ Nubes: 41 % de los píxeles se rechazan por nubes y 19 % por bandera de calidad; solo 47 % de los granulos tienen ≥ 50 % del dominio válido (31 de 61 días buenos). Conviene usar TEMPO por píxel y no exigir el 50 % del dominio.
- ✅ Cobertura: con TEMPO, el 100 % de las celdas se ve en ≥ 20 % de las horas (con estaciones solas, 58 %). Las candidatas que las estaciones no ven (Acolman 0 %, Ecatepec 13–26 %) quedan cubiertas por TEMPO en ~50 % de las horas.
- ⚠️ La central de Acolman no destaca con claridad en TEMPO: 1.0e16 a ≤ 3 km de la planta contra 0.8e16 al este, pero el gradiente urbano (Ecatepec, al SO) domina. Además está a 5.5 km del borde norte y a 7 km del borde este del dominio: **conviene ampliar el dominio ~10 km al N y al E** para que no quede en la frontera.

## TEMPO feb–may 2024 y comparación de periodos

| | Nov–dic 2023 | 15 feb–31 may 2024 |
|---|---|---|
| Estaciones NOₓ válidas por mes | 18 | 14–17 |
| Viento REDMET | ✅ limpio | ⚠️ velocidad ×2.2 (corregir ÷ 2.237) |
| Ecatepec visto por estaciones | 13–26 % | 7–8 % (XAL caída en abr–may, ACO sin NOₓ) |
| Granulos TEMPO (12–17 h) | 396 | 672 |
| Días TEMPO buenos (≥ 50 % válido) | 31 de 61 | 81 de 107 |
| Celdas vistas por TEMPO (candidatas) | ~50 % de las horas | ~72 % de las horas |
| TEMPO vs estaciones, pares hora-estación | r = 0.76 | r = 0.71 |
| TEMPO vs estaciones, dentro de cada granulo (meta > 0.6) | **r = 0.70** ✅ | **r = 0.55** ❌ |
| TEMPO vs estaciones, promedio por estación | r = 0.84 | r = 0.66 |
| Contingencias | casi ninguna | 23 días |

**Recomendación:** nov–dic 2023 como periodo principal (entradas más limpias y TEMPO más coherente con las estaciones). Feb–may 2024 queda como segundo periodo de prueba, una vez confirmada la corrección del viento. La concordancia más baja en primavera podría deberse a la capa de mezcla más profunda, a la fotoquímica y a los incendios de temporada seca. Es una hipótesis sin verificar.

## Decisiones (2026-10-20)

- Periodo principal: **nov–dic 2023**. Feb–may 2024 queda como periodo secundario de prueba.
- Corrección de viento REDMET 2024 **aplicada** en `qc_simat.py`: WSP ÷ 2.237, con el valor original en `WSP_raw` y la bandera `wsp_fix_mph`. Tras la corrección, la velocidad media mensual de la tarde en 2024 es de 2.6–3.1 m/s, contra 2.1–3.0 m/s en ERA5.
- Dominio **ampliado** a 19.25–19.77 °N, 99.35–98.81 °O (3,260 km², +52 %), definido en `scripts/config.py`. Todos los QC se re-corrieron.
  - Entran CUT, CHO y MON. Las estaciones NOₓ válidas en nov–dic 2023 pasan de 18/18 a 20/19, y las de viento de 16/15 a 18/17.
  - Entra el aeropuerto AIFA (NLU) como candidata; no está en el inventario 2018.
  - TEMPO nov–dic 2023 en el dominio ampliado: r = 0.70 por granulo, 0.77 por pares hora-estación y 0.85 por promedios de estación. Centro/alrededores 2.15×.
  - La fracción de celdas vistas por estaciones baja de 58 % a 46 %, porque el área nueva es rural; con TEMPO sigue en 100 %.
  - Acolman y AIFA no tienen ninguna estación viento abajo (0 %); TEMPO las ve en ~52 % de las horas. Ecatepec no cambia.
  - ⚠️ CUT ("Cuautitlán") cae en Tepotzotlán según INEGI; probablemente está cerca del límite municipal, falta verificarlo.
  - OSM anterior conservado en `data/raw/osm_v1/`.

## Factibilidad con inversión lineal (ver `feasibility_linear_2023-11-01_2023-12-31.md`)

Modelo: pluma gaussiana con el viento real por hora, 16 fuentes puntuales candidatas, 9 regiones viales (3×3, ~18 km) y fondo por hora; 50 gemelos por escenario. Corre en ~30 s.

| | Solo estaciones | + TEMPO | + TEMPO, pesimista (errores ×2, viento perturbado ±20°) |
|---|---|---|---|
| Grados de libertad de las fuentes (de 25) | 19.7 | 24.5 | 23.3 |
| Error en emisión vial por región | 1–14 % | 0–1 % | 4–14 % |
| Error en central de Acolman | 14 % | 1 % | 17 % |
| Error en aeropuertos (AIFA / AICM) | 46 % / 22 % | 3 % / 3 % | 13 % / 28 % |
| Error en clústeres industriales (~100–230 t/año) | 5–46 % | 3–31 % | **13–352 %** |

- ✅ **Factible:** emisión vial por región, la central de Acolman y los aeropuertos, con TEMPO, aun en el escenario pesimista (meta < 25 %; AICM 28 %, al límite).
- ❌ **No factible como fuentes individuales:** los clústeres industriales. Su señal es ~100 veces menor que la vial de su región, y con errores de viento realistas su error va de 13 a 352 %. Se confunden con la región vial vecina (r = −0.5 a −0.74).
- TEMPO es imprescindible: sube los grados de libertad de 19.7 a 24.5.
- El error de viento es el error dominante, así que mejorar el campo de viento (y propagar su incertidumbre) es la prioridad.
- Limitaciones: en los escenarios nominales la verdad y la inversión usan el mismo modelo ("crimen inverso", resultado optimista); sin química ni fuentes de área; errores TEMPO supuestos independientes.

## Prueba con datos reales: inversión lineal (ver `real_check_linear_2023-11-01_2023-12-31.md`)

- ✅ Hay señal: ajuste en muestra r = 0.77 en estaciones y r = 0.74 en TEMPO. Sin suponerlo en el a priori, la emisión vial baja a **0.76× en sábado y 0.39× en domingo/festivo**. La dirección es correcta, aunque la magnitud del domingo parece grande. Las σ (±0.01) son irrealmente pequeñas porque se suponen errores independientes; hace falta un bootstrap por días.
- ⚠️ Escala absoluta: el total vial inferido es ~35 % del a priori del inventario. Lo más probable es un sesgo del modelo de transporte (mezcla y dispersión), así que hay que comparar patrones, no absolutos, y estimar la mezcla (difusividad como incógnita).
- ❌ Clústeres industriales individuales: valores negativos (hasta −114 t/año) y uno 8× su a priori (GAM, 903 t/año). Esto confirma la prueba de factibilidad: se deben agrupar por región.
- ⚠️ Acolman: 300 t/año contra 2,615 a priori. Probablemente se debe a que se modela a nivel de suelo y no como chimenea elevada.
- ❌ Estación retenida contra IDW: el modelo gana en 7 de 24 estaciones (RMSE 14.1 frente a 11.6 ppb). Gana en las periféricas (ACO, CHO, MON, VIF, CUA, ATI, TLI) y pierde en el núcleo denso, donde IDW es difícil de vencer. Con un solo viento por hora, el transporte no basta para el campo de concentración.

## Bootstrap por días y viento espacial (ver `real_check_linear_{domain,field}_2023-11-01_2023-12-31.md`)

| | Viento único por hora | Campo de viento IDW (promedio sobre la trayectoria) |
|---|---|---|
| Domingo-festivo / hábil (IC 90 %, bootstrap de 61 días) | 0.39 (0.31–0.50) | 0.31 (0.23–0.43) |
| Sábado / hábil | 0.76 (0.60–0.96) | 0.83 (0.61–1.06) |
| RMSE LOO: modelo / IDW / híbrido (ppb) | 14.1 / 11.6 / 12.2 | 14.0 / 11.6 / 12.0 |
| Estaciones donde el híbrido < IDW | 13 de 24 | 13 de 24 |

- ✅ La baja dominical es robusta: el IC 90 % queda muy por debajo de 1 con ambos vientos. La magnitud (−60 a −70 %) es mayor que la baja de concentración (−33 %), así que solo se confía en la dirección.
- ❌ El campo de viento espacial **no mejora** el modelo (14.1 → 14.0 ppb). El cuello de botella no es la variación espacial del viento interpolado, sino probablemente el supuesto estacionario (no arrastra emisiones de horas previas) y la mezcla.
- El híbrido (modelo + IDW de residuos) le gana a IDW en la mitad de las estaciones, pero no en el promedio (12.0 frente a 11.6 ppb).

## Transporte no estacionario (puffs) y diagnóstico del error (ver `real_check_linear_puff_2023-11-01_2023-12-31.md`)

| | Pluma estacionaria | Campo de viento | No estacionario (pluma 1 h + puffs 6 h) |
|---|---|---|---|
| Ajuste TEMPO (r) | 0.74 | 0.73 | **0.83** |
| Total vial hábil / a priori del inventario | 35 % | 30 % | **67 %** |
| Domingo-festivo / hábil (IC 90 %) | 0.39 (0.31–0.50) | 0.31 (0.23–0.43) | 0.47 (0.39–0.56) |
| RMSE LOO modelo / IDW / híbrido (ppb) | 14.1 / 11.6 / 12.2 | 14.0 / 11.6 / 12.0 | 15.1 / 11.6 / 14.6 |
| Error de nivel por estación (sesgo RMS): modelo / IDW | 6.2 / 6.6 | — | 6.2 / 6.6 |
| Error hora a hora: modelo / IDW | **12.7 / 9.5** | — | **13.7 / 9.5** |

- ✅ Arrastrar las horas previas mejora lo regional: TEMPO pasa de r = 0.74 a 0.83, la escala absoluta se acerca al inventario (67 %) y la baja dominical (−53 %) es más creíble.
- 🔎 Diagnóstico: el modelo **ya acierta el nivel medio de cada estación** tan bien o mejor que IDW (sesgo 6.2 frente a 6.6 ppb). Lo que falla es la **variación hora a hora** (12.7 frente a 9.5 ppb). IDW gana porque las estaciones vecinas comparten la ventilación de cada hora (capa límite, estancamiento), y el modelo la toma de una sola celda de ERA5 con dispersión fija.
- ➡️ El cuello de botella es la **mezcla y ventilación por hora**, no el viento espacial ni el arrastre temporal. Para la PINN, la mezcla (difusividad o altura de mezcla por hora) debe ser una incógnita estimada de los datos.

## Factor de dilución por hora y prueba sin clústeres industriales (ver `dilution_test_domain_*.md`, `real_check_linear_*_sin_industria_*.md`)

- ❌ **Factor de dilución por hora:** no ayuda. El error hora a hora pasa de 12.7 a 12.8 ppb, y el s_h ajustado no se correlaciona con la capa límite de ERA5 (r = −0.01). Se descarta que el problema sea una ventilación común a toda la ciudad, lo que corrige el diagnóstico anterior.
- ✅ **Sin clústeres industriales como fuentes puntuales:**

| Transporte estacionario | Con industria | Sin industria |
|---|---|---|
| RMSE LOO modelo / IDW / híbrido (ppb) | 14.1 / 11.6 / 12.2 | 13.6 / 11.6 / **11.7** |
| Error hora a hora del modelo | 12.7 | 11.8 |
| Estaciones donde el híbrido < IDW | 13 de 24 | **15 de 24** |
| TLA, a 0.5 km de un clúster (modelo / IDW / híbrido) | 26.0 / 14.8 / 26.7 | 18.9 / 14.8 / **14.3** |
| Domingo-festivo / hábil (IC 90 %) | 0.39 (0.31–0.50) | 0.42 (0.35–0.54) |

- 🔎 Parte del error hora a hora venía de **plumas de campo cercano** de fuentes puntuales: con una dirección de viento algo equivocada, la pluma pega o no pega en la estación. SAG y XAL (Ecatepec) siguen mal, sobre todo con puffs (SAG 32.9 ppb), probablemente por la misma razón con las fuentes grandes del NE y por las trayectorias de 6 h con un solo viento.
- Con transporte no estacionario (puffs), quitar la industria también ayuda (15.1 → 14.5), pero sigue peor que el estacionario en estaciones, aunque mejor en TEMPO (r = 0.83).

## Conclusión de las pruebas lineales

1. **Inferencia de emisiones: factible** para la emisión vial por región, su ciclo semanal (domingo ≈ 0.4–0.5 del hábil, robusto en todas las variantes) y las fuentes grandes en los gemelos.
2. **Clústeres industriales individuales: no factibles.** Agruparlos por región también mejora las predicciones en estaciones.
3. **Campo de concentración en estaciones:** el híbrido (modelo + interpolación de residuos) empata con IDW (11.7 frente a 11.6 ppb) y gana en 15 de 24 estaciones. Superar a IDW en el núcleo denso no es una meta realista para el POC; el valor agregado está en la inferencia de emisiones y en las zonas sin estaciones.
4. **Diseño de la PINN:** transporte dependiente del tiempo (mejora TEMPO y la escala absoluta), con incertidumbre de dirección del viento (ensamble), fuentes puntuales solo grandes y elevadas (Acolman), e industria agregada por región.

## ¿Qué datos existentes acercan la opción A? (ver `improvement_tests.md`, `real_check_linear_*_extras_*.md`)

| Escenario (gemelo, errores ×2) | Clústeres industriales: error mediano | Clústeres < 25 % | Acolman / AIFA / AICM | Vial por región |
|---|---|---|---|---|
| A. Base (viento ±20°) | 51 % | 3 de 12 | 20 / 34 / 22 % | 9 % |
| B. + estaciones solo NO₂ | 61 % | 2 de 12 | 20 / 31 / 18 % | 9 % |
| C. + trazadores CO y SO₂ | 56 % | 2 de 12 | 20 / 34 / 17 % | 9 % |
| D. Viento ±10° | 34 % | 5 de 12 | 8 / 15 / 14 % | 3 % |
| F. Más tiempo (2 periodos), ±20° | 62 % | 1 de 12 | 21 / 21 / 33 % | 9 % |
| G. Todo con ±10° | 33 % | 4 de 12 | 9 / 9 / 13 % | 3 % |
| H. Todo con ±5° | **18 %** | **10 de 12** | **3 / 4 / 5 %** | 1 % |

- La precisión del viento es la palanca dominante. Con ±5° la opción A (clústeres individuales < 25 %) es casi alcanzable con los datos actuales.
- Más estaciones, trazadores o más meses casi no ayudan mientras el error de viento sea de ±20°.
- Con datos reales, las estaciones extra (BJU, FAR, GAM) y el viento de los aeropuertos dejan el híbrido apenas por debajo de IDW (11.4 frente a 11.5 ppb; gana en 16 de 24 estaciones).
- ⚠️ Open-Meteo no tiene la capa límite ERA5 de ene–jun 2024. Se rellenó con la climatología para los gemelos; para usar datos reales de primavera 2024 hace falta ERA5 del CDS o MERRA-2.

## Investigaciones en paralelo (2026-10-20)

| Tema | Reporte | Conclusión |
|---|---|---|
| Error real del viento | `viento.md` | Validación cruzada de 22 estaciones: mediana de 32° con el vector del dominio y 28° con IDW (ERA5: 55°). El error del flujo está entre ±20° y ±30°, **peor que el ±20° supuesto**. Con ±30° el gemelo da vial 15 %, fuentes grandes 32–37 % y 1 de 12 clústeres. Recomendación: pedir a SEDEMA sus salidas WRF de 1 km; mientras tanto, bajar el peso de estaciones mal ubicadas y representar σ ≈ 30° en la inversión; WRF propio si no responden en ~4 semanas. |
| Mejoras | `mejoras.md` | 1) Transporte barato: industria agrupada, Acolman como chimenea, ensamble de vientos. 2) Conteos de Infovial (abiertos, 2016–2019) como perfil de tráfico: implican domingo/hábil ≈ 0.6–0.9 en emisión, así que **el modelo exagera la baja dominical** (0.31–0.47). 3) Alianza con UNAM-ICAyCC/LSCE (MERCI-CO₂: WRF e inversiones a 1 km). Otros gases solo ayudan después de mejorar el viento. |
| Otras ciudades | `otras_ciudades.md` | Validar el método en paralelo en Los Ángeles (TEMPO + HRRR de 3 km archivado + tráfico PeMS + inversión publicada). En CDMX, Borsdorff et al. 2020 (CO con TROPOMI y WRF-Chem) encontraron la misma limitación de viento. No se encontró inversión de NOₓ publicada para la CDMX. |
| Caso de uso | `caso_de_uso.md` | Principal: evaluar si las restricciones vehiculares de contingencia bajan la emisión vial por zona (CAMe/SEDEMA). Solo es defendible para cambios ≥ 20 % y **condicionado a corregir el sesgo de magnitud** que muestran los conteos de Infovial. Secundario: verificar el reparto por zona y los perfiles del inventario. |
| Explicadores | `explainer.html` (traducido), `como_funciona.html` (nuevo) | En español. Actualizados con el error de viento medido y el sesgo dominical. |

**Revisión de conclusiones:** con el viento actual solo la emisión vial por zona y la dirección del ciclo semanal son confiables. Las fuentes grandes y la magnitud de los cambios requieren un viento mejor; esa es la prioridad del proyecto.

## Segunda ronda en paralelo (2026-10-21)

| Tema | Reporte | Conclusión |
|---|---|---|
| Mejoras baratas | `mejoras.md` (Resultados de las pruebas), `improve_real_*.md` | **Representar el error de viento (σθ = 30°) en la inversión** es lo que más ayuda. En el gemelo con ±30°: Acolman/AIFA/AICM pasan de 33/38/48 % a 13/26/15 % y la vial de 16 a 8 %. Con datos reales, el híbrido queda en 11.2 frente a 11.5 ppb de IDW (gana en 18 de 24). Adoptarlo. Ponderar el viento: efecto nulo pero gratis. Acolman como chimenea de 200 m: sin efecto (sigue en ~220–320 frente a 2,615 t/año), así que hay que revisar el a priori con CENACE. Perfil de Infovial: no corrige la baja dominical (0.43–0.51 frente a 0.80). AIFA y AICM, inestables con datos reales. |
| Validación 2020 (confinamiento) | `validacion_2020.md` | **La inversión completa falla el placebo:** en 2019, sin confinamiento, da una caída falsa (0.56; IC 0.39–0.77) porque sin satélite el fondo se intercambia con la emisión. Un **estimador normalizado por meteorología** (observado ÷ modelo con emisión fija) pasa el placebo (1.00–1.03) y da −35 % en 2020 (IC 21–46 %), frente a −40 a −60 % esperado (NO₂ ajustado −43 %, movilidad −59 a −68 %). Para comparar periodos separados conviene el estimador normalizado. |
| Los Ángeles | `otras_ciudades.md` (Estimación cuantitativa) | Error de viento de 17° en LA (interpolando estaciones y con HRRR 3 km) frente a 28–32° en CDMX; LA tiene menos estaciones de NOₓ (9, a 14.3 km). Gemelo con su viento real: vial 9 % (LA) frente a 19 % (CDMX), aeropuertos 31 frente a 45 %. Con el mismo viento rinden parecido: **la ventaja es el viento, no las estaciones**. Vale la pena usar LA (1–2 semanas) para probar con datos reales que un mejor viento mejora la inversión; no sirve para validar industria. |
| Puntos calientes TEMPO | `puntos_calientes.html` | La red vial explica el 71 % de la variación del NO₂ promedio (78 % con gradiente regional), y el patrón es estable entre periodos (r = 0.90). Destacan, como indicios: Vallejo–Azcapotzalco, AICM y GAM. No destacan Acolman, AIFA ni 7 de 12 zonas industriales. |
| Capa límite ene–jun 2024 | `capa_limite.md` | MERRA-2 corregido (r = 0.68 con ERA5; error del relleno ~12–14 %). Serie sin huecos nov 2023–jun 2024 en `data/interim/pbl_2023_2024.parquet`, **ya integrada** en `feasibility_linear.py`. La primavera 2024 queda desbloqueada. |
| Solicitudes de datos | `solicitudes_datos.md` | Cartas listas: SEDEMA (correo y Plataforma Nacional de Transparencia), UNAM–LSCE (correos sin verificar) y ADIP. No se envió nada. |

**Estado actualizado:**
- **Confiable hoy:** reparto vial por zona, dirección del ciclo semanal y del confinamiento, y el estimador normalizado por meteorología para cambios entre periodos (con una ligera subestimación).
- **Con la mejora de σθ = 30°:** las fuentes grandes vuelven a estar cerca de la meta en gemelos; con datos reales aún son inestables.
- **Abierto:** el tamaño de los cambios en la inversión completa (exagerado), el a priori de Acolman y el placebo con TEMPO (TEMPO empezó en ago-2023, así que no hay primavera 2023).
- **Siguientes pasos:** (1) adoptar σθ = 30° como estándar; (2) placebo con TEMPO entre dos periodos sin intervención posteriores a ago-2023 (p. ej. nov frente a dic 2023, o semanas de feb–mar 2024 sin contingencia) y contingencias de 2024 con el estimador normalizado; (3) enviar las solicitudes de datos; (4) prueba de 1–2 semanas en LA con HRRR.

## Tercera ronda en paralelo (2026-10-21)

| Tema | Reporte | Conclusión |
|---|---|---|
| σθ = 30° como estándar | `base_sigma30.md` | Ya es el valor por defecto en `feasibility_linear.py` y `real_check_linear.py` (15° con `SIGMA_THETA_DEG=15` o `--sigma-theta 15`). Con datos reales, el híbrido gana a IDW en 1–2 estaciones más en todas las configuraciones; las fuentes con emisión negativa bajan de 5 a 1 (AIFA). El reparto vial por región se mueve hasta ±0.2: solo indicativo. |
| Sesgo de los domingos | `sesgo_domingos.md` | **El cociente de la inversión (0.42) no lo deciden los datos:** si se fija entre 0.42 y 1.0 el ajuste y el LOO casi no cambian, porque el fondo por hora absorbe la diferencia. Corrige `mejoras.md` ("los datos lo jalan con fuerza"). La referencia correcta de Infovial es el día completo ponderado por emisión (0.65–0.73), no la tarde: el NOₓ de la mañana se sigue midiendo por la tarde. **El estimador normalizado da 0.65 (IC 90 % 0.55–0.75), coherente con Infovial.** Recomendación: reportar el estimador normalizado y usar el cociente de tráfico como restricción en la inversión. |
| Contingencias 2024 | `contingencias_2024.md` | Con el estimador normalizado, en las tardes de los 23 días de contingencia **no se ve una baja de emisión de NOₓ**: 1.13 (IC 90 % 1.05–1.22); hábiles 1.07 (0.97–1.18). Los placebos con días falsos dan 0.90–0.98 (±10 %), así que una baja de ≥10–15 % se habría detectado; queda un sesgo positivo en los episodios (acumulación de varios días o fondo regional) que podría ocultar una de ~5–10 %. Fechas tomadas de prensa: confirmar con comunicados de la CAMe. |
| Placebo con TEMPO | `placebo_tempo.md` | **El estimador normalizado falla el placebo con TEMPO** (6–10 de 18 pares significativos, frente a ~2 esperados) porque el modelo con viento medio explica poco de la columna (r ≈ 0.2–0.35). El contraste crudo centro − periferia sí pasa (2 de 18), con cambio mínimo detectable de ~30–35 % dentro de la misma temporada. La química de primavera baja la columna ~30 % de feb a may sin cambio de emisión. TEMPO sirve para ubicar puntos calientes, no para medir cambios con el estimador normalizado. Domingo con TEMPO: 0.50–0.67. |
| Centrales eléctricas | `centrales_generacion.md` | El a priori de Valle de México/Acolman (2,615 t/año) venía de WRI GPPD con unidades retiradas y sin el ciclo combinado II. Nuevo a priori con Climate TRACE 2023: **1,600 ± 650 t/año**; Nonoalco es un turbogás de respaldo: **100 ± 100** (antes 277). CENACE no publica generación por central. La inversión casi no cambia (Valle ~300 ± 45, fijado por TEMPO); hipótesis: cociente NO₂/NOₓ urbano aplicado a la pluma fresca, prueba propuesta. Las centrales siguen sin poder separarse: se agrupan en la opción B. |
| PINN y app | `pinn_prototipo.md`, `app/app.py` | PINN de advección–difusión 2D (PyTorch, CPU, 18 min de entrenamiento, error 4–7 % frente a la solución exacta) usada como operador de la inversión. Nov–dic 2023: domingo/hábil 0.43 (lineal 0.42), LOO 12.5 frente a 13.4 ppb, r con TEMPO 0.78 frente a 0.75, pero el total vial sale 42 % mayor. En el gemelo cruzado los totales difieren 26–36 % y los cocientes ≤4 %: **solo los cambios relativos son robustos al modelo**. El entrenamiento conjunto (física + datos) no mejora. App Streamlit local con mapa, incertidumbre, selectores y pestaña clima frente a emisión: `.venv/bin/streamlit run app/app.py`. |

**Estado actualizado:**
- **Entregable del plan:** existe la PINN (opción B) y la app local.
- **Confiable hoy:** cambios relativos (tipo de día, antes/después) con el estimador normalizado sobre estaciones: domingo 0.65, confinamiento −35 %, contingencias sin efecto visible (±10 %). Puntos calientes de TEMPO como mapa.
- **No confiable:** totales absolutos (dependen del modelo), cocientes de la inversión completa (los fija el a priori), cambios medidos con TEMPO normalizado, fuentes puntuales individuales.
- **Siguientes pasos:** (1) usar el cociente de tráfico como restricción y el estimador normalizado como salida principal en la app; (2) ~~cociente NO₂/NOₓ de pluma fresca~~ descartado (ver abajo); probar si el fondo de TEMPO absorbe la pluma ancha; (3) confirmar fechas de contingencias con la CAMe; (4) enviar las solicitudes de datos; (5) prueba de 1–2 semanas en LA con HRRR.

**Pluma fresca de centrales (`centrales_generacion.md`, `centrales_pluma_fresca_2023-11-01_2023-12-31.md`):** hipótesis descartada. Con química realista (ozono limitante o conversión lenta) el cociente efectivo en los píxeles de TEMPO es 0.73–0.76 frente a 0.77 urbano; Valle de México sigue en 313–326 t/año. En el gemelo, ignorar la pluma fresca sesga −18 a −28 %, no un factor de 5; con el cociente correcto se recupera (1,570–1,650 de 1,600). Con un cociente extremo de 0.25 Valle sube a ~980, lo que confirma que TEMPO lo fija. Nonoalco se vuelve inestable. Siguiente hipótesis: el fondo de TEMPO absorbe la pluma ancha.

**Estimador normalizado como salida principal (`pinn_prototipo.md`):** la inversión (lineal y PINN, `scripts/pinn/invert.py`) ata por defecto el sábado y el domingo de cada región a Infovial de día completo (0.87 y 0.69, σ = 0.02; `--sin-restriccion` para desactivarlo). Con solo estaciones el ajuste no empeora (LOO 13.37 frente a 13.38 ppb), pero con TEMPO el domingo queda en 0.51–0.54: **es TEMPO el que tira el cociente hacia abajo** (en `placebo_tempo.md` su domingo crudo es 0.50–0.67). Estimador normalizado: domingo 0.65 (lineal) / 0.58 (PINN) en nov–dic 2023 y 0.69 / 0.68 en primavera 2024, frente a 0.65–0.73 de Infovial. La app tiene las pestañas «Cambios de emisión» (principal) y «Contingencias 2024», y muestra los totales como rango lineal–PINN con aviso.

**Fondo de TEMPO (`fondo_tempo.md`):** el modelo del fondo **no explica** ni el domingo bajo ni Valle en ~300. Ningún fondo (gradiente, por escaneo, por día, separado por tipo de día) sube a Valle; los más flexibles la bajan (−164 a 539). Sin los píxeles a < 10 km sale −22 ± 113: lejos, TEMPO no ve pluma; cerca, el modelo ya pone más NO₂ del observado y el AMF es normal (1.32 frente a 1.30). **Valle no es identificable**: su ±45 supone errores independientes por píxel. El domingo queda en 0.36–0.49 con cualquier fondo y solo sube si TEMPO pesa menos (con restricción: 0.62 con σ_TEMPO×3, 0.67 con ×10), porque sus residuos tienen estructura espacial (2.6e15 frente a 5e15 por píxel) y TEMPO pesa de más. El gemelo con ese patrón de residuos no reproduce los síntomas. Recomendación: σ_TEMPO×3 o superobservaciones, y probar química de fin de semana en el Jacobiano.

**Los Ángeles con datos reales (`otras_ciudades.md`, sección "Prueba con datos reales"):** **un mejor viento no mejoró la inversión.** El campo HRRR completo (427/427 h) tiene 16° de error de dirección frente a 17° de IDW y 30° del promedio del dominio, pero el LOO empeora un poco (13.6 → 14.1 ppb) y la correlación del modelo con emisión fija contra TEMPO baja (0.24 → 0.14). La inversión completa falla en LA (con 9 estaciones la vial hábil sale casi nula o negativa). El estimador normalizado es estable con los cuatro vientos: domingo 0.47–0.52, placebo ±0.15–0.19 (CDMX ±0.25); referencia sin PeMS: CalNex 2010 (fin de semana ~0.66). **Implicación para pedir el WRF de CDMX:** el viento solo no basta; hace falta junto con transporte dependiente del tiempo y emisión basada en tráfico. Siguiente prueba barata: puffs + HRRR en LA. Esto matiza la conclusión de los gemelos ("mejor viento le gana a más sensores"), que con datos reales no se confirmó.

**Peso de TEMPO ×1/3 como estándar (`peso_tempo.md`):** `--tempo-sigma-mult` (default 3; `TEMPO_SIGMA_MULT=1` para la versión anterior, resultados viejos con sufijo `_tp1`) en lineal y PINN. Con la restricción de tráfico, el domingo sube de 0.51–0.54 a **0.62–0.65** en nov–dic 2023 y primavera 2024, junto al estimador normalizado (0.58–0.69) y al borde de Infovial (0.65–0.73); sin restricción sigue en 0.41–0.44. El ajuste no empeora (LOO 12.36–13.38 ppb, r TEMPO 0.74–0.78). Centrales y aeropuertos siguen sin identificarse (incertidumbre ±90–220 t/año, ahora honesta). Superobservaciones de 8 km quedan como opción (domingo 0.57–0.58). App regenerada.

**LA con puffs (`otras_ciudades.md`, «Puffs + HRRR»):** **lo que limitaba en LA era el transporte estacionario, no el viento.** Con puffs y el viento promedio del dominio, r del modelo con emisión fija frente a TEMPO sube de 0.24 a 0.49, la vial hábil de 8,200 a 36,000 t/año (a priori 40,300), el domingo de la inversión completa de −0.14 a 0.43, el placebo baja de ±0.17 a ±0.14 y el LOO de 13.6 a 13.3 ppb. Meter HRRR o IDW en los puffs no mejora nada. El perfil horario de tráfico es supuesto (`puff.PROFILE`, sin PeMS). **Implicación para CDMX:** el WRF se justificaría por capa límite, viento en altura y recirculación, no por el viento a 10 m. Siguiente paso: revisar los puffs en CDMX con σθ = 30° y el peso reducido de TEMPO antes de adoptarlos.

**Puffs en CDMX con la configuración actual (`puffs_cdmx.md`):** opción en `scripts/puffs_cdmx.py`, sin cambiar el estándar. Mejoran casi todo (nov–dic 2023 / primavera 2024): r con TEMPO con emisión fija 0.50→0.65 / 0.50→0.58 e invertido 0.75→0.83 / 0.73→0.80; vial/inventario 42→75 % / 25→45 %; estimador normalizado más estable (CV de hábiles 0.35→0.26 / 0.27→0.23, placebo ±0.26→±0.19 en nov–dic) con domingo casi igual (0.65→0.61 / 0.70→0.68); domingo libre 0.42→0.49 / 0.43→0.53; AICM sube hacia su a priori. **Estaciones:** en nov–dic el híbrido empeora (11.2→12.3 ppb), toda la pérdida en SAG y XAL (Ecatepec); sin ellas el modelo mejora (13.0→12.2) y el híbrido empata. En primavera, empate. Causa: Ecatepec cae en la región "Centro" y su factor vial casi se duplica, un problema del proxy vial en una región grande, no del transporte. No ayudaron: viento IDW, perfil horario de Infovial, quitar el perfil; vida química de 2 h empeora. Confirma lo de LA: el transporte no estacionario importa más que el viento.

**Multifísica (`multifisica.md`, `multifisica_leighton.md`):** la caída de primavera **no es de la partición NO₂/NOₓ** (en superficie sube 3–6 %, al revés de lo necesario) **ni de dilución vertical** (columna/superficie plana en 0.87–0.93): cae la masa de NOₓ, en estaciones (0.70–0.75) y en TEMPO (~0.6). Lo más probable es una **vida química más corta** con más OH en temporada de ozono. Implicación: tampoco se pueden comparar estaciones entre temporadas sin corregir la vida química. Prioridades: (1) vida química por mes y hora (alto valor, 3–5 días); (2) capa límite de dos capas en los puffs (mezcla + residual nocturna, 1–2 semanas); (3) GEOS-CF como fondo y fuente de OH; (4) HCHO de TEMPO como indicador de OH. No recomendados por ahora: WRF propio, viento por topografía, depósito, PINN acoplada. Datos: radiosondeos 76679 descargados (`data/raw/igra/`, solo 06 y 18 h locales); GEOS-CF y HCHO de TEMPO disponibles; radiación UV de SIMAT pendiente (servidor sin respuesta).

**Zonas administrativas (`zonas_admin.md`):** esquema `admin_grupos` en `feasibility_linear.py` (opcional; el default sigue en `3x3_ecatepec`). 13 grupos de alcaldías y municipios (5 en CDMX, 8 en Edomex), cada uno con ≥1 estación de NOₓ y sin cruzar la frontera entre entidades (`data/interim/zonas_admin.gpkg`). Gemelo: ningún grupo requirió fusión (|corr| ≤ 0.28, error ≤ 14 %); con emisión distinta por municipio, los tres esquemas recuperan igual zonas, entidades y total, y **ninguno da valores municipales útiles** (16 % frente a ~20 % del a priori). Datos reales: empate en LOO (±0.1–0.2 ppb), TEMPO, domingo, estimador normalizado y placebo; SAG algo peor (23.0 frente a 20.7). Patrón espacial más estable entre temporadas (Spearman 0.82 frente a 0.70); CDMX Norte es la zona más alta en ambas, igual que el punto caliente de Vallejo en TEMPO. Cociente CDMX/Edomex: 0.71–0.76 en nov–dic frente a 0.71 del inventario 2018; 0.47 en primavera (efecto de temporada). Recomendación: adoptarlas por utilidad, a igual desempeño.

**Configuración final adoptada (`config_final.md`):** puffs como transporte estándar y Ecatepec como región propia (`3x3_ecatepec`), con σθ = 30°, TEMPO ×1/3 y restricción de tráfico. LOO del modelo 13.4 → 12.9 ppb (nov–dic); híbrido 11.7 (12.3 sin separar Ecatepec; 11.2 con pluma) y 6.8 en primavera (6.7 con pluma). XAL falla con cualquier esquema: problema local de la estación. r con TEMPO 0.83 / 0.80, vial 76 % del inventario, placebo ±0.19, domingo 0.64–0.66 (restringido) y 0.61–0.68 (normalizado). La PINN sigue con pluma: la referencia es el lineal-puff; el total vial de la PINN queda ahora 28–34 % por debajo. Corregido un `KeyError` en `invert.py --full`. App regenerada (Ecatepec con su límite real); resultados anteriores en `data/processed/pinn/anterior_pluma3x3/`.

**Plan de validación (`plan_validacion.md`):** cómo se valida la separación emisión/clima sin una emisión real de referencia. Resume la evidencia actual, lo no demostrado (sesgo en días estancados de +15–35 %, cambios entre temporadas, cambios < 10–20 %, totales, subestimación en cambios grandes), 9 pruebas planeadas con criterio de éxito y estado, y reglas para publicar.

**Bogotá (`bogota.md`):** agregarla **después**, como versión del método solo con estaciones. TEMPO no cubre Bogotá (solo TROPOMI, una pasada diaria, ciudad muy nublada): se pierden el mapa satelital y la parte satelital de la inversión; el estimador normalizado y la inversión con estaciones funcionan igual. RMCAB: 17 estaciones con NO₂/NOₓ y 16 con viento, endpoint público sin registro; muestra nov–dic 2023 descargada (`data/raw/bogota/`), 15 estaciones con ≥86 % de datos (Puente Aranda 26 %, Bolivia sin datos). NOₓ medio 33 ppb, pico a las 7 h; domingo/hábil crudo 0.71–0.73. Disponibles: METAR SKBO, inventario SDA 2023, radiosondeos; tráfico público solo hasta 2019–2020. Valor: caso replicable para ciudades sin satélite geoestacionario y el Día sin carro como experimento natural anual. Esfuerzo: 3–5 semanas.

**EDGAR (`edgar.md`):** EDGAR v8.1 NOₓ 2022 y 2018 por sector, recortado a CDMX, LA y Bogotá (`data/raw/edgar/`, CC BY 4.0). Sirve para el **patrón espacial**, no para totales ni para la fracción de tráfico. Nuestra emisión por zona coincide con el NOₓ **total** de EDGAR (Spearman 0.75 nov–dic, 0.59 primavera) y no con su transporte (0.25): la inversión sube justo las zonas con más emisión no vial en EDGAR (CDMX Norte, Tlalnepantla, Cuautitlán: 55–71 % no vial). Respalda llamarla "emisión de la zona". CDMX/Edomex: EDGAR 0.73 total y 0.82 transporte, frente a 0.71 del inventario y 0.71–0.76 nuestro. Fracción vial: EDGAR 52 % frente a 86 % del inventario; transporte de EDGAR ≈ 1/3 del inventario local (15.6 frente a 44.5 mil t/año en CDMX). Pendiente: CARB en LA; primavera sin corrección de vida química.

**Bogotá ligera: Día sin carro (`bogota.md`, sección "Versión ligera"):** viable y ejecutada. 10 jornadas verificadas (2015–2020, 2022–2024; sin 2021), RMCAB con 3–7 estaciones antes de 2020 y 14–16 después; capa límite ERA5 (ene–jun 2024 con mediana mes-hora). **NOₓ: +3 % (IC 90 % −8 a +15 %), sin baja visible; CO: −23 % (−30 a −16 %, p ≤ 0.002).** El placebo de jueves falsos queda centrado en 1 (±9 %): el método no inventa cambios y sí detecta el cambio en CO. Lectura: la medida saca autos y motos, pero buses y camiones diésel, que dominan el NOₓ, siguen circulando; el Día sin carro es control positivo para CO, no para NOₓ. Hallazgo de método: en Bogotá la capa límite de ERA5 hace la normalización más ruidosa que usar solo el viento (±17 % frente a ±9 %).

**Vida química por temporada y zonas administrativas como estándar (`vida_quimica.md`):** pérdida de NOₓ por OH calculado con radiación, O₃ y humedad de SIMAT (no ajustada con el NOₓ evaluado): ~4 h al mediodía en mayo, ~23 h en diciembre; los puffs ahora siguen cada emisión 24 h (antes 6). **Placebo dentro de primavera (abr–may frente a feb–mar) ahora pasa:** estimador normalizado 0.85 → 1.01, TEMPO 0.72 → 0.94, total invertido 0.70 → 0.87. **Placebo invierno frente a primavera sigue fallando** (estaciones 0.87; TEMPO y total 1.3–1.5): no se reportan cambios entre esas temporadas. Ajuste mejora (híbrido 10.8 ppb, gana en 18 de 24); domingo, placebos y contingencias iguales; el total vial absoluto baja de 76 % a 40 % del inventario (los totales siguen sin ser confiables). Las zonas administrativas empatan con 3×3 + Ecatepec y ya son el estándar (`REGION_SCHEME="admin_grupos"`). App regenerada con los 13 grupos.

**LA como control positivo (`otras_ciudades.md`, "Control positivo"):** **no pasa limpio**: confirma la dirección de la caída del domingo, no su tamaño. (1) Viento de la capa de mezcla HRRR (852/852 h): mejor viento en métricas sin inversión (r con TEMPO a emisión fija 0.47 → 0.55), pero LOO igual (13.2–13.5 ppb); la capa límite mediana nov–dic es ~370 m. (2) EMFAC: el portal rechaza descargas automáticas y no trae perfiles por día de semana; hay que bajarlo a mano. Referencia de literatura (Kim 2016, Pollack 2012, Goldberg 2021): domingo 0.67 ± 0.07, sábado 0.80 ± 0.08. (3) Configuración estándar con 7 zonas de grupos de ciudades (las Source Receptor Areas no tienen geometría pública): identificables en gemelo (corr. máx. 0.21), desempeño igual o algo mejor que 3×3. **Estimador normalizado: domingo 0.52 (0.44–0.59), por debajo de la referencia.** Para resolverlo: PeMS y separar festivos de domingos.

**Banco datos frente a desempeño (`banco_datos.md`, `figs/banco_*.png`):** corrido con vida química fija de 4 h y zonas admin (antes de que existiera `vida_quimica.md`). **El cambio mínimo detectable lo fija el transporte, no la cantidad de datos:** puffs ±0.19 frente a caja ±0.28; con 24, 15 o 9 estaciones (±0.18–0.19) o viento 20–30° peor no cambia. **El reparto por zonas depende del satélite:** con TEMPO, 9 estaciones casi igualan a 24 (Spearman con EDGAR 0.80); sin TEMPO, el LOO sube 2–3 ppb, Spearman cae a ~0.4 y el error por zona del gemelo se duplica. El viento: el gemelo lo sobrevalora; en datos reales no cambia nada (igual que LA). Bogotá con solo viento y sin satélite logra ±0.17, comparable. Regla para ciudades nuevas: placebo ≈ 2·CV·√(1/k + 1/(n−k)) (conservadora en LA: ±0.20 predicho frente a ±0.14 medido). Pendiente: degradación inversa en LA.

**CO en contingencias 2024 (`contingencias_2024.md`, "CO como trazador"):** la restricción **no se ve tampoco en el CO**. Tarde 12–17 h: NOₓ 1.15 (1.06–1.23), CO 1.22 (1.12–1.32), CO/NOₓ 1.06 (0.98–1.16). Mañana 7–11 h: NOₓ 1.08 (0.97–1.20), CO 1.08 (0.98–1.19), CO/NOₓ 1.00 (0.93–1.07). Placebos 0.83–1.12. A diferencia de Bogotá (CO −23 %, CO/NOₓ ≈ 0.75), no hay señal de que salgan autos; el CO sube más que el NOₓ por la tarde, lo que apunta a un sesgo común de los días de episodio (ver prueba de estancamiento). No distingue tipos de vehículo porque la restricción no se detecta en ningún gas.

**Sesgo en días estancados (`estancamiento.md`): corrige una afirmación anterior.** El placebo "estancado" con el modelo estándar ya daba 0.94 (0.86–1.02); el "+15–35 %" era el cociente de los días de contingencia sobre ese placebo (1.24), no un sesgo de los días estancados. El defecto real es una **pendiente**: sin contingencia, el cuartil más estancado sale en 0.86 y el más ventilado en 1.21, porque el modelo exagera el efecto del viento débil (la observación responde con exponente ~0.5). No es la mañana, ni el arrastre (puffs de 48 h igual), ni rachas, ni recirculación; los radiosondeos muestran capa límite ~10 % alta en algunas tardes, sin efecto en la pendiente. **Corrección propuesta (no adoptada aún):** piso de viento `U_MIN` de 1.0 a 2.0 m/s → placebo estancado 0.96, aleatorio 0.98, domingo 0.67/0.69, confinamiento 2020 −41 % (antes −38 %), contingencias 1.09 (1.00–1.16), sin baja. Límites: el piso se eligió con feb–may 2024; en nov 2023–ene 2024 la pendiente no cambia; no se probó en la inversión completa.

**Piso de viento 2 m/s adoptado (`estancamiento.md`, "Validación en invierno e inversión completa"):** `U_MIN = 2.0` es el estándar (`U_MIN=1.0` o `--u-min 1.0` para volver). Inversión completa: LOO híbrido mejora 0.1–0.2 ppb, r con TEMPO y domingo sin cambio, placebos pasan en ambas temporadas, total vial +37 % (nov–dic) y +30 % (feb–may), validación 2020 −41/−42 %. **En invierno la pendiente se corrige solo en parte:** el cuartil ventilado baja de 1.25 a 1.15 (justo en el límite de ±15 %) y la dispersión sube algo (0.268 frente a 0.246); la causa restante es que el modelo exagera el efecto de la capa límite. Las alternativas solo de viento (meandro, u^−0.5) no corrigen; un tope de capa límite de 1,500 m (`PBL_MAX`) queda como opción porque baja el placebo 2019 a 0.84. App regenerada.
