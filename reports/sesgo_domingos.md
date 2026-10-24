# Sesgo de la caída dominical

Fecha: 2026-10-21. Periodo: nov–dic 2023, tardes de 12 a 17 h. Scripts: `scripts/sunday_diag.py` (diagnóstico), `scripts/sunday_fix.py` (correcciones) y `scripts/sunday_profile.py` (perfil del cociente). Resultados en `data/interim/sunday_diag_days.csv`, `sunday_fix.json` y `sunday_profile.json`. Base de todas las pruebas: industria agrupada, estaciones extra y σθ = 30°.

## Resumen

- **El 0.42 no lo deciden los datos.** Fijamos el cociente domingo/hábil en distintos valores, de 0.42 a 1.0. El ajuste casi no cambia: el RMSE en muestra va de 12.62 a 12.66 ppb y el LOO de 13.38 a 13.41 ppb. El fondo por hora compensa la diferencia: si se fuerza un domingo más alto, el fondo dominical baja de 15 a 12 ppb y el error queda igual. Es el mismo intercambio entre fondo y emisión que hizo fallar el placebo de 2019 (`validacion_2020.md`).
- **El valor de 0.42 sale de los a priori, no de las mediciones.** El fondo tiene a priori 5 ± 10 ppb y la emisión 1 ± 0.5. El intervalo del bootstrap (0.33–0.53) es demasiado estrecho porque supone fijo todo lo que no son datos.
- **Corrección recomendada: no reportar el cociente de la inversión.** En su lugar se reporta el **estimador normalizado por meteorología**, que da **0.65 (IC 90 % 0.55–0.75)**. Está más cerca de lo que esperan los conteos de Infovial, sobre todo si se cuenta el tráfico del día completo (0.65–0.73) y no solo el de la tarde (0.73–0.80).
- **Imponer el cociente de Infovial no empeora la validación.** Con el cociente fijo en 0.80 el LOO queda igual (híbrido 11.22 ppb, 18 de 24 estaciones ganan a IDW). Los datos son compatibles con 0.80, pero no lo confirman.
- Ninguna corrección física mueve el cociente a ~0.8: separar el fondo por tipo de día, atarlo a la emisión, quitar festivos atípicos o modelar el arrastre de la mañana con puffs.

## 1. Diagnóstico: qué dicen las mediciones

Medias de la tarde por tipo de día, en las estaciones que miden NOₓ:

| | Hábil | Sábado | Domingo/festivo | Domingo ÷ hábil |
|---|---|---|---|---|
| NOₓ observado (ppb) | 35.6 | 27.4 | 19.8 | **0.56** |
| Percentil 10 de la hora (≈ fondo) | 18.7 | 15.8 | 11.7 | 0.63 |
| Contraste (media − p10, ≈ señal vial local) | 16.9 | 11.6 | 8.1 | 0.48 |
| Modelo con emisión fija (solo meteorología) | 22.2 | 19.1 | 19.0 | 0.85 |
| Viento del dominio (m/s) | 1.49 | 1.44 | 1.26 | 0.84 |
| Capa límite (m) | 1,241 | 1,387 | 1,439 | 1.16 |
| NOₓ de la mañana, 6–11 h (ppb) | 74.4 | 75.9 | 56.6 | 0.76 |

Lo que muestra la tabla:

- **La meteorología explica poco.** Los domingos del periodo tuvieron una capa límite algo más alta y menos viento. Con emisión fija, el modelo solo espera una baja a 0.85.
- **El NOₓ bajó mucho más: a 0.56.** Por eso el estimador normalizado da 0.56 ÷ 0.85 ≈ 0.65.
- **El fondo también baja en domingo** (p10: 0.63). Tiene sentido: el "fondo" de la tarde es, en buena parte, NOₓ emitido por la misma ciudad horas antes. Por eso no basta con separarlo como si fuera independiente del tráfico.
- **No lo explican pocos días raros.** Los once domingos y festivos tienen un cociente observado ÷ modelo de 0.67 a 1.38, todos por debajo de la mediana de los hábiles (1.72). Los festivos atípicos (20-nov, 24, 25 y 31-dic) no son los extremos.

### Infovial (ene-2017): de qué tráfico hablamos

| Ponderación por clase | Mañana 6–11 h | Tarde 12–17 h | Día completo |
|---|---|---|---|
| Conteo simple | 0.64 | 0.91 | 0.84 |
| Emisión base (C1…C6 = 1, 2, 5, 10, 15, 20) | 0.57 | 0.80 | 0.73 |
| Pesados ×3 | 0.54 | 0.74 | 0.67 |
| Solo C3–C6 | 0.54 | 0.73 | 0.65 |

*(Cociente domingo ÷ hábil.)*

- **El domingo cae sobre todo por la mañana**, cuando circulan muchos menos vehículos (0.54–0.64).
- **El NOₓ de la tarde no es solo tráfico de la tarde.** Con viento de ~1.3 m/s y una cuenca cerrada, buena parte del NOₓ medido a las 12–17 h se emitió en la mañana. Si la comparación se hace contra el tráfico del día completo y se da más peso a los pesados, Infovial espera **0.65–0.73**. Eso concuerda con el estimador normalizado (0.65).
- **Comparar contra 0.80 (solo la tarde) exageraba la discrepancia.**

## 2. Correcciones probadas

| Variante | RMSE LOO modelo / IDW / híbrido (ppb) | Híbrido < IDW | Domingo/hábil (IC 90 %) | Fondo hábil / sáb / dom (ppb) |
|---|---|---|---|---|
| B0. Base | 13.4 / 11.5 / 11.2 | 18 de 24 | 0.42 (0.33–0.53) | 23.3 / 19.2 / 15.0 |
| B1. Sin festivos atípicos (20-nov, 24, 25 y 31-dic) | 13.7 / 11.8 / 11.5 | 18 de 24 | 0.50 (0.39–0.68) | 23.3 / 19.2 / 11.7 |
| B2. Fondo por tipo de día + desviación horaria σ 3 ppb | 14.6 / 11.5 / 11.2 | 19 de 24 | 0.42 (0.33–0.53) | 25.2 / 20.6 / 16.1 |
| B3. Fondo atado a la emisión del tipo de día | 16.2 / 11.5 / 11.3 | 18 de 24 | 0.44 (0.36–0.54) | 6.0 / 5.1 / 5.0 |
| B4. A priori de Infovial fuerte (0.80 ± 0.05 por región) | 13.4 / 11.5 / 11.2 | 18 de 24 | 0.48 (0.40–0.57) | 23.4 / 19.1 / 14.8 |
| P1. Puffs + perfil horario de Infovial por tipo de día | 13.7 / 11.5 / 12.5 | 15 de 24 | 0.50 (0.41–0.58) | 16.8 / 15.0 / 11.6 |
| P2. P1 con vida media química de 12 h (más arrastre de la mañana) | 13.1 / 11.5 / 11.6 | 16 de 24 | 0.52 (0.42–0.60) | 18.0 / 15.9 / 12.3 |
| **Estimador normalizado (observado ÷ modelo con emisión fija)** | — | — | **0.65 (0.55–0.75)**; sin festivos atípicos, 0.66 (0.56–0.78) | incluido |
| Estimador normalizado sobre el contraste (sin fondo) | — | — | 0.56 (0.46–0.66) | excluido |

Qué dice cada prueba:

- **Fondo por tipo de día (B2) y fondo atado a la emisión (B3):** no mueven el cociente. B3 además empeora el LOO del modelo solo. En la base el fondo ya puede bajar en domingo, así que separarlo no aporta.
- **Festivos atípicos (B1):** sube a 0.50, pero el IC se ensancha y el LOO empeora un poco. Explica una parte menor.
- **Arrastre de la mañana con puffs (P1, P2):** sube a 0.50–0.52, en la dirección esperada. Pero los puffs empeoran el LOO, como ya se había visto.
- **A priori de Infovial (B4):** el a priori de ±0.05 apenas mueve el resultado porque, formalmente, cada α tiene una precisión muy alta (σ ≈ 0.01). Esa precisión es ficticia: supone errores independientes hora a hora y no ve el intercambio con el fondo.

## 3. Prueba clave: perfil del cociente

Fijamos α_domingo = c · α_hábil en las 9 regiones y medimos el ajuste para cada c:

| c fijado | RMSE en muestra (ppb) | LOO modelo / híbrido (ppb) | Híbrido < IDW | Fondo hábil / domingo (ppb) |
|---|---|---|---|---|
| libre (sale 0.42) | 12.63 | 13.38 / 11.22 | 18 | 23.3 / 15.0 |
| 0.55 | 12.66 | 13.40 / 11.24 | 18 | 23.6 / 14.1 |
| 0.65 | 12.66 | 13.41 / 11.24 | 18 | 23.8 / 13.5 |
| 0.80 | 12.65 | 13.40 / 11.22 | 18 | 24.3 / 12.7 |
| 1.00 | 12.62 | 13.38 / **11.17** | 18 | 25.0 / 12.0 |

- **Entre 0.42 y 1.0 el ajuste cambia menos de 0.05 ppb.** Las mediciones no distinguen "el domingo emitió la mitad" de "emitió lo mismo y el fondo bajó".
- **El cociente de la inversión es, en la práctica, no identificable** con un fondo libre por hora. Lo mismo vale para comparar dos periodos (placebo de 2019).
- Esto corrige lo que decía `mejoras.md`: los datos **no** jalan con fuerza lejos de Infovial. El a priori de 0.80 no movía el resultado porque el modelo tenía una precisión formal irreal, no porque las mediciones lo rechazaran.

## 4. Qué hacer

1. **Para cambios entre tipos de día o entre periodos, reportar el estimador normalizado**, no el cociente de la inversión. Esto ya era la recomendación tras la validación de 2020. Domingo: **0.65 (0.55–0.75)**. Sábado: 0.89 (0.68–1.16).
2. **Comparar contra la referencia correcta:** el tráfico del día completo ponderado por emisión (Infovial 0.65–0.73), no solo el de la tarde. Con esa referencia, el sesgo queda dentro del IC.
3. **Si se usa la inversión, imponer el cociente de tráfico como restricción** (Infovial, o aforos de 2023 cuando lleguen). No cuesta ajuste y libera a la inversión para lo que sí determina: la distribución espacial entre regiones.
4. **Para que la inversión mida el cociente por sí misma, hay que romper el intercambio fondo–emisión.** Opciones:
   - un fondo con a priori independiente: estaciones a barlovento o rurales, o un modelo regional (AQFS-Mex);
   - TEMPO con más peso o con más píxeles por hora;
   - un modelo de transporte que lleve el arrastre de horas previas sin pagarlo en LOO, como un WRF de 1 km.
5. **Química (efecto fin de semana en NOₓ → NOz) no probada.** La tarde dominical tiene más O₃ y OH, lo que acorta la vida del NOₓ y bajaría algo el cociente observado. Es un efecto secundario frente al intercambio con el fondo.

**Fuera de alcance, para quien corresponda:** `mejoras.md` ("Lo que no se resolvió") y `caso_de_uso.md` citan el cociente de la inversión (0.31–0.51) como "sesgo de magnitud por el viento". Según esta prueba, la causa principal es la falta de identificabilidad del fondo, no el viento, y el número a citar es el del estimador normalizado.
