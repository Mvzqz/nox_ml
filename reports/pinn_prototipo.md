# Prototipo PINN y app (opción B)

Fecha: 2026-10-21.
- Scripts: `scripts/pinn/kernel.py`, `scripts/pinn/model.py`, `scripts/pinn/invert.py` y `scripts/pinn/export_app.py`.
- App: `app/app.py`.
- Resultados: `data/processed/pinn/` y `data/processed/app/`.

## Resumen

> **Nota (2026-10-21):** las cifras de esta sección y de «Resultados» son de la inversión **sin** restricción de cociente. La versión actual ata los cocientes al tráfico de Infovial y usa el estimador normalizado como salida principal; ver «Actualización (2026-10-21)» más abajo.

- **La PINN funciona y reproduce la inversión lineal donde importa.**
  - **Cocientes por tipo de día:** son casi iguales. Domingo ÷ hábil da 0.43 en la PINN contra 0.42 en la lineal; sábado ÷ hábil, 0.76 contra 0.79.
  - **Ajuste:** es igual o algo mejor. El error con estación retenida baja de 13.4 a 12.5 ppb y la correlación con TEMPO sube de 0.75 a 0.78.
  - **Nivel absoluto:** es 42 % mayor (58 % del inventario contra 41 %).
- **El nivel absoluto depende de la física elegida; los cocientes no.**
  - En el gemelo cruzado (datos simulados con un modelo e invertidos con el otro), el total vial se equivoca 26–36 %. El cociente domingo ÷ hábil solo se equivoca 3–4 %.
  - Esto confirma la regla del proyecto: reportar cambios relativos (por tipo de día, entre periodos), no toneladas absolutas.
- **El entrenamiento conjunto no aporta en este problema.** La pérdida combinada (ecuación + estaciones + a priori) no mejora el ajuste a datos frente a congelar la red y resolver la estadística exacta.
  - Con poco peso de la física (λ = 0.1), la red se deforma (error contra la solución exacta hasta 19 %) sin ganar ajuste.
  - Con λ = 10, la física se conserva, pero las emisiones apenas cambian.
- **Costo en CPU:** de minutos.
  - Entrenar la red: 18 min, con varios procesos de otros análisis compitiendo por la máquina.
  - Invertir un periodo de dos meses: ~2 min.
  - La red se entrena una vez y sirve para cualquier periodo; aquí se reutilizó en primavera de 2024 sin reentrenar.
- **La app de Streamlit corre**, con mapa, emisiones por región con IC, selector de periodo, modelo y tipo de día, y la pestaña «Clima vs emisión».

## Qué hace

### 1. La red aprende una pluma, no un mapa

Con un viento uniforme por hora (el mismo supuesto de la inversión lineal en modo `domain`), la ecuación de advección–difusión 2D es lineal. Además, no cambia si se traslada o se gira. La columna que deja una fuente en un receptor solo depende de:

- la posición relativa en el marco del viento: a lo largo (A) y transversal (C);
- de γ = L / (|u| τ), que combina rapidez del viento y vida media.

La red F(A, C, γ) aprende esa **función de Green** solo con física. Para cualquier inventario, el campo es la suma de plumas sobre las celdas viales de 1 km y las fuentes grandes.

**Ecuación** (adimensional, L = 10 km):

> ∂F/∂A − ε ∇²F + γ F = δσ(A, C), con ε = κ/L = 0.15

**Términos:**
- K = κ|u| con κ = 1,500 m, que reproduce el ancho de la pluma con σθ = 30° a ~10 km. El serpenteo del viento queda representado como difusión.
- δσ es una fuente gaussiana de 1.5 km: el modelo no resuelve escalas menores.
- τ = 12 h, lo que equivale a casi sin pérdida dentro del dominio, como la pluma lineal. La red acepta τ de 4 a 12 h sin reentrenar.

**Pérdida:** residuo de la ecuación (relativo al valor local), más F ≈ 0 a 10 km contra el viento y a 40 km de lado. Se usan puntos de colocación concentrados cerca de la fuente y en la pluma.

**Arquitectura y entrenamiento:**
- Red: 4 capas de 64, tanh y salida exp(·), positiva y simétrica en C.
- Entrenamiento: 3,000 pasos de Adam (750 s) y 15 rondas de L-BFGS (315 s).
- La pérdida bajó de 8×10⁻³ (solo Adam, estancada) a 1.4×10⁻³.

**Vertical:** se usa la misma altura de mezcla efectiva que la pluma, min(√(π/2)·σz, capa límite). Así la comparación aísla el cambio de física horizontal.

### 2. Validación de la red contra la solución exacta

Con coeficientes constantes existe solución exacta: un núcleo de Bessel K₀ convolucionado con la fuente. Se usó para verificar la red.

| γ | Situación típica | Error relativo mediano | Percentil 90 | Error de masa | Centro a 20 km: red / exacto |
|---|---|---|---|---|---|
| 0.04 | viento 6 m/s, τ 12 h | 4.1 % | 8.9 % | +3.9 % | 0.48 / 0.46 |
| 0.10 | 2.3 m/s, 12 h | 3.5 % | 6.9 % | −2.9 % | 0.39 / 0.40 |
| 0.25 | 1 m/s, 12 h | 6.6 % | 15 % | −4.9 % | 0.28 / 0.30 |
| 0.60 | 1 m/s, 4–5 h | 5.2 % | 15 % | +6.4 % | 0.17 / 0.15 |

Errores de 4–7 % son aceptables para un prototipo. Son mucho menores que el error por la dirección del viento (28–32°).

**Antes de L-BFGS el error era de 10–20 %.** Adam solo no basta; hay que refinar.

### 3. Inversión

La red entra en la misma inversión lineal de las pruebas de mejoras. `model.jacobian_hour_pinn` tiene la firma de `feasibility_linear.jacobian_hour`, así que se conecta a `real_check_linear.build` sin modificarlo.

**Configuración (S2 de `improve_real`):**
- Industria agrupada en las regiones viales.
- Estaciones extra que solo miden NO₂, y viento METAR.
- Viento uniforme del dominio; σθ = 30° en la pluma lineal.
- Estado: 4 fuentes grandes, α vial por región (3×3) × tipo de día, y un fondo por hora (estaciones y TEMPO).

La lineal reproduce exactamente S2: domingo ÷ hábil 0.42, r TEMPO 0.75 y error con estación retenida 13.4 ppb.

## Resultados: nov–dic 2023 (366 horas, 8,564 datos de estación, 78,227 píxeles TEMPO)

### Datos reales, red congelada

| | Lineal (pluma σθ 30°) | PINN |
|---|---|---|
| Total vial, días hábiles (t/año equivalente) | 40,627 (41 % del inventario) | 57,532 (58 %) |
| Sábado ÷ hábil (IC 90 %) | 0.79 (0.64–1.05) | 0.76 (0.62–0.97) |
| **Domingo ÷ hábil (IC 90 %)** | **0.42 (0.32–0.56)** | **0.43 (0.35–0.55)** |
| r estaciones / RMSE en muestra | 0.78 / 12.6 ppb | 0.79 / 12.3 ppb |
| **RMSE con estación retenida** | 13.4 ppb | **12.5 ppb** |
| r TEMPO | 0.75 | 0.78 |
| Valle de México (Acolman), a priori 2,615 t/año | 316 ± 45 | 521 ± 78 |
| Nonoalco, a priori 277 | 326 ± 46 | 535 ± 71 |
| AICM / AIFA, a priori 500 c/u | 123 / −154 | −77 / −194 |

**Qué muestra la tabla:**
- **El patrón regional es parecido.** α por región en días hábiles:
  - Lineal: SO −0.04, Centro 0.73, NO 0.65, E 0.15.
  - PINN: SO 0.12, Centro 0.99, NO 0.80, E 0.26.
  - La PINN sube todo en proporción, porque su pluma es más ancha y diluye más cerca de la fuente.
- **Los aeropuertos siguen sin ser identificables con ningún modelo** (valores negativos).
- **Acolman queda muy por debajo del a priori en ambos modelos**, lo que confirma que el a priori está alto.
- **El sesgo del domingo persiste igual en ambos** (0.42–0.43 contra 0.80 de Infovial). No es un problema de la física horizontal.

**Sin TEMPO, todo se desestabiliza.** Usando solo estaciones:
- domingo ÷ hábil da 0.82 en la lineal y 0.67 en la PINN;
- Acolman sale en 5,643 y 2,609 t/año.

TEMPO es lo que separa fondo de emisión, en ambos modelos.

### Estimador normalizado por meteorología (observado ÷ modelo con emisión fija)

| | Lineal | PINN | Referencia Infovial |
|---|---|---|---|
| Sábado ÷ hábil (IC 90 %) | 0.90 (0.69–1.18) | 0.83 (0.69–1.00) | 0.95 |
| Domingo ÷ hábil (IC 90 %) | 0.65 (0.56–0.76) | 0.58 (0.49–0.68) | 0.80 |
| Concentración observada, domingo ÷ hábil | 0.56 | 0.56 | |
| Efecto del clima solo, domingo ÷ hábil | 0.86 | 0.96 | |

El estimador normalizado queda más cerca de Infovial que la inversión completa (0.58–0.65 contra 0.42). Sigue siendo bajo, y es conservador por construcción (ver `validacion_2020.md`).

### Gemelo: emisiones conocidas, 20 réplicas

- **Verdad simulada:**
  - α regional ~ LN(0, 0.4);
  - tipo de día 1 / 0.9 / 0.7;
  - fuentes grandes = a priori × LN(0, 0.5);
  - fondos = los inferidos con datos reales.
- **Ruido:** 10 ppb en estaciones y 3×10¹⁵ en TEMPO, sin error de viento. Es optimista: aísla el efecto de equivocarse de física.

| Datos simulados con → invertidos con | Error total vial (hábil) | Error sábado÷hábil | Error domingo÷hábil | Error α mediano | Error Acolman |
|---|---|---|---|---|---|
| lineal → lineal | 0 % | 0.3 % | 0.3 % | 0.8 % | 1 % |
| PINN → PINN | 1 % | 0.3 % | 0.3 % | 1.2 % | 4 % |
| **lineal → PINN** | **36 %** | **1 %** | **4 %** | 39 % | 32 % |
| **PINN → lineal** | **26 %** | **1 %** | **3 %** | 26 % | 51 % |

- **Con la misma física, recupera todo.** Pero ese es el «crimen inverso»: no dice nada sobre datos reales.
- **Con la física equivocada, los niveles absolutos fallan 25–40 % y los cocientes siguen bien (≤ 4 %).** La diferencia entre la lineal y la PINN con datos reales (+42 %) cae justo en ese rango. Los dos modelos son igual de defendibles, y el nivel absoluto tiene una incertidumbre de física de ese tamaño.

### Entrenamiento conjunto (solo estaciones; la red también se ajusta)

- **Pérdida:** χ² de estaciones + a priori + λ · residuo de la ecuación.
- **Arranque:** la solución congelada de solo estaciones.
- **Optimización:** 150 pasos de Adam con lotes de 6 horas.

| | Red congelada (solución exacta) | Conjunto λ = 10 | Conjunto λ = 0.1 |
|---|---|---|---|
| Total vial hábil (t/año) | 77,413 | 84,091 | 81,666 |
| Domingo ÷ hábil | 0.67 | 0.62 | 0.63 |
| RMSE estaciones (ppb) | 11.6 | 12.9 | 12.7 |
| Error de la red contra la exacta, después | 3.5–6.6 % | 3.6–7.5 % | 1.3–19 % (masa −12 %) |
| Tiempo | 17 s | 286 s | 200 s |

**Lectura:** en un problema lineal, congelar la red y resolver la estadística exacta es mejor y mucho más barato. Con lotes y Adam, el ajuste conjunto no llega al óptimo exacto en 150 pasos. Darle libertad a la red (λ bajo) la aleja de la física sin ganar ajuste.

**Dónde sí tendría sentido el entrenamiento conjunto:**
- estimar parámetros físicos inciertos, como κ, τ o un factor de capa límite;
- con química no lineal;
- con un campo de viento variable, donde no hay superposición de plumas.

### Primavera 2024 (15 feb–31 may; misma red, sin reentrenar)

| | Lineal | PINN |
|---|---|---|
| Total vial hábil (t/año) | 25,263 (25 % del inventario) | 34,356 (35 %) |
| Sábado ÷ hábil | 0.66 (0.50–0.94) | 0.67 (0.53–0.86) |
| Domingo ÷ hábil | 0.44 (0.33–0.59) | 0.45 (0.32–0.58) |
| Normalizado, domingo ÷ hábil | 0.69 (0.61–0.79) | 0.68 (0.59–0.80) |
| r TEMPO | 0.74 | 0.76 |

Los cocientes coinciden otra vez entre modelos. El nivel absoluto cae a ~60 % del de nov–dic en ambos. Lo más probable es el supuesto de mezcla con la capa límite profunda de primavera (MERRA-2 corregido, `capa_limite.md`), no una baja real de 40 % del tráfico. **No hay que comparar toneladas entre temporadas**; para eso está el estimador normalizado con placebo de la misma temporada.

## Actualización (2026-10-21): restricción de cociente y estimador normalizado como salida principal

Aplica lo aprendido en `sesgo_domingos.md`: en la inversión los datos de estaciones no fijan el cociente domingo/hábil (el fondo por hora absorbe la diferencia), así que el cociente se toma del tráfico medido y los cambios se reportan con el estimador normalizado.

### Restricción de cociente por tipo de día (nueva opción por defecto en `invert.py`)

- **Qué es:** un a priori que ata la emisión vial de cada región en sábado y domingo/festivo a la del día hábil: α_dt,r ≈ r_dt · α_hábil,r. Se usa el tráfico de Infovial del **día completo ponderado por emisión** (no solo la tarde, porque el NOₓ de la mañana se sigue midiendo por la tarde): **sábado 0.87 (rango 0.84–0.89), domingo 0.69 (rango 0.65–0.73)**, según cuánto pesen los pesados.
- **σ = 0.02 por región (casi fija).** Con σ = 0.08 la restricción apenas movía el domingo (0.42 → 0.45), porque la verosimilitud supone errores independientes y es demasiado confiada. La incertidumbre real del cociente es el rango de Infovial y se reporta aparte. `--sin-restriccion` reproduce la versión anterior; el entrenamiento conjunto no la usa.

| nov–dic 2023 | Sábado ÷ hábil | Domingo ÷ hábil (IC 90 %) | RMSE estaciones | Estación retenida | r TEMPO |
|---|---|---|---|---|---|
| Lineal, sin restricción | 0.79 | 0.42 | 12.63 | 13.38 | 0.751 |
| Lineal, con restricción | 0.81 | 0.51 (0.44–0.60) | 12.63 | 13.37 | 0.750 |
| Lineal, solo estaciones, con restricción | 0.87 | 0.69 | 12.38 | — | — |
| PINN, sin restricción | 0.76 | 0.43 | 12.30 | 12.51 | 0.783 |
| PINN, con restricción | 0.80 | 0.52 (0.48–0.60) | 12.29 | 12.50 | 0.782 |

| feb–may 2024 | Sábado ÷ hábil | Domingo ÷ hábil | RMSE estaciones | r TEMPO |
|---|---|---|---|---|
| Lineal, sin / con restricción | 0.66 / 0.75 | 0.44 / 0.53 | 7.40 / 7.41 | 0.738 / 0.736 |
| PINN, sin / con restricción | 0.67 / 0.77 | 0.45 / 0.54 | 7.40 / 7.40 | 0.764 / 0.763 |

Lo que muestran:
- **La restricción no empeora nada:** el ajuste a estaciones, el error con estación retenida y la correlación con TEMPO quedan iguales (diferencias ≤ 0.01).
- **Con solo estaciones, el cociente queda exactamente en el de Infovial**: las estaciones no se oponen.
- **Lo que jala el domingo hacia abajo es TEMPO.** Con TEMPO incluido el domingo queda en 0.51–0.54 aun con la restricción casi fija: 78 mil píxeles con errores supuestos independientes pesan más que el a priori. Es coherente con `placebo_tempo.md`, donde el contraste crudo de TEMPO da domingo 0.50–0.67. Puede ser real (TEMPO pasa ~13–14 h y ve la columna, no la superficie) o un artefacto (química del NO₂, fondo de columna); no está resuelto. Por eso el cociente de la inversión **no** es la salida principal.
- **Totales:** la restricción casi no los cambia en días hábiles (lineal 40,400 → 39,800 t/año eq. en nov–dic). La diferencia lineal ↔ PINN sigue siendo ~40 % (gemelo cruzado: 25–37 % en el total, ≤ 3 % en el cociente).

### Estimador normalizado por periodo y modelo (salida principal)

| Periodo | Modelo | Sábado ÷ hábil (IC 90 %) | Domingo ÷ hábil (IC 90 %) |
|---|---|---|---|
| nov–dic 2023 | Lineal | 0.90 (0.69–1.18) | **0.65 (0.56–0.76)** |
| nov–dic 2023 | PINN | 0.83 (0.69–1.00) | 0.58 (0.49–0.68) |
| feb–may 2024 | Lineal | 0.92 (0.79–1.09) | **0.69 (0.61–0.79)** |
| feb–may 2024 | PINN | 0.94 (0.80–1.09) | 0.68 (0.59–0.80) |

Infovial día completo: sábado 0.84–0.89, domingo 0.65–0.73. Los dos periodos y los dos modelos caen en ese rango o cerca (la PINN de nov–dic, algo abajo). Con más domingos (primavera), el IC se estrecha.

### Cambios en la app

- **Nueva pestaña principal «Cambios de emisión»:** domingo y sábado ÷ hábil con el estimador normalizado y su IC 90 %, junto a la referencia de Infovial; confinamiento 2020 (fase 2, hábiles: −37 %); resumen de contingencias 2024; serie diaria observado contra modelo con emisión fija; tabla de todos los periodos y modelos.
- **Nueva pestaña «Contingencias 2024»:** índice por grupo (todos, hábiles, fin de semana), con restricción al día siguiente, placebos con días falsos, tabla por episodio y gráfica diaria con los días de contingencia marcados. Lee `data/interim/contingencias_2024*.json` y `contingencias_2024_hourly.parquet` vía `export_app.py`. La validación 2020 se movió aquí como referencia.
- **«Emisiones por región»:** aviso de que los totales dependen del modelo, con el rango lineal–PINN por tipo de día; los cocientes de la inversión se explican como atados a Infovial.
- **«Modelo y confianza»:** filas con y sin restricción para comparar.
- La pestaña «Clima vs emisión» desaparece: su contenido está en «Cambios de emisión».

**Verificación:** `AppTest` recorrió las 12 combinaciones (2 periodos × 2 modelos × 3 tipos de día) sin excepciones; `streamlit run` en modo headless respondió 200 en `/` y `/_stcore/health` y se detuvo.

## Tiempos (CPU, 1 hilo, máquina compartida con varios procesos más)

| Paso | Tiempo |
|---|---|
| Entrenar la red (Adam + L-BFGS), una sola vez | 18 min |
| Jacobiano de nov–dic (366 h): lineal / PINN | 67 s / 93 s |
| Jacobiano de primavera (642 h): lineal / PINN | 130 s / 169 s |
| Inversión + bootstrap (100) + estación retenida | ~16 s por modelo |
| Gemelo (20 réplicas × 4 combinaciones) | 22 s |
| Entrenamiento conjunto (150 pasos) | 3–5 min |

## Limitaciones

- **Viento uniforme por hora.** Es lo que hace válida la función de Green. Un campo de viento variable (IDW, o WRF de SEDEMA/UNAM) rompe la superposición: habría que pasar a una PINN del campo completo c(x, y, t), mucho más cara (horas de GPU). Es justo lo que haría falta para la opción A.
- **Estado estacionario por hora.** No hay memoria de las horas previas; el modelo de puffs sí la tiene (`puff.py`).
- **Resolución de ~1.5 km.** No resuelve el gradiente junto a una avenida.
- **Química.** Se representa solo como vida media τ.
- **Aeropuertos e industria no identificables**, igual que con la lineal.
- **La red reproduce la solución exacta con 4–7 % de error.** En este problema lineal con viento uniforme, un solucionador clásico (la fórmula exacta o diferencias finitas) haría lo mismo más barato. El valor de la PINN aparece al pasar a física sin solución cerrada; este prototipo deja lista la tubería para ese paso.
- **El sesgo del domingo** (0.42 contra 0.80) es el mismo con ambas físicas. Su causa no está en el transporte horizontal: lo más probable es la mezcla fondo/emisión (ver `validacion_2020.md`).

## Cómo correr

```bash
# 1. red (una vez; ~18 min)
.venv/bin/python scripts/pinn/kernel.py --steps 3000
.venv/bin/python scripts/pinn/kernel.py --resume data/processed/pinn/kernel_adam3000.pt --lbfgs 15
# 2. inversiones (--full agrega gemelo, estación retenida y entrenamiento conjunto)
.venv/bin/python scripts/pinn/invert.py 2023-11-01 2023-12-31 --full
.venv/bin/python scripts/pinn/invert.py 2024-02-15 2024-05-31
# 3. datos de la app y app
.venv/bin/python scripts/pinn/export_app.py
.venv/bin/streamlit run app/app.py      # http://localhost:8501
```

**Pestañas de la app:**
- **Mapa:** regiones coloreadas por α, estaciones, fuentes grandes y vías primarias.
- **Cambios de emisión (principal):** estimador normalizado por tipo de día con IC 90 % y referencia de Infovial, confinamiento 2020, resumen de contingencias y serie diaria.
- **Emisiones por región:** α por región y tipo de día con IC 90 %, totales con el rango lineal–PINN, cocientes y fuentes grandes.
- **Contingencias 2024:** índice por grupo y episodio, placebos y serie diaria.
- **Modelo y confianza:** lineal contra PINN, gemelo y validación de la red.

**Selectores:** periodo, modelo (lineal o PINN) y tipo de día.

**Verificación:**
- `streamlit run` en modo headless respondió 200 en `/` y en `/_stcore/health`, y se detuvo después.
- `AppTest` recorrió las 12 combinaciones de periodo × modelo × tipo de día sin excepciones.

**Dependencias nuevas en `.venv`:** torch 2.14.1 (CPU) y streamlit 1.66.1.
