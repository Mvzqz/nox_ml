# ¿Hay ciudades con mejor información para inferir emisiones de NOₓ?

Fecha: 2026-10-20. Investigación web para la tarea 1. Solo se citan páginas que sí se abrieron (lista al final). Los datos que no se pudieron verificar se marcan como "no verificado".

## Respuesta corta

- **Sí, Los Ángeles es la mejor candidata para validar el método antes de aplicarlo en CDMX.** Tiene el mismo satélite (TEMPO), viento de alta resolución abierto y por hora (HRRR, 3 km, archivo desde 2014), datos de tráfico abiertos de unos 40,000 detectores (PeMS) y un estudio de referencia de inversión de NOₓ con el que comparar (Brioude et al., 2013).
- **En CDMX ya existe un antecedente muy cercano:** Borsdorff et al. (2020), con coautores del ICAyCC-UNAM, invirtieron emisiones de **CO** con TROPOMI y WRF-Chem a 3 km. Encontraron el mismo ciclo de fin de semana que nosotros y la misma limitación principal: **los errores del viento local**. No encontramos un estudio equivalente para NOₓ en CDMX.
- La literatura confirma nuestro diagnóstico. Incluso con modelos de 444 m (Houston), el ajuste a las mediciones de NO₂ es pobre (r² = 0.34) cuando el transporte o el inventario fallan.

## Comparación de ciudades

| Ciudad | Estaciones de referencia | Sensores de bajo costo | Viento de alta resolución abierto | Tráfico abierto | Inventario en malla | Satélite horario |
|---|---|---|---|---|---|---|
| **CDMX** (este proyecto) | 19–27 con NOₓ en nuestro dominio (SIMAT) | No encontrado | No: usamos ERA5 (~25 km) | No | No: solo totales 2018 | TEMPO |
| **Los Ángeles** | No verificado | No verificado | **HRRR 3 km, por hora, desde 2014** | **PeMS: ~40,000 detectores, registro gratuito** | No verificado | TEMPO |
| **Houston** | No verificado | — | HRRR (mismo modelo) | No verificado | No verificado | TEMPO; campaña TRACER-AQ 2021 con Pandora y avión |
| **Londres** | LAQN: más de 120 sitios en 32 municipios | Breathe London (no pude abrir sus reportes; cifra no verificada) | No investigado | **Flujos, velocidades y veh-km por tramo (LAEI 2022)** | **LAEI 2022: NOₓ a 1 km y por tramo vial; concentraciones a 20 m** | No (TEMPO no cubre Europa; solo TROPOMI diario) |
| **París** | Airparif: más de 70 estaciones (nov 2023) | Programa "Challenge Microcapteurs" | **AROME ~1.3 km, licencia abierta** | No investigado | Airparif produce inventario (detalle no verificado) | No (solo TROPOMI) |
| **Zúrich** | No verificado | Piloto de NO₂/O₃ en 6 sitios (Empa); no alcanzó la exactitud de tubos pasivos | No investigado | No investigado | No investigado | No |
| **Seúl** | No verificado | No investigado | No investigado | No investigado | No investigado | **GEMS (satélite geoestacionario asiático)** |
| **São Paulo** | CETESB: 62 automáticas + 22 manuales (jul 2025) | No investigado | No investigado | No investigado | No investigado | No (fuera de TEMPO) |
| **Monterrey** | SIMA: 15 estaciones (propuesta de ampliar a 28–32) | No investigado | No | No | No | TEMPO |
| Guadalajara, Bogotá, Santiago | No encontré un conteo oficial vigente | — | — | — | — | Solo Guadalajara en TEMPO |

Lectura: ninguna ciudad latinoamericana revisada tiene un paquete claramente mejor que CDMX. Las ventajas reales están en EE. UU. (viento HRRR y tráfico PeMS, con TEMPO) y en Londres y París (inventario y tráfico por tramo, viento de 1.3 km, pero sin satélite horario).

## Estudios de inversión top-down relevantes

| Estudio | Ciudad | Datos | Qué lograron | Relevancia para nosotros |
|---|---|---|---|---|
| Borsdorff et al. 2020 (ACP) | **CDMX** | TROPOMI **CO**, nov 2017–ago 2019; WRF-Chem 3 km, dominio de 270 km; inventario INEM por distritos | CDMX ≈ 0.14 Tg/año de CO (la mitad del inventario), zona conurbada ≈ el doble del inventario; el total combinado coincide. Mínimo en fin de semana. Tula y Pachuca muy por encima del inventario | Mismo valle y mismo tipo de problema. Las limitaciones que reportan coinciden con las nuestras: viento local, plumas demasiado angostas, acumulación de varios días |
| Brioude et al. 2013 (ACP) | Los Ángeles | Vuelos CALNEX (2010); modelo lagrangiano con 3 configuraciones de WRF | NOₓ 27–32 % por debajo del NEI 2005, incertidumbre ~15 %; **fin de semana −40 %**; total a 15 % del inventario de CARB, pero la distribución espacial difiere | Valida nuestro hallazgo dominical (−50 a −60 %) en orden de magnitud. Usar varias configuraciones de viento es un "ensamble" barato |
| Goldberg et al. 2019 (EST) | NY, Chicago, Toronto, 2 centrales | TROPOMI NO₂ reprocesado con mejor factor de masa de aire | Centrales a 10 % de lo reportado; NY +22 %, Toronto −21 %; Chicago 45 % más en días hábiles | Las fuentes puntuales grandes son lo más fácil de recuperar (como Acolman). Corregir el sesgo bajo del satélite sobre ciudades es necesario |
| Nawaz et al. 2024 (ACP), TRACER-AQ | Houston | Pandora, avión GCAS, TROPOMI; WRF–CAMx a 444 m | TROPOMI −18 a −23 % frente a Pandora; el modelo correlaciona mal con Pandora (r² = 0.34, −21 %) | Ni a 444 m el modelo reproduce bien el NO₂ urbano. Un Pandora en tierra es clave para calibrar el satélite |
| Estudios con GEMS (Asia) | Seúl, Beijing, Bangkok, etc. | NO₂ horario de GEMS + WRF-Chem | Picos de emisión a distintas horas por ciudad; las emisiones ajustadas con datos horarios dan las mejores simulaciones | Es el análogo asiático de TEMPO: confirma que el dato horario sirve para el ciclo diario |
| Chuprov et al. 2025 (arXiv) | Dominio de 20 km, datos de H₂S | PINN para el problema inverso de advección-difusión, viento conocido | Ubica una fuente; con dos fuentes y difusión baja empeora; sensible a hiperparámetros; inestabilidad de entrenamiento | Es la referencia PINN más cercana, pero supone viento conocido y solo estima ubicación. Nuestro problema, con muchas fuentes, intensidades y viento incierto, es más difícil |

No encontré una inversión de NOₓ urbana con TEMPO específica para Los Ángeles, ni una inversión de NOₓ para CDMX con OMI o TROPOMI. Un estudio nacional de EE. UU. con TEMPO y TROPOMI (Hsu et al., 2025) apareció en la búsqueda, pero su página no abrió (error 502), así que no se usa.

## Conclusiones prácticas

### a) ¿Validar primero en otra ciudad?

**Sí, en Los Ángeles, como prueba en paralelo de unas 2–3 semanas.** Razones:

1. **Mismo satélite (TEMPO)**: el pipeline actual (recortes, control de calidad, cobertura) se reutiliza sin cambios.
2. **Viento HRRR de 3 km por hora, abierto**: permite probar con datos reales la hipótesis central de nuestras pruebas, que un viento mejor reduce el error a la mitad o más. En CDMX eso requiere correr WRF nosotros.
3. **Tráfico real (PeMS)**: permite medir cuánto mejora el proxy vial frente a "longitud de vía por clase".
4. **Referencias publicadas** (Brioude 2013, inventario CARB) para comparar resultados.

Advertencias: HRRR cubre el territorio continental de EE. UU., no México (conocimiento general; la página de AWS no lo especifica), así que no se puede reutilizar para CDMX. El conteo de estaciones de NOₓ de South Coast AQMD y el inventario en malla de CARB no se verificaron.

Londres o París tienen mejor inventario y tráfico, pero sin satélite horario. Servirían para probar la parte de estaciones, no la combinación estaciones + TEMPO que es el núcleo del proyecto.

### b) Qué replicar en CDMX

| Práctica | De dónde | Cómo aplicarla aquí |
|---|---|---|
| WRF a 3 km sobre el valle | Borsdorff 2020 (ICAyCC-UNAM) | **Colaborar con el ICAyCC**, que ya corre esta configuración. Es la vía más corta hacia el "mejor viento" |
| Inversión de CO con TROPOMI como verificación independiente | Borsdorff 2020 | Repetir su método para 2023–2024 y comparar el ciclo semanal y el reparto entre CDMX y la zona conurbada con nuestro resultado de NOₓ |
| Ensamble de configuraciones de viento | Brioude 2013 | Correr la inversión con 3–5 campos de viento distintos y usar la dispersión como incertidumbre |
| Inventario en malla y por tramo vial | LAEI (Londres) | Pedir a SEDEMA la distribución espacial del inventario y aforos por vialidad |
| Pandora para calibrar el satélite | TRACER-AQ (Houston) | Usar el Pandora de la UNAM para corregir el sesgo de TEMPO, típicamente de −10 a −20 % en ciudades |
| Red densa de sensores de bajo costo | Breathe London, Zúrich | Con cautela: en Zúrich los sensores de NO₂ no alcanzaron la exactitud de tubos pasivos. Para mapas promedio, tubos pasivos; para series horarias, sensores calibrados junto a estaciones SIMAT |
| Validar con fuentes conocidas | Goldberg 2019 | Comparar Acolman con las emisiones reportadas por CFE, si se consiguen |

## Estimación cuantitativa: Los Ángeles

Fecha: 2026-10-21. Corrimos el mismo método en Los Ángeles con datos reales del mismo periodo que la CDMX (nov–dic 2023, tarde de 12 a 17 h). El dominio es de 55 × 55 km (33.80–34.30 °N, 118.55–117.95 °O; ~3,080 km², frente a 3,260 km² en la CDMX). Scripts: `scripts/la_*.py`; datos en `data/raw/la/` (con su `MANIFEST.md`); resultados en `data/interim/la/`.

### Respuesta corta

- **El viento de LA es mucho mejor.** El error de dirección medido es de **17°** (interpolando estaciones o con el modelo HRRR de 3 km), frente a **28–32°** en la CDMX. Esa es la diferencia que importa.
- **Las estaciones de LA no son mejores.** Hay **9** estaciones de NOₓ en el dominio, separadas 14 km entre sí, contra unas 20 en la CDMX separadas 6 km.
- **Con el viento de cada ciudad, LA recupera la emisión vial por región con la mitad del error:** 9 % frente a 19 % de mediana con TEMPO, y 13 % frente a 60 % en la peor región.
- **Con el mismo error de viento, las dos ciudades rinden parecido.** La ventaja de LA viene del viento, no de los datos de contaminación. Esto confirma con datos reales lo que decían los gemelos de la CDMX.
- **La industria individual tampoco se recupera en LA** (0–2 de 12 fuentes por debajo de 25 %). LA no sirve para validar la escala de fábrica.

### Viento: error medido con el mismo método

Cada estación de viento se predice con las demás (`la_wind.py`, que replica `wind_loo.py`), en la tarde y con viento observado ≥ 1 m/s. LA usa 20 estaciones: 11 aeropuertos ASOS (sin Mount Wilson, que está en la cima de una montaña) y 9 sitios de monitoreo de EPA. La CDMX usa 22.

| Método | Los Ángeles: mediana (p75) | CDMX: mediana (p75) |
|---|---|---|
| Vector medio de las demás estaciones (lo que usa el modelo lineal) | 30° (56°) | 32° (66°) |
| Interpolación IDW de las demás estaciones | **17° (32°)** | 28° (59°) |
| Modelo HRRR de 3 km en la estación | **17° (31°)**, 4,480 horas-estación | — (no existe para México) |
| ERA5 (reanálisis global) | — | 55° |

- En ambas ciudades, un solo viento para todo el dominio es malo (~30°). La diferencia está en lo que se gana al resolver el viento en el espacio: en LA se baja a 17°; en la CDMX la interpolación solo llega a 28°, porque la cuenca y las montañas cortan el flujo.
- HRRR iguala a la interpolación en las estaciones, y además da el viento en todo el dominio, incluso donde no hay estaciones. Es lo que buscaríamos con un WRF de 1–3 km en la CDMX.
- Verificamos que el viento de HRRR estuviera bien rotado de su malla Lambert al norte verdadero: el sesgo medio de dirección baja de 19° sin rotar a 6° rotado.

### Datos de contaminación

| | Los Ángeles | CDMX |
|---|---|---|
| Estaciones de NOₓ en el dominio | 9 (EPA AQS), completitud de tarde 96–100 % | 19–20 válidas por mes |
| Distancia a la estación vecina (mediana) | 14.3 km | 5.7 km |
| NOₓ de tarde, promedio | 16.9 ppb | 31.2 ppb |
| Cociente NO₂/NOₓ de tarde | 0.80 | 0.77 |
| Altura de la capa de mezcla de tarde (ERA5, mediana) | 580 m (capa marina) | 1,300 m |
| TEMPO: píxeles válidos de tarde | 48,246 en 57 días | 78,227 en 61 días |
| TEMPO vs estaciones: pares hora-estación / por escaneo | r = 0.67 / 0.60 | r = 0.77 / 0.70 |

LA tiene menos estaciones y TEMPO concuerda algo peor con ellas. Su capa de mezcla es la mitad de profunda, así que la misma emisión produce más concentración cerca del suelo. Eso ayuda un poco a la señal.

### Gemelo comparativo

Usamos el mismo código y los mismos supuestos en las dos ciudades (`la_twin.py`, que reutiliza `feasibility_linear.py` e `improvement_tests.py`): pluma estacionaria, errores de observación ×2, 50 gemelos y verdad generada con viento perturbado.

| Ciudad | Observaciones | Error de viento (σ) | Vial por región: mediana (máx) | Aeropuertos | Centrales | Industria | Industria < 25 % |
|---|---|---|---|---|---|---|---|
| Los Ángeles | solo estaciones | ±30° | 25 % (51 %) | 64 % | 32 % | 64 % | 0 de 12 |
| Los Ángeles | solo estaciones | ±20° | 13 % (37 %) | 72 % | 36 % | 46 % | 1 de 12 |
| Los Ángeles | solo estaciones | ±10° | 8 % (25 %) | 56 % | 31 % | 40 % | 1 de 12 |
| Los Ángeles | estaciones + TEMPO | ±30° | 13 % (21 %) | 37 % | 55 % | 47 % | 0 de 12 |
| **Los Ángeles** | **estaciones + TEMPO** | **±20° (≈ su error real)** | **9 % (13 %)** | **31 %** | **40 %** | **37 %** | **2 de 12** |
| Los Ángeles | estaciones + TEMPO | ±10° | 4 % (8 %) | 10 % | 36 % | 32 % | 1 de 12 |
| CDMX | solo estaciones | ±30° | 18 % (55 %) | 122 % | 50 % | 75 % | 1 de 12 |
| CDMX | solo estaciones | ±20° | 10 % (30 %) | 87 % | 37 % | 70 % | 1 de 12 |
| CDMX | solo estaciones | ±10° | 4 % (16 %) | 62 % | 29 % | 38 % | 2 de 12 |
| **CDMX** | **estaciones + TEMPO** | **±30° (≈ su error real)** | **19 % (60 %)** | **45 %** | **127 %** | **163 %** | **1 de 12** |
| CDMX | estaciones + TEMPO | ±20° | 13 % (40 %) | 25 % | 73 % | 115 % | 2 de 12 |
| CDMX | estaciones + TEMPO | ±10° | 4 % (14 %) | 8 % | 23 % | 47 % | 2 de 12 |

Cómo leerla:
- **Cada ciudad con su viento real** (filas en negritas): LA tiene un error vial de 9 % (máximo 13 %) y la CDMX de 19 % (máximo 60 %). Los aeropuertos quedan en 31 % frente a 45 %.
- **Con el mismo viento** (compara filas con igual σ): las ciudades quedan cerca. Con ±10° y TEMPO, ambas dan 4 % en lo vial. La ventaja de LA es el viento, no su red de estaciones.
- **TEMPO ayuda más en LA**, donde las estaciones están más separadas: con ±30°, el error vial máximo baja de 51 % a 21 %.
- **La industria individual no se recupera en ninguna** de las dos ciudades con el modelo actual.

Precisión del propio gemelo: entre dos corridas con distinta semilla, los valores de la CDMX cambiaron hasta unos 5 puntos en lo vial y bastante más en industria y centrales. Diferencias menores no son significativas.

### Supuestos para LA (documentados en `la_twin.py`)

- **Emisión vial a priori:** no usamos un inventario. La calibramos para que la contribución vial modelada en las estaciones sea el 80 % del NOₓ medido sobre un fondo de 5 ppb, lo que da 38,500 t/año en el dominio (CDMX: 99,300 t/año del inventario).
- **Centrales:** las 11 de GPPD de 100 MW o más (gas), con el 2 % del total repartido por capacidad: 21–167 t/año cada una. No son comparables con Acolman (2,615 t/año a priori).
- **Aeropuertos:** LAX, BUR y LGB, 500 t/año cada uno, igual que en la CDMX.
- **"Industria":** los 12 polígonos `landuse=industrial` más grandes de OSM, 150 t/año cada uno. Es un sustituto geográfico de los clústeres DENUE de la CDMX, no un inventario.
- **Datos faltantes:** 10 de 305 escaneos de TEMPO y 31 de 366 horas de HRRR fallaron al descargar. Se excluyeron 2 horas sin capa límite ERA5 (el hueco de Open-Meteo a inicios de 2024).
- **Hora local:** se usó UTC−8 todo el periodo, aunque del 1 al 4 de noviembre regía el horario de verano (UTC−7).

### Conclusiones

1. **¿Cuánto mejor en LA?** Con su viento real, alrededor de la **mitad del error** en emisión vial por región (9 % frente a 19 %) y una peor región mucho más acotada (13 % frente a 60 %). Las fuentes puntuales siguen fuera de la meta del 25 %, y la industria individual no se resuelve. La mejora viene **del viento**.
2. **¿Vale la pena LA como validación antes de invertir en WRF para la CDMX?** **Sí, como prueba barata con datos reales de la hipótesis "mejor viento → mejor inversión"**, que hasta ahora solo probamos con gemelos. Ya tenemos casi todo descargado (AQS, TEMPO, viento ASOS y HRRR en estaciones, OSM). Falta bajar el campo HRRR completo sobre el dominio para el transporte y comparar en datos reales tres vientos (vector medio, IDW y HRRR) con las mismas métricas de la CDMX: LOO, el ciclo semanal frente a PeMS y TEMPO. Estimamos 1–2 semanas. **No sirve** para validar fuentes industriales individuales, porque tampoco se resuelven en LA.
3. **Qué se traslada a la CDMX:**
   - El **objetivo de calidad del viento**: un modelo de 1–3 km debería acercarse a la interpolación en las estaciones (~17–20°) y cubrir lo que hay entre ellas. Es la meta realista para el WRF de SEDEMA o del ICAyCC, y se valida con el mismo `wind_loo.py`.
   - El **procedimiento** completo, ya probado aquí: recortar TEMPO, rotar el viento del modelo a norte verdadero, validar por estaciones retenidas y correr el gemelo con el error de viento medido.
   - **La densidad de estaciones de la CDMX no es el cuello de botella**: LA rinde parecido con menos de la mitad de estaciones cuando el viento es igual.

## Prueba con datos reales: ¿un mejor viento mejora la inversión?

Fecha: 2026-10-22. Scripts: `scripts/la_real.py` (inversión y métricas), `scripts/la_hrrr_field.py` (campo HRRR), `scripts/la_tempo_retry.py`. Resultados por variante en `data/interim/la/la_real_*.json`.

### Respuesta corta

**No.** En Los Ángeles, con datos reales, cambiar el viento uniforme (error de dirección de 30°) por el campo HRRR o la interpolación de estaciones (16–17°) **no mejora ninguna métrica de la inversión**: el error en estaciones ocultas sube un poco (13.6 → 14.1 ppb), la concordancia con TEMPO baja, y el ciclo semanal no se vuelve más estable. El viento mejor sí está bien medido; lo que no mejora es el resultado. **La hipótesis "mejor viento → mejor inversión", que salía de los gemelos, no se confirma con datos reales en LA.**

### Qué corrimos

- **Mismo método que la CDMX:** inversión lineal de `real_check_linear.py` con σθ = 30°, fondo por hora para estaciones y TEMPO, emisión vial 3×3 × tipo de día y fuentes grandes (aeropuertos LAX, BUR y LGB; 11 centrales de gas ≥ 100 MW). Sin "industria", como en la opción B. Los puertos de LA y Long Beach quedan fuera del dominio (al sur de 33.80 °N).
- **Cuatro vientos sobre las mismas 363 horas** (nov–dic 2023, tarde 12–17 h, ≥ 8 estaciones de viento por hora):
  1. *domain*: el vector medio de las 20 estaciones para todo el dominio (lo que usa la CDMX).
  2. *idw*: interpolación de las estaciones en malla de 1 km.
  3. *hrrr*: campo HRRR de 3 km, promedio de los análisis h y h+1, en la misma malla de 1 km.
  4. *hrrr_pbl*: HRRR con su propia capa límite en lugar de la de ERA5 en un punto.
- **Datos nuevos:** se bajó el campo HRRR completo (U/V a 10 m y capa límite, 427 de 427 análisis, `data/raw/la/hrrr_field/`) y se recuperaron los 10 escaneos de TEMPO que habían fallado.
- **Hora local:** se trabajó en UTC y la tarde se definió en hora civil de Los Ángeles (PDT = UTC−7 hasta el 5 de noviembre, después PST = UTC−8). Antes se usaba UTC−8 todo el periodo.
- **Festivos tratados como domingo:** Acción de Gracias (23 nov) y Navidad.
- **Mismas métricas en la CDMX:** se volvieron a calcular con el mismo código (`--city cdmx`) para comparar. Reproducen lo ya reportado (por ejemplo, domingo normalizado 0.65).

**Control del viento.** El campo HRRR usado es correcto: en las estaciones, el error mediano de dirección es 16° (p75 30°), contra 17° de la interpolación sin la estación y 30° del vector medio. En los sitios de EPA, que HRRR no asimila, también da 15°.

### Resultados

| Métrica | LA *domain* (30°) | LA *idw* (17°) | LA *hrrr* (16°) | LA *hrrr_pbl* | CDMX *domain* | CDMX *field* |
|---|---|---|---|---|---|---|
| **Estaciones ocultas (LOO), RMSE modelo** | **13.6** | 13.8 | 14.1 | 14.0 | 13.4 | 13.7 |
| LOO, RMSE IDW de NOₓ | 16.4 | 16.4 | 16.4 | 16.4 | 11.6 | 11.6 |
| LOO, RMSE híbrido | 16.2 | 16.4 | 16.7 | 16.5 | 11.5 | 11.6 |
| LOO modelo: sesgo / hora a hora | 8.2 / 10.8 | 8.6 / 10.7 | 8.5 / 11.2 | 8.9 / 10.9 | 6.6 / 11.7 | 6.8 / 11.8 |
| Híbrido gana a IDW | 6 de 9 | 5 de 9 | 2 de 9 | 3 de 9 | 16 de 24 | 14 de 24 |
| Ajuste en muestra, r estaciones / TEMPO | 0.66 / 0.71 | 0.65 / 0.69 | 0.63 / 0.70 | 0.63 / 0.70 | 0.78 / 0.75 | 0.77 / 0.75 |
| **Modelo con emisión fija frente a TEMPO, r (global / mediana por hora)** | **0.24 / 0.36** | 0.15 / 0.20 | 0.14 / 0.24 | 0.14 / 0.24 | 0.50 / 0.68 | 0.50 / 0.65 |
| Modelo con emisión fija frente a estaciones, r (estación-hora / patrón espacial) | 0.36 / 0.24 | 0.31 / 0.16 | 0.31 / 0.18 | 0.33 / 0.18 | 0.38 / 0.33 | 0.37 / 0.28 |
| Inversión completa: vial de días hábiles (a priori 40,300 t/año en LA; 99,300 en la CDMX) | 8,200 | 4,700 | −1,000 | −1,200 | 40,500 | 34,700 |
| Inversión completa: domingo / hábil (IC 90 %) | −0.14 (−0.73–0.51) | −0.35 (−2.3–0.22) | sin sentido | sin sentido | 0.41 (0.30–0.53) | 0.30 (0.22–0.43) |
| **Estimador normalizado: domingo / hábil (IC 90 %)** | 0.52 (0.45–0.59) | 0.52 (0.45–0.59) | 0.51 (0.44–0.58) | 0.47 (0.42–0.53) | 0.65 (0.56–0.76) | 0.66 (0.56–0.77) |
| Estimador normalizado: sábado / hábil | 0.63 | 0.61 | 0.59 | 0.64 | 0.90 | 0.90 |
| **Placebo (hábiles falsos como "domingos"): rango 5–95 %** | 0.85–1.19 (±0.17) | 0.85–1.18 (±0.17) | 0.83–1.21 (±0.19) | 0.87–1.17 (±0.15) | 0.77–1.27 (±0.25) | 0.77–1.26 (±0.25) |
| Variación día a día en hábiles (CV): normalizado / crudo | 0.33 / 0.35 | 0.31 / 0.35 | 0.34 / 0.35 | 0.29 / 0.35 | 0.34 / 0.33 | 0.30 / 0.33 |

RMSE en ppb. LA tiene 9 estaciones de NOₓ y 10 domingos/festivos; la CDMX, 24 estaciones y 11.

### Cómo leerla

- **El mejor viento no ayuda en ninguna métrica.**
  - El error en estaciones ocultas empeora un poco (13.6 → 14.1 ppb).
  - La concordancia del modelo con TEMPO, antes de invertir, baja de 0.24 a 0.14.
  - El estimador normalizado apenas se mueve: domingo 0.47–0.52 y placebo de ±0.15 a ±0.19 en todas las variantes.
  - La única mejora pequeña viene de la capa límite de HRRR, no del viento: el placebo pasa de ±0.17 a ±0.15 y la variación día a día de 0.33 a 0.29.
- **Por qué, probablemente.** El viento ya no es lo que más limita. El modelo es una pluma estacionaria de una hora. En LA la contaminación se acumula de un día a otro, la brisa marina la recircula y la capa marina es baja (~580 m), y nada de eso entra en el modelo. Además, la emisión a priori se reparte por la clase de vía de OSM, no por el tráfico real. Un viento más detallado concentra las plumas en lugares más precisos, pero si la emisión a priori está mal ubicada, esa precisión no ayuda o incluso estorba. Esto concuerda con la CDMX, donde el campo IDW tampoco mejoró al viento uniforme.
- **La inversión completa no funciona en LA.** Con 9 estaciones, los fondos por hora absorben casi toda la señal, y la emisión vial de días hábiles cae a 8,200 t/año o hasta valores negativos. Ahí los cocientes por tipo de día no tienen sentido. Esto refuerza lo que ya aprendimos en la CDMX: los cambios relativos se reportan con el estimador normalizado, no con la inversión completa.
- **El estimador normalizado sí funciona en LA, y mejor que en la CDMX.** El placebo da ±0.17 contra ±0.25 de la CDMX, con cualquier viento. Para el domingo da 0.47–0.52 de un día hábil y para el sábado 0.59–0.64. Como referencia (sin PeMS, porque no hay cuenta):
  - el inventario de CalNex 2010 da para el fin de semana en conjunto ~0.66 de un día hábil (410 contra 620 t/día de NOₓ en la cuenca), por menos camiones diésel ([Kim et al. 2016](https://escholarship.org/uc/item/0z89x2db));
  - TROPOMI da en promedio para EE. UU. un NO₂ 24 % menor en domingo ([Goldberg et al. 2021](https://pmc.ncbi.nlm.nih.gov/articles/PMC8047911)).

  Nuestro sábado (~0.62) queda por debajo de esa referencia de fin de semana, y es posible que el periodo festivo de noviembre–diciembre acentúe la baja. La dirección es correcta y el orden de magnitud plausible, pero no hay una referencia de tráfico medido para LA que permita validar el tamaño.
- **Donde hay pocas estaciones, el modelo sí aporta.** En LA, con estaciones a 14 km entre sí, el modelo predice mejor una estación oculta que la interpolación (13.6 contra 16.4 ppb). En la CDMX, con estaciones a 6 km, pasa al revés.

### Qué implica para pedir el WRF de la CDMX

1. **Un WRF por sí solo no basta para mejorar la inversión.** En LA un viento con la mitad del error (HRRR, que es esencialmente un WRF de 3 km operativo) no mejoró nada con datos reales. Los gemelos sobreestimaban el beneficio del viento porque suponen que el modelo de transporte y la emisión a priori son correctos.
2. **Lo que hay que pedir es el paquete completo.** Un WRF sirve si va con:
   - transporte dependiente del tiempo, con acumulación de varias horas y días y recirculación (puffs o lagrangiano, o una PINN dependiente del tiempo);
   - la capa límite del propio modelo;
   - una distribución espacial de la emisión basada en tráfico (aforos, Infovial) y no solo en la clase de vía.

   En la solicitud a SEDEMA y UNAM conviene pedir también los campos 3D y horarios (viento a varias alturas y capa límite), no solo el viento a 10 m.
3. **Antes de invertir en un WRF propio, una prueba barata:** repetir esta comparación en LA con transporte de puffs (`puff.py` con el campo HRRR) y con una emisión ponderada por tráfico (aforos de Caltrans o PeMS). Si con transporte dependiente del tiempo el viento de HRRR sí mejora las métricas, el WRF vale la pena para la CDMX. Si no, el cuello de botella está en el modelo de transporte y en la emisión a priori.
4. **El estimador normalizado, la salida principal, no depende de un mejor viento.** Rindió igual con los cuatro vientos en LA y con los dos en la CDMX. El POC de la opción B puede seguir sin WRF.

### Limitaciones

- **Una sola ciudad y un periodo de dos meses** con temporada festiva. Hay 9 estaciones de NOₓ, solo 10 domingos y no hay datos de tráfico (sin PeMS).
- **La emisión a priori de LA está calibrada, no inventariada:** el 80 % del NOₓ medido sobre un fondo de 5 ppb, repartido por clase de vía. Los aeropuertos y las centrales llevan los mismos supuestos que en la CDMX. Por eso las fuentes puntuales no son comparables; por ejemplo, Scattergood sale en ~950 t/año contra un a priori de 175.
- **Se probó solo la pluma estacionaria.** El modelo de puffs con el campo HRRR se probó después: ver la subsección siguiente.

### Puffs + HRRR

Fecha: 2026-10-22. Script: `scripts/la_puff.py` (y `scripts/la_hrrr_morning.py` para el viento de la mañana). Resultados en `data/interim/la/la_real_la_puff_*.json`.

**Pregunta.** La pluma estacionaria no mejoró con mejor viento. ¿Mejora si además el transporte es dependiente del tiempo, es decir, si la contaminación de las horas previas viaja con el viento real de esas horas?

**Respuesta corta. El transporte dependiente del tiempo sí mejora casi todo; el viento HRRR, dentro de ese transporte, no agrega nada.** Con puffs, la concordancia del modelo con TEMPO se duplica, la inversión completa deja de dar emisiones negativas y el estimador normalizado se vuelve más preciso. Pero puffs con el vector medio de las estaciones rinden igual o un poco mejor que puffs con el campo HRRR.

**Qué corrimos.**
- **Transporte:** el de `puff.py`, el mismo que en la CDMX: la pluma de la hora actual más sub-puffs cada 15 min de las 6 horas previas, con perfil horario de tráfico y decaimiento químico (vida de 4 h).
- **Trayectorias con campo de viento:** en los modos con campo, cada sub-puff sigue su propia trayectoria por el campo (pasos de ≤ 15 min, interpolado en el tiempo). La pluma de la hora actual usa el viento por par fuente–receptor.
- **Viento de la mañana:** para las trayectorias se bajaron también los análisis HRRR de 05 a 11 h local (425 de 427; a dos horas del 6 de diciembre les falta la capa límite y se usa el análisis más cercano).
- **Configuración fija:** las mismas 363 horas que `la_real.py`, σθ = 30°, σ de estaciones 15 ppb y **peso de TEMPO fijo en σ = 5e15 molec/cm²** (el de `la_real.py`, para que la comparación sea directa).
- **Perfil horario de tráfico:** el supuesto urbano típico de `puff.PROFILE` (picos de 7–9 h y 16–18 h). No es un perfil medido de LA, porque no hay PeMS. La variante *flat* quita el perfil para medir cuánto importa.

| Métrica | Pluma *domain* | Pluma *hrrr* | **Puffs *domain*** | Puffs *idw* | **Puffs *hrrr*** | Puffs *hrrr*, sin perfil |
|---|---|---|---|---|---|---|
| LOO, RMSE modelo (ppb) | 13.6 | 14.1 | **13.3** | 13.3 | 13.5 | 13.4 |
| LOO modelo: sesgo / hora a hora | 8.2 / 10.8 | 8.5 / 11.2 | 8.4 / 10.4 | 8.5 / 10.2 | 8.6 / 10.5 | 8.5 / 10.4 |
| LOO híbrido (IDW 16.4) | 16.2 | 16.7 | 16.1 | 16.1 | 16.3 | 16.2 |
| **Modelo con emisión fija frente a TEMPO, r (global / mediana por hora)** | 0.24 / 0.36 | 0.14 / 0.24 | **0.49 / 0.55** | 0.41 / 0.49 | 0.47 / 0.55 | 0.47 / 0.55 |
| Modelo con emisión fija frente a estaciones, r (estación-hora / patrón espacial) | 0.36 / 0.24 | 0.31 / 0.18 | 0.40 / 0.29 | 0.37 / 0.24 | 0.39 / 0.29 | 0.39 / 0.29 |
| Ajuste en muestra, r estaciones / TEMPO | 0.66 / 0.71 | 0.63 / 0.70 | 0.67 / 0.77 | 0.68 / 0.76 | 0.66 / 0.77 | 0.66 / 0.77 |
| **Inversión completa: vial de días hábiles (a priori 40,300 t/año)** | 8,200 | −1,000 | **36,000** | 28,800 | 34,100 | 42,700 |
| Inversión completa: domingo / hábil (IC 90 %) | −0.14 (sin sentido) | sin sentido | **0.43 (0.33–0.55)** | 0.35 (0.25–0.51) | 0.41 (0.30–0.57) | 0.41 (0.30–0.60) |
| Estimador normalizado: domingo / hábil (IC 90 %) | 0.52 (0.45–0.59) | 0.51 (0.44–0.58) | 0.52 (0.44–0.59) | 0.51 (0.44–0.59) | 0.50 (0.42–0.58) | 0.50 (0.43–0.58) |
| **Placebo (± medio ancho 5–95 %)** | ±0.17 | ±0.19 | **±0.14** | ±0.15 | ±0.16 | ±0.16 |
| Variación día a día en hábiles (CV), normalizado | 0.33 | 0.34 | **0.25** | 0.26 | 0.27 | 0.28 |

Las columnas de pluma son las de la tabla anterior. La IDW de NOₓ no cambia con el transporte (16.4 ppb).

**Cómo leerla.**
- **Lo que limitaba en LA era el transporte estacionario, no el viento.** Con puffs y el mismo viento uniforme:
  - el modelo con emisión fija explica el doble del mapa de TEMPO (r 0.24 → 0.49);
  - la inversión completa recupera una emisión vial física (36,000 contra 8,200 t/año, cerca del a priori) y un domingo con sentido (0.43);
  - el estimador normalizado se vuelve más estable: la variación día a día baja de 0.33 a 0.25 y el placebo de ±0.17 a ±0.14.
- **Mejor viento dentro de los puffs: nada.** Puffs con HRRR quedan igual o ligeramente peor que puffs con el vector medio en todas las métricas, y la IDW de estaciones también. Sobre ~55 km y 6 horas, lo que importa es el viento medio que acumula la contaminación de la mañana, y eso ya lo da el promedio de 20 estaciones.
- **El perfil horario de tráfico no cambia los cocientes.** Sin perfil, los cocientes y el normalizado son iguales; solo cambia la escala absoluta (34,100 → 42,700). Medir un perfil de tráfico de LA (PeMS) no cambiaría esta conclusión.
- **La inversión completa sigue sin servir para el domingo.** Ahora da 0.35–0.43, un poco por debajo del normalizado (0.50–0.52), igual que en la CDMX. El estimador normalizado sigue siendo la salida para cambios relativos.

**Qué implica para pedir el WRF de la CDMX.**
1. **La prioridad es el transporte dependiente del tiempo, que ya tenemos (`puff.py`), no un viento más fino.** En LA, pasar a puffs mejoró las métricas tanto o más que lo que los gemelos atribuían al viento, y un viento de 3 km dentro de los puffs no aportó.
2. **Un WRF de la CDMX se justifica por lo que no es viento a 10 m:** la capa límite horaria y espacial, el viento en altura y la recirculación en la cuenca cerrada (algo que el vector medio no representa y que en la CDMX sí podría pesar más que en LA). Pedir los campos 3D y horarios, no solo U/V a 10 m. Es una hipótesis: LA no la prueba.
3. **Siguiente paso en la CDMX:** usar puffs como transporte estándar en la opción B y en el estimador normalizado. En la CDMX, la prueba anterior con puffs ya subió la concordancia con TEMPO (0.74 → 0.83) pero empeoró las estaciones (14.1 → 15.1). Hay que revisar ese resultado con σθ = 30° y el peso de TEMPO reducido antes de adoptarlo.

## Control positivo: capa de mezcla, EMFAC y configuración estándar

Fecha: 2026-10-23. Scripts: `scripts/la_hrrr_ml.py`, `scripts/la_puff_ml.py`, `scripts/la_zonas.py`, `scripts/la_estandar.py`. Resultados en `data/interim/la/la_real_la_puff_hrrr_ml*.json` y `data/interim/la/la_estandar_*.json`.

**Pregunta.** LA debe servir como control positivo: ahí el método tendría que funcionar mejor que en la CDMX y compararse contra referencias independientes. Probamos tres cosas:
1. si el viento de 10 m explica que HRRR no ayudara;
2. qué dice CARB (EMFAC) y la literatura sobre el fin de semana;
3. cómo rinde LA con la configuración estándar de la CDMX.

### Respuesta corta

- **Viento de la capa de mezcla: ayuda poco, pero en la dirección esperada.** Promediar el viento de HRRR entre 10 m y la capa límite mejora un poco la concordancia con TEMPO frente al viento de 10 m, y es la mejor de todas las variantes en las métricas que no usan la inversión. No mejora el error con estación retenida. El viento de 10 m explica una parte del resultado anterior, no todo.
- **EMFAC no se pudo descargar automáticamente**, y no da perfiles por día de la semana. Como referencia de fin de semana usamos la literatura: **domingo ≈ 0.65–0.70** del hábil (detalle abajo).
- **Configuración estándar en LA: funciona como en la CDMX, pero el control positivo no pasa del todo.** El estimador normalizado da **domingo 0.52 (0.44–0.59)**, por debajo de la referencia (~0.66). En la CDMX, el mismo estimador coincide con Infovial. Es la advertencia más importante de esta sección: o la referencia de LA está desactualizada, o el estimador subestima el cociente dominical.

### 1. Viento de la capa de mezcla

El producto `sfc` de HRRR trae viento a 10 m, 80 m y en 1000, 925 y 850 hPa. Con eso calculamos el viento medio entre 10 m y la capa límite en cada punto y hora: 852 análisis, 852 completos. En nov–dic la capa límite es baja (mediana 370 m, contando la mañana). Por eso el viento de la capa de mezcla difiere poco del de 10 m: la dirección cambia ~13° en mediana y la rapidez, ~10 %.

Misma configuración que `la_puff.py` (puffs, σθ = 30°, peso de TEMPO ×1), para comparar directamente:

| Métrica | Puffs *domain* | Puffs *idw* | Puffs HRRR 10 m | **Puffs HRRR capa de mezcla** | Capa de mezcla, solo dirección |
|---|---|---|---|---|---|
| LOO, RMSE modelo (ppb) | 13.3 | 13.3 | 13.5 | 13.5 | **13.2** |
| LOO híbrido (IDW 16.4) | 16.1 | 16.1 | 16.3 | 16.0 | **15.9** |
| **Emisión fija frente a TEMPO, r (global / mediana por hora)** | 0.49 / 0.55 | 0.41 / 0.49 | 0.47 / 0.55 | **0.55 / 0.58** | 0.51 / 0.57 |
| Emisión fija frente a estaciones, r (estación-hora / patrón espacial) | 0.40 / 0.29 | 0.37 / 0.24 | 0.39 / 0.29 | **0.42 / 0.32** | 0.41 / 0.30 |
| Inversión: vial de días hábiles (a priori 40,300 t/año) | 36,000 | 28,800 | 34,100 | **43,400** | 40,200 |
| Inversión: domingo / hábil | 0.43 | 0.35 | 0.41 | 0.48 | 0.47 |
| Estimador normalizado: domingo / hábil | 0.52 | 0.51 | 0.50 | 0.48 | 0.51 |
| Placebo (± medio ancho) | ±0.14 | ±0.15 | ±0.16 | **±0.14** | ±0.16 |
| Variación día a día en hábiles (CV) | 0.25 | 0.26 | 0.27 | **0.24** | 0.27 |

**Cómo leerla.**
- **El viento de la capa de mezcla es mejor que el de 10 m en todo lo que no depende de la inversión.** Sube la concordancia del modelo con emisión fija frente a TEMPO (0.47 → 0.55) y frente a las estaciones (0.39 → 0.42), y el total vial invertido queda cerca del a priori. Por primera vez, un viento de HRRR supera al vector medio de las estaciones en esas métricas.
- **El efecto es chico** porque en noviembre y diciembre la capa límite es baja y el viento cambia poco con la altura. En verano, o en la CDMX con capas de 2–3 km por la tarde, la diferencia puede ser mayor; no está probado.
- **El error con estación retenida no cambia** (13.2–13.5 ppb en todas). Con 9 estaciones, ese no es el cuello de botella.
- **Implicación para la CDMX:** si se consigue el WRF de SEDEMA, hay que usar el viento promediado en la capa de mezcla, no el de 10 m. Esto refuerza lo de la sección anterior: el valor del WRF está en la estructura vertical.

### 2. CARB/EMFAC y la referencia de fin de semana

- **EMFAC2021 (CARB):** el portal web (`emfac.arb.ca.gov`) entrega emisiones diarias por condado y por clase de vehículo, incluida la fracción de pesados. Pero rechaza las peticiones automatizadas: su firewall respondió "Request Rejected". **Hay que descargarlo a mano:** región Los Angeles (SC) y Orange (SC), año 2023, temporada Winter, NOx por clase de vehículo. Además, **EMFAC no da perfiles por día de la semana ni por hora**, así que no sustituye a PeMS para el ciclo semanal.
- **Referencia de fin de semana, de la literatura:**
  - **Inventario CalNex 2010 (Kim et al. 2016):** NOₓ de la cuenca de ~620 t/d en días hábiles y ~410 t/d en fin de semana (**0.66**). La caída se atribuye sobre todo a menos tráfico de camiones diésel.
  - **Observaciones CalNex 2010 (Pollack et al. 2012):** NOₓ de fin de semana 34 ± 4 % menor en superficie y 46 ± 11 % menor desde avión.
  - **TROPOMI y superficie, años recientes:** el NO₂ del domingo en LA es 30–35 % menor que a mitad de semana, y el cociente domingo/media semanal es 0.68. En EE. UU., sábado y domingo quedan 16 % y 24 % por debajo de los días hábiles (Goldberg et al. 2021).
  - **Lo que usamos como restricción de cociente** (equivalente a Infovial en la CDMX): **domingo 0.67 ± 0.07 y sábado 0.80 ± 0.08**. El sábado sale de aplicar la proporción nacional sábado/domingo a la caída dominical de LA. La incertidumbre es mayor que la de Infovial porque es una referencia de 2010 o de concentraciones, no un conteo de tráfico de 2023. Desde 2010 los camiones son más limpios, así que la caída de fin de semana en emisiones probablemente es hoy **menor**, es decir, un cociente más cercano a 1.

### 3. LA con la configuración estándar

Transporte con puffs y viento del dominio, peso de TEMPO ×1/3, vida química constante de 4 h y zonas administrativas:
- **Vida química:** `vida_quimica.py` está calibrada con O₃, temperatura y humedad de SIMAT y aún no se valida. En LA solo hay un periodo (nov–dic), donde la temporada no cambia.
- **Zonas:** no encontramos una geometría pública de las Source Receptor Areas del South Coast AQMD. Usamos **7 zonas** formadas por grupos de ciudades (límites del Censo 2023), según las subregiones de los consejos de gobierno del condado de LA más el norte de Orange: Westside, Valle de San Fernando, Centro de LA, Valle de San Gabriel, Gateway Cities, South Bay y Puerto, y Norte de Orange. La ciudad de LA se parte entre cuatro de ellas. **Cada zona tiene al menos una estación de NOₓ.**

| Métrica | 3×3, TEMPO ×1 (anterior) | 3×3, TEMPO ×3 | Zonas, TEMPO ×3 | **Zonas, TEMPO ×3, restricción (estándar)** |
|---|---|---|---|---|
| LOO modelo / híbrido (IDW 16.4) | 13.3 / 16.1 | 13.7 / 16.3 | 13.5 / 16.0 | **13.5 / 16.0** |
| Híbrido mejor que IDW | 6 de 9 | 5 de 9 | 6 de 9 | **7 de 9** |
| Ajuste en muestra, r estaciones / TEMPO | 0.67 / 0.77 | 0.70 / 0.76 | 0.72 / 0.75 | 0.72 / 0.75 |
| Vial de días hábiles (a priori 40,300) | 36,000 | 37,700 | 40,200 | 38,500 |
| Inversión: domingo / hábil (IC 90 %) | 0.43 (0.33–0.55) | 0.49 (0.42–0.62) | 0.46 (0.39–0.57) | **0.62 (0.59–0.65)** |
| Inversión: sábado / hábil | 0.61 | 0.61 | 0.56 | 0.71 |
| Estimador normalizado: domingo (IC 90 %) | 0.52 (0.44–0.59) | igual | igual | **0.52 (0.44–0.59)** |
| Placebo / CV de hábiles | ±0.14 / 0.25 | igual | igual | ±0.14 / 0.25 |

El estimador normalizado no depende de las zonas ni del peso de TEMPO, por eso no cambia entre columnas.

**Identificabilidad de las zonas (gemelo).**
- **Correlación posterior entre zonas:** máxima de 0.21 y mediana de 0.12.
- **Error mediano del factor vial de días hábiles:** 2–7 % por zona.
- **Error del total vial:** 3 %.
- **Advertencia:** este gemelo solo tiene ruido de medición, sin errores de transporte ni de distribución de emisiones, así que es optimista; es la lección de la sección anterior. Ninguna zona necesitó fusionarse.

**Resultado por zona** (factor vial de días hábiles respecto al a priori de calles OSM, con restricción):

| Zona | Factor vial | Incertidumbre |
|---|---|---|
| South Bay y Puerto | 1.75 | ±0.05 |
| Gateway Cities | 1.11 | ±0.04 |
| Norte de Orange | 1.03 | ±0.13 |
| Westside | 0.98 | ±0.07 |
| Centro de LA | 0.78 | ±0.03 |
| Valle de San Gabriel | 0.78 | ±0.05 |
| Valle de San Fernando | 0.39 | ±0.05 |

- **South Bay y Puerto:** el factor alto concuerda con la actividad de camiones y barcos de los puertos de LA y Long Beach, que el a priori de calles no representa. Es una señal física plausible, no una verificación.
- **Valle de San Fernando:** el factor bajo merece revisión. Una de sus dos estaciones (037-4010) está junto a una autopista y la otra en el extremo oeste.

**Cómo leerla.**
- **Las zonas administrativas rinden igual o algo mejor que la malla 3×3:** LOO del híbrido 16.0 contra 16.3, y total vial más cerca del a priori. Son identificables en el gemelo, igual que en la CDMX.
- **El peso de TEMPO ×1/3 no cambia mucho en LA.** Sube un poco el domingo de la inversión (0.43 → 0.49) y empeora un poco el LOO (13.3 → 13.7) con la malla 3×3.
- **La restricción de cociente se respeta sin costo:** el LOO y el ajuste no cambian, como en la CDMX. Pero los datos la empujan hacia abajo (0.62 contra 0.67 del a priori).
- **El control positivo no pasa limpio.**
  - El estimador normalizado da 0.52 (0.44–0.59), y la referencia más cercana a una emisión es 0.66 (inventario de 2010).
  - La caída dominical de NO₂ observada (30–35 %) es una concentración, no una emisión, y también depende del clima.
  - Explicaciones posibles, sin probar:
    1. La referencia es vieja o no es comparable.
    2. Los días festivos de nov–dic (Acción de Gracias, Navidad, tratados como domingo) bajan más de lo normal.
    3. Lo que vimos en la CDMX: en días de aire estancado, el estimador no descuenta todo el clima.
  - Mientras no se resuelva, **LA no confirma la magnitud del cociente dominical, solo su dirección.**

### Qué falta para que LA sea un control positivo completo

1. **PeMS** (el usuario creará la cuenta): conteos por hora de 2023 con camiones separados, para fijar la referencia del fin de semana con datos del mismo periodo. Es lo que decide si el 0.52 es un sesgo del método o de la referencia.
2. **EMFAC descargado a mano:** fracción de pesados en el NOₓ vehicular de LA y Orange en 2023, para traducir los conteos de PeMS a emisión.
3. **Separar festivos de domingos** y repetir el estimador. Es barato.
4. **Ampliar el dominio:** pasar de 9 a 16 estaciones de NOₓ con una caja de −118.75 a −117.55 °O y de 33.65 a 34.30 °N (23 con toda la cuenca). Requiere volver a bajar las calles de OSM, el subconjunto de TEMPO y HRRR. No es barato, pero es lo que más reduciría la incertidumbre por zona.
5. **Un periodo de verano**, para probar la vida química y el viento de la capa de mezcla con capas límite altas.

## Fuentes (páginas abiertas)

- Borsdorff et al. 2020, *Mexico City CO emissions from TROPOMI* — [ACP 20, 15761](https://acp.copernicus.org/articles/20/15761/2020/)
- Brioude et al. 2013, *Top-down estimate of LA Basin emissions (CALNEX)* — [ACP 13, 3661](https://acp.copernicus.org/articles/13/3661/2013/)
- Goldberg et al. 2019, *Enhanced capabilities of TROPOMI NO₂* — [KNMI](https://www.knmi.nl/research/publications/enhanced-capabilities-of-tropomi-no2-estimating-nox-from-north-american-cities-and-power-plants)
- Nawaz et al. 2024, *TRACER-AQ NO₂ columns, Houston* — [ACP 24, 6719](https://acp.copernicus.org/articles/24/6719/2024/) · [NASA TRACER-AQ](https://www-air.larc.nasa.gov/missions/tracer-aq/index.html)
- GEMS y emisiones horarias en Asia — [Springer Nature, "Behind the Paper"](https://communities.springernature.com/amp/posts/uncovering-no-emissions-at-asia-s-pollution-hotspots-through-time-resolved-no-monitoring-from-space)
- Chuprov et al. 2025, *PINNs para localizar fuentes* — [arXiv 2503.18849](https://arxiv.org/html/2503.18849v1)
- Sensores de NO₂/O₃ en Zúrich (Empa) — [AMT 10, 3783](https://amt.copernicus.org/articles/10/3783/2017/)
- Caltrans PeMS — [Fuente de datos](https://dot.ca.gov/programs/traffic-operations/mpr/pems-source)
- NOAA HRRR en AWS — [Registry of Open Data](https://registry.opendata.aws/noaa-hrrr-pds)
- London Atmospheric Emissions Inventory 2022 — [London Datastore](https://data.london.gov.uk/dataset/london-atmospheric-emissions-inventory--laei--2022)
- London Air Quality Network (guía RGS) — [PDF](https://www.rgs.org/media/qz4lvfxn/londonair.pdf) · [Breathe London](https://www.breathelondon.org/)
- Airparif, plaquette internationale (nov 2023) — [PDF](https://www.airparif.fr/sites/default/files/document_publication/plaquette-internationale-fr.pdf)
- Météo-France AROME en datos abiertos — [data.gouv.fr](https://www.data.gouv.fr/datasets/modele-numerique-de-previsions-meteorologiques)
- CETESB, red de São Paulo (jul 2025) — [SEMIL](https://semil.sp.gov.br/?p=127204)
- SIMA Monterrey — [H. Congreso de Nuevo León](https://www.hcnl.gob.mx/glpmc/2025/03/va-rocio-montalvo-por-mas-estaciones-de-monitoreo-de-la-calidad-del-aire-en-el-area-metropolitana.php)
- Datos usados en la estimación de Los Ángeles: [EPA AQS Air Data, archivos horarios](https://aqs.epa.gov/aqsweb/airdata/download_files.html) (NO₂, NO/NOₓ y viento 2023) · [Iowa Environmental Mesonet, ASOS](https://mesonet.agron.iastate.edu/request/download.phtml) · [NOAA HRRR en AWS](https://registry.opendata.aws/noaa-hrrr-pds) vía [Herbie](https://herbie.readthedocs.io/) · [TEMPO NO₂ L2 V04, NASA ASDC](https://asdc.larc.nasa.gov/project/TEMPO) · [ERA5 vía Open-Meteo](https://open-meteo.com/en/docs/historical-weather-api) · OpenStreetMap (Overpass) · [WRI Global Power Plant Database](https://datasets.wri.org/dataset/globalpowerplantdatabase)
- Referencias de ciclo semanal en LA (sin PeMS): [Kim et al. 2016, inventario CalNex 2010, días hábiles frente a fin de semana](https://escholarship.org/uc/item/0z89x2db) · [Goldberg et al. 2021, TROPOMI NO₂ en EE. UU.](https://pmc.ncbi.nlm.nih.gov/articles/PMC8047911)
- Kim et al. 2016, *Modeling the weekly cycle of NOx and CO emissions … LA-South Coast Air Basin during CalNex 2010* — [NOAA IR](https://repository.library.noaa.gov/view/noaa/21669)
- Pollack et al. 2012, *Airborne and ground-based observations of a weekend effect … South Coast Air Basin* — [Harvard ACMG](https://atmos.seas.harvard.edu/publications/airborne-and-ground-based-observations-weekend-effect-ozone-precursors-and)
- Goldberg et al. 2021, *TROPOMI NO2 in the United States … weekly cycles* — [PMC8047911](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC8047911/)
- Caída dominical de NO₂ y CO en LA (Caltech, 2022) — [CaltechAUTHORS](https://resolver.caltech.edu/CaltechAUTHORS:20220513-557957000)
- CARB EMFAC (portal web) — [emfac.arb.ca.gov](https://emfac.arb.ca.gov/emissions-inventory/) · [Guía EMFAC202x](https://ww2.arb.ca.gov/sites/default/files/2021-01/EMFAC202x_Users_Guide_01112021_final.pdf)
- Censo de EE. UU., límites de lugares 2023 — [cb_2023_06_place_500k](https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_06_place_500k.zip)
