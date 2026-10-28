# Qué puede hacer el sistema (y qué no)

Fecha: 2026-10-28. Base: resultados de los avances 4 y 5 en `results/runs/` (noviembre–diciembre de 2023 y febrero–mayo de 2024). Sirve para diseñar la experiencia de usuario: cada capacidad dice qué pregunta responde, con qué precisión y con qué límites. Casos de uso: [casos_de_uso.md](casos_de_uso.md).

## Qué datos usa (sin captura del usuario)

| Dato | Fuente | Resolución |
|---|---|---|
| NOₓ y NO₂ en superficie, viento | SIMAT (red de monitoreo de la CDMX), ~24 estaciones | Horaria |
| Columna de NO₂ | Satélite TEMPO (NASA) | Horaria de día, píxeles de ~2 × 4.5 km |
| Altura de la capa de mezcla | ERA5; MERRA-2 corregido donde ERA5 no llega (enero–junio 2024) | Horaria |
| Química (ozono, temperatura, humedad) | SIMAT | Horaria |
| Punto de partida de la emisión | Inventario de SEDEMA (vialidades) y fuentes puntuales | Solo como punto de partida; el resultado no se ajusta a él |

Todo el análisis usa las tardes (12–17 h), cuando la capa de mezcla está desarrollada y TEMPO observa.

## Capacidades

| # | Pregunta que responde | Respuesta | Precisión actual | Límites |
|---|---|---|---|---|
| 1 | ¿Cuánto cambió la emisión de NOₓ entre dos tipos de día o periodos? | Cociente de emisión (p. ej., domingo ÷ hábil) con intervalo del 90 % | Con ~9 días por grupo: ±12 % con el estimador normalizado (E7), ±25–30 % con la inversión (E5b) | Mejora con la raíz del número de días |
| 2 | ¿El cambio de concentración de un episodio fue por el clima o por la emisión? | Descomposición: concentración = clima × emisión (más el fondo regional) | La del punto 1 para la parte de emisión | El factor clima depende del modelo de transporte; un día suelto es ruidoso |
| 3 | ¿Una medida redujo la emisión? | Cociente de los días con la medida frente a días comparables, con placebo y límite de detección | 9 días hábiles (contingencias 2024): detecta bajas de ~20 % o más; no detecta 10 % | Las medidas cortas con efecto chico (5–10 %) no se pueden evaluar; las sostenidas sí |
| 4 | ¿Cuántos días necesita una medida para poder evaluarla? | Límite de detección por número de días (prueba de inyección en datos reales) | ~15–20 % con 9 días; estimado ~6–8 % con una temporada (~60 días) y ~3–4 % con un año de días hábiles | Las cifras de temporada y año son extrapolaciones; se confirman con más años de datos |
| 5 | ¿El método inventa cambios? | Placebo: días sin cambio reetiquetados al azar | Centro en 1 ± 0.15 obligatorio; E5b 1.01 ± 0.12 | Es la compuerta de calidad de todo resultado |
| 6 | ¿Qué concentración de NOₓ hay donde no hay estación? | Predicción con la física y las emisiones estimadas | ~12 ppb de error en estación oculta (E5b 11.9) | Interpolar las estaciones (kriging, 10.3 ppb) es más exacto para concentración sola; el valor del modelo es explicarla, no interpolarla |
| 7 | ¿Cómo se reparte la emisión vial en la ciudad? | Emisión relativa por región (9 regiones de ~18 km) y por tipo de día | Cocientes entre regiones con intervalos amplios | Las regiones con pocas estaciones a favor del viento quedan mal determinadas (algunas salen negativas) |
| 8 | ¿Cuántas toneladas se emiten? | Nivel absoluto indicativo | Cambia hasta un factor de 2 según el modelo de transporte (30 frente a 60 kt/año de emisión vial en día hábil, E5b frente a E2) | No es un dato confiable sin una referencia externa; se reporta como orden de magnitud, no como número |

## Qué no hace

- **Ozono:** mide la emisión de NOₓ, un precursor. No explica la química del ozono ni pronostica contingencias.
- **Detalle por fuente:** no separa autos de camiones ni ubica fuentes individuales; la escala es de regiones de ~18 km y fuentes puntuales grandes.
- **Noche y madrugada:** solo tardes.
- **Tiempo real:** depende de la publicación de los datos (TEMPO y SIMAT tardan días). Sirve para diagnóstico y evaluación, no para alertas.
- **Toneladas absolutas confiables:** ver la capacidad 8.

## Escala relevante para la salud

- La OMS (guías de 2021) fijó la guía de NO₂ en 10 µg/m³ como media anual y 25 µg/m³ como media de 24 horas; no hay un umbral seguro.
- La exposición de largo plazo es la que más pesa: los meta-análisis encuentran ~2 % más mortalidad por todas las causas por cada 10 µg/m³ de NO₂ promedio de largo plazo (1.02, IC 95 % 1.01–1.04, revisión para las guías de la OMS) y un riesgo de 1.047 (1.023–1.072) por cada 10 ppb (Stieb et al., 2021).
- El NO₂ del tráfico se asocia con ~4 millones de casos nuevos de asma infantil al año en el mundo, ~13 % de la incidencia (Achakulwisut et al., 2019).
- Una baja de pocos días casi no cambia la exposición anual; una baja sostenida de pocos puntos porcentuales sí. **El sistema mide bien justo esa escala si se acumulan suficientes días (capacidad 4).** Una baja de emisión se traduce en una baja menor de concentración (fondo regional y química del ozono).
- Pendiente de verificar con la fuente primaria: el efecto de corto plazo (Orellano et al., 2020) y el promedio anual de NO₂ de la ciudad (informe anual de SEDEMA).

## Costo de cómputo (para el diseño de la interfaz)

| Análisis | Tiempo |
|---|---|
| Estimador normalizado (E7), un evento con 200 placebos | ~1–2 min |
| Prueba de inyección con E7 (3 niveles) | ~1 min más |
| Inversión con puffs y PINN (E5b), un periodo de 4 meses | ~1–2 h (matrices ~20 min, una vez por periodo) |
| Validación con estación oculta y placebo de E5b | Incluida en el anterior |

Consecuencia: la interfaz debe tratar los análisis con la inversión como tareas en segundo plano (o precalculadas por periodo), y los del estimador normalizado como interactivos.

## Referencias

- OMS (2021). *WHO global air quality guidelines.* Valores de NO₂ confirmados en la tabla de prensa de la OMS (Swiss TPH) y DieselNet.
- Huangfu, P. y Atkinson, R. (2020). Long-term exposure to NO₂ and O₃ and all-cause and respiratory mortality: a systematic review and meta-analysis. *Environment International*, 144, 105998.
- Stieb, D. M. et al. (2021). Systematic review and meta-analysis of cohort studies of long term outdoor nitrogen dioxide exposure and mortality. *PLoS One*.
- Achakulwisut, P. et al. (2019). Global, national, and urban burdens of paediatric asthma incidence attributable to ambient NO₂ pollution. *The Lancet Planetary Health*, 3(4), e166–e178.
- Orellano, P. et al. (2020). Short-term exposure to PM10, PM2.5, NO₂ and O₃ and all-cause and cause-specific mortality. *Environment International*, 142 (cifra de NO₂ pendiente de verificar).
