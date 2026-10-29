# Qué puede hacer el sistema (y qué no)

Fecha: 2026-10-29 (actualizado con [verificaciones_nivel1.md](verificaciones_nivel1.md), [controles_de_verdad.md](controles_de_verdad.md) y [sesgo_domingo.md](sesgo_domingo.md)). Base: resultados en `results/runs/` (noviembre–diciembre de 2023, febrero–mayo de 2024, el confinamiento de 2020 y gemelos). Sirve para diseñar la experiencia de usuario: cada capacidad dice qué pregunta responde, con qué precisión y con qué límites. Casos de uso: [casos_de_uso.md](casos_de_uso.md).

## Qué datos usa (sin captura del usuario)

| Dato | Fuente | Resolución |
|---|---|---|
| NOₓ y NO₂ en superficie, viento | SIMAT (red de monitoreo de la CDMX), ~24 estaciones, hasta 2024; desde 2025, las mismas estaciones vía OpenAQ (SINAICA, sin validar, ~60–65 % de las horas) con el viento de los aeropuertos | Horaria |
| Columna de NO₂ | Satélite TEMPO (NASA) | Horaria de día, píxeles de ~2 × 4.5 km |
| Altura de la capa de mezcla | ERA5; MERRA-2 corregido donde ERA5 no llega (enero–junio 2024) | Horaria |
| Química (ozono, temperatura, humedad) | SIMAT | Horaria |
| Punto de partida de la emisión | Inventario de SEDEMA (vialidades) y fuentes puntuales | Solo como punto de partida; el resultado no se ajusta a él |

Todo el análisis usa las tardes (12–17 h), cuando la capa de mezcla está desarrollada y TEMPO observa.

## Capacidades

Para cada capacidad: estado y precisión, cómo se compara con las alternativas ([alternativas.md](alternativas.md)), para qué uso alcanza hoy y si ese uso aporta valor.

| # | Capacidad | Estado y precisión | Frente a las alternativas | Uso para el que alcanza hoy | ¿Ese uso aporta valor? |
|---|---|---|---|---|---|
| 1 | **Cambio de emisión entre periodos** | Validado para cambios grandes: confinamiento de 2020, −50 % con E7 (esperado −40 a −60 %) y placebo de 2019 en 1 | Normalización estadística (rmweather): equivalente para toda la ciudad, más simple. Econometría cuasi-experimental: más aceptada, pero mide concentración. Satélite (divergencia de flujo): total de la ciudad, sin placebo. **Lo propio:** emisión, placebo y límite de detección juntos | Medidas o choques grandes y sostenidos (≥ 20–30 %) | **Alto:** "¿funcionó?" descontando el clima, con límite de detección |
| 2 | **No inventar cambios** | Validado: placebos en 1 ± 0.15 en 2019, 2023 y 2024; gemelos con verdad conocida | Pocas alternativas reportan placebo; la econometría usa grupos de control | Respaldar o refutar afirmaciones públicas | **Alto** para verificación: medios, evaluadores, organizaciones civiles |
| 3 | **Límite de detección por número de días** (`nox-ml detection`) | Con 9 días hábiles: ~20 % en feb–may, 28–37 % en invierno; ~19 % con una temporada y ~10 % con un año (80 % de potencia, extrapolado) | Ninguna alternativa lo ofrece de forma explícita | Planear pilotos: cuánto tiempo mantener una medida | **Medio–alto:** útil aunque no se use el resto |
| 4 | **Incertidumbre honesta** | Bootstrap por bloques de 7 días: el intervalo del 90 % cubre la verdad el 85 % de las veces en gemelos (antes, ~60 %) | Muchos estudios no validan la cobertura de sus intervalos | Todo reporte con intervalos | **Medio** por sí sola; da confianza a las demás |
| 5 | **Diagnóstico de episodios** (`nox-ml episode`) | Pista, no veredicto: separa bien el clima; confundió acumulación con emisión antes de Navidad de 2023 (el tráfico de esas fechas en 2018 fue normal) | Los reportes oficiales explican por meteorología sin separar la emisión; un modelo químico con asimilación lo haría mejor, a mucho mayor costo | Episodios dominados por el clima | **Medio:** pregunta frecuente y puerta de entrada, pero sin veredicto firme sobre la emisión |
| 6 | **Cambios moderados (domingo ÷ hábil)** | E7 y E6 sin fin de año: 0.63–0.75, cerca del tráfico; E5b 0.53 frente a 0.76–0.81 del tráfico de nov–dic 2018 | Inventario con perfiles de tráfico; normalización estadística | Dirección y orden de magnitud de cambios de 5–20 % | **Bajo hoy:** las medidas reales mueven 5–10 % |
| 7 | **Concentración sin estación** | 10.2 ppb con la regresión-kriging (kriging solo 10.3, E5b 11.9); piso de ~4 ppb | Kriging, modelos de satélite y uso de suelo, pronósticos químicos: iguales o mejores | Mapas aproximados por hora | **Bajo como producto aparte;** su valor es salir del mismo modelo que explica la emisión |
| 8 | **Emisión por zona (9 regiones de ~18 km)** | Débil: regiones mal determinadas (algunas negativas) | Inventario: mucho más detalle; modelo químico: mejor física | Comparación cualitativa entre grandes zonas | **Bajo hoy;** el valor alto exige 10–15 zonas confiables, sin probar |
| 9 | **Toneladas absolutas** | No confiable: ×2 según el transporte (30 frente a 60 kt/año viales en día hábil) | Inventario, EDGAR, satélite con divergencia de flujo (~20–30 %): mejores | Orden de magnitud | **Bajo hoy;** con un ancla externa serviría para contrastar inventarios |
| 10 | **Calendario y contingencias** (`nox-ml calendar`, `contingencies`) | Funciona, con periodos atípicos fuera de la referencia; contingencias 2024 sin efecto detectable (límite ~20 %) | La econometría hace lo mismo con concentraciones | Eventos de varios días con efecto grande | **Medio:** el resultado típico es "no detectable", pero evita conclusiones falsas |

**Lectura.** El nicho son las filas 1–3: emisión descontando el clima, con placebo y límite de detección, con datos públicos y bajo costo, validado con un cambio real. Para concentración y toneladas (7 y 9) hay alternativas mejores. El cuello de botella del valor es la fila 6: las medidas que más interesan mueven 5–10 %, así que el sistema necesita medir cambios moderados con confianza (sesgo del domingo y más temporadas).

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

## Otras razones para medir la emisión de NOₓ, además de la salud

- **Cumplimiento de normas y programas:** las normas mexicanas de NO₂ y de ozono, y los programas de contingencias, se activan por concentraciones; saber si la emisión cambió ayuda a ajustar esos programas.
- **Formación de ozono y partículas secundarias:** el NOₓ es precursor del ozono y del nitrato en partículas finas; reducir NOₓ cambia esas dos contaminaciones, con efectos que pueden ser no lineales (en algunas zonas, bajar NOₓ sube el ozono por un tiempo).
- **Clima:** el NOₓ sale de la misma combustión que el CO₂, así que su emisión sirve como indicador de la actividad de combustión de vehículos e industria. Las estimaciones de NOₓ con satélite se usan en la literatura para verificar emisiones de CO₂ de ciudades y centrales; además, el ozono que forma es un gas de efecto invernadero.
- **Ecosistemas y cultivos:** el ozono daña la vegetación y reduce rendimientos agrícolas; el depósito de nitrógeno acidifica suelos y agua y altera ecosistemas (por ejemplo, en los bosques que rodean la ciudad).
- **Economía:** costos en salud, ausentismo y productividad, y daño a materiales y edificios.
- **Equidad:** la exposición se concentra cerca de vialidades y zonas industriales; medir la emisión por zona permite ver quién carga con ella.
- **Rendición de cuentas y verificación:** comprobar con datos independientes si los inventarios, los compromisos y los proyectos financiados cumplen lo que prometen.

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
