# Régimen del ozono en la ZMVM (frente F2)

Fecha: 2026-11-14; repetición con 2026 y revisión de literatura: 2026-11-15 (sección "Repetición con 2026", antes de "Cómo reproducir"). Ramas `explore/ozone-regime` y `explore/ozone-regime-2`. Pregunta: ¿el ozono de la ZMVM está limitado por COV o por NOₓ, y cambia por zona? Plan: [exploraciones_valor.md](../management/exploraciones_valor.md), sección F2.

## Resumen

El domingo el NOₓ baja ~30 % en promedio diario y ~42 % en la mañana, y el ozono máximo de 8 h **no baja**: sube 3 % en el centro y queda igual en la periferia (temporada de ozono, feb–jun, con días emparejados por clima). En el confinamiento de 2020 el NOₓ bajó ~33 % y el ozono bajó solo 2–4 % (intervalo que cruza cero). Las dos pruebas dicen lo mismo: recortar NOₓ casi no baja el ozono de la ciudad y en el centro lo sube. El cociente HCHO/NO₂ de TEMPO lo confirma en el espacio: las seis estaciones donde el ozono sube en domingo tienen los cocientes más bajos de la red (1.0–1.2) y la única donde baja (Ajusco) uno de los más altos (3.6); la correlación entre el cociente y el efecto de domingo es −0.73 (2024) y −0.68 (2025). Con los umbrales de Duncan et al. (2010), el núcleo urbano queda limitado por COV en febrero (cociente 0.56) y pasa a transición de marzo a mayo (1.1–1.4). Dos condiciones: el ordenamiento espacial lo da casi todo el NO₂ (el NO₂ solo correlaciona igual, −0.71), y los umbrales absolutos dependen del instrumento; la línea donde el domingo no cambia el ozono queda en un cociente de ~2.0.

## Paso 1. Efecto de fin de semana (sin datos nuevos)

**Datos.** SIMAT 2019, 2020, 2023 y 2024 (horarios, 34 estaciones con ozono) y OpenAQ (SINAICA) 2025–2026. Métricas por estación y día: ozono máximo de 8 h (ventanas que empiezan de 07 a 16 h, ≥ 6 horas válidas), Oₓ = O₃ + NO₂ medio de 12 a 17 h, NOₓ medio de 24 h y NOₓ de 06 a 09 h. Temporada de ozono: feb–jun; invierno: nov–ene.

**Exclusiones.** Festivos (`inversion.linear.HOLIDAYS`), fin de año y Semana Santa (`nox_ml.data.calendar`), y días con medidas de contingencia: los 11 episodios de 2024 (`contingencias_ozono_2024_episodios.csv`) y, para los demás años, el día siguiente a cualquier hora con O₃ > 154 ppb en alguna estación (umbral de la Fase I). 2020 va aparte.

**Control por clima.** Cada domingo se compara con los días hábiles de la misma temporada y año, a ±21 días, con temperatura máxima a ±1.5 °C y viento medio de la tarde a ±25 % (mediana de las estaciones de SIMAT; METAR de MMMX en 2025–2026). Se exigen ≥ 2 días emparejados; quedan 80 de 92 domingos de temporada de ozono y 31 de 41 de invierno. Cociente = Σ domingo / Σ media de sus días emparejados. Intervalos del 90 % por bootstrap de semanas (1000 réplicas; cada domingo con sus días es una semana). Zona: mediana de las estaciones con ≥ 8 pares; centro = a menos de 12 km del Zócalo.

**Resultados (domingo ÷ hábil, emparejado por clima).**

| Caso | Zona | O₃ máx. 8 h | Oₓ tarde | NOₓ 24 h | NOₓ mañana |
|---|---|---|---|---|---|
| Temporada de ozono (2019, 2023–2026) | centro | **1.03** (1.00–1.06) | 0.93 (0.90–0.96) | 0.70 (0.67–0.73) | 0.58 (0.56–0.62) |
| | periferia | **1.00** (0.97–1.03) | 0.93 (0.90–0.96) | 0.69 (0.66–0.71) | 0.56 (0.53–0.59) |
| Invierno | centro | 1.09 (1.01–1.15) | 0.94 (0.88–0.99) | 0.77 (0.70–0.84) | 0.68 (0.59–0.76) |
| | periferia | 1.05 (1.01–1.11) | 0.95 (0.90–1.00) | 0.73 (0.68–0.78) | 0.61 (0.55–0.68) |
| Confinamiento: hábiles abr–may 2020 ÷ 2019 | centro | 0.96 (0.91–1.01) | 0.94 (0.89–0.97) | 0.67 (0.62–0.71) | 0.69 (0.60–0.75) |
| | periferia | 0.98 (0.95–1.02) | 0.99 (0.95–1.03) | 0.67 (0.63–0.71) | 0.65 (0.60–0.69) |
| Domingo en el confinamiento (mar–jun 2020) | centro | 0.99 (0.94–1.04) | 0.93 (0.89–0.97) | 0.66 (0.59–0.72) | 0.54 (0.46–0.64) |

Sin emparejar por clima las cifras cambian poco (O₃ de temporada 1.03 y 1.00), así que el resultado no depende del emparejamiento.

**Por estación** (temporada de ozono, `results/weekend_ratios.csv`): el ozono sube en domingo con intervalo por encima de 1 en 6 de 34 estaciones, todas del centro y el norte-oriente urbano: MER 1.09, TLA 1.08, CAM 1.07, XAL 1.07, TLI 1.05, UIZ 1.04. Baja con intervalo por debajo de 1 solo en AJU (Ajusco, 0.95), la estación más alta y a favor del viento del sur-poniente; AJM (0.97), MPA (0.97), LLA (0.97) y SAC (0.98) también quedan bajo 1 sin llegar a ser significativas. En invierno sube en 11 de 33 y no baja en ninguna. El gradiente es el esperado: limitado por COV en el núcleo urbano, en transición o con tendencia a NOₓ en la orilla sur-poniente, donde llega la masa de aire ya envejecida por la tarde.

**Oₓ.** El oxidante total baja ~7 % en domingo (y ~6 % en el confinamiento en el centro) mientras el ozono no baja: una parte de la "subida" del ozono es menos titulación por NO, pero la producción neta de oxidante solo cae 7 % con 30–40 % menos NOₓ. Eso es lo que se espera de un régimen limitado por COV o de transición, no de uno limitado por NOₓ, donde Oₓ y O₃ caerían en proporción parecida al NOₓ.

**Contingencias.** Con el umbral de 154 ppb en una hora, los días de activación (indicador aproximado) fueron 4 en 2019, 1 en 2020, 4 en 2023, 17 en 2024 (los episodios reales de 2024 fueron 11, algunos de varios días), 5 en 2025 y 8 en 2026 (OpenAQ, con menos estaciones: cuenta de menos). Del orden de 5–10 activaciones al año, casi todas en marzo–junio.

## Paso 2. HCHO/NO₂ de TEMPO

**Datos.** TEMPO HCHO L2 V04 (la versión vigente; V03 termina en septiembre de 2025), feb–may de 2024 y de 2025, granulos de 18–22 UTC (12–16 h local): 1161 granulos, 99 MB. La descarga usa el servidor OPeNDAP de Earthdata para pedir solo las filas y columnas del dominio (las del granulo de NO₂ del mismo barrido) y las variables necesarias: ~80 kB y ~8 s por granulo, en lugar de ~90 MB del granulo completo. La búsqueda CMR por mes y el filtro de horas son los de `nox_ml.data.tempo`. El NO₂ es el de `data/raw/tempo/` (V04, columna troposférica). Febrero tiene ~15 días en ambos años porque faltan granulos de NO₂ V04 a inicios de mes.

**Método.** HCHO y NO₂ del mismo barrido se emparejan píxel a píxel. Píxel válido: bandera de calidad 0 en los dos productos, fracción de nubes efectiva < 0.2 y ángulo cenital solar < 70°. Rejilla de 0.05° (167 celdas en el dominio); cociente de cada celda = media de HCHO / media de NO₂ en el periodo (cociente de medias: el HCHO de un píxel es demasiado ruidoso para un cociente píxel a píxel; los valores negativos se conservan para no sesgar la media). Ruido: error por bootstrap de días, mapas de semanas pares contra impares y de un mes contra otro. Cada estación toma la celda que la contiene.

**Ruido: el HCHO alcanza.** Con una temporada, el error típico del cociente por celda es 0.10–0.12 (bootstrap de días) frente a un rango espacial de 1.2 a 4.2 (percentiles 10 y 90). Los mapas de semanas pares e impares coinciden con Spearman 0.99 (2024) y 0.98 (2025), y los de dos meses distintos con 0.87–0.91: un mes basta para separar zonas.

**Mapa por temporada** (fracción de las 167 celdas del dominio, que incluye montaña y zonas rurales):

| Umbrales | 2024 COV / transición / NOₓ | 2025 COV / transición / NOₓ |
|---|---|---|
| Duncan et al. (2010): < 1, 1–2, > 2 | 0 % / 48 % / 52 % | 2 % / 41 % / 57 % |
| Jin et al. (2017): < 3.2, 3.2–4.1, > 4.1 | 80 % / 10 % / 11 % | 84 % / 15 % / 1 % |
| Calibrado con las estaciones (ver abajo): < 1.25, 1.25–2, > 2 | 12 % / 36 % / 52 % | 12 % / 31 % / 57 % |

Los umbrales de la literatura fueron derivados para OMI y con modelos de otras ciudades; aplicados a TEMPO dan mapas muy distintos (todo COV con Jin, casi nada con Duncan en la media de la temporada). El sesgo de cada producto (TEMPO subestima el NO₂ urbano y el HCHO tiene su propio sesgo según las validaciones publicadas; no los cuantificamos aquí) mueve los umbrales. Por eso el resultado útil es el ordenamiento y el umbral calibrado localmente, no la clasificación con un umbral importado.

**Ciclo de la temporada (núcleo, celdas a < 0.1° del Zócalo; mediana del dominio).**

| Mes | 2024 núcleo | 2024 dominio | 2025 núcleo | 2025 dominio |
|---|---|---|---|---|
| Febrero | 0.56 | 1.06 | 0.72 | 1.61 |
| Marzo | 1.11 | 1.97 | 1.01 | 1.99 |
| Abril | 1.34 | 2.40 | 1.11 | 2.01 |
| Mayo | 1.43 | 2.67 | 1.36 | 2.57 |

Con el calor sube el HCHO (más COV biogénicos y más fotoquímica) y el régimen se corre hacia NOₓ: el núcleo pasa de COV claro en febrero a transición en mayo, y en mayo 70 % del dominio queda sobre 2.

**Prueba decisiva: coincidencia con el paso 1.** Por estación (34, `results/stations_fnr_<año>.csv`):

| | 2024 | 2025 |
|---|---|---|
| Spearman cociente vs. domingo ÷ hábil del O₃ | **−0.73** | **−0.68** |
| Parcial, quitando la distancia al Zócalo | −0.59 | −0.52 |
| Solo la distancia | −0.53 | −0.53 |
| Solo −NO₂ (la columna de NO₂ sola) | −0.71 | −0.70 |
| Solo HCHO | +0.62 | +0.57 |
| Cociente mediano de las 6 estaciones donde el O₃ sube | 1.05 | 1.05 |
| Cociente mediano de las demás | 1.43 | 1.36 |
| Cociente donde la recta del domingo cruza 1 | 2.14 | 1.95 |

Las seis estaciones donde el ozono sube en domingo (MER, CAM, TLA, XAL, TLI, UIZ) están entre las 12 de cociente más bajo (1.0–1.2); la única donde baja (AJU, 3.6) es la segunda más alta; MPA (3.8), INN, TAH y CHO, en la orilla con cociente > 2.5, tienen domingo ÷ hábil de 0.97–1.01. La recta del domingo cruza el 1 en un cociente de ~2, el límite superior de Duncan: los dos pasos coinciden en el espacio y fijan un umbral local.

**Dos límites.**

1. **El ordenamiento lo da el NO₂.** La columna de NO₂ varía 4–5 veces en el dominio y el HCHO solo 1.5 veces; el NO₂ solo ordena las estaciones igual que el cociente (−0.71 frente a −0.73), y el HCHO es mayor en el centro (correlaciona al revés). Lo que el HCHO aporta es la escala absoluta (dónde está el cruce) y el cambio de la temporada, no la forma del mapa.
2. **El ciclo de la temporada no se confirma con el fin de semana.** Si el núcleo pasa de COV en febrero a transición en mayo, el ozono del domingo debería subir más en feb–mar que en abr–jun. Medido: centro 1.01 (0.96–1.06) en feb–mar y 1.04 (1.01–1.08) en abr–jun, intervalos que se traslapan; no contradice con significancia, pero tampoco lo confirma. El invierno, con la fotoquímica más baja, sí tiene la mayor subida (1.09).

## Comparación con la literatura

- **MCMA-2003 y MILAGRO-2006.** Los estudios de modelado y de radicales de esas campañas (Lei et al. 2007 y 2008 con CAMx; Volkamer et al. 2010; Song et al. 2010; síntesis en Molina et al. 2007 y 2010) concluyeron que la producción de ozono en el núcleo urbano está limitada por COV en la mañana y se acerca a la transición o a NOₓ en la tarde y a favor del viento (sur y sur-poniente). Stephens et al. (2008) documentaron con la RAMA 1986–2007 que el ozono de fin de semana es igual o mayor que el de entre semana pese a menos NOₓ.
- **Lo que aporta este frente.** Confirma lo conocido con datos de 2019–2026, después de dos décadas de cambio de flota y de inventario: el núcleo sigue limitado por COV y el efecto de fin de semana persiste. Lo que parece nuevo (la búsqueda de abajo no encontró lo contrario, pero no fue exhaustiva) es (a) la cifra actual por estación con control por clima e intervalos, (b) la réplica con el confinamiento de 2020 (NOₓ −33 %, ozono −2 a −4 %, no significativo) y (c) el mapa de régimen de TEMPO cada temporada, con umbral calibrado contra el fin de semana de la red (cruce en ~2) y el corrimiento del núcleo de COV en febrero a transición en mayo, que las campañas de 2003 y 2006 (un mes cada una) no miraron; con la repetición de 2026 el corrimiento mensual del cociente se repite, pero el del ozono de domingo no (ver "Repetición con 2026").
- **Búsqueda de literatura (2026-11-15, web, no exhaustiva).** No se encontró ningún estudio con TEMPO para la ZMVM. Lo más cercano: Vazquez Santiago et al. (2021) usaron el cociente HCHO/NO₂ de OMI en la ZMVM (2006–2016) y concluyen que el núcleo se volvió más limitado por COV y que reducir COV sería lo adecuado; comparan dos pares de umbrales y el resultado depende de cuál se use, como aquí. Tian et al. (2025) calibran el umbral global del cociente con el efecto de fin de semana del ozono (transición cerca de 3.1, rango ~2.7–3.4), la misma idea de nuestro cruce local; la ZMVM no está en su análisis. Para TEMPO solo se hallaron trabajos sobre EE. UU. (p. ej. Canty, 2025), que no se leyeron completos. Lo no cubierto por lo encontrado: el cociente de TEMPO en la ZMVM, su ciclo mensual y su contraste con el domingo del ozono por estación.

## Valor: qué cambiaría en el programa de contingencias

La Fase I por ozono activa el Doble Hoy No Circula, que reduce sobre todo NOₓ vehicular (y algo de COV del escape). Con el régimen medido, recortar NOₓ ~30 % (la reducción real de NOₓ en una contingencia no se midió aquí; se espera menor que la del domingo) deja el ozono del centro igual o un poco más alto y lo baja apenas en la orilla sur-poniente. Consecuencias para la CAMe y la autoridad ambiental:

1. **La medida principal no ataca el ozono del día.** Su efecto esperado en el máximo de 8 h, por analogía con el domingo y el confinamiento, es nulo en el centro y pequeño en la periferia (no se probó con un modelo); no se midió aquí por qué terminan las contingencias (probablemente el clima). Eso es compatible con que el sistema no detecta el efecto de las contingencias sobre la emisión ([casos_de_uso.md](casos_de_uso.md)).
2. **Las medidas sobre COV serían las eficaces:** venta y carga de combustible (vapores), solventes y pinturas, gas LP (fugas domésticas, una fuente conocida de la ZMVM desde MCMA-2003), talleres, y restringir actividades con COV en los días de activación.
3. **El NOₓ sigue importando** por el NO₂ y las partículas secundarias, y porque fuera del núcleo (orilla sur-poniente, Ajusco) el régimen se acerca a NOₓ: recortar solo NOₓ desplaza el máximo de ozono hacia afuera.
4. **Uso frecuente para el sistema:** un mapa de régimen por temporada (TEMPO, gratis, cada hora) y el efecto de fin de semana por estación como indicador de seguimiento, del orden de 5–10 episodios al año y una revisión por temporada.

## Veredicto

| Criterio | Escala | Resultado |
|---|---|---|
| **¿Funciona?** | 0–3 | **2, funciona con condiciones.** El paso 1 es robusto (con y sin emparejar por clima, réplica con el confinamiento) y el mapa del paso 2 coincide en el espacio con él; pero el ordenamiento lo da casi todo el NO₂ y los umbrales absolutos hay que calibrarlos con la red |
| **Evidencia** | Prueba decisiva y cifra | Domingo: NOₓ 0.70 (24 h) y 0.58 (mañana), O₃ máx. 8 h 1.03 (1.00–1.06) en el centro y 1.00 (0.97–1.03) en la periferia. Confinamiento: NOₓ 0.67, O₃ 0.96–0.98. Spearman cociente HCHO/NO₂ vs. domingo del O₃: −0.73 (2024) y −0.68 (2025); mapas de semanas pares e impares 0.98–0.99 |
| **Usuario** | Rol de casos_de_uso.md | CAMe y autoridad ambiental (diseño del programa de contingencias, CU3 y CU9); planeadores del inventario (CU5) |
| **Frecuencia** | Usos al año | Un mapa por temporada de ozono (1–2 al año) y una revisión del programa cada pocos años; consulta en los ~5–10 episodios al año para explicar por qué la medida no baja el ozono |
| **Alternativa** | Ninguna · peor · igual · mejor | Confirma, con datos de 2019–2026, lo que ya concluyeron los modelos y campañas de 2003 y 2006 y el estudio con OMI de 2021 (el núcleo está limitado por COV); su ventaja sería el costo bajo y poder actualizarlo cada año, no una conclusión distinta. No se comparó contra un modelo químico. Peor que un modelo para cuantificar cuánto baja el ozono por tonelada de COV |
| **Decisión que cambia** | Qué haría distinto | Que la Fase I deje de apoyarse solo en reducir NOₓ vehicular: agregar medidas de COV (vapores de combustible, solventes, gas LP, pinturas) en los días de activación, y dirigir las de NOₓ a la orilla sur-poniente, donde el régimen se acerca a NOₓ |
| **Costo de llevarlo a producto** | Días y costo al mes | 3–5 días: mover la descarga de HCHO a `nox_ml.data.tempo` (por OPeNDAP), el mapa y el efecto de fin de semana con pruebas; operación: ~600 granulos por temporada, ~50 MB y ~1 h de descarga, cálculo en minutos, sin costo |
| **Veredicto** | Adoptar · seguir con condiciones · descartar | **Seguir con condiciones:** (1) presentar el efecto de fin de semana como el resultado principal, que no depende del satélite; (2) usar el mapa de HCHO/NO₂ solo con el umbral calibrado con la red (~2) y decir que su forma la da el NO₂; (3) antes de comunicarlo, revisar si ya hay estudios con TEMPO HCHO/NO₂ para la ZMVM y la validación de los sesgos de los dos productos |

## Repetición con 2026: ¿cambia el régimen dentro de la temporada? (2026-11-15)

**Pregunta y criterio (fijado antes).** F2 vio el centro limitado por COV en febrero y en transición en mayo, pero la subida del ozono en domingo no fue claramente mayor en feb–mar que en abr–jun. Aumenta la confianza si en al menos 2 de 3 años (2024, 2025, 2026) el cociente HCHO/NO₂ del centro sube de febrero a mayo **y** el domingo ÷ hábil del O₃ baja en la misma dirección; no la aumenta si los años se contradicen.

**Datos nuevos.** HCHO V04 feb–may 2026, 545 granulos de 18–22 UTC con el mismo script (`data/raw/tempo_hcho/`, anotado en `data/raw/MANIFEST.md`). O₃ de 2026 de OpenAQ (desde el 15 de febrero, así que febrero de 2026 casi no tiene domingos). Script: `notebooks/exploraciones/ozone_regime/monthly_regime.py`; tablas `monthly_fnr_center.csv`, `monthly_weekend_center.csv` y `monthly_criterion.csv`. Mismo emparejamiento por clima del paso 1, solo estaciones del centro (< 12 km del Zócalo), domingos cortados por mes; intervalos del 90 % por bootstrap de semanas (domingos) para el ozono y de días para el cociente. No se exige mínimo de pares por estación (un mes tiene 2–5 domingos tras las exclusiones), así que los intervalos son anchos.

**Cociente HCHO/NO₂ del centro por mes** (intervalo 90 %):

| Mes | 2024 | 2025 | 2026 |
|---|---|---|---|
| Febrero | 0.56 (0.46–0.67) | 0.72 (0.60–0.87) | 0.75 (0.67–0.87) |
| Marzo | 1.11 (1.00–1.24) | 1.01 (0.95–1.09) | 0.90 (0.83–0.98) |
| Abril | 1.34 (1.24–1.43) | 1.11 (0.99–1.28) | 1.26 (1.16–1.36) |
| Mayo | 1.43 (1.34–1.54) | 1.36 (1.27–1.45) | 1.28 (1.15–1.44) |

El corrimiento de febrero a mayo se repite en los tres años, con intervalos de febrero y mayo que no se traslapan. Eso confirma la parte del satélite.

**Domingo ÷ hábil del O₃ máximo de 8 h, centro** (intervalo 90 %; domingos entre paréntesis):

| Periodo | 2024 | 2025 | 2026 |
|---|---|---|---|
| Febrero | 0.78 (0.57–1.05; 2) | 1.22 (1.06–1.42; 4) | sin dato (2 domingos, sin pares) |
| Marzo | 0.97 (0.90–1.04; 3) | 1.06 (1.01–1.10; 5) | 1.00 (0.92–1.04; 3) |
| Abril | 1.14 (1.07–1.18; 3) | 1.13 (1.00–1.26; 2) | sin domingos válidos |
| Mayo | 1.12 (1.09–1.12; 2) | 0.98 (0.89–1.02; 3) | 1.10 (1.01–1.23; 5) |
| Feb–mar | 0.91 (0.76–1.03; 5) | 1.09 (1.03–1.18; 9) | 1.00 (0.88–1.07; 5) |
| Abr–may | 1.13 (1.08–1.16; 5) | 1.02 (0.96–1.11; 5) | 1.07 (1.00–1.17; 6) |

**Criterio, año por año** (de febrero a mayo; entre paréntesis, intervalo del cambio):

| Año | Cociente sube | Domingo del O₃ | Cambio del O₃ feb a may | Cambio feb–mar a abr–may | Cumple |
|---|---|---|---|---|---|
| 2024 | sí (0.56 a 1.43) | sube (0.78 a 1.12) | +0.34 (+0.04 a +0.55) | +0.22 (+0.09 a +0.38) | no, direcciones opuestas |
| 2025 | sí (0.72 a 1.36) | baja (1.22 a 0.98) | −0.25 (−0.49 a −0.06) | −0.07 (−0.18 a +0.04) | **sí** |
| 2026 | sí (0.75 a 1.28) | sin dato en febrero | sin dato | +0.07 (−0.02 a +0.23) | no |

Solo 1 de 3 años cumple (2025). En 2024 el efecto de domingo va en sentido contrario al esperado, con intervalo del cambio sobre cero; 2026 tampoco lo debilita. Spearman entre cociente mensual y domingo ÷ hábil, con los 11 pares año-mes que tienen dato: +0.24 (p = 0.51); no hay relación, y el signo es contrario al esperado (negativo).

**Veredicto de esta repetición: no aumenta la confianza en el ciclo dentro de la temporada.** El cociente sube de febrero a mayo en los tres años, pero el ozono de domingo no lo sigue: 2024 contradice a 2025. Se sostiene lo que ya estaba (el cociente sube con el calor y el orden espacial coincide con el domingo); no se sostiene que el régimen del ozono del centro cambie de COV a transición en el curso de la temporada. Cautelas: los meses tienen 2–5 domingos, el ozono de domingo de un mes mezcla clima, episodios y exclusiones (Semana Santa saca domingos de abril; las contingencias de 2026 son un indicador), y febrero y abril de 2026 quedan sin dato; con tan pocos domingos la prueba tiene poca potencia, así que "no se confirma" no equivale a "se descarta". Tampoco se descarta que la columna total de TEMPO a mediodía no represente el régimen de la mañana, cuando se forma el ozono.

**Qué cambia en el veredicto.** "Funciona" sigue en 2 (con condiciones). Se agrega la condición (4): no afirmar un cambio de régimen dentro de la temporada con base en el satélite; presentar el ciclo mensual del cociente como un cambio del indicador, no como un cambio comprobado de la química del ozono. La fila "Alternativa" se corrigió: el resultado confirma lo que ya concluían las campañas y el estudio de OMI (2021); no es una conclusión mejor.

**Verificación de cifras del veredicto.** Domingo y confinamiento: `weekend_ratios.csv`. Spearman, cruce y mapas de semanas pares e impares: `fnr_summary.csv` y `stations_fnr_<año>.csv`. Núcleo por mes y 70 % del dominio sobre 2 en mayo (0.73 en 2024, 0.70 en 2025): `fnr_monthly.csv`. Se suavizaron las afirmaciones sin fuente en los resultados: la reducción de NOₓ de una contingencia (~5–10 %), "las contingencias terminan por el clima", "unos pocos por ciento" en la periferia y la comparación con los modelos de campaña. Los DOI de las referencias de la sección de literatura anterior no se verificaron en esta pasada.

**Referencias nuevas (APA 7).**

- Duncan, B. N., Yoshida, Y., Olson, J. R., Sillman, S., Martin, R. V., Lamsal, L., Hu, Y., Pickering, K. E., Retscher, C., Allen, D. J., & Crawford, J. H. (2010). Application of OMI observations to a space-based indicator of NOx and VOC controls on surface ozone formation. *Atmospheric Environment, 44*(18), 2213–2223. https://doi.org/10.1016/j.atmosenv.2010.03.010
- Jin, X., Fiore, A. M., Murray, L. T., Valin, L. C., Lamsal, L. N., Duncan, B., Folkert Boersma, K., De Smedt, I., Abad, G. G., Chance, K., & Tonnesen, G. S. (2017). Evaluating a space-based indicator of surface ozone-NOx-VOC sensitivity over midlatitude source regions and application to decadal trends. *Journal of Geophysical Research: Atmospheres, 122*(19), 10439–10461. https://doi.org/10.1002/2017JD026720
- Tian, Y., Wang, S., & Jin, X. (2025). Global patterns and trends in ground-level ozone chemical formation regimes from 1996 to 2022. *Atmospheric Chemistry and Physics, 25*(16), 9127–9149. https://doi.org/10.5194/acp-25-9127-2025
- Vazquez Santiago, J., Inoue, K., & Tonokura, K. (2021). Diagnosis of ozone formation sensitivity in the Mexico City Metropolitan Area using HCHO/NO2 column ratios from the ozone monitoring instrument. *Environmental Advances, 6*, Article 100138. https://doi.org/10.1016/j.envadv.2021.100138

**Veredicto actualizado (plantilla).** ¿Funciona? 2 (sin cambio). Evidencia: la de arriba más el cociente del centro de febrero a mayo (0.56 a 1.43 en 2024, 0.72 a 1.36 en 2025, 0.75 a 1.28 en 2026) y el domingo del O₃, que solo se debilita en 2025 (1.22 a 0.98). Alternativa: confirma lo conocido, no lo mejora. Decisión que cambia: igual, con el límite (4). Veredicto: **seguir con condiciones (1)–(4); la repetición no aumenta la confianza**.

**Sigue sin probarse.** Cociente por hora (mañana frente a tarde); un criterio con más domingos (juntar los años por mes, o usar sábados); la lista oficial de contingencias; los sesgos de TEMPO frente a Pandora; una lectura completa de la literatura con TEMPO.

## Cómo reproducir

```sh
# Paso 1 (≈ 3 min): tablas en notebooks/exploraciones/ozone_regime/results/
uv run python notebooks/exploraciones/ozone_regime/weekend_effect.py
# Paso 2: descarga por OPeNDAP (Earthdata en ~/.netrc), ~8 s y ~80 kB por granulo
uv run python notebooks/exploraciones/ozone_regime/tempo_hcho_download.py 2024-02-01 2024-05-31
uv run python notebooks/exploraciones/ozone_regime/tempo_hcho_download.py 2025-02-01 2025-05-31
uv run python notebooks/exploraciones/ozone_regime/hcho_no2_ratio.py
# Repetición con 2026 (primero la descarga 2026-02-01 2026-05-31)
uv run python notebooks/exploraciones/ozone_regime/monthly_regime.py
```

Archivos de salida: `weekend_ratios.csv` (cociente, intervalo y número de pares por estación, zona, métrica y caso), `days.csv` (clima y tipo de cada día), `activations_per_year.csv`, `fnr_map.csv` (celda de 0.05°, temporada, HCHO, NO₂, FNR, error y régimen), `fnr_summary.csv` y `stations_fnr_<temporada>.csv`.

## Lo que faltó

- **Química más fina.** No se calculó el umbral con modelo (cociente de producción de radicales, LROx/PHOx) ni la sensibilidad por hora: TEMPO tiene barridos cada hora y el régimen de la mañana (más COV-limitado) es distinto al de la tarde.
- **Sesgos de los productos.** No se cuantificó cómo los sesgos de NO₂ y HCHO de TEMPO frente a Pandora mueven los umbrales; el umbral calibrado (~2) absorbe una parte.
- **Contingencias reales fuera de 2024.** Para 2019, 2020, 2023, 2025 y 2026 se usó un indicador (O₃ > 154 ppb en una hora); la lista oficial de la CAMe mejoraría las exclusiones y el conteo.
- **Febrero incompleto.** Faltan granulos de NO₂ V04 a inicios de febrero de 2024 y 2025 (~15 días por año).
- **Otros años de TEMPO.** 2026 se descargó el 2026-11-15; 2023 no existe en V04 (empieza en agosto de 2023).
- **Clima en el emparejamiento.** Se emparejó por temperatura máxima y viento de la tarde; no por radiación, capa de mezcla ni humedad. El resultado sin emparejar es casi igual, lo que sugiere que el clima no domina el cociente.
- **Literatura con TEMPO.** Búsqueda web somera el 2026-11-15; no se leyeron completos los trabajos de TEMPO sobre EE. UU. y no se consultaron bases como Scopus.
