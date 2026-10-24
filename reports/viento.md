# Viento: error real y cómo mejorarlo

Fecha: 2026-10-20. Scripts: `scripts/wind_loo.py`, `scripts/wind_pairs.py`, `scripts/wind_scenarios.py`.

## Resumen

- El error de viento real es **mayor que el ±20° supuesto**. Al predecir cada estación con las demás, el error de dirección tiene una mediana de 28–32° (σ equivalente ≈ 42–48°). Parte de ese error es ruido propio de cada sitio, así que el error del flujo promediado sobre una trayectoria está probablemente entre ±20° y ±30°.
- Con ±30°, el gemelo ya **no cumple** la meta ni para las fuentes grandes (32–37 %), y la emisión vial por región sube a 15 % de mediana. Esto concuerda con los resultados en datos reales (Acolman y AIFA mal estimados).
- Los modelos globales no sirven: ERA5 tiene 55° de mediana. Hace falta un modelo de ~1 km.
- **SEDEMA ya opera un WRF a 1 km** (sistema de pronóstico con el BSC, desde 2017). Pedir sus salidas archivadas es la opción más barata y rápida. Si no se obtienen, la alternativa es correr WRF nosotros con asimilación de las estaciones.

## 1. Error medido (nov–dic 2023, 12–17 h, 22 estaciones, 6,857 horas-estación con viento ≥ 1 m/s)

| Método para predecir la estación retenida | Error de dirección: mediana | p75 | Sesgo de velocidad | Error abs. de velocidad: mediana |
|---|---|---|---|---|
| Vector medio del dominio (lo que usa el modelo lineal) | 32° | 66° | −0.81 m/s | 0.69 m/s |
| IDW de las demás estaciones | 28° | 59° | −0.68 m/s | 0.64 m/s |
| ERA5, una celda de 0.25° | 55° | 98° | — | — |

Estaciones con error mucho mayor, probablemente por exposición del sitio o terreno: CHO (101°), FAC (72°), ACO (50°), CUA (50°). Las mejores, en el centro y el oriente plano: NEZ (18°), SAC (19°), PED (20°).

**¿Cuánto es ruido de sitio?** Diferencia de dirección entre pares de estaciones a la misma hora:

| Distancia entre estaciones | Pares-hora | Diferencia mediana | p75 |
|---|---|---|---|
| 0–5 km | 335 | 38° | 74° |
| 5–10 km | 8,131 | 32° | 68° |
| 10–15 km | 11,040 | 43° | 82° |
| 15–20 km | 10,120 | 45° | 86° |
| 20–30 km | 15,869 | 52° | 98° |
| 30–60 km | 15,746 | 54° | 102° |

Estaciones a menos de 10 km ya difieren 32–38°. Ese piso es ruido local de cada sitio (≈ 23° por estación) y no variación del flujo que transporta la contaminación. Después la diferencia crece con la distancia, así que sí hay variación real dentro de la cuenca. Consecuencia práctica: ningún campo de viento, por bueno que sea, bajará de ≈ 20–25° de error medido en una estación, y la meta de validación debe fijarse con eso en mente.

## 2. Qué significa para la inversión (gemelo pesimista, nov–dic 2023, sin datos extra)

| Error de dirección (1σ) | Clústeres industriales: mediana | Clústeres < 25 % | Acolman / AIFA / AICM | Vial por región: mediana (máx) |
|---|---|---|---|---|
| ±40° | 145 % | 0 de 12 | 43 / 41 / 44 % | 21 % (40 %) |
| ±30° | 113 % | 1 de 12 | 32 / 35 / 37 % | 15 % (36 %) |
| ±20° | 66 % | 1 de 12 | 18 / 27 / 22 % | 9 % (24 %) |
| ±10° | 32 % | 4 de 12 | 7 / 10 / 14 % | 3 % (9 %) |

(Las cifras de ±20° difieren un poco del escenario A de `improvement_tests.md` por el muestreo aleatorio de los gemelos.)

Pasar de ±30° a ±10° es la diferencia entre "solo zonas viales aproximadas" y "zonas viales y fuentes grandes dentro de la meta".

## 3. Opciones

| Opción | Qué es | Mejora esperada | Costo | Tiempo | Quién |
|---|---|---|---|---|---|
| **A. Salidas WRF de SEDEMA** | El sistema de pronóstico de calidad del aire de SEDEMA (con el BSC) corre WRF-ARW anidado 27 → 9 → 3 → **1 km**, con GFS de entrada, de forma operativa desde 2017 ([BSC/CIO](https://www.cio.com/article/2084521/el-bsc-y-ciudad-de-mexico-desarrollaran-herramientas-para-mitigar-la-contaminacion-del-aire.html); [presentación SEDEMA–WRI 2020](https://thecityfixlearn.org/wp-content/uploads/AQ_TechTalk_Forecast-compressed_0.pdf), lámina 12). Se pedirían u10, v10 y altura de capa límite horarias para los periodos de estudio. | Alta en la zona urbana y plana. Es un pronóstico, no un reanálisis, y en montaña puede fallar: en un WRF de 1 km evaluado en la CDMX hubo sobreestimación de 2–3 m/s y estaciones del sur con unos 90° de error ([Xu et al., EGU 2021](https://meetingorganizer.copernicus.org/EGU21/EGU21-15117.html?EGUSphere)). | Bajo: una solicitud | 2–6 semanas, según SEDEMA | SEDEMA (Dirección de Calidad del Aire) / BSC |
| **B. Correr WRF nosotros** | WPS + WRF con ERA5 (cuenta CDS) o GFS-FNL, 3–4 dominios hasta 1 km, dosel urbano (SLUCM/BEP) y **obs-nudging** con REDMET + METAR. | La mayor: el nudging acerca el campo a las estaciones y la física resuelve el flujo entre ellas. | Cómputo: con 8 núcleos y 15 GB, dos meses tardarían días a semanas (estimación aproximada); en una máquina de nube de ~64 vCPU, del orden de 1–2 días | 3–6 semanas, incluyendo instalación, pruebas y validación | Nosotros, idealmente con asesoría de un modelador; el ICAyCC de la UNAM trabaja con WRF, pero no verifiqué que pueda colaborar |
| C. Ensamble de WRF | 4–8 corridas con distintas físicas o condiciones iniciales. | No mejora la exactitud, pero da la incertidumbre del viento, que la PINN necesita. | 4–8× el costo de B | +1–2 semanas sobre B | Nosotros |
| D. Ensamble estocástico barato | En la inversión, perturbar la dirección con el error medido (σ ≈ 30°) en lugar de suponer un viento exacto. | Ninguna en exactitud; incertidumbres honestas y menos sobreajuste a plumas de campo cercano. | Casi nulo | Días | Nosotros |
| E. Modelo diagnóstico de conservación de masa (WindNinja, CALMET, QUIC) | Ajusta un campo inicial a la topografía conservando masa. | Baja–media. Funciona bien con viento fuerte y efectos mecánicos del terreno; es débil con flujos térmicos de ladera, que dominan la cuenca por la tarde ([Wagenbrenner et al., ACP 2016](https://acp.copernicus.org/articles/16/5229/2016/)). | Compilar WindNinja (C++, GDAL) no es trivial; CALMET requiere licencia | 1–2 semanas | Nosotros. Solo vale como refinamiento de A o B |
| F. Modelos globales (ERA5, GFS, ECMWF) | — | **Descartado**: ERA5 tiene 55° de mediana, el doble que interpolar estaciones. | — | — | — |
| G. Control de calidad de sitios | Revisar y bajar el peso de las estaciones mal expuestas (CHO, FAC, ACO, CUA) en la interpolación y la validación. | Pequeña pero gratuita. | Nulo | Días | Nosotros |

No probé WindNinja aquí: requiere compilar dependencias pesadas y, por lo anterior, su ganancia esperada en la cuenca por la tarde es baja.

## 4. Recomendación y plan

1. **Esta semana:** solicitar a SEDEMA las salidas horarias del WRF de 1 km (u10, v10, altura de capa límite) para nov–dic 2023 y feb–may 2024. En paralelo, abrir una cuenta en el CDS de Copernicus; también resuelve el hueco de capa límite de ene–jun 2024.
2. **Mientras llega:** aplicar G y D en el modelo lineal y en el diseño de la PINN (σ de dirección ≈ 30°, menor peso a las estaciones de mal sitio).
3. **Al recibir un campo de viento** (de SEDEMA o propio), validarlo con `scripts/wind_loo.py` sobre las estaciones retenidas. Meta realista: mediana ≤ 20–25°, cerca del piso de ruido de sitio, con la mejora concentrada en el norte y el poniente.
4. **Si SEDEMA no responde en ~4 semanas:** correr WRF propio (B) con obs-nudging en una máquina de nube, primero una semana de prueba y luego los dos meses.
5. **Re-correr el gemelo** (`scripts/wind_scenarios.py`) con el error que logre el nuevo campo, para fijar qué fuentes entran en la meta.

Pendiente: no está confirmado que SEDEMA archive las salidas meteorológicas de periodos pasados ni en qué formato.
