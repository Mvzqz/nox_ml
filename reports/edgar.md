# EDGAR como fuente independiente de validación

**Pregunta:** ¿nuestros resultados por zona se parecen a un inventario global independiente? EDGAR sustituye, mientras no llegue, al inventario por municipio que pedimos a SEDEMA (prueba 9 de `plan_validacion.md`).

**Respuesta corta:**
- **El patrón espacial sí se parece, pero al total de EDGAR, no a su transporte carretero.** Nuestra emisión por zona tiene una correlación de rangos de 0.75 con el NOₓ total de EDGAR y de solo 0.25 con su transporte carretero. La inversión mueve las zonas justo hacia donde EDGAR pone emisión no vial: industria en CDMX Norte, Tlalnepantla y Cuautitlán. Es evidencia independiente de que lo que estimamos es la "emisión de la zona", que incluye la industria, y no solo tráfico.
- **El cociente CDMX/Edomex es coherente:** EDGAR da 0.73 en total y 0.82 en transporte, el inventario 2018 da 0.71 y nosotros 0.71–0.76.
- **EDGAR y el inventario de la ZMVM no coinciden en tamaño ni en mezcla de sectores.** El transporte carretero de EDGAR en el dominio (34 mil t/año) es un tercio del a priori que tomamos del inventario (99 mil), y su fracción vial es 52 % frente a 86 % del inventario. EDGAR no sirve para validar totales ni la fracción de tráfico; sí sirve para el patrón espacial.

Datos: EDGAR v8.1 NOx 2022 (último año disponible) y 2018, malla de 0.1° por sector (`data/raw/edgar/MANIFEST.md`). Scripts: `scripts/edgar_extract.py` (recorte) y `scripts/edgar_compare.py` (comparación). Resultados: `data/interim/edgar/edgar_compare.json`.

## Cómo se comparó

- **Reparto a zonas:** cada celda de 0.1° (~11 km) se reparte entre las 13 zonas administrativas según la fracción de su área. Supone emisión uniforme dentro de la celda; con celdas de ese tamaño, las zonas chicas (CDMX Centro, 93 km²) toman buena parte de su valor de celdas compartidas.
- **Nuestros números:** emisión de día hábil por zona = α a posteriori × a priori vial de la zona, con puffs y la configuración estándar (`zonas_admin.md`, nov–dic 2023 y feb–may 2024). Son anteriores a la corrección de vida química (`vida_quimica.md`, en curso). Afecta sobre todo a primavera.
- **Sectores de EDGAR:** transporte carretero (TRO); energía (ENE); industria (IND, química, hierro, no ferrosos, minerales no metálicos, refinación, alimentos y papel, manufactura); residencial y comercial (RCO); aviación en aterrizajes y despegues; otros.

## (a) Patrón espacial por zona

Correlación de rangos (Spearman) entre zonas; n = 13.

| Comparación | Con transporte carretero de EDGAR | Con NOₓ total de EDGAR |
|---|---|---|
| A priori vial (calles de OSM) | 0.29 | 0.46 |
| Inversión nov–dic 2023 | 0.25 | **0.75** |
| Inversión feb–may 2024 | 0.10 | 0.59 |

**¿La inversión se movió en la dirección de EDGAR?** Se compara α (lo que la inversión cambió respecto al a priori) con el cociente EDGAR/a priori de cada zona:
- contra el transporte de EDGAR: −0.02 y −0.12, sin relación;
- contra el total de EDGAR: **0.59 y 0.55**.

Las zonas que la inversión sube son las que EDGAR considera más cargadas de emisión no vial.

| Zona | A priori (% del dominio) | Inversión nov–dic (%) | Transporte EDGAR (%) | Parte no vial en EDGAR |
|---|---|---|---|---|
| CDMX Centro | 7.6 | 7.6 | 9.2 | 49 % |
| CDMX Poniente | 9.2 | 6.7 | 8.6 | 41 % |
| **CDMX Norte** | 6.5 | **13.5** | 8.5 | **57 %** |
| CDMX Oriente | 7.7 | 10.5 | 9.1 | 39 % |
| CDMX Sur | 7.6 | 4.8 | 9.8 | 27 % |
| Naucalpan–Huixquilucan | 8.3 | 7.8 | 6.1 | 38 % |
| **Tlalnepantla–Atizapán** | 8.8 | **12.3** | 6.8 | **55 %** |
| Ecatepec | 6.6 | 5.2 | 7.4 | 42 % |
| Neza–Chimalhuacán | 7.6 | 4.9 | 7.2 | 35 % |
| Chalco–Ixtapaluca | 5.1 | 2.6 | 4.8 | 28 % |
| Texcoco | 5.7 | 5.1 | 6.3 | 38 % |
| **Cuautitlán–Tultitlán** | 11.6 | 12.5 | 9.3 | **71 %** |
| Tecámac–Acolman | 7.9 | 6.5 | 7.0 | 45 % |

**Lectura:**
- **Las tres zonas que más sube la inversión** son las de mayor emisión no vial en EDGAR: CDMX Norte (Vallejo, Azcapotzalco), Tlalnepantla y Cuautitlán. Coincide con el punto caliente de Vallejo en TEMPO (`puntos_calientes.html`).
- **Las que más baja** (CDMX Sur, Chalco, Neza) son las más residenciales: EDGAR les da 27–35 % no vial.
- **El transporte de EDGAR** está repartido casi parejo entre zonas (4.8–9.8 %), más que nuestro a priori de OSM. Su reparto espacial usa sus propios indicadores, como la densidad de población y la red vial, con la incertidumbre que eso trae.

## (b) CDMX frente a Estado de México

Parte de cada entidad dentro del dominio.

| Fuente | CDMX / Edomex |
|---|---|
| EDGAR 2022, total | 0.73 |
| EDGAR 2022, transporte carretero | 0.82 |
| EDGAR 2018, total / transporte | 0.72 / 0.82 |
| Inventario ZMVM 2018, móviles (entidades completas) | 0.71 |
| Nuestra inversión nov–dic 2023 (3×3 + Ecatepec / grupos administrativos) | 0.71 / 0.76 |

Las cuatro fuentes caen entre 0.71 y 0.82. El total de EDGAR (0.73) queda más cerca de nuestro número que su transporte (0.82), igual que en el patrón por zona. El inventario 2018 abarca las entidades completas y no solo el dominio, así que la comparación es aproximada.

## (c) Fracción de transporte

| Fuente | Fracción vial del NOₓ |
|---|---|
| Inventario ZMVM 2018 (móviles / total) | 86 % (124 mil de 145 mil t/año) |
| EDGAR 2022 en el dominio | 52 % |
| EDGAR 2022, CDMX dentro del dominio | 56 % |

**No coinciden.** EDGAR pone mucha más industria (17 mil t/año en el dominio) y energía (5.7 mil) que el inventario (puntuales: 1.6 mil en la CDMX y 7.6 mil en todo el Edomex). No podemos decidir cuál tiene razón con estos datos. Por eso la "emisión de la zona" no se debe leer como tráfico puro, y separar orígenes sigue pendiente (`mejoras.md`, al final).

Nota: el "~80 %" de `feasibility_linear.py` es otra cosa. Es la fracción del NOₓ vehicular de la ZMVM que suponemos dentro del dominio (a priori vial = 0.8 × 124 mil = 99 mil t/año), no la fracción de tráfico del total.

## (d) Totales

| Fuente | t/año en el dominio |
|---|---|
| A priori vial (0.8 × móviles del inventario 2018) | 99,000 |
| Nuestra inversión, día hábil, nov–dic 2023 | 76,000 |
| Nuestra inversión, día hábil, feb–may 2024 (sin vida química por temporada) | 45,000 |
| EDGAR 2022, total de todos los sectores | 65,000 |
| EDGAR 2022, transporte carretero | 34,000 |
| EDGAR 2018, transporte carretero, CDMX completa en el dominio | 15,600 frente a 44,500 del inventario 2018 |

- **El transporte de EDGAR es un tercio del inventario local.** En la CDMX, donde toda la entidad está en el dominio, EDGAR 2018 da 15.6 mil t/año de transporte frente a 44.5 mil del inventario 2018. Es una diferencia entre inventarios, no un error nuestro.
- **Nuestro total queda entre los dos:** en invierno, cerca del inventario; en primavera, cerca del total de EDGAR. La caída de primavera es en buena parte química, no de emisión (`multifisica.md`). Los totales ya se sabían dependientes del modelo (26–42 %); EDGAR no ayuda a fijarlos.

## Los Ángeles y Bogotá (solo EDGAR, como referencia)

| | Total | Transporte carretero | Industria | Residencial | Aviación | Fracción vial |
|---|---|---|---|---|---|---|
| Los Ángeles 2022 (dominio de `la_common.py`) | 69,800 | 21,300 | 18,300 | 15,400 | 5,800 | 31 % |
| Bogotá 2022 (urbana con Soacha) | 35,400 | 19,700 | 8,800 | 3,900 | 800 | 56 % |

- **Los Ángeles:** nuestro a priori vial (40 mil t/año, `otras_ciudades.md`) es casi el doble del transporte de EDGAR. La inversión con puffs dio 36 mil. CARB/EMFAC lo está descargando otro agente; esa comparación no está aquí, para no duplicarla.
- **Bogotá:** queda como referencia para la versión ligera (`bogota.md`). No se comparó contra el inventario de la SDA.

## Qué significa para el proyecto

1. **Validación espacial independiente: sí.** El patrón por zona coincide con EDGAR (0.75 de correlación de rangos en invierno). La inversión corrige el a priori de OSM en la misma dirección en que EDGAR difiere de él: suma la emisión no vial que el proxy de calles no ve.
2. **Respalda el nombre "emisión de la zona".** Lo que estimamos se parece más al total que al tráfico.
3. **Cociente CDMX/Edomex coherente** entre cuatro fuentes (0.71–0.82).
4. **Totales y fracción de tráfico: no validables con EDGAR,** que difiere del inventario local por un factor de ~3 en transporte. Siguen dependiendo del inventario oficial y de SEDEMA.
5. **Limitaciones:** las celdas de 0.1° son grandes frente a zonas de ~100–500 km², los datos de EDGAR son de 2022 y no de 2023, y EDGAR reparte con indicadores propios. Con 13 zonas, una correlación de 0.75 tiene un intervalo amplio, aproximadamente 0.35–0.92.
