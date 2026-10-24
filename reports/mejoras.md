# Mejoras al proyecto: otros gases, datos de tráfico y cambios de diseño

Fecha: 2026-10-20. Este documento se apoya en `RESUMEN.md` e `improvement_tests.md`. "Verificado" significa que se abrió la fuente o se descargó una muestra en esta revisión.

## Conclusión

Las tres mejoras con mejor relación impacto/costo son:

1. **Mejorar el transporte, no solo los datos:** agrupar la industria por región, tratar Acolman como chimenea elevada y representar la incertidumbre del viento con un ensamble. Cuesta días y ya mostró mejoras con datos reales.
2. **Usar conteos vehiculares reales (Infovial, abierto) para el perfil horario y semanal del tráfico.** Hoy ese perfil es un supuesto. Además, los conteos sirven de referencia independiente para la baja dominical que infiere el modelo, y esa referencia sugiere que el modelo la **exagera**.
3. **Buscar socios con un modelo de viento de 1 km ya montado para la CDMX** (proyecto MERCI-CO₂: UNAM-ICAyCC y LSCE). Es la mejora de mayor impacto según los gemelos y la que más cuesta hacer solos.

Otros gases (CO, SO₂, CO₂, HCHO) **no ayudan mientras el error de viento sea de ±20°**. Su valor aparece después de mejorar el viento.

## 1. Cambios de diseño, por prioridad

| # | Cambio | Impacto esperado (evidencia) | Costo | Estado |
|---|---|---|---|---|
| 1 | Agrupar los 12 clústeres industriales en un término por región | Alto. Con datos reales, el híbrido pasa de 12.2 a 11.7 ppb y la peor estación (TLA) de 26.7 a 14.3 ppb | Horas | Ya probado (`real_check_linear --no-industry`) |
| 2 | Ensamble de vientos en la PINN (direcciones perturbadas ±10–20°) | Alto. El error de viento domina todos los escenarios; un ensamble da incertidumbre honesta y evita sobreajustar plumas | Días | Por hacer |
| 3 | Acolman como chimenea elevada (altura efectiva de cientos de metros) | Medio. Con datos reales sale en 300 t/año contra 2,615 de a priori, y el modelo a nivel de suelo es la causa más probable | Horas | Por hacer |
| 4 | Perfil horario y semanal medido con Infovial (sección 3) | Medio. Sustituye el perfil supuesto de `puff.py` y valida la baja dominical | Horas | Datos verificados |
| 5 | Viento de 1 km (WRF) con socios | Muy alto. Con ±10°, clústeres 51 → 34 % y fuentes grandes ≈ 10 %; con ±5°, 10 de 12 clústeres < 25 % | Semanas o meses (menos con socios) | Ver tarea 3 |
| 6 | TEMPO sobremuestreado en varios meses (mapa promedio de ~1–2 km) | Medio para fuentes fijas (Acolman, AIFA, industria). Se descargan solo recortes (~120 KB por escaneo) | Días | Ya hay 1,068 recortes |
| 7 | Segundo periodo seco: nov–dic 2024 | Medio, como prueba de robustez y no de precisión. Ya está en los archivos de SIMAT 2024 (viento corregido), TEMPO existe y ERA5 tiene la capa límite de jul–dic 2024. Ojo: ACO sin NOₓ y XAL al 44 % en dic 2024 | Horas | Datos listos |
| 8 | Química NO–NO₂–O₃ (O₃ en 32 estaciones) | Medio. Hoy NO₂ = 0.77 × NOₓ fijo para comparar con TEMPO; la química lo haría variable por hora y zona | Semanas | Extensión del plan |
| 9 | Más meses con el mismo viento | Bajo. El escenario F (2 periodos, ±20°) no mejora: 62 % frente a 51 % | — | Descartado como palanca |

## 2. Otros gases y contaminantes

| Gas | Datos disponibles | Qué aporta para ubicar fuentes de NOₓ | Dificultad | Recomendación |
|---|---|---|---|---|
| **CO** | 29 estaciones SIMAT (verificado, resolución 0.01 ppm, tarde ≈ 0.42 ppm); TROPOMI CO diario, píxel ~5.5 × 7 km ([colección S5P_L2__CO_____HiR](https://cmr.earthdata.nasa.gov/search/collections.json?short_name=S5P_L2__CO_____HiR), verificada en CMR) | Huella de tráfico: CO/NOₓ ≈ 5.6 en vehículos y ≈ 0.6 en industria (inventario 2018) | Baja | Mantener como apoyo. En los gemelos, con viento ±20° no ayuda (51 → 56 %); con ±10° ayuda poco. Útil después de mejorar el viento |
| **SO₂** | 28 estaciones SIMAT (verificado; tarde 3.9 ± 4.1 ppb, en ppb enteros); TROPOMI SO₂ | Huella industrial (SO₂/NOₓ ≈ 0.11 en industria frente a 0.009 en vehículos) | Media-alta: episodios de Tula (refinería y termoeléctrica, fuera del dominio) dominan la varianza | Baja prioridad. Habría que modelar la entrada desde Tula como fuente de frontera |
| **CO₂** | OCO-3 tiene "Snapshot Area Maps" con objetivo Mexico_City_Mexico ([lista de SAMs](https://ocov3.jpl.nasa.gov/sams/), verificado); red FTIR de UNAM (6 EM27/SUN + 1 IFS 125HR) y 20 imágenes OCO-3 entre oct 2020 y may 2021 ([Che et al., EGU23](https://meetingorganizer.copernicus.org/EGU23/EGU23-16636.html)) | La pluma de CO₂ marca la combustión; el cociente NO₂/CO₂ distingue tipos de fuente | Alta: pocas imágenes y unidades muy distintas | **El valor está en el socio, no en el dato.** Ese grupo ya corre WRF a 1 km e inversiones bayesianas a 1 km y 1 h en la CDMX |
| **HCHO** (TEMPO) | Colección TEMPO_HCHO_L2 V03/V04, 8 escaneos la tarde del 15-nov-2023 sobre el dominio (verificado en CMR) | Indica COV y producción de ozono, no fuentes de NOₓ | Media | No para este objetivo |
| **O₃** | 32 estaciones SIMAT; TEMPO O₃ total (verificado en CMR) | Necesario para la química NO–NO₂–O₃ (mejora 8) | Media | Sí, como parte de la extensión química |
| **PM2.5** | 18 estaciones SIMAT | Mayormente secundaria; no ubica fuentes de NOₓ | Alta | No |

## 3. Datos de tráfico

| Fuente | Qué tiene | Resolución | Acceso | Verificado |
|---|---|---|---|---|
| **Infovial (CDMX)** | Conteos vehiculares por clase (C1–C6) y velocidades en 26 vialidades primarias, 341 sensores, ~350 km | Horaria, por tramo y sentido; **solo 2016–2019** | Abierto, CC-BY 4.0 ([dataset](https://datos.cdmx.gob.mx/dataset/informacion-vial-de-apoyo-a-la-gestion-del-transito-infovial)) | ✅ Muestra de ene-2017 en `data/raw/trafico/` |
| Waze for Cities | Congestión y velocidades en tiempo real por tramo | Minutos, toda la red | Convenio CDMX–Waze firmado el 7-feb-2019, gratuito ([Chilango](https://www.chilango.com/noticias/acuerdo-entre-waze-y-gobierno-de-la-cdmx/)); acceso vía SEMOVI | Convenio sí; vigencia no confirmada |
| TomTom | Índice de congestión (2025: 75.9 %, 167 % a las 15 h) ([Traffic Index](https://www.tomtom.com/traffic-index/mexico-city-traffic/)); datos por tramo en productos de pago (Area Analytics) | Horaria por tramo (pago) | Pago | Solo la página pública |
| Encuesta Origen-Destino 2017 (INEGI) | Viajes por distrito, modo y hora | Distrito, día típico | Abierto ([INEGI EOD 2017](https://www.inegi.org.mx/programas/eod/2017/)) | Página sí, datos no descargados |
| Google Environmental Insights Explorer | Emisiones de transporte de CO₂ por ciudad | Anual, ciudad | Web ([EIE](https://insights.sustainability.google/)) | Sitio sí; sin datos por hora ni por zona |
| Uber Movement | Tiempos de viaje | — | **Descontinuado**: movement.uber.com redirige a "movement-decommissioning" | ✅ |
| SCT Datos Viales | Aforos TDPA en carreteras federales | Anual, por estación | No se encontró descarga 2023 | No |
| C5 / SEMOVI (cámaras, aforos propios) | Conteos en intersecciones | Variable | Solicitud o convenio | No buscado a fondo |

### Lo que dicen los conteos de Infovial (ene-2017, 26 vialidades, tarde 12–17 h)

| Clase de vehículo* | Domingo / hábil | Sábado / hábil |
|---|---|---|
| C1 (63 % del tránsito) | 0.93 | 1.01 |
| C2 (25 %) | 0.85 | 0.99 |
| C3 (6 %) | 0.75 | 0.95 |
| C4 | 0.71 | 0.93 |
| C5 | 0.65 | 0.91 |
| C6 | 0.56 | 0.88 |

\* Las clases parecen ordenadas por tamaño del vehículo; no se confirmó la definición.

- El tránsito diario total del domingo es 0.81 del hábil y el de la tarde, 0.88. Como los vehículos pesados emiten mucho más NOₓ por vehículo, la baja de **emisiones** en domingo debería quedar entre ~0.6 y ~0.9 del hábil.
- **El modelo lineal infiere 0.31–0.47**, una baja mayor de la que permite el tránsito medido, aun suponiendo que el NOₓ venga casi todo de pesados. La dirección es correcta, pero la magnitud está sesgada; probablemente el modelo atribuye a las emisiones diferencias de meteorología entre pocos domingos (9). Esto refuerza la mejora 2: más incertidumbre de transporte y no confiar en la magnitud.
- Perfil horario medido en días hábiles, relativo a la media diaria: 0.13 a las 3 h, 1.31 a las 7 h, ~1.3–1.4 de 8 a 18 h, sin el pico matutino marcado que supone `puff.py` (1.6 a las 8 h). Conviene usar este perfil medido.

## Resultados de las pruebas

Se probaron las mejoras baratas con datos reales (nov–dic 2023) y, donde aplica, con un gemelo. Todo parte de la base "industria agrupada + estaciones extra". Scripts: `scripts/improve_real.py` (datos reales) y `scripts/improve_twin.py` (gemelo); la tabla completa está en `improve_real_2023-11-01_2023-12-31.md`.

### Conclusión

| Mejora | Ayuda | Adoptar |
|---|---|---|
| **Representar el error de viento (σθ = 30°)** | **Mucho en el gemelo; algo en datos reales.** Fuentes grandes de 33/38/48 % a 13/26/15 %, vial de 16 % a 8 %. En datos reales el híbrido gana en 18 de 24 estaciones (antes 16). | **Sí**: cuesta un parámetro |
| Viento ponderado (CHO, FAC, ACO, CUA × 0.25) | Casi nada en el promedio | Sí, por consistencia: no cuesta y no empeora |
| Acolman como chimenea de 200 m | **Nada**: la estación más cercana viento abajo está a más de 7 km, donde la pluma ya está mezclada | No por ahora |
| Perfil horario de Infovial (con puffs) | Nada en estaciones; baja la escala vial del 69 al 63 % del inventario | Solo como documentación del supuesto |
| Cociente semanal de Infovial como a priori | No cambia el resultado: el domingo sigue en 0.43–0.51 | No resuelve el sesgo (ver abajo) |

### Datos reales: todas las variantes

| Variante | RMSE LOO modelo / IDW / híbrido (ppb) | Hora a hora modelo / híbrido | Híbrido < IDW | Domingo/hábil (IC 90 %) | Vial / inventario | TEMPO r | Acolman / AICM / AIFA (t/año) |
|---|---|---|---|---|---|---|---|
| S0. Base estacionaria | 13.6 / 11.5 / 11.4 | 11.7 / 9.8 | 16 de 24 | 0.43 (0.34–0.55) | 38 % | 0.74 | 223 / 46 / −11 |
| S1. S0 + a priori semanal | 13.6 / 11.5 / 11.4 | 11.7 / 9.8 | 16 de 24 | 0.45 (0.36–0.55) | 38 % | 0.74 | 223 / 43 / −11 |
| S2. S0 + σθ 30° | 13.4 / 11.5 / **11.2** | 11.6 / 9.7 | **18 de 24** | 0.42 (0.33–0.53) | 41 % | 0.75 | 316 / 123 / −154 |
| S3. S0 + viento ponderado | 13.6 / 11.5 / 11.4 | 11.7 / 9.8 | 16 de 24 | 0.42 (0.33–0.52) | 39 % | 0.74 | 215 / 58 / 26 |
| S4. S0 + Acolman elevada | 13.6 / 11.5 / 11.4 | 11.7 / 9.8 | 16 de 24 | 0.43 (0.34–0.55) | 38 % | 0.74 | 223 / 46 / −11 |
| S5. S2 + S3 + S4 | 13.4 / 11.5 / **11.2** | 11.6 / 9.7 | **18 de 24** | 0.41 (0.32–0.51) | 42 % | 0.75 | 294 / 183 / −141 |
| S6. S5 + a priori semanal | 13.4 / 11.5 / **11.2** | 11.6 / 9.7 | **18 de 24** | 0.43 (0.33–0.53) | 42 % | 0.75 | 297 / 179 / −140 |
| P0. Base no estacionaria (puffs) | 14.4 / 11.5 / 13.3 | 12.6 / 11.5 | 13 de 24 | 0.49 (0.40–0.56) | 69 % | 0.83 | 250 / 224 / −74 |
| P1. P0 + perfil horario Infovial | 14.5 / 11.5 / 13.4 | 12.7 / 11.6 | 13 de 24 | 0.50 (0.41–0.57) | 63 % | 0.83 | 287 / 270 / −83 |
| P2. P1 + σθ 30° + viento ponderado | 13.7 / 11.5 / 12.4 | 12.1 / 10.8 | 15 de 24 | 0.50 (0.40–0.57) | 74 % | 0.83 | 304 / 242 / 52 |
| P3. P2 + a priori semanal | 13.7 / 11.5 / 12.4 | 12.1 / 10.8 | 15 de 24 | 0.51 (0.42–0.58) | 74 % | 0.83 | 302 / 242 / 52 |

IC del domingo: bootstrap de 100 remuestreos de días completos. Acolman tiene un a priori de 2,615 t/año; AICM y AIFA, de 500 t/año.

### Gemelo con viento ±30°

| Modelo (verdad con viento ±30°) | Clústeres: mediana | Clústeres < 25 % | Acolman / AIFA / AICM | Vial por región: mediana (máx) |
|---|---|---|---|---|
| σθ = 15° (actual) | 81 % | 2 de 12 | 33 / 38 / 48 % | 16 % (32 %) |
| σθ = 30° (error representado) | 69 % | 1 de 12 | **13 / 26 / 15 %** | **8 % (20 %)** |

Representar el error de viento no lo elimina, pero evita que el modelo confíe en plumas angostas que en realidad no sabe dónde caen. Con eso, la emisión vial y dos de las tres fuentes grandes vuelven a la meta del 25 % aun con el viento actual. Los clústeres industriales siguen fuera.

### Lo que no se resolvió

> **Corrección (2026-10-21, `sesgo_domingos.md`):** la frase siguiente es incorrecta. Fijar el cociente entre 0.42 y 1.0 casi no cambia el ajuste ni el LOO: el fondo por hora absorbe la diferencia y el 0.42 lo deciden los a priori, no los datos. La referencia de Infovial correcta es el día completo (0.65–0.73), y el estimador normalizado da 0.65 (0.55–0.75).

- **La baja dominical sigue exagerada.** Con el cociente de Infovial como a priori (sábado 0.95 y domingo 0.80 del hábil, ±0.15), el modelo sigue dando 0.43–0.51: los datos lo jalan con fuerza lejos de lo que dicen los conteos. Ninguna corrección física lo movió. Causas posibles, sin probar: (1) diferencias de meteorología entre pocos domingos (9 en el periodo); (2) los pesados, que caen más en domingo (C6: 0.56), pesan en NOₓ más de lo supuesto; (3) los conteos son de 2017 y de 26 vialidades primarias, no de toda la red en 2023. Siguiente paso: repetir con feb–may 2024 (más domingos) y con un perfil de pesados más fuerte.
- **Acolman sale ~220–320 t/año frente a 2,615 a priori en todas las variantes,** y tratarla como chimenea no lo cambia. El bajo valor no es un artefacto de la altura. Conviene revisar el a priori, que reparte el 2 % del inventario por capacidad instalada: la generación real de la planta y sus quemadores pueden ser muy distintos. Una fuente es la generación por central que publica CENACE.
- **AIFA y AICM son inestables** (de −154 a 270 t/año según la variante). No se deben reportar con el viento actual.

### Datos nuevos

- `data/raw/trafico/infovial_201701_clasificacion.csv`: conteos de Infovial por clase de vehículo, enero de 2017, completo (136 MB). Fuente: https://archivo.datos.cdmx.gob.mx/infovial/clasificacion/201701_clasificacion_limpio.csv. De ahí salen el perfil horario y los cocientes semanales usados arriba, ponderados por emisión con pesos supuestos C1…C6 = 1, 2, 5, 10, 15, 20 (sin definición oficial de las clases; se excluyeron el 1 y el 2 de enero). Ponderados así, los cocientes de la tarde son sábado 0.95 y domingo 0.80; sin ponderar, 0.99 y 0.91.

## Fuentes abiertas en esta revisión

- [Infovial, Datos Abiertos CDMX](https://datos.cdmx.gob.mx/dataset/informacion-vial-de-apoyo-a-la-gestion-del-transito-infovial) (API CKAN y CSV de ene-2017)
- [OCO-3 Snapshot Area Maps](https://ocov3.jpl.nasa.gov/sams/)
- [Che et al., EGU23-16636: CO₂ de la CDMX con FTIR y OCO-3](https://meetingorganizer.copernicus.org/EGU23/EGU23-16636.html)
- [Convenio CDMX–Waze (Chilango)](https://www.chilango.com/noticias/acuerdo-entre-waze-y-gobierno-de-la-cdmx/)
- [TomTom Traffic Index, Mexico City](https://www.tomtom.com/traffic-index/mexico-city-traffic/)
- [INEGI, Encuesta Origen-Destino 2017](https://www.inegi.org.mx/programas/eod/2017/)
- [Google Environmental Insights Explorer](https://insights.sustainability.google/)
- NASA CMR: colecciones TEMPO_HCHO_L2, TEMPO_O3TOT_L2, S5P_L2__CO_____HiR, S5P_L2__SO2____HiR y OCO3_L2_Lite_FP (consultadas por API)

Datos guardados: `data/raw/trafico/infovial_201701_clasificacion_muestra.csv` (primeros 2 MB del CSV de ene-2017; el archivo completo de 136 MB se analizó y se descartó). Fuente: https://archivo.datos.cdmx.gob.mx/infovial/clasificacion/201701_clasificacion_limpio.csv


## Pendiente para después: separar el origen de la emisión (tráfico, industria, área)

Registrado el 2026-10-23; no forma parte del resumen ejecutivo.

**Situación actual.** La "emisión de la zona" está dominada por tráfico, pero no es solo tráfico. Se reparte sobre la red de calles con el ciclo del tráfico. La industria no tiene término propio: los 12 clústeres industriales eran inestables y se quitaron de la configuración estándar (`base_sigma30.md`). Lo industrial y las fuentes de área (~7 % del NOₓ) quedan absorbidos en el factor de cada zona y en el fondo. En zonas industriales (Tlalnepantla, Vallejo) el número mezcla ambos orígenes.

**Cómo separarlos, de menor a mayor costo:**
1. **Ciclo temporal.** El tráfico cae fuerte en domingo y tiene picos de hora punta; la industria es más plana. Agregar por zona un término "plano" además del de tráfico y probar con gemelos si se distinguen.
2. **Trazadores con datos que ya tenemos** (`data/interim/simat_tracers.parquet`). CO/NOₓ es alto en vehículos y bajo en industria; el SO₂ viene casi solo de industria y combustibles pesados. Es la prueba 3 de `plan_validacion.md`.
3. **Excesos en el mapa de TEMPO** que la red vial no explica (Vallejo destacó en `puntos_calientes.html`).
4. **Datos por establecimiento:** cédulas de operación anual (COA/LAU) de SEDEMA o monitoreo continuo de chimeneas por convenio.

**Criterio para adoptarlo.** El gemelo recupera la fracción industrial por zona con un error menor a ±25 %, la separación pasa el placebo, y los totales por origen coinciden en proporción con el inventario.
