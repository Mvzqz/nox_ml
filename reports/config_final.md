# Configuración final: puffs y Ecatepec como región propia

**Qué se decidió.** El transporte estándar de la inversión pasa de la pluma estacionaria a los **puffs**: cada hora de emisión se sigue durante las 6 horas previas, con perfil horario de tráfico y vida química de 4 h (`scripts/puff.py`). Además, **Ecatepec es una región vial propia** (`REGION_SCHEME = "3x3_ecatepec"`, el estándar en `scripts/feasibility_linear.py`). El resto de la configuración no cambia:

- σθ = 30°;
- TEMPO con σ ×3, es decir, un tercio de peso;
- restricción de cociente de Infovial (sábado 0.87, domingo 0.69);
- a priori de centrales de Climate TRACE (Valle 1,600 ± 650, Nonoalco 100 ± 100).

**Por qué.** En `puffs_cdmx.md` los puffs mejoraron:
- la correlación con TEMPO;
- el total vial;
- la estabilidad del estimador normalizado.

Pero en nov–dic 2023 el híbrido empeoraba en dos estaciones de Ecatepec (SAG y XAL). Esas estaciones caían en la región "Centro", cuyo factor vial casi se duplica con puffs. El problema era el proxy vial dentro de una región grande, no el transporte. Se probaron dos esquemas de regiones:

- **3×3 + Ecatepec:** el municipio de Ecatepec es la región 10. Para el modelo, son las celdas de 1 km cuyo centro cae dentro del municipio.
- **Centro partido en dos:** la mitad norte del Centro, que incluye el sur de Ecatepec y el norte de GAM, es la región 10.

Scripts: `scripts/config_final.py` (esquemas y tablas) y `scripts/puffs_cdmx.py` (corridas). Resultados en `data/interim/puffs_cdmx/<periodo>_puff_<esquema>.json`.

## Resultado

**Ecatepec como región propia es el mejor de los dos esquemas en nov–dic 2023, y en primavera 2024 es neutro.** Partir el Centro en dos no ayuda: SAG empeora (28.3 ppb).

| Métrica (nov–dic 2023 / feb–may 2024) | Pluma, 3×3 (estándar anterior) | Puffs, 3×3 | **Puffs, 3×3 + Ecatepec (nuevo estándar)** |
|---|---|---|---|
| LOO híbrido (ppb) | 11.2 / 6.7 | 12.3 / 6.8 | **11.7 / 6.8** |
| LOO modelo (ppb) | 13.4 / 8.0 | 13.6 / 7.8 | **12.9 / 7.8** |
| LOO híbrido sin SAG y XAL (ppb) | 10.5 / 6.6 | 10.5 / 6.4 | **10.5 / 6.5** |
| SAG híbrido (ppb; IDW 10.7 / 4.3) | 17.5 / 5.5 | 27.1 / 9.0 | **20.7 / 8.9** |
| r con TEMPO, emisión fija | 0.50 / 0.50 | 0.65 / 0.58 | **0.65 / 0.58** |
| r con TEMPO, invertido | 0.75 / 0.73 | 0.83 / 0.80 | **0.83 / 0.80** |
| Vial hábil / inventario | 42 % / 25 % | 75 % / 45 % | **76 % / 46 %** |
| Domingo libre (sin restricción) | 0.42 / 0.43 | 0.49 / 0.53 | **0.49 / 0.53** |
| Domingo con restricción | 0.62 / 0.65 | 0.63 / 0.65 | **0.64 / 0.66** |
| Estimador normalizado, domingo (IC 90 %) | 0.65 (0.56–0.76) / 0.70 (0.61–0.79) | 0.61 (0.53–0.70) / 0.68 (0.61–0.77) | **0.61 (0.53–0.69) / 0.68 (0.61–0.76)** |
| Placebo ± (mitad del ancho) | 0.26 / 0.12 | 0.19 / 0.11 | **0.19 / 0.11** |
| CV del estimador en hábiles | 0.35 / 0.27 | 0.26 / 0.23 | **0.26 / 0.23** |

**Lectura**
- **Ecatepec separado** recupera la mayor parte de lo que los puffs perdían en nov–dic:
  - el LOO del modelo es el mejor de todas las configuraciones (12.9 ppb);
  - el híbrido baja de 12.3 a 11.7 ppb;
  - SAG baja de 27.1 a 20.7 ppb.
- **No alcanza del todo a la pluma en el híbrido de nov–dic** (11.7 frente a 11.2 ppb). La diferencia sigue en SAG y XAL; sin ellas, las tres configuraciones empatan (10.5 ppb). XAL no mejora con ningún esquema (18.7 frente a 13.9 ppb de IDW): es un problema local de esa estación, no de la región.
- **En primavera 2024 todo empata** en estaciones, con diferencias ≤ 0.1 ppb.
- **Lo que ganan los puffs se conserva intacto:**
  - TEMPO 0.50 → 0.65;
  - total vial 42 → 76 % del inventario;
  - placebo ±0.26 → ±0.19;
  - CV 0.35 → 0.26.
- **El domingo queda igual** con la restricción (0.64–0.66), con el estimador normalizado (0.61–0.68) y frente a Infovial (0.65–0.73).
- **Identificabilidad:** Ecatepec se distingue de sus vecinos. Su α hábil es 0.55 ± 0.02 en nov–dic y 0.47 ± 0.02 en primavera. La correlación a posteriori más fuerte es Centro–Ecatepec, de −0.18 (nov–dic) y −0.28 (primavera). Es aceptable, pero indica que agregar regiones más chicas en el norte tiene poco margen.
- **El Centro cambia de significado.** Sin Ecatepec, su α sube (0.97 → 1.39 en nov–dic). Lo que antes se promediaba con Ecatepec ahora queda solo en el Centro. Hay que comparar α entre esquemas con cuidado.

## Fuentes puntuales: siguen sin identificarse

Valle de México, Nonoalco, AICM y AIFA cambian mucho entre esquemas con los mismos datos. Eso confirma que no son identificables por separado: se reportan como parte de su región, no como números propios.

| t/año, nov–dic 2023 | Pluma 3×3 | Puffs 3×3 | Puffs + Ecatepec |
|---|---|---|---|
| Valle de México | 313 ± 130 | 425 ± 128 | 685 ± 126 |
| Nonoalco | 235 ± 78 | 430 ± 77 | −4 ± 79 |
| AICM | 69 ± 141 | 646 ± 135 | −144 ± 139 |
| AIFA | −36 ± 123 | 53 ± 121 | 45 ± 122 |

## Tablas completas

Bootstrap de 200 días completos. «Valle»…«AIFA» en t/año. LOO = predecir cada estación con las demás.
### nov–dic 2023

| Configuración | LOO modelo / IDW / híbrido (ppb) | Híbrido < IDW | Sin SAG y XAL: modelo / IDW / híbrido | SAG híbrido / IDW | XAL híbrido / IDW | r TEMPO (fija / invertido) | Vial hábil / inventario |
|---|---|---|---|---|---|---|---|
| Pluma, 3×3 (estándar anterior) | 13.4 / 11.5 / 11.2 | 17 de 24 | 13.0 / 11.4 / 10.5 | 17.5 / 10.7 | 15.9 / 13.9 | 0.50 / 0.75 | 42% |
| Puffs, 3×3 | 13.6 / 11.5 / 12.3 | 15 de 24 | 12.2 / 11.4 / 10.5 | 27.1 / 10.7 | 18.8 / 13.9 | 0.65 / 0.83 | 75% |
| Puffs, 3×3 + Ecatepec | 12.9 / 11.5 / 11.7 | 15 de 24 | 12.1 / 11.4 / 10.5 | 20.7 / 10.7 | 18.7 / 13.9 | 0.65 / 0.83 | 76% |
| Puffs, Centro partido en dos | 13.7 / 11.5 / 12.5 | 15 de 24 | 12.1 / 11.4 / 10.5 | 28.3 / 10.7 | 19.2 / 13.9 | 0.65 / 0.83 | 76% |

| Configuración | Domingo libre (IC 90 %) | Con restricción | Normalizado (IC 90 %) | Placebo ± | CV hábiles | Valle | Nonoalco | AICM | AIFA | Correlación a posteriori más negativa entre regiones |
|---|---|---|---|---|---|---|---|---|---|---|
| Pluma, 3×3 (estándar anterior) | 0.42 (0.34–0.54) | 0.62 | 0.65 (0.56–0.76) | 0.26 | 0.35 | 313 ± 130 | 235 ± 78 | 69 ± 141 | -36 ± 123 | – |
| Puffs, 3×3 | 0.49 (0.43–0.58) | 0.63 | 0.61 (0.53–0.70) | 0.19 | 0.26 | 425 ± 128 | 430 ± 77 | 646 ± 135 | 53 ± 121 | -0.14 |
| Puffs, 3×3 + Ecatepec | 0.49 (0.43–0.57) | 0.64 | 0.61 (0.53–0.69) | 0.19 | 0.26 | 685 ± 126 | -4 ± 79 | -144 ± 139 | 45 ± 122 | -0.18 |
| Puffs, Centro partido en dos | 0.49 (0.41–0.58) | 0.64 | 0.61 (0.54–0.70) | 0.19 | 0.26 | 526 ± 128 | 131 ± 79 | 8 ± 141 | 30 ± 121 | -0.23 |

Factor vial α de día hábil por región (± σ a posteriori):

- Puffs, 3×3: SO 0.49 ± 0.02, S 0.83 ± 0.01, SE 0.40 ± 0.03, O 1.00 ± 0.01, Centro 0.97 ± 0.02, E 0.51 ± 0.04, NO 0.87 ± 0.03, N 0.66 ± 0.02, NE 0.58 ± 0.07
- Puffs, 3×3 + Ecatepec: SO 0.49 ± 0.02, S 0.78 ± 0.01, SE 0.41 ± 0.03, O 0.95 ± 0.01, Centro 1.39 ± 0.02, E 0.52 ± 0.04, NO 0.86 ± 0.03, N 0.72 ± 0.03, NE 0.62 ± 0.07, Ecatepec 0.55 ± 0.02
- Puffs, Centro partido en dos: SO 0.49 ± 0.02, S 0.79 ± 0.01, SE 0.40 ± 0.03, O 0.99 ± 0.01, Centro-S 1.29 ± 0.03, E 0.51 ± 0.04, NO 0.87 ± 0.03, N 0.71 ± 0.02, NE 0.60 ± 0.07, Centro-N 0.68 ± 0.02

Pares de regiones más correlacionados a posteriori (α hábil):

- Puffs, 3×3: SO–S -0.14, O–NO -0.09, NO–N -0.08
- Puffs, 3×3 + Ecatepec: Centro–Ecatepec -0.18, N–Ecatepec -0.16, S–Centro -0.14
- Puffs, Centro partido en dos: Centro-S–Centro-N -0.23, S–Centro-S -0.16, N–Centro-N -0.15

### feb–may 2024

| Configuración | LOO modelo / IDW / híbrido (ppb) | Híbrido < IDW | Sin SAG y XAL: modelo / IDW / híbrido | SAG híbrido / IDW | XAL híbrido / IDW | r TEMPO (fija / invertido) | Vial hábil / inventario |
|---|---|---|---|---|---|---|---|
| Pluma, 3×3 (estándar anterior) | 8.0 / 7.1 / 6.7 | 14 de 22 | 7.9 / 7.0 / 6.6 | 5.5 / 4.3 | 12.4 / 12.7 | 0.50 / 0.73 | 25% |
| Puffs, 3×3 | 7.8 / 7.1 / 6.8 | 13 de 22 | 7.5 / 7.0 / 6.4 | 9.0 / 4.3 | 12.5 / 12.7 | 0.58 / 0.80 | 45% |
| Puffs, 3×3 + Ecatepec | 7.8 / 7.1 / 6.8 | 12 de 22 | 7.5 / 7.0 / 6.5 | 8.9 / 4.3 | 12.6 / 12.7 | 0.58 / 0.80 | 46% |

| Configuración | Domingo libre (IC 90 %) | Con restricción | Normalizado (IC 90 %) | Placebo ± | CV hábiles | Valle | Nonoalco | AICM | AIFA | Correlación a posteriori más negativa entre regiones |
|---|---|---|---|---|---|---|---|---|---|---|
| Pluma, 3×3 (estándar anterior) | 0.43 (0.32–0.59) | 0.65 | 0.70 (0.61–0.79) | 0.12 | 0.27 | 272 ± 89 | -27 ± 68 | 63 ± 99 | 123 ± 88 | – |
| Puffs, 3×3 | 0.53 (0.46–0.62) | 0.65 | 0.68 (0.61–0.77) | 0.11 | 0.23 | 321 ± 87 | 7 ± 67 | 334 ± 94 | 130 ± 86 | -0.19 |
| Puffs, 3×3 + Ecatepec | 0.53 (0.47–0.63) | 0.66 | 0.68 (0.61–0.76) | 0.11 | 0.23 | 437 ± 87 | -93 ± 69 | 207 ± 97 | 108 ± 87 | -0.28 |

Factor vial α de día hábil por región (± σ a posteriori):

- Puffs, 3×3: SO 0.16 ± 0.01, S 0.40 ± 0.01, SE 0.23 ± 0.02, O 0.58 ± 0.01, Centro 0.56 ± 0.01, E 0.41 ± 0.03, NO 0.65 ± 0.02, N 0.60 ± 0.02, NE 0.60 ± 0.04
- Puffs, 3×3 + Ecatepec: SO 0.16 ± 0.01, S 0.40 ± 0.01, SE 0.23 ± 0.02, O 0.58 ± 0.01, Centro 0.63 ± 0.02, E 0.42 ± 0.03, NO 0.65 ± 0.02, N 0.64 ± 0.02, NE 0.61 ± 0.05, Ecatepec 0.47 ± 0.02

Pares de regiones más correlacionados a posteriori (α hábil):

- Puffs, 3×3: SO–S -0.19, O–NO -0.14, NO–N -0.13
- Puffs, 3×3 + Ecatepec: Centro–Ecatepec -0.28, N–Ecatepec -0.24, SO–S -0.18

## PINN, inversión estándar y app

`scripts/pinn/invert.py` ya usa por defecto **puffs** en el modelo lineal y el esquema **3×3 + Ecatepec**. Se volvió a correr con esa configuración: nov–dic 2023 con `--full` (gemelo, estación retenida y entrenamiento conjunto) y primavera 2024 sin `--full`, igual que antes.

La PINN aprendió solo la pluma estacionaria (`kernel.py`), así que su núcleo sigue siendo pluma, aunque ahora usa las 10 regiones. **La referencia de transporte es el lineal con puffs**, y la PINN queda como contraste de modelo.

| nov–dic 2023 / feb–may 2024 | Lineal antes (pluma, 3×3) | **Lineal ahora (puffs + Ecatepec)** | PINN ahora (pluma, 10 regiones) |
|---|---|---|---|
| Total vial de día hábil (t/año) | 41,375 / 24,757 | **75,744 / 45,191** | 59,240 / 33,816 |
| Domingo ÷ hábil, inversión con restricción | 0.62 / 0.65 | **0.64 / 0.66** | 0.63 / 0.65 |
| Sábado ÷ hábil, inversión con restricción | 0.86 / 0.84 | **0.85 / 0.86** | 0.86 / 0.85 |
| Estimador normalizado, domingo ÷ hábil | 0.65 / 0.69 | **0.62 / 0.68** | 0.58 / 0.68 |
| r con TEMPO, invertido | 0.75 / 0.73 | **0.83 / 0.80** | 0.78 / 0.76 |

**Lectura**
- **El total vial cambia de lado.** Antes el lineal quedaba 30 % abajo de la PINN; ahora queda 28 % arriba en nov–dic y 34 % arriba en primavera. La distancia entre modelos se mantiene en ~30 %, así que los totales siguen siendo solo un orden de magnitud. El rango lineal–PINN de día hábil es ahora 59–76 mil t/año (nov–dic) y 34–45 mil (primavera).
- **Los cocientes no cambian** entre configuraciones ni entre modelos (domingo 0.58–0.68).

**Arreglo en `invert.py`.** La clave del caché de entradas ya incluía el esquema de regiones, pero `main` guardaba la clave vieja, de tres elementos. El entrenamiento conjunto (`--full`) fallaba con `KeyError`; ya está corregido.

**App** (`data/processed/app/`, regenerada con `scripts/pinn/export_app.py`)
- `regiones.geojson` tiene 10 regiones. Ecatepec se dibuja con su **límite municipal real** (156 km²) y los bloques vecinos se recortan con ese límite: suman 3,260 km² sin traslapes. El modelo asigna las celdas de 1 km por su centro, así que el borde del cálculo difiere del dibujo en menos de 1 km.
- **Verificación:**
  - Las 12 combinaciones de periodo, modelo y tipo de día corren sin error con `streamlit.testing.AppTest`, en las pestañas Cambios de emisión, Mapa, Emisiones por región, Contingencias 2024, y Modelo y confianza.
  - `streamlit run` en modo headless respondió HTTP 200 en `/` y en `/_stcore/health`. Después se detuvo.

## Cómo reproducir

```
.venv/bin/python scripts/config_final.py --period nov23 --schemes 3x3 3x3_ecatepec 3x3_centro_norte
.venv/bin/python scripts/config_final.py --period prim24 --schemes 3x3 3x3_ecatepec
.venv/bin/python scripts/config_final.py --report
.venv/bin/python scripts/pinn/invert.py 2023-11-01 2023-12-31 --full
.venv/bin/python scripts/pinn/invert.py 2024-02-15 2024-05-31
.venv/bin/python scripts/pinn/export_app.py
```

Opciones para volver a configuraciones anteriores:
- `--transporte pluma` en `invert.py`: pluma estacionaria.
- `--regiones 3x3` en `invert.py`, o `REGION_SCHEME=3x3`: las 9 regiones originales.

Los resultados anteriores de la app (pluma, 3×3) quedaron en `data/processed/pinn/anterior_pluma3x3/`.
