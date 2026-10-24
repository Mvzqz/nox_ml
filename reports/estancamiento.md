# Sesgo del estimador normalizado en días estancados

Fecha: 2026-10-23. Prueba 2 de `plan_validacion.md`. Scripts: `scripts/estancamiento_base.py`, `_comun.py`, `_diagnostico.py`, `_evaluar.py`, `_val2020.py`, `_contingencias.py`. Resultados en `data/interim/estancamiento_*.json` y `estancamiento_horario*.parquet`.

## Resumen

- **El sesgo no tiene el signo que se suponía.** Con la configuración estándar (puffs de 24 h, vida química por OH, zonas `admin_grupos`, capa límite ERA5 + MERRA-2), el placebo "estancado" da **0.94 (90 %: 0.86–1.02)**, ya dentro de ±15 %. El "15–35 % de más" del plan es el cociente entre los días reales de contingencia y ese placebo (1.24 aquí; 1.25 en `resultados.json`). Es el exceso sin explicar de las contingencias, no un error de los días estancados.
- **Lo que sí existe es una pendiente.** Los días sin contingencia del cuartil más estancado salen en **0.86** (hábiles 0.89) y los del cuartil más ventilado en **1.21**. La concentración observada responde a la meteorología modelada con un exponente de ~0.5 en vez de 1: el modelo exagera el efecto del viento débil (concentración ∝ 1/viento).
- **Causa principal: el viento, no la capa límite.** No es la acumulación de la mañana, ni el arrastre de días previos, ni la recirculación. La capa límite pesa poco, aunque los radiosondeos delatan una capa demasiado alta en ~10 % de las tardes.
- **Corrección barata que pasa:** subir el piso de la rapidez del viento (`U_MIN`) de 1.0 a **2.0 m/s**. Deja el placebo estancado en 0.97 (cuartil estricto) y 0.96 (definición del script), el aleatorio igual (0.98), el domingo en 0.67 / 0.69, y la validación 2020 mejora (−41 % frente a −38 %).
- **Efecto en contingencias:** el estimador baja de 1.16 a **1.09 (IC 90 % 1.00–1.16)** en todos los días y de 1.10 a **1.05 (0.95–1.15)** en hábiles. La conclusión no cambia: no se ve una baja de emisión. El exceso sobre el placebo estancado baja de 1.24 a 1.13.
- **Límite:** `U_MIN` se escogió con feb–may 2024, los mismos meses de la prueba. Con nov 2023–ene 2024 la pendiente no cambia (−0.27 a −0.26). Falta confirmar con otro año.

## Qué se hizo

| Paso | Detalle |
|---|---|
| Modelo | El estándar actual, sin industria, con emisión fija: puffs de 24 h, vida química `oh_24h`, σθ = 30°, `admin_grupos`, capa límite `pbl_2023_2024.parquet`. Se suman todas las zonas viales (el script de contingencias suma solo 9). Serie horaria de 6 a 17 h locales, 1 nov 2023–31 may 2024 (2,342 horas, ~1 min) |
| Índice de un día | observado ÷ modelo de la tarde (12–17 h), dividido entre el mismo cociente en sus referencias (mismo día de la semana, ±4 semanas, sin contingencia ni día siguiente). Es el placebo de un solo día: 1 = sin cambio |
| Días | 88 días sin contingencia, 1 feb–31 may 2024 |
| Estancado | Cuartil más bajo de viento × capa límite de la tarde (22 días, 17 hábiles). No depende del modelo, así que no hay sesgo de selección por el denominador |
| Radiosondeos | AICM 76679 a 06 y 18 h locales. Solo traen temperatura en superficie y a 700 hPa (~900 m sobre el suelo), así que dan la estabilidad Δθ = θ700 − θsuperficie, no la altura de la capa |

La definición "estancado" del script de contingencias no es un cuartil: son los días con ventilación por debajo de la de la mediana de los días de contingencia, **75 de 88**. Por eso su placebo (0.94) se parece al del azar (0.98) y no muestra la pendiente.

## Diagnóstico

Índice (media geométrica) por cuartil de ventilación, días sin contingencia:

| Cuartil | Viento (m/s) | Capa límite (m) | Índice | Índice, hábiles | Mañana (7–11 h) | Día previo | Recirculación R | Δθ18 > 0 |
|---|---|---|---|---|---|---|---|---|
| 1 (más estancado) | 1.1 | 2,290 | **0.86** | **0.89 (0.80–0.91)** | 0.99 | 1.01 | 0.60 | 10 % |
| 2 | 1.6 | 2,400 | 0.96 | 0.98 | 0.91 | 0.89 | 0.64 | 15 % |
| 3 | 2.0 | 2,390 | 1.00 | 0.98 | 1.04 | 1.06 | 0.72 | 14 % |
| 4 (más ventilado) | 2.8 | 2,430 | **1.21** | 1.14 | 1.01 | 1.04 | 0.79 | 0 % |

R = |viento vectorial medio| ÷ rapidez media entre 6 y 16 h (1 = flujo constante, bajo = recirculación). Δθ18 > 0: a las 18 h el aire entre el suelo y 700 hPa es estable.

Regresiones de log(índice) sobre log(ventilación modelada relativa) (`lmet`) y otras variables:

| Hipótesis | Variable | Coeficiente (t) | R² | Veredicto |
|---|---|---|---|---|
| Base | lmet | −0.48 (−6.3) | 0.32 | La observación responde con exponente 0.52 |
| Viento y capa límite por separado | log viento / log capa límite | +0.36 (6.3) / +0.60 (3.2) | 0.32 | Domina el viento (varía 0.40 frente a 0.12 de la capa límite) |
| Acumulación de la mañana | índice de la mañana | −0.06 (−0.8) | 0.32 | **No.** Sin relación; en el cuartil estancado la mañana sale en 0.99 |
| Arrastre, en el modelo | ventilación del día previo | −0.06 (−0.8) | 0.32 | **No** |
| Arrastre, con puffs de 48 h en vez de 24 h | – | – | – | **No**: la serie es igual a la base (pendiente −0.48, mismo placebo) |
| Persistencia del error del día previo | log índice del día previo | +0.19 (3.0) | 0.38 | Real pero secundario, y no es modelable sin usar el observado de ayer |
| Racha de días estancados seguidos | 0 / 1 / 2+ días previos | índice 1.01 / 0.96 / 0.92 | – | **No**: más días seguidos no suben el índice |
| Recirculación | R | −0.22 (−2.3) | 0.36 | Débil; se anula (−0.05) al agregar Δθ18 y el día previo |
| Capa límite alta (radiosondeo 18 h) | Δθ18 | +0.08 por K (4.4) | 0.44 | **Sí, en parte**: en 10 % de las tardes la capa real es de menos de ~900 m y el modelo dice ~2,650 m (r = 0.12 entre Δθ18 y la capa modelada) |
| Estabilidad nocturna (radiosondeo 6 h) | Δθ06 | 0.00 (0.1) | 0.32 | **No** |

La pendiente cambia de una época a otra: nov–dic 2023 (ERA5) da exponente 0.69, enero 1.03, feb 0.68, mar 0.48, abr 0.35. No es solo la capa límite rellenada con MERRA-2.

## Correcciones probadas

Cada fila es una corrida completa del modelo (salvo las empíricas). Placebos con 300 sorteos.

| Corrección | Índice cuartil estancado / ventilado | Estricto hábil (IC 90 %) | Pendiente (t) | Placebo estancado (script) | Placebo azar | Domingo nov–dic / feb–may | Contingencias todos / hábiles |
|---|---|---|---|---|---|---|---|
| **Base (estándar)** | 0.86 / 1.21 | 0.89 (0.80–0.91) | −0.48 (−6.3) | 0.94 (0.86–1.02) | 0.98 (0.91–1.07) | 0.65 / 0.69 | 1.16 / 1.10 |
| Capa límite con tope 1,500 m | 0.86 / 1.19 | 0.88 | −0.49 | 0.91 | 0.96 (0.88–1.06) | 0.63 / 0.68 | 1.15 / 1.08 |
| Capa límite con tope 1,000 m | 0.85 / 1.16 | 0.88 | −0.47 | 0.92 | 0.96 | 0.59 / 0.67 | 1.16 / 1.09 |
| Capa límite encogida a la mitad hacia su climatología | 0.86 / 1.20 | 0.88 | −0.47 | 0.94 | 0.98 | 0.58 / 0.68 | 1.15 / 1.09 |
| Capa límite escalada con Δθ18 del radiosondeo (0.20/K) | 0.85 / 1.28 | 0.87 | −0.48 | 0.93 | 1.00 (0.91–1.08) | 0.70 / 0.67 | 1.16 / 1.10 |
| Puffs de 48 h (arrastre) | 0.86 / 1.20 | 0.89 | −0.48 | 0.94 | 0.98 | 0.64 / 0.69 | 1.17 / 1.10 |
| Piso de viento 1.5 m/s | 0.90 / 1.13 | 0.93 | −0.37 (−4.1) | 0.95 | 0.99 | 0.66 / 0.69 | 1.12 / 1.07 |
| **Piso de viento 2.0 m/s** | **0.94 / 1.07** | **0.97 (0.88–0.99)** | **−0.26 (−2.3)** | **0.96 (0.90–1.03)** | **0.98 (0.92–1.07)** | **0.67 / 0.69** | **1.09 / 1.05** |
| Piso de viento 2.5 m/s | 0.96 / 1.02 | 0.99 | −0.18 | 0.96 | 0.98 | 0.67 / 0.68 | 1.08 / 1.06 |
| Piso de viento 3.0 m/s | 0.98 / 0.98 | 1.01 | −0.16 | 0.96 | 0.98 | 0.67 / 0.67 | 1.08 / 1.06 |
| Piso 2.0 + capa límite con Δθ18 (0.10/K) | 0.93 / 1.09 | 0.96 | −0.22 | 0.96 | 0.99 (0.93–1.06) | 0.69 / 0.68 | 1.09 / 1.05 |
| Exponente empírico γ = 0.52 (ajustado en feb–may) | 0.92 / 0.99 | 0.95 | 0.00 | 0.95 | 0.96 (0.89–1.04) | **0.59** / 0.67 | 1.09 / 1.05 |
| Exponente empírico γ = 0.73 (ajustado antes de feb) | 0.89 / 1.08 | 0.92 | −0.21 | 0.94 | 0.97 | **0.61** / 0.68 | 1.12 / 1.07 |

- **La capa límite no es la palanca.** Ninguna de las cuatro variantes de capa límite mueve la pendiente (−0.47 a −0.49). La escala con el radiosondeo sí baja la dispersión de los índices (0.233 a 0.227–0.230), pero empeora el cuartil ventilado y la variabilidad de los hábiles (CV 0.29 frente a 0.25).
- **El arrastre tampoco.** Duplicar la memoria de los puffs no cambia nada.
- **El exponente empírico se descarta.** Corrige las contingencias igual, pero saca el domingo de nov–dic de la ventana de tráfico (0.59–0.61 frente a 0.65–0.73), porque γ no es el mismo en todas las épocas.
- **El piso de viento actúa donde está el error.** Con 1 m/s de piso, los vientos débiles producen concentraciones modeladas muy altas que la atmósfera real no tiene (el viento vectorial medio del dominio subestima la rapidez de transporte cuando hay recirculación). Con 2 m/s, la pendiente baja a la mitad, la desviación de los índices a 0.199 (de 0.233) y el CV de los hábiles a 0.22 / 0.18 (de 0.25 / 0.20).

## Criterios para el piso de 2.0 m/s

| Criterio | Antes | Con 2.0 m/s | Pasa |
|---|---|---|---|
| Placebo estancado centrado en 1 ± 15 % | 0.94 (script); 0.86–0.89 (cuartil estricto) | 0.96 (script); 0.97 (cuartil estricto) | Sí |
| Placebo aleatorio no empeora | 0.98 (0.91–1.07), ancho 0.16 | 0.98 (0.92–1.07), ancho 0.15 | Sí |
| Domingo 0.65 frente a 0.65–0.73 de tráfico | 0.65 (nov–dic) / 0.69 (feb–may) | 0.67 / 0.69 | Sí |
| Confinamiento 2020 (−40 a −60 % esperado) | hábil −38 %, fin de semana −27 % | hábil −41 %, fin de semana −42 % | Sí, mejora |
| Placebo 2019 (esperado 1.00) | hábil 1.01, fin de semana 1.15 | hábil 0.90, fin de semana 0.94 | Sí (±10 %) |

Validación 2020 con el modelo de pluma estacionaria de `val2020_linear.py`, reconstruido sin inversión (`estancamiento_val2020.py`), fase 3 frente a base:

| Piso | 2020 hábil | 2020 fin de semana | 2019 hábil | 2019 fin de semana |
|---|---|---|---|---|
| 1.0 m/s | 0.62 | 0.73 | 1.01 | 1.15 |
| 1.5 m/s | 0.62 | 0.65 | 0.94 | 1.02 |
| **2.0 m/s** | **0.59** | **0.58** | **0.90** | **0.94** |
| 2.5 m/s | 0.57 | 0.55 | 0.88 | 0.89 |
| 3.0 m/s | 0.56 | 0.52 | 0.87 | 0.88 |

La reconstrucción con 1.0 m/s no coincide exactamente con `val2020_ratio.json` (0.67 y 0.78 en 2020; 1.03 y 1.18 en 2019), porque esas series se generaron antes de los últimos cambios de `feasibility_linear.py`. Se compara dentro de la misma reconstrucción. Con pisos mayores el placebo de 2019 baja de 1 en hábiles (0.87–0.90), así que 2.0 es un buen compromiso.

## Contingencias 2024 con la corrección

Serie nueva (puffs, `admin_grupos`), 500 réplicas.

| Grupo | Días | Base (IC 90 %) | Piso 2.0 m/s (IC 90 %) | Piso 2.0 ÷ placebo estancado |
|---|---|---|---|---|
| Todos | 23 | 1.16 (1.06–1.24) | **1.09 (1.00–1.16)** | 1.13 |
| Hábiles | 14 | 1.10 (0.99–1.18) | **1.05 (0.95–1.15)** | 1.09 |
| Fin de semana / festivo | 9 | 1.23 (1.12–1.34) | **1.11 (1.00–1.21)** | – |
| Fechas +1 día, todos | 23 | 1.10 (1.00–1.18) | 1.05 (0.96–1.14) | 1.09 |

- **Qué explicaba el exceso.** Los días de contingencia no eran estancados: su ventilación modelada era 0.94 de la de sus referencias (más ventilados). La pendiente por sí sola predice un índice de 1.01 para ellos. El observado es 1.09, así que queda un exceso sin explicar de ~8 % (5.8 % si se agrega Δθ18).
- **Lectura.** Sigue sin verse una baja de emisión en las tardes de contingencia. El sesgo residual (1.05–1.09) es menor que antes y compatible con el persistente error del día previo (las contingencias duran 2–4 días; el índice del día previo es 1.19 frente a 1.05 en días normales).
- **Ya no hay motivo para el aviso de "15–35 %"** tal como está escrito en el plan. Debe cambiar por: el placebo estancado queda en 0.94–0.97 y los días ventilados salen altos.

## Límites

- **El piso de 2.0 m/s se escogió con feb–may 2024**, el mismo periodo de la evaluación. Se probó una rejilla de tres valores (1.5, 2.0, 2.5; con 3.0 como extremo). En nov 2023–ene 2024 la pendiente no cambia (−0.27 con 1.0 m/s; −0.26 con 2.0 m/s), así que no hay evidencia independiente de la mejora fuera de la primavera. Conviene repetir con 2023.
- **Solo se probó el estimador normalizado.** El piso también cambia la inversión completa, la comparación con TEMPO y el LOO; no se evaluaron aquí.
- **Es un parámetro empírico.** Representa que el viento vectorial medio del dominio no es la rapidez de transporte cuando hay recirculación. Una solución más física sería usar la rapidez escalar de las estaciones, que no se probó.
- **Capa residual nocturna.** No se pudo probar de noche, porque la serie cubre solo 6–17 h. En la mañana no se ve el efecto, y el radiosondeo de las 6 h (Δθ06) no se relaciona con el índice.
- **Radiosondeos.** Solo tienen temperatura en superficie y 700 hPa; no permiten medir la altura de la capa, solo si es menor a ~900 m.
- **Muestras pequeñas.** 88 días, 22 por cuartil, 17 hábiles en el cuartil estancado. Los intervalos del cuartil estricto son anchos (0.88–0.99).
- **Fechas de contingencia** siguen sin verificarse con la CAMe.

## Para adoptarlo

Fijar `U_MIN = 2.0` en `feasibility_linear`, `puff` y `puffs_cdmx` antes de construir el Jacobiano; `estancamiento_base.py umin20` lo hace en las tres. Ningún script existente se modificó.

## Validación en invierno e inversión completa

Fecha: 2026-10-23. Scripts nuevos: `scripts/estancamiento_invierno.py` (series horarias por variante), `_invierno_eval.py` (tablas por temporada) y `_inversion.py` (inversión estándar con una variante). Resultados en `data/interim/estancamiento_horario_inv_*.parquet`, `estancamiento_invierno_eval.json` y `estancamiento_inversion_<variante>_<periodo>.json`.

**Decisión: se adopta `U_MIN = 2.0` como estándar** (con la opción de volver a 1.0). El tope de la capa límite en 1,500 m queda como opción, no como estándar.

### 1. Por qué no corregía en invierno

Misma serie horaria (puffs de 24 h, `admin_grupos`), días sin contingencia. Invierno = 8 nov 2023–31 ene 2024 (sin 20 dic–7 ene); primavera = feb–may 2024. Cuartiles de viento × capa límite dentro de cada temporada.

- **El viento débil es lo normal en invierno:** 76 % de las horas de la tarde tienen < 2 m/s (60 % en primavera). El piso de 2.0 m/s deja casi plana la respuesta del modelo al viento, y lo que queda de la pendiente (−0.26) ya no viene del viento.
- **Regresión del error sobre viento y capa límite de la tarde (con piso 2.0):** invierno, viento −0.10 (t −1.4), capa límite **+0.43 (t 4.5)**; primavera, viento +0.14 (t 2.5), capa límite +0.76 (t 4.4). La concentración observada responde a la capa límite con un exponente de ~0.2–0.6, no 1 como supone el modelo. Con piso 1.0 esto se escondía detrás del viento.
- Resultado: en invierno, con piso 2.0, el cuartil ventilado queda en **1.15** (antes 1.25) pero la dispersión de los índices **empeora** (0.268 frente a 0.246).

### 2. Alternativas físicas (elegir con una temporada, evaluar en la otra)

Índice del día ÷ referencias por cuartil (estancado / ventilado), pendiente de log(índice) sobre log(ventilación modelada) y dispersión (sd del log). Domingo = estimador normalizado de la serie fija.

| Variante | Invierno: pend. (t), q1 / q4, sd | Primavera: pend. (t), q1 / q4, sd | Domingo nov–dic / feb–may |
|---|---|---|---|
| Base (piso 1.0) | −0.27 (−3.8), 0.93 / 1.25, 0.246 | −0.48 (−6.3), 0.86 / 1.21, 0.233 | 0.65 / 0.69 |
| Piso 1.5 | −0.25 (−3.1), 0.95 / 1.19, 0.251 | −0.37 (−4.1), 0.90 / 1.13, 0.208 | 0.66 / 0.69 |
| **Piso 2.0** | −0.26 (−2.9), 0.97 / 1.15, 0.268 | −0.26 (−2.3), 0.94 / 1.07, 0.199 | 0.67 / 0.69 |
| Piso 2.5 | −0.29 (−2.9), 0.98 / 1.11, 0.285 | −0.18 (−1.3), 0.96 / 1.02, 0.202 | 0.67 / 0.68 |
| Rapidez √(u² + 1.5²) (meandro) | −0.24 (−2.9), 0.95 / 1.19, 0.252 | −0.37 (−3.7), 0.90 / 1.11, 0.212 | 0.65 / 0.69 |
| Rapidez √(2·u) (concentración ∝ u^−0.5) | −0.23 (−2.9), 0.95 / 1.20, 0.243 | −0.39 (−4.2), 0.88 / 1.12, 0.214 | 0.64 / 0.69 |
| Piso 2.0 + capa límite ≤ 1,500 m | −0.20 (−2.1), 0.99 / 1.12, 0.251 | −0.25 (−2.5), 0.92 / 1.06, 0.192 | 0.65 / 0.67 |
| Piso 2.0 + capa límite ≤ 1,000 m | −0.06 (−0.6), 1.03 / 1.07, 0.236 | −0.23 (−2.3), 0.92 / 1.05, 0.190 | 0.61 / 0.67 |
| Piso 2.0 + capa límite^0.7 | +0.01 (0.1), 1.02 / 1.09, 0.227 | −0.22 (−2.0), 0.93 / 1.06, 0.194 | 0.62 / 0.68 |
| Piso 2.0 + capa límite^0.5 | +0.22 (2.0), 1.06 / 1.06, 0.217 | −0.21 (−1.9), 0.92 / 1.05, 0.191 | 0.60 / 0.68 |
| Piso 1.5 + capa límite^0.5 | +0.08 (0.9), 1.04 / 1.10, 0.207 | −0.34 (−3.8), 0.89 / 1.11, 0.202 | 0.59 / 0.68 |

(Capa límite^p = 1000^(1−p)·capa^p m.)

- **Las formas suaves del viento (meandro, u^−0.5) no ayudan:** se comportan como un piso de ~1.5 y ni en invierno ni en primavera pasan al ventilado ±15 % con margen. Ninguna alternativa solo de viento corrige el invierno.
- **Lo que corrige el invierno es la capa límite**, coherente con la regresión. Las compresiones fuertes (≤ 1,000 m, ^0.5, ^0.7) llevan la pendiente a ~0 en invierno, pero bajan el domingo de nov–dic a 0.59–0.62, fuera del rango de Infovial (0.65–0.73). Con base en eso se descartan.
- **Elegida con el invierno solamente:** entre las que pasan placebos (±15 %) y no mueven el domingo (≥ 0.64), la que más reduce la pendiente es **piso 2.0 + capa ≤ 1,500 m** (el tope ya existía como variante de la prueba original). En primavera, que no se usó para elegirla, queda 0.92 / 1.06, igual que el piso 2.0 solo (el tope no cambia nada ahí). Elegida con la primavera, el piso 2.0 también pasa en invierno, pero con el cuartil ventilado en 1.146, al límite.
- **Contingencias 2024 (serie fija):** piso 2.0 da 1.09 todos / 1.05 hábiles; con tope 1,500, 1.09 / 1.04. Placebo estancado 0.96 y 0.94; aleatorio 0.98 y 0.97.
- **Validación 2020 (fase 3 contra base, pluma sin inversión):**

| Variante | 2020 hábil / fin de semana | Placebo 2019 hábil / fin de semana |
|---|---|---|
| Piso 1.0 | 0.62 / 0.73 | 1.01 / 1.15 |
| Piso 2.0 | 0.59 / 0.58 | 0.90 / 0.94 |
| Piso 2.0 + capa ≤ 1,500 m | 0.53 / 0.55 | **0.84 / 0.85** |

  El tope baja el placebo de 2019 a 0.84, fuera de ±15 %. Es la razón principal para no adoptarlo.

### 3. Inversión completa estándar

Lineal, puffs, `admin_grupos`, vida química OH de 24 h, TEMPO ×1/3, restricción de cociente (`vida_quimica.py --completo` equivalente; `estancamiento_inversion.py`), bootstrap de 200 días.

| Métrica | Base nov–dic | Piso 2.0 | Piso 2.0 + tope 1,500 | Base feb–may | Piso 2.0 | Piso 2.0 + tope 1,500 |
|---|---|---|---|---|---|---|
| LOO modelo / IDW / híbrido (ppb) | 12.44 / 11.51 / 11.04 | 12.35 / 11.51 / 10.87 | 12.32 / 11.51 / 10.86 | 7.93 / 7.07 / 6.86 | 7.83 / 7.07 / 6.76 | 7.67 / 7.07 / 6.71 |
| Híbrido < IDW | 17 de 24 | 17 de 24 | 17 de 24 | 14 de 22 | 16 de 22 | 17 de 22 |
| r con TEMPO, fija / invertido | 0.68 / 0.84 | 0.69 / 0.84 | 0.69 / 0.84 | 0.64 / 0.81 | 0.63 / 0.80 | 0.63 / 0.80 |
| Domingo libre | 0.46 | 0.49 | 0.49 | 0.52 | 0.52 | 0.52 |
| Domingo restringido | 0.64 | 0.65 | 0.65 | 0.66 | 0.66 | 0.66 |
| Domingo, estimador normalizado | 0.65 | 0.66 | 0.64 | 0.69 | 0.69 | 0.68 |
| Total vial hábil (t/año; % del a priori) | 39,004 (39 %) | 53,535 (54 %) | 53,519 (54 %) | 26,802 (27 %) | 34,815 (35 %) | 34,895 (35 %) |
| Placebo dentro de la temporada (±) | 0.19 | 0.20 | 0.20 | 0.09 | 0.08 | 0.10 |
| CV del estimador en hábiles | 0.25 | 0.23 | 0.22 | 0.20 | 0.18 | 0.20 |

- **LOO:** no empeora en ninguna (el híbrido mejora 0.1–0.2 ppb; muy por debajo del umbral de 0.3 ppb). El IDW no cambia, así que el híbrido gana en más estaciones en primavera (14 → 16 de 22).
- **TEMPO y domingo:** sin cambio relevante (r ±0.01; domingo restringido 0.64–0.66, libre un poco más cerca de Infovial en invierno: 0.46 → 0.49).
- **El total vial sube 37 % en invierno y 30 % en primavera.** Es el efecto esperado: con piso 2.0 el modelo diluye más con vientos débiles y hacen falta más emisiones para igualar lo observado. Se pasa de 39 % y 27 % a 54 % y 35 % del inventario vial a priori; la inversión queda más cerca del inventario. Cualquier cifra absoluta publicada antes cambia en esa proporción; los cocientes (domingo, sábado) no.
- **Total por zona (t/año, hábil, base → piso 2.0), nov–dic / feb–may:** CDMX Centro 3,800 → 6,002 / 2,388 → 3,383; CDMX Norte 6,724 → 8,993 / 2,922 → 3,767; Tlalnepantla 5,275 → 7,364 / 3,570 → 4,830; Ecatepec 2,523 → 3,109 / 2,246 → 2,864; Cuautitlán–Tepotzotlán 5,317 → 6,749 / 4,904 → 5,931; Neza–Chimalhuacán 1,329 → 1,100 / 1,531 → 1,780. El aumento no es uniforme: Centro y Oriente suben ~50–60 % en invierno, Norte y Tlalnepantla 35–40 %, Ecatepec y Cuautitlán 20–25 %, y Neza–Chimalhuacán baja en invierno. Con el tope de 1,500 m las zonas cambian < 3 % respecto del piso 2.0 solo.
- **Placebos entre temporadas (estimador normalizado, estaciones):** abr–may ÷ feb–mar 1.01 (base), 0.99 (piso 2.0), 0.90 (con tope); nov–dic ÷ feb–may 0.87, 0.87 y 1.12. El tope arregla el cociente invierno/primavera en estaciones, pero no en TEMPO (1.32 → 1.43) ni en el total vial (1.49 → 1.58), y empeora el interno de primavera (0.90). El problema invierno contra primavera de `vida_quimica.md` sigue abierto; no se reportan cambios entre temporadas.

### 4. Criterio de adopción

| Criterio | Piso 2.0 | Piso 2.0 + tope 1,500 m |
|---|---|---|
| Placebos estancado y ventilado ±15 % en ambas temporadas | Sí (0.97 / 1.15 invierno, 0.94 / 1.07 primavera); el ventilado de invierno queda al límite | Sí, con margen (0.99 / 1.12; 0.92 / 1.06) |
| LOO sin empeorar > 0.3 ppb | Sí (mejora 0.1–0.2) | Sí |
| Domingo | Sí | Sí |
| Validación 2020 | Sí (−41 % / −42 %; placebo 2019 0.90 / 0.94) | Placebo 2019 0.84 / 0.85, fuera de ±15 % |

El piso 2.0 pasa todo; el tope no pasa la validación 2020 y se eligió con el mismo invierno que se evalúa, así que queda como opción (`PBL_MAX=1500` o `PBL_MAX` en el entorno). Límites que se mantienen:

- El invierno sigue con pendiente −0.26 y dispersión mayor que la base; el piso 2.0 mejora la primavera y solo aprueba por poco el invierno. La corrección completa del invierno pasa por la capa límite (la observación responde con exponente < 1) y falta un criterio independiente (radiosondeos o perfiles) para fijarla sin sobreajustar.
- Solo hay dos temporadas de 2023–2024; falta repetir con otro año.
- La contingencia sigue sin verse: 1.09 (1.00–1.16).

### 5. Cambios en el código

- `feasibility_linear.py`: `U_MIN` por defecto 2.0 (variable de entorno `U_MIN=1.0` para volver), función `speed()` que usan la pluma (`plume`), los puffs (`puff.py`, `puffs_cdmx.py`) y el núcleo PINN (`pinn/model.py`); opciones `U_TURB`, `U_POW` y `PBL_MAX` (sin efecto por defecto).
- `pinn/invert.py`: opción `--u-min` (estándar 2.0; `--u-min 1.0` reproduce lo anterior). Resultados anteriores en `data/processed/pinn/anterior_umin1/`.
- Scripts de otros análisis que importan `feasibility_linear` (p. ej. `val2020_linear.py`) ahora usan 2.0 salvo que se fije `U_MIN=1.0`; `estancamiento_base.py base` sigue reproduciendo el 1.0 original porque lo fija explícitamente en las variantes `umin*`, pero la variante `base` ahora toma 2.0: para la serie original use `U_MIN=1.0`. Los demás reportes no se regeneraron.
- Se corrió `scripts/pinn/invert.py` con el nuevo estándar en nov–dic 2023 y 15 feb–31 may 2024 (sobrescribe `resultados_*.json` y `normalizado_*.parquet`), se regeneró la app con `scripts/pinn/export_app.py` y arrancó en modo headless (HTTP 200, `/_stcore/health` ok); el proceso se detuvo.
