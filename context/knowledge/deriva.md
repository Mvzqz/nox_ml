# La deriva lenta de E7: de dónde sale

Fecha: 2026-11-01. Dentro de cada temporada, E7 tiene semanas enteras ±15 % arriba o abajo de lo normal que el clima no explica. Por eso las fichas suman una deriva de 0.15 al rango de las medidas de días seguidos ([fichas.md](fichas.md)), y una medida sostenida de una temporada necesita ~35 % para detectarse. Esta nota busca la causa. Datos: días hábiles normales (sin periodos atípicos ni contingencias) de 7 temporadas, nov–dic 2023 a feb–may 2026 con las lluvias de 2024; 75 semanas con al menos 3 días. Scripts en el scratchpad de la sesión (`drift/`).

## El satélite ve la misma deriva

La deriva de E7 es la dispersión de sus medias semanales menos la que pone el ruido diario. Comparada con la del satélite solo (`nox-ml flux-divergence`), que no usa estaciones ni viento de aeropuertos:

| Temporada | Deriva E7 | Deriva satélite | Correlación semanal E7–satélite |
|---|---|---|---|
| nov–dic 2023 (3 semanas) | 0.11 | 0.15 | −0.01 |
| feb–may 2024 | 0.21 | 0.26 | +0.80 |
| jun–oct 2024 | 0.15 | 0.14 | +0.37 |
| nov–dic 2024 | 0.12 | 0.12 | +0.95 |
| feb–may 2025 | 0.10 | 0.10 | +0.32 |
| nov–dic 2025 | 0.25 | 0.05 | +0.91 |
| feb–may 2026 | 0.12 | 0.16 | +0.83 |

Las dos series ven las mismas semanas altas y bajas en 4 de 7 temporadas, así que la deriva no es, sobre todo, un error de E7. Combinar E7 con el satélite no la quita.

## Qué la acompaña

Correlación de las anomalías semanales (dentro de cada temporada, en logaritmo) con E7 y con el satélite:

| Variable | Con E7 | Con el satélite |
|---|---|---|
| Viento de la tarde | +0.35 | +0.03 |
| Capa de mezcla | +0.30 | −0.23 |
| Viento medio de las 72 h previas (estancamiento) | +0.13 | +0.07 |
| Columna de TEMPO a más de 25 km del centro | +0.45 | +0.37 |
| Percentil 10 de la columna de cada escaneo | +0.40 | +0.61 |
| NO₂/NOₓ de las estaciones | −0.15 | −0.32 |
| Semana de quincena (días 13–17 y 28–2) | −0.02 | +0.12 |

- **Una parte es de E7: el clima mal corregido.** E7 sube en las semanas con más viento y capa de mezcla más alta; el satélite no. El modelo de transporte de E7 baja la concentración modelada con el viento más de lo que baja la observada.
- **La otra parte la comparten E7, el satélite y la columna lejana.** No es la quincena ni el estancamiento de varios días.

## Corregirla

Deriva de E7 después de quitar cada grupo de variables. Los coeficientes se ajustan con las otras seis temporadas, nunca con la evaluada:

| Corrección | Deriva media (7 temporadas) |
|---|---|
| Ninguna | 0.15 |
| Clima (viento, capa de mezcla) | 0.13 |
| Columna lejana | 0.14 |
| Clima y columna lejana | 0.09 |

**La columna lejana no sirve para corregir.** Cae en domingo casi tanto como el centro: 0.61–0.82, frente a 0.52–0.69 del centro. Es decir, a 25 km todavía hay pluma de la ciudad. Corregir con ella le quitaría a una medida real buena parte de su efecto. La única corrección válida es la del clima, y quita poco: de 0.15 a 0.13.

## Lectura

- La deriva que queda la ven dos métodos independientes. Puede ser **variación real de la emisión**, semanas en que la ciudad emite más o menos, o **acumulación regional** que llega desde fuera con la misma dirección. Con el recorte actual de TEMPO, que da ~27 km desde el centro, no se separan: lo que hay a 25 km todavía es ciudad.
- Si es variación real, la deriva no es ruido del método sino el piso de lo que se puede atribuir a una medida sin un grupo de control. Ningún estimador mejor la quita.
- Separarlo pide uno de dos caminos:
  - un recorte de TEMPO más grande (≥ 60–100 km), con columna de fondo realmente regional; es el mismo que pide la vida media del NOₓ ([sesgo_domingo.md](sesgo_domingo.md));
  - un dato semanal de actividad que no sea concentración: congestión, aforos o ventas de combustible.
- La corrección por clima de E7 (de 0.15 a 0.13) se puede agregar a las fichas, pero baja poco el mínimo detectable.

## Con un recorte amplio de TEMPO (2026-11-01)

Se descargó TEMPO con ~65 km más de margen para nov–dic 2023 y 2024 (3 escaneos por día). El fondo regional se midió como la mediana de la columna a 40–80 km del centro del lado de barlovento, adonde la pluma de la ciudad no llega. Es ~1.3 × 10¹⁵, contra 2–4 × 10¹⁵ a sotavento y 1–2 × 10¹⁶ en el centro.

| Temporada | Domingo ÷ hábil: barlovento | Sotavento | Centro | Correlación diaria con E7 |
|---|---|---|---|---|
| nov–dic 2023 | 0.91 | 0.62 | 0.70 | −0.01 |
| nov–dic 2024 | 0.68 | 0.77 | 0.49 | +0.45 |

- En 2023 el barlovento es casi fondo puro: cae poco en domingo y no sigue a E7.
- En 2024 también cae en domingo (0.68) y sigue a E7. O la recirculación devuelve aire de la ciudad, o las ciudades vecinas tienen el mismo ciclo semanal.
- Corregir E7 por el barlovento y el clima no da un resultado usable. Con 23 días por temporada y el ajuste dentro de la misma temporada, la deriva de 2023 baja a 0 (sobreajuste) y la de 2024 no cambia.

**Conclusión:** con dos temporadas el satélite tampoco separa la emisión real del fondo regional. Lo que queda es un dato semanal de actividad que no sea concentración.

## Tres intentos más de quitarla (2026-11-05)

Pruebas con bloques de días seguidos, como los de una medida real: la deriva es la dispersión de bloques de 9 días seguidos contra el resto de la temporada, menos la de 9 días al azar. Seis temporadas, sin feb–may 2024. Scripts en el scratchpad de la sesión (`sheets/`).

| Intento | Deriva con 9 días seguidos (media de 6 temporadas) | ¿Sirve? |
|---|---|---|
| Ninguno (E7) | 0.125 | — |
| Corregir E7 por viento y capa de mezcla (coeficientes de las otras temporadas) | 0.133 | No: la mejora de 0.15 a 0.13 se veía en medias semanales, no en bloques de días |
| Combinar E7 y satélite (0.5/0.5) | 0.132 | No para días seguidos: la deriva es la misma en los dos. Sí baja el ruido de días al azar, de 0.116 a 0.096 |
| Una zona contra el resto de la ciudad | ~0 entre oriente y poniente (6 de 6 temporadas) y entre norte y sur (4 de 6) | La deriva se cancela, pero el estimador de una zona tiene mucho ruido (ver abajo) |

- **La deriva es de toda la ciudad.** Las estaciones del oriente y del poniente suben y bajan juntas semana a semana; la diferencia entre ellas no deriva. Encaja con una variación de la emisión de toda la ciudad o con fondo regional; no con algo local.
- **El contraste entre zonas no da, por ahora, una capacidad nueva.** Un estimador de diferencias con efecto fijo por día (absorbe la deriva común) y la exposición de cada estación a la zona de la medida (la fracción de su NOₓ vial modelado que viene de esa zona) mide el cambio de la emisión de una zona con un mínimo detectable de 25–60 % con 9 días seguidos, contra 24–43 % de la ciudad entera con E7. Las inyecciones salen sesgadas en el centro (−20 % se lee como −35 a −60 %). La razón: el transporte mezcla las zonas (las estaciones del oriente reciben solo 7–16 % de su NOₓ vial de su propio lado) y cada estación sola tiene mucho ruido.

## Actividad y más escaneos (2026-11-05)

- **Afluencia del transporte público** (Metro, Metrobús y Cablebús, diaria, datos abiertos de la CDMX, completa de nov 2023 a sep 2026): en secas e invierno varía 1–3 % de una semana a otra, cuando E7 varía 17–28 %. La correlación semanal con E7 es +0.37 juntando temporadas, sobre todo por lluvias y vacaciones; dentro de secas e invierno va de −0.47 a +0.11. Corregir E7 por la afluencia (coeficientes de otras temporadas) deja la deriva igual (0.122 → 0.120). Si la deriva fuera actividad de la gente, la afluencia la mostraría: apunta a fondo regional o a meteorología que los modelos no capturan. Queda abierta la actividad vehicular, sin datos diarios abiertos (solo combustible y casetas, mensuales).
- **Escaneos de TEMPO de la mañana** (nov–dic 2024 y feb–may 2025): sumarlos a los de la tarde baja el límite de 9 días al azar de 20–22 % a 17–22 % (2–5 puntos con los mismos días), con el placebo en 1 y el domingo igual (0.60–0.62). La mañana tiene capa de mezcla baja (560–930 m), viento débil y otra química, y no toca la deriva, que domina las medidas de días seguidos. No se adopta.
