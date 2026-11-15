# Contraste del inventario: el oriente de la ZMVM

Fecha: 2026-11-15. Frente F4 de [exploraciones_valor.md](../management/exploraciones_valor.md). Pregunta: el oriente aporta el 7 % de la emisión vial en la inversión final (E5b≥0, `pinn_puff_nonneg`, 6 zonas) frente al 19 % del inventario SEDEMA 2018. ¿Resiste pruebas independientes de las estaciones?

## De dónde sale la cifra (reproducida)

- **Zona "Oriente"** (`report_final.ZONES`): las regiones 2, 5 y 8 de la partición 3 × 3 del dominio (`data.roads`), es decir, **toda la columna este del dominio**, no solo Ecatepec, Nezahualcóyotl y Texcoco. Cada una tiene una estación: CHO (región 2), MON (5) y ACO (8). La estación NEZ cae en la región S (1), no en el oriente.
- **Inversión:** `report_final.zone_shares` sobre `results/runs/pinn_puff_nonneg*/emissions.parquet`, día hábil, regiones recortadas a 0. Oriente: nov–dic 2023 8.2 %, nov–dic 2024 6.8 %, feb–may 2025 4.8 %, nov–dic 2025 9.5 %, feb–may 2026 7.4 % (media 7.3 %; el "7 %" del artículo es esa media, con rango 4.8–9.5 %).
- **Inventario 19 %:** `report_final.region_prior`, 18.9 %. **No es una tabla municipal de SEDEMA:** es el peso de las vialidades de OSM (por clase) repartido en celdas de 1 km, escalado al total vehicular del inventario 2018. El PDF del inventario (`data/raw/inventario/`) no trae NOₓ vehicular por municipio. El "19 %" es, por tanto, una distribución espacial del *prior* de la inversión, no una medición del inventario.

## Pruebas

### 1. Satélite solo (divergencia de flujo de TEMPO por zona)

`flux_zones.py`: mismas escaneos, malla de 5 km y fórmula que `nox_ml.validation.divergence`, pero las celdas interiores se suman por zona (mismas regiones 3 × 3), solo días hábiles sin periodos atípicos ni contingencias; fracción del oriente con IC 90 % por bootstrap de días.

| Temporada | Días | τ = 2 h | τ = 4 h | Solo divergencia | Solo columna |
|---|---|---|---|---|---|
| nov–dic 2023 | 18 | 11.3 % | 12.3 % | 16.4 % | 8.0 % |
| feb–may 2024 | 40 | 14.0 % | 15.3 % | 19.7 % | 10.4 % |
| nov–dic 2024 | 26 | 12.5 % | 13.8 % | 17.6 % | 9.3 % |
| feb–may 2025 | 46 | 11.3 % | 10.9 % | 12.6 % | 10.4 % |
| nov–dic 2025 | 25 | 9.1 % | 9.8 % | 14.5 % | 7.0 % |
| feb–may 2026 | 49 | 10.9 % | 11.4 % | 15.3 % | 8.8 % |
| **Media** | | **11.5 %** | **12.3 %** | 16.0 % | 9.0 % |

- Los IC 90 % por temporada miden ±1–2 puntos (ej. τ = 2 h: 10.5–12.1 % en nov–dic 2023). Con el viento ×2: τ = 2 h 9.8–15.3 % (media 12.2 %), τ = 4 h 10.8–16.8 % (13.4 %).
- **Lectura:** el satélite confirma que el oriente es **menor** que el 19 % del inventario en las seis temporadas (cualquier τ razonable), pero **no llega al 7 %**: da ~11–13 %. Cae justo en el borde del criterio (≤ 12 %). Sin química (solo divergencia) sube a 13–20 %, y la divergencia sola es la más ruidosa: en una zona de borde del dominio la divergencia depende del viento y de la cobertura. La columna sin transporte (9 %) no es una emisión: solo dice cuánto NO₂ hay sobre la zona.
- **Cuidado:** el satélite ve todo el NOₓ (industria, aeropuerto, quemas), no solo el vial; y el oriente está al borde del dominio, donde la celda exterior se pierde en el cálculo de la divergencia.

### 2. Perfil horario (12–17 h)

El perfil horario del repositorio es de toda la ciudad (`perfil_infovial.json`), no por zona; Infovial son 26 corredores primarios de la CDMX sin coordenadas en el archivo y solo uno (Calzada Ignacio Zaragoza) lleva al oriente (Edomex no está). `infovial_east.py` usa los corredores orientales como sustituto: su peso en 12–17 h frente a su peso en el día completo (nov–dic 2018, días hábiles, pesados ×1 a ×30), aplicado al 18.9 %.

| Sustituto | Factor 12–17 h / día | Oriente del inventario en 12–17 h |
|---|---|---|
| Zaragoza | 0.85–0.95 | 16.5–18.1 % |
| Zaragoza + Ejes 1, 2 y 3 Oriente | 0.96–0.98 | 18.2–18.6 % |

**Lectura:** el perfil horario no explica la diferencia: la fracción del oriente en la tarde cae como mucho 2 puntos (de 18.9 a ≥ 16.5 %). Limitación: solo la CDMX, sin Ecatepec ni Nezahualcóyotl.

### 3. Sensibilidad de E5b≥0 (6 corridas de un tope de 8)

`sensitivity.py`, nov–dic 2023 (config congelada, SIMAT). Solo el ajuste y las fracciones por zona (sin leave-one-out, bootstrap ni placebo). El control (`base`) reproduce 8.23 %, igual que la corrida guardada.

| Corrida | Oriente | Zonas (SO / S / O / Centro / Norte) |
|---|---|---|
| Base | 8.2 % | 0.0 / 14.9 / 19.7 / 37.7 / 19.5 |
| Sin CHO (región 2) | 8.2 % | casi igual |
| Sin MON (región 5) | 8.2 % | casi igual |
| Sin ACO (región 8) | 8.3 % | casi igual |
| Viento girado +20° | **4.5 %** | 1.9 / 11.6 / 33.6 / 26.6 / 21.8 |
| Viento girado −20° | **14.6 %** | 0.0 / 19.6 / 10.7 / 39.7 / 15.4 |

**Lectura:** (a) quitar una estación del oriente no mueve la fracción (8.2–8.3 %): el reparto lo fijan las columnas de TEMPO y el prior, no esas tres estaciones; (b) **girar el viento ±20° lo mueve de 4.5 a 14.6 %**, y también el resto de las zonas (el poniente pasa de 11 a 34 %). La dirección del viento (los vientos de aeropuerto escalados a la red tienen 30° de diferencia mediana, ver `inputs.py`) es una incertidumbre del mismo tamaño que la diferencia con el inventario. El "7 %" no resiste el giro del viento como cifra; sí la desigualdad "menor que 19 %" en +20° y en la base, y no en −20° (14.6 %, todavía menor).

### 4. Composición (carga pesada)

Infovial (`infovial_corridors.csv`, clases C3–C6 como pesadas, días hábiles nov–dic 2018): la fracción pesada de los corredores orientales (Zaragoza 6.9 % de los conteos, Eje 3 Oriente 6.1 %, Eje 1 Oriente 6.0 %) es **menor** que la de los demás corredores (5–10 %, mediana ~7 %); y el domingo / día hábil de Zaragoza es 1.07 y del Eje 3 Oriente 0.98 (frente a ~0.75 de los corredores centrales). Es decir, el oriente no tiene más carga pesada ni cae más en domingo que el resto: **la composición no explica una emisión menor**. Limitación: solo dos o tres corredores y solo la CDMX.

## Veredicto (plantilla)

| Criterio | Escala | Resultado |
|---|---|---|
| **¿Funciona?** | 2 | Funciona con condiciones. El satélite solo da 11.5–12.3 % (frente a 19 %): confirma la dirección, no el 7 %; resiste quitar estaciones pero no girar el viento ±20° (4.5–14.6 %). |
| **Evidencia** | Divergencia de flujo de TEMPO por zona, seis temporadas: 9–15 % (media 11.5 % con τ = 2 h, 12.3 % con 4 h); perfil horario 16.5–18.6 %; sin una estación del oriente 8.2–8.3 %; viento ±20° 4.5 / 14.6 %. |
| **Usuario** | Equipo de inventario de emisiones (revisor del reparto espacial); autoridad ambiental (CU3) como lector. |
| **Frecuencia** | 1 a 2 veces al año (cada actualización del inventario o cuando cambia el viento de referencia). |
| **Alternativa** | Mejor que nada, peor que un inventario con aforos: el único contraste independiente por zona es del satélite, con incertidumbre de ±5 puntos por el viento. |
| **Decisión que cambia** | Pedir que el inventario revise el reparto del oriente (de 19 % a un orden de 8–15 %), no el nivel total; priorizar aforos y factores de flota en Ecatepec, Nezahualcóyotl y Texcoco. |
| **Costo de llevarlo a producto** | ~3 días: zonas de divergencia en `nox_ml.validation.divergence` con pruebas; operación sin costo adicional (ya corre `flux-divergence`). Una tabla municipal real del inventario costaría pedirla a SEDEMA. |
| **Veredicto** | **Seguir con condiciones.** (1) Decir "el oriente es 8–15 % de la emisión vial, no 19 %" y no "7 %": el 7 % es la media de un modelo cuya dirección de viento mueve la cifra ±5 puntos. (2) Comparar con el inventario municipal de SEDEMA, no con el prior de OSM. (3) Definir el oriente como los tres municipios, no como la columna este del dominio. |

## Lo que faltó

- El inventario municipal con NOₓ vehicular por alcaldía y municipio (el PDF solo trae la flota); sin él, el 19 % es el prior de la propia inversión.
- Perfil horario y por clase de Ecatepec, Nezahualcóyotl y Texcoco (Infovial solo cubre 26 corredores de la CDMX).
- Sensibilidades con E5b en otras temporadas (solo se corrió nov–dic 2023, 6 de 8 corridas; no se movió la frontera de la zona).
- Un giro del viento por hora (el giro de ±20° es uniforme) y la divergencia con la zona definida por los municipios.
- Las estaciones tienen casi nulo efecto: conviene entender por qué (el modelo parece dominado por TEMPO en el reparto espacial).

## Cómo reproducir

```bash
# 1. La cifra (inversión y prior)
uv run python notebooks/exploraciones/inventory_east/shares.py
# 2. Prueba 1, divergencia por zona (viento ×1 y ×2), salida en out/flux_zones_w*.csv
uv run python notebooks/exploraciones/inventory_east/flux_zones.py 1.0
uv run python notebooks/exploraciones/inventory_east/flux_zones.py 2.0
# 3. Pruebas 2 y 4, Infovial
uv run python notebooks/exploraciones/inventory_east/infovial_east.py
# 4. Prueba 3, una corrida de ~10 min cada una (en serie, con nice)
C=configs/experiments/pinn_puff_nonneg.yaml
S=notebooks/exploraciones/inventory_east/sensitivity.py
for a in "base" "drop CHO" "drop MON" "drop ACO" "rotate 20" "rotate -20"; do set -- $a; nice -n 10 uv run python $S $1 $C $2; done
```

Salidas en `notebooks/exploraciones/inventory_east/out/`. No se tocó `results/runs/`.

## Borrador de reporte para un equipo de inventario (una página)

**Asunto: el reparto espacial de la emisión vial en el oriente de la ZMVM parece sobrestimado**

**Qué encontramos.** Con tres fuentes independientes del inventario (estaciones de calidad del aire, columnas de NO₂ del satélite TEMPO y un modelo de transporte), la fracción de la emisión vial de NOₓ que corresponde al oriente de la zona metropolitana (la columna este de la ciudad, que incluye Ecatepec, Nezahualcóyotl y Texcoco) sale **entre 7 y 15 %**, frente a **19 %** del reparto espacial que usa el inventario 2018. Solo con el satélite, sin estaciones ni modelo de transporte, sale 9–15 % (promedio 11.5–12.3 %) en seis temporadas de 2023 a 2026. Con estaciones y modelo, 5–10 %.

**Qué no sabemos.** (a) El 19 % lo construimos con el peso de las vialidades de OpenStreetMap escaladas al total vehicular del inventario, porque el documento publicado no da NOₓ vehicular por municipio; pedimos la tabla municipal para compararla de forma directa. (b) El satélite mide todo el NOₓ, no solo el vial. (c) La fracción del oriente cambia entre 4.5 y 14.6 % si se gira la dirección del viento ±20°. (d) Solo la CDMX tiene aforos por hora; para Ecatepec, Nezahualcóyotl y Texcoco no hay perfil horario ni composición de flota.

**Lo que descartamos como explicación.** El perfil horario (en la tarde, las vialidades hacia el oriente pesan 2 puntos menos que en el día completo), la carga pesada (las vialidades orientales tienen igual o menos camiones que el resto) y la fuerza de unas pocas estaciones (quitar cada una de las tres del oriente no cambia el resultado).

**Qué pedimos.** 1) La tabla municipal de NOₓ vehicular por tipo de vehículo y la hora del día. 2) Aforos o flota por tipo de vialidad en Ecatepec, Nezahualcóyotl y Texcoco. 3) Revisar si los factores de actividad (km recorridos) del oriente están sobrestimados; un reparto de 8–15 % en vez de 19 % equivaldría a 1.3 a 2.4 veces menos actividad relativa.

**Qué aporta nuestro lado.** Fracciones por zona con su incertidumbre (viento, temporada, modelo), reproducibles con el código del repositorio (`context/knowledge/inventario_oriente.md`). No sirve para auditar el total de toneladas (el nivel absoluto tiene un factor ×2 de incertidumbre) pero sí el reparto entre zonas.
