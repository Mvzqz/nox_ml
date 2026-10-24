# Más multifísica: qué agregar, cuánto cuesta y cuánto vale

**Resumen.** Las dos adiciones con más valor por esfuerzo son:
- una **vida química del NOₓ que cambie con la temporada y la hora**;
- una **capa límite de dos capas**: la capa de mezcla y la capa residual nocturna.

Las dos atacan problemas medidos en nuestros resultados y usan datos que ya tenemos o que se descargan gratis.

Una prueba rápida (`multifisica_leighton.md`) mostró que la caída de ~30 % de la columna TEMPO en primavera:
- **no** viene de la partición NO/NO₂ (Leighton);
- **sí** aparece también en superficie;
- y es pérdida de masa de NOₓ, probablemente porque la vida química es más corta.

Lo de menor prioridad:
- resolver el viento nosotros (WRF propio o un modelo de viento por topografía);
- depósito y lavado;
- una PINN acoplada de varios campos.

## Punto de partida

Hoy el modelo tiene tres piezas:
- **Transporte:** advección–difusión 2D, con puffs (estándar) y PINN.
- **Meteorología:** prescrita. El viento sale de las estaciones o de ERA5; la capa límite, de ERA5 corregida con MERRA-2.
- **Química:** mínima. Vida de ~4 h en los puffs (12 h en la PINN) y un cociente NO₂/NOₓ fijo para comparar con TEMPO.

Es transporte de un contaminante con meteorología como dato, o sea una multifísica ligera.

## Prueba rápida: ¿Leighton explica el bajón de primavera de TEMPO?

Tardes de 12 a 17 h, del 15 de febrero al 31 de mayo de 2024. Valores relativos a febrero:

| Mes | NO₂/NOₓ superficie | O₃ | NOₓ superficie | Columna TEMPO en estaciones | Columna / superficie | Capa límite |
|---|---|---|---|---|---|---|
| marzo | 1.03 | 0.99 | 0.75 | 0.62 | 0.90 | 1.11 |
| abril | 1.04 | 1.10 | 0.70 | 0.58 | 0.87 | 1.22 |
| mayo | 1.06 | 1.34 | 0.70 | 0.65 | 0.93 | 1.36 |

- **El cociente NO₂/NOₓ sube un poco.** Con Leighton, TEMPO vería más NO₂, no menos. Descartado como causa.
- **La superficie cae igual que la columna.** El cociente columna/superficie se queda plano, así que no es que el NOₓ se reparta en una capa más alta: falta masa de NOₓ. El modelo con emisión fija no lo reproduce.
- **El j(NO₂) implícito baja 20 %** con la radiación de onda corta constante. Es la desviación clásica del estado fotoestacionario por radicales peróxido: más química oxidante, lo que es coherente con más OH y una vida del NOₓ más corta.

**Implicación práctica.** Hoy no podemos comparar meses de distintas temporadas, ni con TEMPO ni con estaciones. Solo podemos comparar el mismo periodo de dos años o periodos cercanos. Una vida química estacional resolvería justamente eso. Importa porque las contingencias caen en la temporada de ozono, entre febrero y junio.

## Candidatos

| # | Modificación | Física que agrega | Problema que atacaría (reporte) | Complejidad | Valor | Datos |
|---|---|---|---|---|---|---|
| 1 | **Vida química del NOₓ variable** (OH por mes y hora) y partición NO₂/NOₓ con O₃ medido | Oxidación de NOₓ a HNO₃ y fotoequilibrio NO–NO₂–O₃ | Deriva de primavera de ~30 % (`placebo_tempo.md`, esta prueba); comparar entre temporadas; contingencias en temporada de ozono | **Baja–media**: 3–5 días. τ(mes, hora) como parámetro con incertidumbre, o tomado de OH de GEOS-CF | **Alto** | Ya tenemos O₃, NO, NO₂ de SIMAT y onda corta de ERA5. Gratis: OH de GEOS-CF (Earth Engine o NCCS). Disponible: UV-A/UV-B/PAR de SIMAT (conjunto aparte; el servidor no respondió hoy, reintentar) |
| 2 | **Capa límite dinámica de dos capas**: mezcla diurna, capa residual nocturna y arrastre al crecer | Estructura vertical y tiempo | Arrastre de la mañana que los puffs ya mostraron que importa (`puffs_cdmx.md`); error hora a hora; cociente columna/superficie | **Media**: 1–2 semanas en los puffs. En la PINN, semanas más | **Medio–alto** | Capa límite horaria ERA5/MERRA-2 ✅. Radiosondeos IGRA 76679 ✅ (descargados; 00 y 12 UTC, sin mediodía). Ceilómetro o lidar UNAM (RUOA): pedir |
| 3 | **Fondo y frontera de un modelo químico** (GEOS-CF 0.25° o CAMS) | Química completa fuera del dominio y transporte regional | Fondo regional y de TEMPO (`fondo_tempo.md`); NOₓ que entra por los bordes; OH para el punto 1 | **Baja–media**: 2–4 días | **Medio** | GEOS-CF horario desde 2018 (Earth Engine, NCCS; producto de investigación). CAMS requiere cuenta ADS. Resolución gruesa (~25 km) |
| 4 | **Multicontaminante**: HCHO de TEMPO, cocientes CO/NOₓ y SO₂/NOₓ, CO₂ de OCO-3 | Trazadores de sector y de química (HCHO como indicador de COV y OH) | Separar sectores y centrales (`centrales_generacion.md`); régimen de ozono; apoyo al punto 1 | **Media**: 1–2 semanas | **Medio**. Para sectores, bajo: en los gemelos, CO y SO₂ apenas ayudaron (`improvement_tests.md`). Para química, medio | CO y SO₂ de SIMAT ✅. HCHO L2 de TEMPO (V03, V04 provisional; mismas credenciales Earthdata) ✅. OCO-3 SAM sobre CDMX: existen pero pocas pasadas. Red FTIR de UNAM: por colaboración |
| 5 | **Viento diagnóstico con topografía** (masa consistente, tipo WindNinja/CALMET) | Flujos de ladera y canalización en la cuenca | Error de dirección de ~30° (`viento.md`) | **Media**: 1–2 semanas con DEM SRTM | **Bajo–medio**. En LA, mejor viento no mejoró ni con puffs (`otras_ciudades.md`) | DEM SRTM (gratis), estaciones REDMET ✅ |
| 6 | **WRF o LES propio** | Meteorología resuelta: brisas montaña-valle, recirculación, perfil vertical | Lo mismo que 2 y 5 | **Alta**: semanas y cómputo de clúster | **Incierto**. Mejor pedir el campo a SEDEMA o UNAM y usarlo por la capa límite y el viento en altura | ERA5 y GFS como frontera (gratis) |
| 7 | **Depósito seco y lavado por lluvia** | Pérdidas en superficie y con lluvia | Poco: el depósito de NOₓ en pocas horas es pequeño frente a la química; la lluvia cae de junio a octubre, fuera de nuestros periodos | **Baja** | **Bajo** | Precipitación de ERA5 y REDMET ✅ |
| 8 | **PINN multifísica acoplada** (NOₓ, O₃, capa límite en una sola red) | Acoplamiento químico y dinámico dentro de la red | En principio, todo lo anterior | **Alta**: semanas a meses, entrenamiento inestable | **Bajo por ahora**. El entrenamiento conjunto física + datos no mejoró ni con un solo campo (`pinn_prototipo.md`) | Los mismos |

**Los Ángeles.** Los puntos 1–4 aplican igual allá, con mejores datos: HRRR tiene capa límite horaria a 3 km, hay radiosondeos (NKX, VBG) y TEMPO HCHO. La química de primavera y verano en LA es bien conocida, así que sirve como control para el punto 1.

## Recomendación priorizada

1. **Vida química estacional** (3–5 días):
   - meter τ(mes, hora) en los puffs, primero como parámetro estimado por mes con un a priori amplio y después con OH de GEOS-CF;
   - prueba de éxito: que desaparezca la deriva de feb–may en estaciones y TEMPO y que los placebos entre meses de primavera pasen;
   - si funciona, se pueden comparar periodos de distinta temporada.
2. **Capa residual y arrastre en los puffs** (1–2 semanas):
   - las bocanadas de la noche quedan en una capa residual y vuelven a mezclarse al crecer la capa límite;
   - comprobar con los radiosondeos de 00 UTC y la capa límite ERA5;
   - prueba: error hora a hora y estaciones del norte (SAG, XAL).
3. **GEOS-CF como fondo y fuente de OH** (2–4 días, en paralelo con 1).
4. **HCHO de TEMPO** como indicador de OH y del régimen químico (1 semana, después de 1). Útil también para explicar las contingencias de ozono.

No recomendado por ahora:
- WRF propio;
- viento por topografía;
- depósito;
- PINN acoplada.

Conviene reconsiderarlos solo si 1 y 2 funcionan y queda error atribuible a la meteorología.

## Datos a descargar o pedir

| Dato | Estado | Acción |
|---|---|---|
| Radiosondeos IGRA 76679 (AICM) | ✅ `data/raw/igra/` | Usar en el punto 2 |
| Radiación UV-A, UV-B y PAR de SIMAT | El servidor de datos abiertos no respondió hoy | Reintentar; también se puede pedir a SEDEMA |
| OH, NO₂, O₃ de GEOS-CF (replay horario) | Disponible (Earth Engine `NASA/GEOS-CF/v1/rpl/tavg1hr`, NCCS) | Descargar el recorte del dominio para nov 2023–may 2024 |
| HCHO L2 de TEMPO | Disponible con las credenciales de Earthdata | Descargar con el mismo flujo de `tempo_download.py` |
| OCO-3 SAM sobre CDMX | Existen (MERCI-CO₂, Che et al.) | Opcional; pocas pasadas |
| Ceilómetro o lidar de UNAM (RUOA) y red FTIR | No públicos | Agregar a la carta 3 de `solicitudes_datos.md` |

## Fuentes

- [GEOS-CF: preguntas frecuentes (GMAO)](https://gmao.gsfc.nasa.gov/gmao-products/geos-cf/faq_geos-cf/)
- [GEOS-CF replay horario en Earth Engine](https://developers.google.com/earth-engine/datasets/catalog/NASA_GEOS-CF_v1_rpl_tavg1hr)
- [TEMPO HCHO L2 V04 (Earthdata)](https://www.earthdata.nasa.gov/data/catalog/larc-cloud-tempo-hcho-l2-v04) y [V03](https://www.earthdata.nasa.gov/data/catalog/larc-cloud-tempo-hcho-l2-v03)
- [Publicación de TEMPO V04 (ASDC)](https://asdc.larc.nasa.gov/news/tempo-v04-standard-and-near-real-time-v02-level-1-2-and-3-product-release)
- [Che et al.: FTIR y OCO-3 SAM en la CDMX (KIT)](https://publikationen.bibliothek.kit.edu/1000176835/155847033)
- [Gradientes urbanos de XCO₂ con FTIR y OCO-3 en la CDMX (HAL)](https://hal.univ-reims.fr/hal-04573466v1)
- [EGU23-16636: inversión de CO₂ en la CDMX](https://meetingorganizer.copernicus.org/EGU23/EGU23-16636.html)
- [Vidas medias de NOₓ desde satélite en 50 fuentes (ACP 2021)](https://acp.copernicus.org/preprints/acp-2021-273/acp-2021-273.pdf)
- [IGRA v2, NOAA NCEI](https://www.ncei.noaa.gov/data/integrated-global-radiosonde-archive/)
