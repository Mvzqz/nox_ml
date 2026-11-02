# Ensambles del avance 5: qué aportó cada uno

Fecha: 2026-11-01. Noviembre–diciembre de 2023, error con estación oculta (24 estaciones). Una diferencia entre dos modelos se lee con un bootstrap pareado de estaciones (4,000 réplicas): si su intervalo del 95 % incluye el 0, no es una mejora. Ese criterio reemplaza el "ruido de ±0.5 ppb" de los avances anteriores, que no tenía una fuente verificable. Corridas en `results/runs/`; frentes en [`avance5_frente_a.md`](../management/avance5_frente_a.md) y [`avance5_frente_b.md`](../management/avance5_frente_b.md).

## Resumen

| Ensamble | Base | Error (ppb) | Frente a su base | Domingo ÷ hábil | Placebo | Emisión | Ajuste |
|---|---|---|---|---|---|---|---|
| X1 `bagged_inversion` | E5b | 11.88 | 11.87: +0.01, IC 95 % [−0.03, +0.05] | 0.51 (0.34–0.63) | 1.02 ± 0.12 | Absoluta por zona | 11 min |
| X2 `wind_ensemble` | E2 | 12.37 | 12.50: −0.13, IC 95 % [−0.44, +0.08] | 0.52 (0.42–0.60) | 0.96 ± 0.18 | Absoluta por zona | 14 min |
| X5 `stacking` (anidado) | E5b, E2, E5a | 11.99 | 11.87 (E5b): +0.12, IC 95 % [−0.03, +0.36] | 0.48 | 1.01 ± 0.13 | Relativa | ~18 min |
| X6 `bayes_average` (anidado) | E5b, E2, E5a | 11.87 | Es E5b (peso 1.0) | 0.48 | 1.01 ± 0.12 | Relativa | ~18 min |

**Ningún ensamble mejora a E5b** (ninguna diferencia a su favor es significativa). El modelo final sigue siendo E5b (`pinn_puff`).

## X1: bagging de E5b

- 20 inversiones de E5b sobre remuestreos de días con reemplazo, estratificados por tipo de día para que ningún bag se quede sin domingos (sin estratificar, en los datos sintéticos del contrato, el nivel del domingo de los bags subía a 14,434 t/año frente a 10,800 de la verdad).
- **Se esperaba** que no cambiara el error: la inversión es lineal y gaussiana, y el promedio de los bags es casi el posterior completo. **Salió** igual (11.88 frente a 11.87) con el mismo placebo. Lo que aporta es una incertidumbre de la emisión que incluye cuánto la deciden los días: el intervalo del domingo se ensancha de 0.36–0.62 a 0.34–0.63.
- Búsqueda: `n_bags` y `block_days` (`trials.csv`).

## X2: ensamble de vientos sobre E2

- 8 inversiones de E2, cada una con el viento perturbado hora por hora: dirección 30°, velocidad y capa límite 20 %.
- **Se esperaba** que promediar sobre la incertidumbre del viento suavizara las plumas mal orientadas. **Salió** −0.13 ppb (no significativo), el mismo domingo y un placebo algo más ancho (±0.18 frente a ±0.16).
- **Por qué 30°:** es el error medido de la dirección (28–32°) y el límite superior de la búsqueda (15–30°). Las 4 pruebas al azar de la búsqueda cayeron entre 15 y 24° (12.41–12.47 ppb); la corrida con 30° da 12.37.
- **Por qué aporta poco:** el ruido es independiente de una hora a otra; el error real del viento persiste varias horas, y sobre trayectorias de 24 h el ruido independiente se promedia. Un ruido correlacionado en el tiempo sería más realista.

## X5 y X6: ensambles heterogéneos

Error anidado: los pesos con que se evalúa cada estación se aprenden sin ella (`stacking.nested_oof`). El de `metrics.json` (11.85 ppb para X5) usa los pesos congelados, que ya vieron a la estación evaluada: no es comparable con el de los modelos individuales.

| Bases | `stack` (X5) | `likelihood` (X6) | `pseudo_bma` | Pesos del stacking (todas las estaciones, ± entre estaciones) |
|---|---|---|---|---|
| E5b + E2 | 11.99 | 11.87 | 11.88 | E5b 0.87 ± 0.06, E2 0.13 ± 0.06 |
| E5b + E5a | 11.87 | 11.87 | 11.87 | E5b 1.00, E5a 0.00 |
| E5b + E2 + E5a (las configuraciones) | 11.99 | 11.87 | 11.88 | E5b 0.87 ± 0.06, E2 0.13 ± 0.06, E5a 0.00 |
| Los 6 elegibles (E5b, E2, E5a, E3, E1, E4) | 11.99 | 11.87 | 11.88 | igual: E3, E1 y E4 reciben 0 |

Referencias individuales: E5b 11.87, E5a 12.49, E2 12.50, E3 13.57, E1 13.59, E4 13.59.

- **X5:** el stacking le da 13 % a E2 porque con las 24 estaciones eso baja el error (11.85); evaluado sin la estación, sube (11.99). Es sobreajuste a las estaciones: E2 y E5b usan los mismos datos y el mismo tipo de transporte (puffs), y sus errores están muy correlacionados, así que mezclarlos no compensa errores. E5a (pluma con PINN) no recibe peso.
- **X6:** el promedio bayesiano colapsa a E5b (pesos 1.0 y ~1e-170). Con ~7,500 filas, cualquier ventaja de E5b se vuelve abrumadora en la verosimilitud. La mitigación que pedía la guía, **pseudo-BMA+** (verosimilitud por día con bootstrap bayesiano sobre los días, Yao et al. 2018; `rule="pseudo_bma"`), también da E5b ≈ 1.0: E5b es mejor casi todos los días, no por unas cuantas horas. El promedio bayesiano termina eligiendo un modelo cuando uno domina; mezclar es lo que hace el stacking, y aquí tampoco ayuda.
- Las bases tienen transportes distintos: la emisión de X5 y X6 es relativa (cocientes por tipo de día), sin toneladas ni zonas.

## Lectura

Los ensambles homogéneos (X1, X2) promedian el mismo modelo lineal y dan casi lo mismo; los heterogéneos (X5, X6) combinan modelos cuyo error está dominado por las mismas causas (el viento único del dominio, el fondo, el sesgo del domingo), así que no se compensan. La mejora del sistema tiene que venir de la física y los datos (transporte, fondo, TEMPO), no de combinar los modelos actuales.
