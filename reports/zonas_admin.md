# Zonas viales con límites administrativos

**Pregunta:** ¿sirve cambiar las 10 zonas cuadradas (3×3 + Ecatepec) por grupos de alcaldías y municipios?

**Respuesta corta:** sí, conviene adoptarlas como esquema de reporte.
- **Técnicamente es un empate.** Con datos reales y en los gemelos, las dos versiones rinden lo mismo dentro del ruido.
- **Es más útil.** Cada zona tiene un nombre y una autoridad, y ninguna cruza el límite CDMX / Estado de México.
- **El patrón espacial es más estable entre temporadas.** La correlación de rangos entre noviembre–diciembre de 2023 y febrero–mayo de 2024 es 0.82, frente a 0.70 con la cuadrícula.
- **Un número por municipio no se debe publicar.** En el gemelo, el error por municipio (16 %) apenas mejora al del a priori (~20 %).

No cambié el estándar: `REGION_SCHEME` sigue en `3x3_ecatepec`. El esquema nuevo se usa con `REGION_SCHEME=admin_grupos`.

## Diseño de los 13 grupos

Criterios:
- cada grupo tiene al menos una estación de NOₓ;
- ningún grupo cruza el límite entre la CDMX y el Estado de México;
- los pesos viales a priori son comparables, entre 5,000 y 11,500 t/año.

Las partes de municipios fuera del dominio se recortan. Las pocas celdas que no caen en ningún municipio, en el borde con Hidalgo, se asignan al grupo más cercano.

| # | Grupo | Municipios | Estaciones NOₓ | km² en el dominio | Vial a priori (t/año) |
|---|---|---|---|---|---|
| 0 | CDMX Centro | Cuauhtémoc, Benito Juárez, Venustiano Carranza | BJU, HGM, MER | 93 | 7,593 |
| 1 | CDMX Poniente | Miguel Hidalgo, Álvaro Obregón, Cuajimalpa | CUA, MGH, PED | 207 | 9,170 |
| 2 | CDMX Norte | Azcapotzalco, Gustavo A. Madero | CAM, GAM | 121 | 6,425 |
| 3 | CDMX Oriente | Iztapalapa, Iztacalco, Tláhuac | IZT, SAC, UIZ | 201 | 7,605 |
| 4 | CDMX Sur | Coyoacán, Tlalpan, La Magdalena Contreras, Xochimilco | AJM, CCA, UAX | 216 | 7,514 |
| 5 | Naucalpan–Huixquilucan | Naucalpan, Huixquilucan, Jilotzingo, Isidro Fabela, Ocoyoacac | FAC | 235 | 8,196 |
| 6 | Tlalnepantla–Atizapán | Tlalnepantla, Atizapán de Zaragoza, Nicolás Romero | ATI, TLA | 235 | 8,695 |
| 7 | Ecatepec | Ecatepec de Morelos | SAG, XAL | 156 | 6,571 |
| 8 | Neza–Chimalhuacán | Nezahualcóyotl, Chimalhuacán, La Paz, Chicoloapan | FAR, NEZ | 195 | 7,523 |
| 9 | Chalco–Ixtapaluca | Chalco, Valle de Chalco Solidaridad, Ixtapaluca | CHO | 221 | 5,016 |
| 10 | Texcoco | Texcoco, Atenco, Chiconcuac, Papalotla, Tepetlaoxtoc, Chiautla, Tezoyuca | MON | 414 | 5,698 |
| 11 | Cuautitlán–Tultitlán | Cuautitlán Izcalli, Tultitlán, Coacalco, Tultepec, Cuautitlán, Tepotzotlán, Teoloyucan, Coyotepec, Melchor Ocampo, Huehuetoca | CUT, TLI, VIF | 472 | 11,479 |
| 12 | Tecámac–Acolman | Tecámac, Acolman, Teotihuacán, San Martín de las Pirámides, Nextlalpan, Jaltenco, Tonanitla, Zumpango, Temascalapa, Otumba, Axapusco | ACO | 495 | 7,806 |

Geometrías: `data/interim/zonas_admin.gpkg`.
- Capa `admin_grupos`: los 13 grupos.
- Capa `admin_mun`: un municipio por zona; solo se usa para el gemelo heterogéneo.

## Identificabilidad (gemelos, nov–dic 2023)

Configuración igual a la de datos reales:
- puffs con el viento del dominio, ensamble σθ = 30°, TEMPO ×1/3;
- restricción de cociente de Infovial;
- a priori de centrales de Climate TRACE, sin clústeres industriales y con estaciones extra.

Las observaciones sintéticas se generan con un Jacobiano construido con el **viento rotado**: error de dirección AR(1) por hora, σ = 30°, con correlación de 0.8 entre horas. Llevan además ruido de 15 ppb en estaciones y de 5·10¹⁵ molec/cm² en TEMPO. Se invierten con el Jacobiano nominal. Cada gemelo usa 40 verdades.

**1. Verdad por zona.** α ~ LN(0, 0.3) en cada zona del propio esquema. Sin información, el error mediano sería de ~20 %.

| Esquema | Error mediano por zona | Peor zona | Total vial | Domingo/hábil | Correlación a posteriori más fuerte |
|---|---|---|---|---|---|
| 3×3 + Ecatepec | 1–8 % | SO, S 8 % | 4 % | 1 % | SE–NE +0.23 |
| Grupos administrativos | 1–14 % | CDMX Sur 14 %, Chalco–Ixtapaluca 10 % | 4 % | 0 % | CDMX Oriente – Neza −0.28 |

Ningún grupo supera los umbrales de fusión (|corr| > 0.6 o error > 25 %), así que se quedaron los 13 grupos de la primera versión. No hizo falta una segunda iteración.

**2. Verdad heterogénea por municipio.** α ~ LN(0, 0.3) distinta en cada uno de los 59 municipios, invertida con cada esquema. Mide el error de agregación, es decir, lo que pasó con Ecatepec dentro del "Centro". El error "por municipio" reparte el α̂ de la zona a sus celdas y se evalúa en los municipios con ≥ 1 % del peso vial.

| Esquema | Por municipio | Por zona del esquema | CDMX | Edomex | Total vial | Domingo |
|---|---|---|---|---|---|---|
| 3×3 | 17 % | 3–9 % | 6.3 % | 4.2 % | 5 % | 1 % |
| 3×3 + Ecatepec | 16 % | 3–9 % | 5.8 % | 4.3 % | 5 % | 1 % |
| Grupos administrativos | 16 % | 2–14 % | 6.1 % | 3.1 % | 5 % | 0 % |

Lectura:
- **Los tres esquemas recuperan igual** los totales por zona, por entidad y del dominio.
- **El valor por municipio no es confiable con ningún esquema:** 16 % frente a ~20 % sin datos.
- **CDMX Sur es el grupo más débil** (14 %), aunque tiene tres estaciones. Una posible causa, no comprobada, es que con viento del norte sus emisiones salen del dominio antes de cruzar otras estaciones.
- **Advertencia:** este gemelo es optimista. Supone que el reparto vial dentro de cada municipio es correcto y que el error de TEMPO no tiene estructura espacial. Los errores reales son mayores; aquí lo que cuenta es la **comparación** entre esquemas.

## Datos reales

Ambos esquemas con puffs y la configuración actual. Bootstrap de 200 días. Los resultados de 3×3 + Ecatepec son los de `config_final.py` (13:18 y 13:21 del 23 de octubre).

### Nov–dic 2023

| Zonas | LOO modelo / IDW / híbrido (ppb) | Híbrido < IDW | Sin SAG y XAL: modelo / IDW / híbrido | SAG híbrido / IDW | XAL híbrido / IDW | r TEMPO (fija / invertido) | Vial hábil / inventario |
|---|---|---|---|---|---|---|---|
| 3×3 + Ecatepec | 12.9 / 11.5 / 11.7 | 15 de 24 | 12.1 / 11.4 / 10.5 | 20.7 / 10.7 | 18.7 / 13.9 | 0.65 / 0.83 | 76 % |
| Grupos administrativos | 13.1 / 11.5 / 11.8 | 14 de 24 | 12.1 / 11.4 / 10.5 | 23.0 / 10.7 | 18.6 / 13.9 | 0.65 / 0.83 | 77 % |

| Zonas | Domingo libre (IC 90 %) | Con restricción | Normalizado (IC 90 %) | Placebo ± | CV hábiles |
|---|---|---|---|---|---|
| 3×3 + Ecatepec | 0.49 (0.43–0.57) | 0.64 | 0.61 (0.53–0.69) | 0.19 | 0.26 |
| Grupos administrativos | 0.48 (0.41–0.57) | 0.65 | 0.61 (0.53–0.70) | 0.19 | 0.26 |

### Feb–may 2024

| Zonas | LOO modelo / IDW / híbrido (ppb) | Híbrido < IDW | Sin SAG y XAL: modelo / IDW / híbrido | SAG híbrido / IDW | XAL híbrido / IDW | r TEMPO (fija / invertido) | Vial hábil / inventario |
|---|---|---|---|---|---|---|---|
| 3×3 + Ecatepec | 7.8 / 7.1 / 6.8 | 12 de 22 | 7.5 / 7.0 / 6.5 | 8.9 / 4.3 | 12.6 / 12.7 | 0.58 / 0.80 | 46 % |
| Grupos administrativos | 7.9 / 7.1 / 6.9 | 13 de 22 | 7.7 / 7.0 / 6.6 | 9.2 / 4.3 | 12.5 / 12.7 | 0.58 / 0.80 | 45 % |

| Zonas | Domingo libre (IC 90 %) | Con restricción | Normalizado (IC 90 %) | Placebo ± | CV hábiles |
|---|---|---|---|---|---|
| 3×3 + Ecatepec | 0.53 (0.47–0.63) | 0.66 | 0.68 (0.61–0.76) | 0.11 | 0.23 |
| Grupos administrativos | 0.53 (0.46–0.61) | 0.66 | 0.68 (0.61–0.77) | 0.11 | 0.23 |

**Lectura:**
- Las diferencias son de 0.1–0.2 ppb en LOO, iguales en TEMPO, el domingo, el estimador normalizado y el placebo.
- SAG empeora un poco (23.0 frente a 20.7 ppb en nov–dic).
- Las correlaciones a posteriori entre grupos vecinos son algo mayores (hasta −0.32), pero lejos del umbral de 0.6.

### Por zona

α de día hábil por zona (± σ a posteriori):

- **Nov–dic 2023:**
  - CDMX Centro 0.76 ± 0.02, CDMX Poniente 0.56 ± 0.02, **CDMX Norte 1.60 ± 0.03**, CDMX Oriente 1.06 ± 0.03, CDMX Sur 0.49 ± 0.03;
  - Naucalpan–Huixquilucan 0.73 ± 0.02, Tlalnepantla–Atizapán 1.08 ± 0.02, Ecatepec 0.61 ± 0.02, Neza–Chimalhuacán 0.50 ± 0.03;
  - Chalco–Ixtapaluca 0.39 ± 0.04, Texcoco 0.68 ± 0.05, Cuautitlán–Tultitlán 0.83 ± 0.02, Tecámac–Acolman 0.64 ± 0.04.
- **Feb–may 2024:**
  - CDMX Centro 0.42, CDMX Poniente 0.20, **CDMX Norte 0.68**, CDMX Oriente 0.49, CDMX Sur 0.18;
  - Naucalpan–Huixquilucan 0.43, Tlalnepantla–Atizapán 0.67, Ecatepec 0.49, Neza–Chimalhuacán 0.35;
  - Chalco–Ixtapaluca 0.14, Texcoco 0.44, Cuautitlán–Tultitlán 0.65, Tecámac–Acolman 0.61 (σ 0.01–0.03).

Los σ a posteriori (±0.02) subestiman la incertidumbre real porque suponen errores independientes. El reparto vial por zona sigue siendo indicativo (`base_sigma30.md`).

**Estabilidad entre temporadas.** Se compara el patrón relativo, α / media del esquema, de nov–dic contra feb–may:

| Esquema | Pearson | Spearman | Mayor diferencia relativa |
|---|---|---|---|
| 3×3 + Ecatepec | 0.64 | 0.70 | 0.60 |
| Grupos administrativos | 0.73 | 0.82 | 0.57 |

El patrón por grupos se repite mejor.
- **CDMX Norte** (Azcapotzalco y GAM) es la zona más alta en las dos temporadas. Coincide con el punto caliente de TEMPO en Vallejo–Azcapotzalco (`puntos_calientes.html`), donde hay industria y carga pesada que el proxy vial no representa.
- **Chalco–Ixtapaluca y CDMX Sur** son las más bajas en las dos temporadas.

## CDMX frente a Estado de México

Emisión vial de día hábil dentro del dominio (t/año). Cada celda vial lleva el α de su zona y se suma por la entidad de la celda, así que el reparto también se puede calcular para la cuadrícula.

| Periodo | Zonas | CDMX | Edomex (parte en el dominio) | CDMX / Edomex | Inventario 2018 móviles: CDMX / Edomex |
|---|---|---|---|---|---|
| Nov–dic 2023 | 3×3 + Ecatepec | 31,539 | 44,205 | 0.71 | 44,526 / 62,606 (0.71) |
| Nov–dic 2023 | Grupos administrativos | 32,962 | 43,390 | 0.76 | |
| Feb–may 2024 | 3×3 + Ecatepec | 14,677 | 30,514 | 0.48 | |
| Feb–may 2024 | Grupos administrativos | 14,430 | 30,606 | 0.47 | |

Los a priori son 38,307 (CDMX) y 60,985 (Edomex en el dominio), con cociente 0.63.
- **En noviembre–diciembre** los datos llevan el cociente a 0.71–0.76, igual o algo arriba del inventario (0.71). La CDMX queda en 71–74 % de su inventario móvil. La parte del Edomex en el dominio queda en 69–71 % del inventario de toda la entidad, así que este último porcentaje no es comparable uno a uno.
- **En primavera** la CDMX cae mucho más (0.47). Es el mismo problema de temporada que ya se veía en el total vial (45 % del inventario; `puffs_cdmx.md`): el modelo atribuye a menos emisión lo que probablemente es química o mezcla de primavera. No es una diferencia real entre entidades.
- **Los dos esquemas dan lo mismo,** así que el cociente lo fijan los datos y no el trazo de las zonas. Con grupos, el número sale directo; con la cuadrícula hay que repartir zonas que cruzan el límite.

## Recomendación

1. **Adoptar `admin_grupos` como esquema de reporte y de la app.** Técnicamente empata con 3×3 + Ecatepec. A cambio, cada número tiene un responsable (alcaldías y municipios con nombre), la comparación CDMX–Edomex es directa y el patrón espacial es más estable entre temporadas.
2. **No publicar valores por municipio.** Si se piden, presentarlos como reparto proporcional al tráfico dentro del grupo, no como medición.
3. **Marcar CDMX Sur y Chalco–Ixtapaluca como zonas de menor confianza.** Tienen el mayor error en el gemelo.
4. **Pendiente para el cambio de default:** no lo cambié porque otro agente regenera la app con `3x3_ecatepec`. Para adoptarlo:
   - poner `REGION_SCHEME` en `admin_grupos` en `feasibility_linear.py`;
   - regenerar la app (`scripts/pinn/export_app.py`), que hoy busca la zona "Ecatepec" por nombre; el nombre existe en ambos esquemas.

## Archivos

- `scripts/zonas_admin_design.py`: diseño de los grupos (capas de `data/interim/zonas_admin.gpkg`).
- `scripts/zonas_admin_twin.py`: gemelos (por zona y `--hetero` por municipio). Salidas en `data/interim/zonas_admin/twin*_<esquema>.json`.
- `scripts/zonas_admin_real.py`: corridas reales y tablas (`--report`). Salidas en `data/interim/puffs_cdmx/<periodo>_puff_admin_grupos.json`.
- `scripts/feasibility_linear.py`: esquemas `admin*` en `region_names()` y `assign_regions()`. El default no cambió.
