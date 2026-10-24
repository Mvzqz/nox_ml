# Vida química del NOₓ por mes y hora

**Qué se hizo.** Antes, los puffs perdían NOₓ con una vida fija de 4 h todo el año. Ahora la pérdida depende de la química de cada hora: el NOₓ se convierte en ácido nítrico al reaccionar con el radical OH, y el OH depende del sol, del ozono y de la humedad. Con eso el NOₓ dura ~4 h al mediodía en mayo y ~20 h en diciembre. Además, los puffs se siguen 24 h en vez de 6 h, porque en invierno el NOₓ de la noche anterior todavía cuenta por la tarde.

**Resultado.** El placebo dentro de la primavera **pasa**: con emisiones iguales, abril–mayo frente a febrero–marzo da 1.01 en estaciones (antes 0.85) y 0.94 en TEMPO (antes 0.72). El placebo invierno frente a primavera **no pasa** con ninguna versión. La nueva química **queda como estándar**, porque arregla la primavera, mejora el ajuste y no cambia el domingo ni las contingencias. Comparar invierno contra primavera sigue sin ser válido.

Script: `scripts/vida_quimica.py`. Cambio mínimo en `scripts/puff.py`: `LOSS_RATE` (serie horaria; con `None` se conserva la vida fija de 4 h). Resultados en `data/interim/vida_quimica/`.

## Cómo se estimó la vida (sin ajustarla a los datos que se evalúan)

Pérdida de NOₓ = k(OH + NO₂) · [OH] · (NO₂/NOₓ), con:

- **[OH] ∝ j(O¹D) · O₃ · H₂O**, la producción primaria de OH.
  - j(O¹D) sale del ángulo solar, con la parametrización J1 del Master Chemical Mechanism.
  - O₃, temperatura y humedad son las medianas horarias de SIMAT.
- **Escala:** OH = 6×10⁶ moléculas/cm³ al mediodía de abril de 2024. Es del orden de lo medido en la CDMX en campañas de primavera (MCMA-2003 y MILAGRO 2006). Es un valor aproximado de la literatura y su sensibilidad está abajo.
- **Constantes:** k = 9.3×10⁻¹² cm³/s (JPL, a ~780 hPa) y NO₂/NOₓ = 0.85 (`multifisica_leighton.md`). De noche la pérdida es cero.
- **Calibración:** ningún parámetro se ajustó con el NOₓ ni con TEMPO.

Vida resultante al mediodía (h), en horas: noviembre 15, diciembre 23, febrero 17, marzo 10, abril 6, mayo 4. Explica la caída de primavera: la producción de OH crece ×4 de febrero a mayo (más sol, ×1.8 de ozono, ×1.6 de humedad).

Ese mismo cálculo da una climatología razonable en 2019–2020: 4–5 h de abril a septiembre y 17–23 h en diciembre y enero. La serie está calculada para 2019–2020 y 2023–2024 (`data/interim/vida_quimica_insumos.parquet`); en Los Ángeles no se aplica.

## Validación: placebo entre temporadas

Todo con emisiones fijas, que no cambian entre periodos. Por eso el cociente debería ser ~1.00. Solo días hábiles.

**1. Tamizado rápido (solo estaciones, 7 variantes).** Cociente observado ÷ modelo, relativo a febrero–marzo:

| Variante | Abr–may (IC 90 %) | Nov–dic (IC 90 %) |
|---|---|---|
| Vida fija 4 h, puffs 6 h (estándar anterior) | **0.83** (0.77–0.90) | 0.97 (0.88–1.08) |
| Vida fija 4 h, puffs 24 h | 0.83 (0.77–0.90) | 0.97 (0.87–1.07) |
| Vida por OH, puffs 6 h | 0.93 (0.87–1.01) | 0.87 (0.79–0.97) |
| **Vida por OH, puffs 24 h (nuevo estándar)** | **0.99** (0.92–1.08) | 0.85 (0.77–0.94) |
| Ídem, OH ∝ producción^0.5 | 0.96 (0.89–1.03) | 0.87 (0.78–0.96) |
| Ídem, OH 9×10⁶ / 4×10⁶ | 1.04 / 0.96 | 0.85 / 0.85 |
| Ídem + pérdida extra de 1/12 h | 0.93 (0.86–1.01) | 0.89 (0.81–0.99) |

Puffs más largos con vida fija no cambian nada. Lo que corrige la primavera es la química, y el resultado es poco sensible a la escala de OH.

**2. Inversión completa (estaciones + TEMPO, configuración final).** Misma matriz para cada temporada, pesos por día, solo hábiles:

| Placebo | Vida fija 4 h | Vida por OH |
|---|---|---|
| Abr–may ÷ feb–mar, estimador normalizado en estaciones | 0.85 | **1.01** ✔ |
| Abr–may ÷ feb–mar, TEMPO normalizado (exceso sobre p10) | 0.72 | **0.94** ✔ |
| Abr–may ÷ feb–mar, total vial invertido | 0.70 | 0.87 |
| Nov–dic ÷ feb–may, estimador normalizado en estaciones | 1.09 | 0.87 ✘ |
| Nov–dic ÷ feb–may, TEMPO normalizado | 1.63 | 1.32 ✘ |
| Nov–dic ÷ feb–may, total vial invertido | 1.70 | 1.49 ✘ |

**Lectura de la validación**

- **Primavera:** queda corregida para las comparaciones que importan, el estimador normalizado en estaciones y en TEMPO. El total vial invertido mejora de −30 % a −13 %, pero no llega a cero.
- **Invierno contra primavera:** sigue sin ser comparable con ningún estimador.
  - El de estaciones pasa de +9 % a −13 %, es decir, cambia de signo.
  - TEMPO y el total invertido mejoran, pero siguen 30–50 % arriba.
  - Hay algo más que la química: probablemente la capa límite y la capa residual de invierno (`multifisica.md`, prioridad 2), y el cociente NO₂/NOₓ y el factor de masa de aire de TEMPO en invierno. Mientras no se resuelva, **no se reportan cambios entre invierno y primavera**.
- **Diciembre es ruidoso:** la primera quincena da 0.72 y la segunda, de vacaciones, 0.95.

## Lo que no empeora

| Nov–dic 2023 / feb–may 2024 | Vida fija 4 h | Vida por OH |
|---|---|---|
| LOO modelo / IDW / híbrido (ppb) | 12.9 / 11.5 / 11.7 · 7.8 / 7.1 / 6.8 | 12.3 / 11.5 / **10.8** · 7.8 / 7.1 / 6.7 |
| Híbrido < IDW | 15 de 24 · 12 de 22 | **18 de 24** · 14 de 22 |
| r con TEMPO, emisión fija / invertido | 0.65 / 0.83 · 0.58 / 0.80 | 0.68 / 0.84 · 0.64 / 0.81 |
| Domingo con restricción / libre | 0.64 / 0.49 · 0.66 / 0.53 | 0.63 / 0.47 · 0.66 / 0.53 |
| Estimador normalizado, domingo (IC 90 %) | 0.61 (0.53–0.70) · 0.68 (0.61–0.77) | 0.65 (0.56–0.74) · 0.69 (0.62–0.77) |
| Placebo ± / CV de hábiles | 0.19 / 0.26 · 0.11 / 0.23 | 0.19 / 0.25 · 0.09 / 0.20 |
| Vial hábil / inventario | 76 % · 46 % | 40 % · 27 % |

- **Mejoras:** el ajuste a estaciones mejora; en nov–dic el híbrido pasa a ganarle a IDW en 18 de 24 estaciones. La correlación con TEMPO también sube.
- **Sin cambio:** el domingo y el placebo de días falsos quedan igual.
- **Total absoluto:** baja. Con vida más larga en invierno, la misma emisión explica más concentración. Los totales siguen dependiendo del modelo y no se usan como resultado.
- **Contingencias 2024:** el script del estimador usa la pluma, así que su resultado oficial no cambia. Como verificación, con puffs y modelo fijo en estaciones el cociente contingencia ÷ referencia da 1.05 con vida fija y 1.08 con vida por OH. La conclusión se mantiene: no se ve una baja.
- **Validación 2020:** usa la pluma y compara abril–mayo contra abril–mayo, así que no cambia.

## Qué cambió en el código

- **`scripts/puff.py`:** gancho `LOSS_RATE`, apagado por defecto, para que Los Ángeles y otros scripts no cambien.
- **`scripts/pinn/invert.py`**, que alimenta la app:
  - `--vida-quimica oh` es el estándar: vida por OH y puffs de 24 h, con el perfil horario de tráfico extendido a la noche con Infovial.
  - `--vida-quimica fija4` reproduce la configuración anterior.
  - Si la serie no cubre el periodo, se detiene con un aviso.
- **Costo de cómputo:** los puffs de 24 h multiplican por ~4 el tiempo de los Jacobianos, que tardan 6–27 min por periodo en esta máquina.

## Zonas administrativas como estándar

`REGION_SCHEME` ahora es `"admin_grupos"` por defecto en `scripts/feasibility_linear.py`. Son los 13 grupos de alcaldías y municipios de `zonas_admin.md`, con geometrías en `data/interim/zonas_admin.gpkg`. `--regiones 3x3_ecatepec` reproduce el esquema anterior.

Métricas clave con la configuración final completa: puffs, vida química por OH, σθ = 30°, TEMPO ×1/3, restricción de tráfico y a priori de Climate TRACE.

| Nov–dic 2023 / feb–may 2024 | 3×3 + Ecatepec | **Grupos administrativos** |
|---|---|---|
| LOO modelo / IDW / híbrido (ppb) | 12.3 / 11.5 / 10.8 · 7.8 / 7.1 / 6.7 | 12.4 / 11.5 / 11.0 · 7.9 / 7.1 / 6.9 |
| Híbrido < IDW | 18 de 24 · 14 de 22 | 17 de 24 · 14 de 22 |
| r con TEMPO, emisión fija / invertido | 0.68 / 0.84 · 0.64 / 0.81 | 0.68 / 0.84 · 0.64 / 0.81 |
| Domingo con restricción / libre | 0.63 / 0.47 · 0.66 / 0.53 | 0.64 / 0.46 · 0.66 / 0.52 |
| Estimador normalizado, domingo | 0.65 · 0.69 | 0.65 (0.56–0.74) · 0.69 (0.62–0.77) |
| Placebo ± / CV de hábiles | 0.19 / 0.25 · 0.09 / 0.20 | 0.19 / 0.25 · 0.09 / 0.20 |
| Vial hábil / inventario | 40 % · 27 % | 39 % · 27 % |
| Placebo abr–may ÷ feb–mar (estaciones / TEMPO / total vial) | 1.01 / 0.94 / 0.87 | 1.01 / 0.94 / 0.88 |

**Lectura de la comparación**

- **Empate en casi todo:** igual que en `zonas_admin.md`, ahora con la vida química. El LOO del híbrido es apenas peor (+0.2 ppb), dentro del ruido.
- **Ventaja de los grupos:** cada número corresponde a alcaldías y municipios reconocibles, y la separación CDMX / Estado de México queda limpia.
- **Fuentes puntuales:** siguen sin identificarse. En primavera dan Valle 418 ± 83, AICM 254 ± 92, AIFA 88 ± 83 y Nonoalco 21 ± 70 t/año.

**App.** Se regeneró con los 13 grupos, dibujados con sus límites reales recortados al dominio y con nombres como "CDMX Centro" o "Neza–Chimalhuacán":

- `invert.py` corrió para ambos periodos con el estándar nuevo.
- `export_app.py` dibuja los grupos administrativos con su geometría.

**Verificación de la app:**

- `AppTest` de Streamlit recorrió las 12 combinaciones de selectores (periodo × modelo × tipo de día) sin excepciones.
- Servidor en modo headless: `/_stcore/health` y la página respondieron 200; luego se detuvo.
