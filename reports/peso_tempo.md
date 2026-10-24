# Peso reducido de TEMPO en la inversión (σ por píxel ×3)

**Resumen.** Desde ahora la inversión le da a TEMPO un tercio del peso por píxel que antes (σ ×3). Con la restricción de tráfico de Infovial, el cociente domingo/hábil pasa de 0.51–0.54 a **0.62–0.65**: queda dentro o en el borde del rango de Infovial (0.65–0.73) y coincide con el estimador normalizado (0.58–0.69). El ajuste a estaciones y la validación con estación retenida no empeoran. Las fuentes puntuales siguen sin poder estimarse por separado; ahora su incertidumbre (±90–220 t/año) es más honesta. Las superobservaciones de 8 km quedan a medio camino (domingo 0.57–0.58) y no se adoptan.

## Por qué

En `fondo_tempo.md` vimos que los residuos de TEMPO tienen un patrón espacial que no se promedia: la desviación de los promedios por celda es 2.6e15 moléculas/cm², frente a los 5e15 supuestos por píxel. La inversión trataba los 78,000 píxeles como errores independientes y le daba a TEMPO mucho más peso del que merece. Ese exceso de peso es lo que tiraba el domingo hacia abajo.

## Qué cambió en el código

| Script | Cambio | Cómo volver a lo anterior |
|---|---|---|
| `scripts/real_check_linear.py` | `SIG_TP = 5e15 × TEMPO_SIGMA_MULT`, con 3 por defecto. Opciones nuevas `--tempo-sigma-mult` y `--superobs-km`, y la función `set_tempo_weight()` | `--tempo-sigma-mult 1` o la variable de entorno `TEMPO_SIGMA_MULT=1` |
| `scripts/pinn/invert.py` | Las mismas dos opciones. Las variantes se guardan con sufijo (`_tp1`, `_so8km`) y no pisan lo que lee la app | `--tempo-sigma-mult 1` |
| `scripts/pinn/export_app.py` | Solo exporta los resultados estándar, sin sufijo | — |

**Superobservaciones** (opcional): promedian los píxeles de TEMPO por celda de N km en cada escaneo. Cada promedio lleva un error σ² = (2.6e15)² + (5e15)²/n, que combina la parte correlacionada con el ruido por píxel.

**Reproducibilidad.** `fondo_tempo.py` y `centrales_pluma_fresca.py` multiplican `SIG_TP` por su cuenta. Para reproducir sus números hay que correrlos con `TEMPO_SIGMA_MULT=1`.

Los resultados anteriores (×1) se conservaron con sufijo:
- `data/processed/pinn/resultados_*_tp1.json`
- `normalizado_*_tp1.parquet`
- `reports/real_check_linear_domain_sin_industria_extras_sigma30_tp1_2023-11-01_2023-12-31.md`

## Resultados

La configuración es la de la opción B: industria agrupada, estaciones extra, viento del dominio, σθ = 30° y restricción de Infovial. Los totales están en t/año.

### Nov–dic 2023

| Variante | Modelo | Domingo/hábil sin restricción | Domingo/hábil con restricción (IC 90 %) | Sábado | Vial hábil | Nonoalco / Valle / AIFA / AICM | r TEMPO | RMSE estaciones (ppb) | LOO (ppb) |
|---|---|---|---|---|---|---|---|---|---|
| TEMPO ×1 (anterior) | Lineal | 0.42 | 0.51 | 0.81 | 39,822 | 266 / 300 / −149 / 62 (±45) | 0.75 | 12.63 | 13.37 |
| TEMPO ×1 (anterior) | PINN | 0.43 | 0.52 | 0.80 | 56,374 | 405 / 499 / −177 / −220 (±70–90) | 0.78 | 12.29 | 12.50 |
| **TEMPO ×3 (estándar)** | Lineal | 0.41 | **0.62** (0.59–0.66) | 0.86 | 41,375 | 416 / 273 / −41 / 84 (±115–140) | 0.74 | 12.46 | 13.38 |
| **TEMPO ×3 (estándar)** | PINN | 0.43 | **0.63** | 0.85 | 59,299 | 84 / 657 / 164 / −214 (±120–220) | 0.78 | 11.85 | 12.36 |
| Superobservaciones 8 km | Lineal | 0.41 | 0.57 | 0.84 | 38,523 | 569 / 174 / −209 / −38 (±95–130) | 0.76 | 12.53 | — |
| Superobservaciones 8 km | PINN | 0.43 | 0.58 | 0.84 | 55,595 | 280 / 377 / −13 / −177 (±105–175) | 0.79 | 12.04 | — |

Con superobservaciones la inversión usa 11,349 observaciones de TEMPO en lugar de 78,227. No se corrió la validación con estación retenida para esa variante.

### Primavera 2024 (15 feb–31 may)

| Variante | Modelo | Domingo/hábil con restricción | Sábado | Vial hábil | Valle | RMSE estaciones (ppb) |
|---|---|---|---|---|---|---|
| ×1 | Lineal / PINN | 0.53 / 0.54 | 0.75 / 0.77 | 24,599 / 33,572 | 258 / 631 | 7.41 / 7.40 |
| **×3** | Lineal / PINN | **0.65 / 0.64** | 0.84 / 0.85 | 24,757 / 33,877 | 247 / 772 | 7.37 / 7.18 |

### Inversión lineal sin restricción

Reporte `real_check_linear_*_sigma30*`, con a priori de centrales de 2018:

| Variante | Domingo/hábil (IC 90 %) | LOO modelo / IDW / híbrido (ppb) | Híbrido < IDW |
|---|---|---|---|
| ×1 | 0.42 (0.34–0.53) | 13.4 / 11.5 / 11.2 | 18 de 24 |
| ×3 | 0.41 (0.34–0.50) | 13.4 / 11.5 / 11.3 | 18 de 24 |
| Superobservaciones 8 km | 0.41 (0.32–0.51) | 13.4 / 11.5 / 11.2 | 18 de 24 |

### Estimador normalizado

No cambia, porque usa solo estaciones:

| Periodo | Lineal | PINN |
|---|---|---|
| Nov–dic 2023 | 0.65 | 0.58 |
| Primavera 2024 | 0.69 | 0.68 |

### Gemelo (nov–dic 2023)

Con ×3 el gemelo pierde algo de información, como era de esperar, porque su ruido sintético sí es independiente por píxel. Errores medianos:

| Prueba | ×1 | ×3 |
|---|---|---|
| Total vial, mismo modelo (lineal→lineal) | ≤ 2 % | 2–3 % |
| Cociente domingo | 1.5 % | 2.2 % |
| Valle de México | 1 % | 4 % |
| Cruce lineal ↔ PINN, totales | 25–38 % | 22–34 % |
| Cruce lineal ↔ PINN, cocientes | ≤ 4 % | ≤ 4 % |

## Lectura

1. **El domingo con restricción ya concuerda con las otras fuentes.** En ambos periodos y con ambos modelos sale 0.62–0.65, junto al estimador normalizado y a Infovial. Antes TEMPO lo jalaba a 0.51–0.54.
2. **Sin restricción nada cambia** (0.41–0.44). Esto confirma `sesgo_domingos.md`: ese cociente no lo deciden los datos, y bajar el peso de TEMPO no basta para liberarlo.
3. **El ajuste no empeora.** El RMSE en estaciones queda igual o mejora un poco (PINN 12.29 → 11.85 ppb). La validación con estación retenida no cambia (lineal 13.37 → 13.38; PINN 12.50 → 12.36). La correlación con TEMPO tampoco cambia (0.74–0.78).
4. **Las fuentes puntuales siguen sin poder separarse.** Valle sale entre 174 y 772 según el modelo y la variante, AIFA y AICM cambian de signo, y las σ se triplican. Esto confirma que deben reportarse agrupadas (opción B).
5. **Las superobservaciones son la versión más rigurosa, pero no cambian la conclusión.** Su domingo (0.57–0.58) queda entre ×1 y ×3. Se dejan como opción y no se adoptan, porque ×3 es más simple y reproduce el resultado del estimador normalizado.

## App

- Regeneré los datos con `scripts/pinn/export_app.py`; la app ya lee los resultados ×3.
- Probé con `streamlit.testing` las 12 combinaciones de periodo, modelo y tipo de día: ninguna da error.
- Lancé el servidor sin interfaz: respondió HTTP 200 en `/` y en `/_stcore/health`, y después lo detuve.
