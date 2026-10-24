# Bogotá como tercera ciudad: factibilidad

## Conclusión

**Agregarla después, no ahora**, y con un papel distinto al de la CDMX:

- Las estaciones de Bogotá son **tan buenas o mejores que las de la CDMX**, y su acceso es abierto y automatizable. Lo comprobamos descargando dos meses.
- Pero **no tiene TEMPO** (está fuera de su campo de visión). Solo hay una pasada diaria de TROPOMI, en una ciudad muy nublada.
- Por eso Bogotá serviría como versión **solo con estaciones** del método. El estimador normalizado y la inversión con estaciones funcionan igual. Lo que depende del satélite no: el mapa de puntos calientes, el contraste centro − periferia y parte de la restricción espacial.

Vale la pena cuando el sistema de dos ciudades esté estable, sobre todo por sus experimentos naturales: el Día sin carro anual y el Pico y placa.

## Datos disponibles

| Dato | Estado | Detalle |
|---|---|---|
| NO, NO₂, NOₓ horarios (RMCAB) | 🟢 | 20 estaciones; **17 con NO₂/NOₓ**. Endpoint público sin registro. Muestra nov–dic 2023: 15 estaciones con ≥ 86 % de datos; Puente Aranda 26 %; Bolivia sin datos. Para comparar, la CDMX tiene ~24 estaciones con NOₓ en un dominio más grande. |
| Viento en estaciones (RMCAB) | 🟢 | 16 estaciones con velocidad y dirección; ≥ 91 % de datos en la muestra (Kennedy sin dirección). |
| CO (trazador vehicular) | 🟢 | En casi todas las estaciones, ≥ 87 %. Sirve para la prueba CO/NOₓ del plan de validación. |
| Viento del aeropuerto (METAR SKBO) | 🟢 | Horario vía IEM; nov–dic 2023 completo. |
| Radiosondeos | 🟡 | Hay registro IGRA de El Dorado (COM00080222); falta revisar la frecuencia y si hay sondeos de mediodía. |
| Capa límite y viento ERA5 | 🟡 | Disponible, pero a 0.25° (~28 km) no resuelve bien la sabana entre cerros. La CDMX tiene el mismo problema, y ahí MERRA-2 y ERA5 funcionaron aceptablemente. |
| Satélite geoestacionario (TEMPO) | 🔴 | **No cubre Bogotá.** TEMPO solo observa Norteamérica; ningún geoestacionario cubre Sudamérica. |
| TROPOMI (Sentinel-5P) | 🟡 | Una pasada diaria (~13:30), píxeles de ~3.5 × 5.5 km. Bogotá es muy nublada, sobre todo en las temporadas de lluvia (abril–mayo, octubre–noviembre), así que quedarían pocos días útiles. No lo cuantificamos. Ya hay estudios con TROPOMI sobre Bogotá en la cuarentena de 2020. |
| Conteos de tráfico | 🟡 | Datos abiertos de la Secretaría de Movilidad ("Conteo Vehículos CGT", "Velocidad Actual en Vía"), pero con última actualización registrada en 2019–2020. Hay que verificar si existen más recientes. |
| Inventario de emisiones (SDA) | 🟢 | Inventarios anuales publicados; el más reciente es el de 2023, publicado en 2025. No revisamos su resolución espacial ni si trae NOₓ por localidad. |
| Experimentos naturales | 🟢 | Día sin carro (anual; el informe oficial de 2008 midió −9 % de NO₂ frente a un día típico), Pico y placa, ciclovía dominical, cuarentena de 2020 (21 feb – 30 jun 2020, según un estudio). |

## Primera mirada a los datos (nov–dic 2023)

- NOₓ medio de 33 ppb, con percentil 95 de 87 ppb: niveles parecidos a la CDMX.
- Ciclo horario con pico de 65 ppb a las 7 h y mínimo de ~17 ppb entre 13 y 15 h. Es el mismo patrón que en la CDMX: la capa de mezcla crece al mediodía y diluye.
- Cociente crudo domingo/hábil (sin descontar el clima): 0.71 por la tarde y 0.73 en el día completo. En la CDMX, el estimador normalizado da 0.65; el cociente de Bogotá es del mismo orden.

## Qué funciona igual y qué no

| Parte del sistema | En Bogotá |
|---|---|
| Ingesta y control de calidad | Igual; solo cambia la fuente (Envista RMCAB) y la zona horaria (UTC−5, sin horario de verano). |
| Transporte con puffs, capa límite y viento de estaciones | Igual. Bogotá también está a ~2,600 m en una cuenca entre montañas. |
| Estimador normalizado con estaciones | Igual. Es la salida principal y no depende del satélite. |
| Inversión por zonas con estaciones | Igual. 15–17 estaciones en un área más compacta (Bogotá urbana ~ 380 km²) dan **mejor densidad** que la CDMX. |
| Zonas administrativas | Natural: grupos de localidades (20 localidades), cada uno con su estación. |
| Mapa de puntos calientes y contraste centro − periferia con satélite | **No**, o muy limitado con TROPOMI. |
| Peso del satélite en la inversión | No aplica. Hay que validar que la inversión con solo estaciones siga pasando los placebos; en la CDMX el satélite tiraba el domingo hacia abajo, así que sin él podría incluso ser más estable. |
| Química por temporada | Distinta: Bogotá no tiene estaciones marcadas de invierno y verano, sino temporadas secas y de lluvia. La radiación es alta todo el año. |

## Esfuerzo estimado

| Paso | Semanas |
|---|---|
| Descarga y control de calidad de RMCAB (2–3 años), METAR, ERA5, OSM, inventario SDA | 1 |
| Configuración de ciudad (dominio, zonas por localidades, zona horaria) y corrida estándar con solo estaciones | 1 |
| Validación: placebos, Día sin carro, cuarentena 2020, CO/NOₓ | 1–2 |
| TROPOMI (opcional) | 1 |
| **Total** | **3–5** |

## Qué aporta frente a la CDMX y Los Ángeles

- **Una versión del método sin satélite geoestacionario.** Es el caso de la mayoría de las ciudades del mundo. Si funciona en Bogotá, el producto se puede llevar a otras ciudades latinoamericanas con red de monitoreo.
- **Experimentos naturales repetidos.** El Día sin carro ocurre cada año, con fecha conocida y una reducción de tráfico grande. Es casi un experimento controlado anual, mejor que las contingencias de la CDMX.
- **Buena densidad de estaciones** con NOₓ, viento y CO en el mismo sitio.
- **Usuarios claros:** la Secretaría Distrital de Ambiente (dueña de la red y del inventario) e IDEAM. Políticas evaluables: Pico y placa, Día sin carro, restricciones de carga y la flota eléctrica de TransMilenio.

**Lo que no aporta:** no ayuda a validar el satélite ni la inversión combinada estaciones + satélite, que es lo central de la propuesta CDMX + LA.

## Recomendación

1. **Ahora no.** Primero estabilizar la versión de dos ciudades (CDMX + LA).
2. **Después, como tercera ciudad** con el papel de "versión solo con estaciones" y de caso latinoamericano replicable. El costo es bajo (3–5 semanas) porque el acceso a datos ya está probado.
3. **Barato desde ya (opcional):** usar el Día sin carro de 2023–2025 como placebo y experimento natural adicional del estimador normalizado, con la muestra de datos y el mismo código. Sería una prueba más del plan de validación, aunque sea en otra ciudad.

## Pendientes de verificar

- Si existen conteos de tráfico de Bogotá posteriores a 2020.
- La resolución espacial del inventario SDA 2023 y si trae NOₓ por localidad.
- Los días útiles de TROPOMI sobre Bogotá por nubosidad.
- La frecuencia de los radiosondeos de El Dorado.

## Fuentes

- RMCAB, portal y reportes: https://rmcab.ambientebogota.gov.co/Report/stationreport
- Inventario de emisiones de Bogotá 2023 (SDA): https://api-aire.ambientebogota.gov.co/documents/10184/397082/INVENTARIO+EMISIONES_2023_w_apnds.pdf
- Día sin carro 2008, informe de la SDA: https://oab.ambientebogota.gov.co/wp-content/uploads/2019/02/2008.pdf
- Cuarentena 2020 con TROPOMI en ciudades latinoamericanas (medRxiv): https://medrxiv.org/content/10.1101/2022.08.08.22277819v1
- Bogotá y Medellín en la cuarentena (Science of the Total Environment, 2020): https://pmc.ncbi.nlm.nih.gov/articles/PMC7418784
- Conteos vehiculares de la Secretaría de Movilidad: https://datosabiertos.bogota.gov.co/en/organization/sdm?tags=aforo
- TEMPO, cobertura de Norteamérica: https://www.earthdata.nasa.gov/sensors/tempo
- Falta de observación geoestacionaria en Sudamérica (NASA NTRS): https://ntrs.nasa.gov/citations/20260003473
- METAR SKBO vía Iowa Environmental Mesonet: https://mesonet.agron.iastate.edu/request/download.phtml
- Muestra descargada: `data/raw/bogota/` (ver `MANIFEST.md`).

## Versión ligera: Día sin carro

**Veredicto.** La prueba es viable y el método funciona como debe, pero **el Día sin carro no baja el NOₓ de forma detectable**: el cambio combinado de 10 jornadas es de +3 % (IC 90 % −8 a +15 %). El método **sí ve la restricción** en el CO, que viene sobre todo de carros a gasolina: −22 a −23 % (IC 90 % −30 a −16 %), muy fuera del ruido del placebo. La lectura más probable es física, no un fallo del método. La medida saca de la calle carros particulares y motos, pero buses, camiones y taxis siguen circulando, y el NOₓ urbano viene sobre todo del diésel. Ese día, además, el transporte público lleva 16–17 % más pasajeros que un día típico (balance de 2023). Para validar el NOₓ, el Día sin carro **no es un buen control positivo**; para el CO, sí.

### Viabilidad

| Requisito | Estado |
|---|---|
| Fechas verificadas | 10 jornadas: primer jueves de febrero de 2015–2020, 2023 y 2024, más las ediciones de septiembre de 2022 y 2023. No hubo jornada en 2021 (pandemia), y la de febrero de 2022 se pasó al 22 de septiembre. Para 2016 la fecha sale de la regla del primer jueves (fuentes abajo). |
| NOₓ, CO y viento horarios de la RMCAB | 🟢 Descargados para las 10 ventanas (`data/raw/bogota/dsc/`, 37 MB, `scripts/bogota_download.py`). Las estaciones con ≥ 70 % de datos son 3–7 entre 2015 y 2020 y 14–16 desde 2022. |
| Capa límite ERA5 | 🟡 Disponible de 2015 a 2023. Para ene–jun 2024, Open-Meteo no la trae y se usó la mediana mes-hora. |
| Referencias | 7–8 jueves no festivos a ±35 días de cada jornada, fuera de las vacaciones de inicio de año y del receso de octubre. |

### Método

Es el mismo estimador que en la CDMX: NOₓ observado ÷ el que predice un modelo con la emisión fija, y luego el cociente entre el evento y sus jueves de referencia (`scripts/bogota_dsc.py`). Sin red vial ni TEMPO de Bogotá, el modelo con emisión fija es una **caja bien mezclada**, C ∝ 1/(U·H), con el viento medio de la RMCAB y la capa límite de ERA5. También se probó una variante **solo con viento**, sin capa límite. Para medir el ruido se usó un placebo con jueves de referencia que hacen de evento falso, en el mismo número de jornadas. Las ventanas son mañana (6–11 h), tarde (12–17 h) y día (6–19 h); la medida rige de 5:00 a 19:30.

### Resultados: 10 jornadas combinadas (media geométrica)

| Variable y normalización | Mañana | Tarde | Día | Placebo del día (90 %) |
|---|---|---|---|---|
| NOₓ, caja (viento × capa límite) | 1.11 (0.93–1.31) | 1.04 (0.84–1.29) | 1.05 (0.90–1.23) | 0.87–1.20 |
| NOₓ, solo viento | 1.05 (0.92–1.20) | 0.90 (0.80–1.02) | 1.03 (0.92–1.15) | 0.87–1.09 |
| NOₓ, crudo | 1.11 (0.90–1.40) | 0.88 (0.72–1.04) | 1.06 (0.89–1.26) | 0.81–1.15 |
| **CO, solo viento** | **0.78 (0.71–0.87)** | **0.80 (0.72–0.89)** | **0.77 (0.70–0.84)** | 0.92–1.09 |
| CO, caja | 0.82 (0.69–0.96) | 0.94 (0.73–1.20) | 0.78 (0.66–0.92) | 0.88–1.23 |

- **NOₓ:** ninguna ventana sale del ruido. Por la tarde hay un indicio de −10 % (p ≈ 0.15), que no es significativo.
- **CO:** baja en 8 de 10 jornadas, y en las 10 combinadas p ≤ 0.002. No baja en 2017 ni 2018, años con solo 3–4 estaciones de CO; las fechas de esos años sí están confirmadas.
- **Placebo:** está centrado en 0.96–1.04 en todas las variantes, así que el método no inventa cambios.

### Lo que esto enseña al proyecto

1. **En Bogotá la capa límite de ERA5 empeora la normalización.** Su placebo es más ancho que el de solo viento (±17 % frente a ±9 % en el día), y produce valores extremos: en febrero de 2023, la tarde da un "clima" de ×0.27 y una emisión de ×2.9. Un punto de ERA5 de ~30 km en los Andes no representa la mezcla de la sabana. Para la versión sin satélite conviene normalizar solo por viento, o con la capa límite de radiosondeos o de un modelo local.
2. **Un experimento natural sirve para validar solo si cambia la fuente del contaminante que se mide.** El Día sin carro cambia la gasolina (CO), no el diésel (NOₓ). Lo mismo aplica al plan de validación de la CDMX: las restricciones que solo afectan a autos particulares deberían moverse más en CO que en NOₓ. Esto refuerza la prueba 3 de `plan_validacion.md` (trazador CO/NOₓ).
3. **Con solo estaciones, la detección es de ~±10 % combinando 10 eventos.** Sirve para cambios moderados repetidos, no para un día aislado: el placebo de un solo evento va de ±30 a ±60 %.

### Expectativa externa

- La SDA reportó para 2023 una baja de 28.6 % en las emisiones vehiculares frente a un día típico. Es una estimación de emisiones, no de concentración de NOₓ, y no está separada por contaminante.
- La cuarentena de 2020, con mucho más tráfico detenido, incluido el de carga, bajó el NO₂ diario 21 % frente a un contrafactual (*Journal of Environmental Economics and Management*, 2022).
- Una revisión internacional encuentra efectos mixtos de los días sin carro sobre el NO₂.
- No encontramos un estudio publicado del NOₓ en los días sin carro de Bogotá.

### Fuentes de esta sección

- Origen y regla del primer jueves de febrero (El Tiempo): https://www.eltiempo.com/historias-el-tiempo/historia-del-dia-sin-carro-y-sin-moto-en-bogota-703627
- 2015, Decreto 38 (restricción del 5 de febrero) y circulares distritales: https://www.alcaldiabogota.gov.co/sisjur/listados/tematica2.jsp?subtema=37216&cadena=
- 2017, 2 de febrero: https://www.eltiempo.com/bogota/primer-dia-sin-carro-en-bogota-del-2017-37673
- 2018, 1 de febrero: https://bogota.gov.co/mi-ciudad/movilidad/recuerda-que-este-jueves-1-de-febrero-es-el-dia-sin-carro-y-sin-moto
- 2019, febrero (IDRD): https://www.idrd.gov.co/noticias/el-dia-sin-carro-2019-servira-para-consolidar-bogota-como-capital-mundial-de-la-bici
- 2020, 6 de febrero: https://bogota.gov.co/mi-ciudad/movilidad/dia-sin-carro-y-sin-moto-en-bogota-2020-asi-lo-vivimos
- 2021, suspendido por COVID-19: https://www.radionacional.co/noticia/dia-sin-carro-moto-bogota-no-se-realizara-aumento-de-casos-covid
- 2022, trasladado al 22 de septiembre: https://bogota.gov.co/mi-ciudad/movilidad/movilidad-cuando-es-el-dia-sin-carro-y-sin-moto-en-bogota-este-2022 y https://www.lafm.com.co/bogota/bogota-otro-dia-sin-carro-y-sin-moto-este-22-de-septiembre
- 2023, 2 de febrero (balance: +16 % de pasajeros y −28.6 % de emisiones vehiculares): https://bogota.gov.co/mi-ciudad/movilidad/positivo-balance-del-dia-sin-carro-y-sin-moto-en-bogota-este-2023
- 2023, 21 de septiembre (registro de decretos de la Alcaldía): https://www.alcaldiabogota.gov.co/sisjur/listados/tematica2.jsp?subtema=37216&cadena=
- 2024, 1 de febrero: https://asosec.co/primera-jornada-2024-dia-sin-carro-y-moto-en-bogota/
- Cuarentena 2020 y NO₂ en Bogotá: https://www.sciencedirect.com/science/article/pii/S0095069622001024
- Revisión de días sin carro (Current Environmental Health Reports, 2022): https://link.springer.com/article/10.1007/s40572-022-00342-y
- Material particulado en días sin carro 2016–2025 (preprint): https://www.researchsquare.com/article/rs-10864736/v1
- Salidas: `data/interim/bogota/dsc_resultados.json` (NOₓ) y `dsc_resultados_co.json` (CO).
