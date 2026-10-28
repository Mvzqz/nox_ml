# Casos de uso más valiosos, qué los frena y cómo mejorarlos

Fecha: 2026-10-28. Base: [casos_de_uso.md](casos_de_uso.md) (qué tan bien se satisface cada caso) y [capacidades.md](capacidades.md). Las estimaciones de costo son de trabajo con agentes, en días; las de impacto son juicios, no mediciones.

## Los casos más valiosos

Valor = qué tan importante es la pregunta para quien la hace × cuántos usuarios distintos la tienen × qué tan difícil es responderla con otras herramientas.

| Orden | Caso | Por qué es valioso | Satisfacción hoy |
|---|---|---|---|
| 1 | CU2. Evaluar una medida sostenida | Es la pregunta de política pública que nadie responde bien: las evaluaciones con concentraciones confunden la medida con el clima. Lo usan autoridades, evaluadores y financiadores | Media (alta en toda la ciudad, baja por zona) |
| 2 | CU8. Medir, reportar y verificar un proyecto financiado | Hay dinero condicionado a resultados (bancos de desarrollo, fondos de clima y aire limpio) y casi ninguna forma barata de verificar emisiones con datos independientes | Baja (falta detalle espacial) |
| 3 | CU1. Diagnosticar un episodio | Ocurre muchas veces al año, se discute en público y es la puerta de entrada al sistema: explica lo que la gente ve | Media (falta construir la herramienta) |
| 4 | CU7. Verificar una afirmación pública | Rendición de cuentas con datos públicos y reproducibles; útil para medios y organizaciones civiles | Media |
| 5 | CU3. Planear un piloto | Barato de construir y cambia cómo se diseñan las medidas: cuánto tiempo mantenerlas antes de juzgarlas | Media |
| 6 | CU4. Seguimiento de la emisión | Valor continuo, pero depende de tener datos actualizados | Baja |
| 7 | CU5. Contrastar el inventario | Valioso para pocos usuarios; exige detalle espacial y nivel absoluto | Baja–media |
| 8 | CU9. Simular un escenario | Responde la pregunta previa a decidir; es lo que la concentración sola no puede hacer. Requiere ancla del nivel absoluto y más detalle espacial | Baja |
| 9 | CU6. Concentración sin estación | Hay alternativas mejores para concentración sola (interpolación, modelos de pronóstico) | Baja |

## Qué impide satisfacerlos

| Brecha | Qué causa | Casos afectados |
|---|---|---|
| B1. Pocos días por evento y solo dos periodos de datos (nov–dic 2023, feb–may 2024) | Límites de detección altos (~15–20 % con 9 días); límites de temporada y año solo extrapolados | CU2, CU3, CU7, CU8 |
| B2. Resolución espacial de 9 regiones de ~18 km | Un proyecto o una medida local queda diluido; reparto espacial mal determinado (regiones negativas) | CU8, CU5, CU2 local |
| B3. Un solo viento uniforme por hora para todo el dominio | Es la mayor fuente de error del transporte; limita la confianza de todo lo demás | Todos |
| B4. Nivel absoluto sin ancla (cambia hasta un factor de 2 según el transporte) | No se pueden dar toneladas confiables | CU5, CU8 |
| B5. Sin flujo continuo de datos: se trabaja con archivos anuales y periodos fijos | Días a meses de retraso; no hay seguimiento mensual ni alertas | CU4, CU1 |
| B6. Sesgo en episodios de acumulación (el fondo regional sube varios días) | El diagnóstico de episodios puede atribuir a la emisión lo que es acumulación | CU1, CU7 |
| B7. No separa fuentes (vialidades frente a industria) | No se puede atribuir un cambio a un sector | CU5, CU8 |
| B8. Faltan herramientas: diagnóstico de episodios, curva de detección, análisis con cualquier conjunto de días, interfaz | Lo que el método ya puede hacer no está al alcance de un usuario | CU1, CU2, CU3, CU7 |
| B9. Sin datos de tráfico recientes (Infovial es de 2017) | No hay una referencia independiente para validar los cambios medidos | CU2, CU7 |

## Mejoras posibles, ordenadas

Factibilidad: alta (técnica conocida y datos disponibles), media (hay que probar), baja (incierta). Impacto: cuánto mejora la satisfacción de los casos más valiosos.

| Orden | Mejora | Brecha | Factibilidad | Costo | Impacto | Casos que habilita o mejora |
|---|---|---|---|---|---|---|
| 1 | Análisis de eventos con cualquier conjunto de días (`--days`) y prueba positiva con calendario (fin de año, Semana Santa) | B8, B1 | Alta | 0.5 día | Alto: valida el método en casos reales y abre CU2 y CU7 | CU2, CU7, CU1 |
| 2 | Diagnóstico de episodios: descomposición clima × emisión × fondo, con veredicto | B8, B6 | Alta | 0.5 día | Alto | CU1, CU7 |
| 3 | Curva de detección por número de días | B8, B1 | Alta | 0.5 día | Medio–alto | CU3, CU8 |
| 4 | Temporadas 2025 y 2026 (datos, control de calidad, código fijo a 2023–2024) | B1 | Alta | 2–4 días | Alto: duplica o triplica los días y valida en años nuevos | CU2, CU3, CU7, CU8 |
| 5 | Ingesta continua: datos en tiempo casi real de SIMAT, TEMPO y la capa de mezcla, con corridas mensuales automáticas | B5 | Media (hay que confirmar la disponibilidad de productos en tiempo casi real) | 3–5 días | Alto para CU4 y CU1 | CU4, CU1 |
| 6 | Interfaz mínima (seguimiento, episodio, evaluar medida) con reportes exportables | B8 | Alta | 3–5 días | Alto: sin ella los casos no llegan a usuarios | Todos |
| 7 | Ancla del nivel absoluto: comparar con el inventario, EDGAR y un modelo químico global (GEOS-CF o CAMS); trazador con CO | B4 | Media | 3–5 días | Medio | CU5, CU8 |
| 8 | Más regiones o regiones administrativas (alcaldías), con regularización espacial y TEMPO para sostenerlas | B2 | Media (identificabilidad incierta) | 3–5 días | Alto para CU8 y CU5 si funciona | CU8, CU5, CU2 |
| 9 | Fondo regional y acumulación de varios días en la inversión | B6 | Media | 2–3 días | Medio | CU1, CU7 |
| 10 | Datos de tráfico recientes (conteos públicos, índices de congestión) como validación | B9 | Media (depende del acceso) | 1–3 días | Medio | CU2, CU7 |
| 11 | Separar orígenes (vialidades frente a industria) con trazadores (CO, SO₂) y perfiles horarios | B7 | Baja–media | 5+ días | Alto si funciona | CU5, CU8 |
| 12 | Campo de viento variable (malla de viento o un modelo meteorológico) en lugar de un viento uniforme | B3 | Baja–media (una PINN del campo completo es mucho más cara) | 10+ días | Alto, en todos | Todos |
| 13 | Replicar en otra ciudad con cobertura de TEMPO; antes, clasificar ciudades con la regla del límite de detección (ver "Otras ciudades") | — | Media (clasificar: alta) | Clasificar: 1–2 días; replicar: 3–5 días por ciudad | Medio–alto: el valor es mayor en ciudades sin alternativas | Otras ciudades |
| 14 | Total de la ciudad con el método de divergencia de flujo o el ajuste de pluma sobre TEMPO, como ancla del nivel absoluto y comparación independiente ([alternativas.md](alternativas.md)) | B4 | Alta (método publicado, datos ya descargados) | 2–3 días | Alto: resuelve el nivel absoluto a nivel ciudad y nos compara con el método que podría sustituirnos | CU5, CU8, credibilidad |

Ruta sugerida: la mejora 14 es la ancla del nivel absoluto más barata y conviene adelantarla a la 7. Las mejoras 1 a 3 son baratas y convierten capacidades que ya existen en herramientas (una semana de trabajo en total con la 4). Con la 6 llegan a usuarios. La 5 y la 8 son las que más amplían el valor después; la 11 y la 12 son investigación.

## Otras palancas de valor (además de mejorar el modelo)

Reutilizan lo que ya existe o responden preguntas nuevas con los mismos datos.

**Publicar lo que ya existe**
- **Conjunto de datos limpio y citable** (por ejemplo, Zenodo con DOI): SIMAT con el viento de 2024 corregido (mph) y los sensores atascados marcados, la capa de mezcla sin el desfase de MERRA-2, las contingencias verificadas y los recortes de TEMPO.
- **Reporte de calidad de datos para quien los publica:** el error de unidades del viento de 2024 en la red de meteorología y el desfase de una hora de MERRA-2. Bien público, bajo costo, abre colaboración con quien opera la red.
- **Guía para correrlo en otra ciudad** (el código ya es público).

**Credibilidad académica**
- **Artículo científico:** no encontramos una inversión de NOₓ con TEMPO para la Ciudad de México; el marco de validación (estación oculta, placebo, inyección, límite de detección) y la comparación de modelos son publicables.
- **Colaboraciones:** el Instituto de Ciencias de la Atmósfera y Cambio Climático de la UNAM (viento de 3 km sobre el valle) y el equipo científico de TEMPO (validación en latitudes del sur).

**Preguntas nuevas con los mismos datos**
- **Régimen del ozono:** TEMPO mide formaldehído; el cociente formaldehído/NO₂ indica si el ozono depende más del NOₓ o de los compuestos orgánicos, es decir, qué reducir en las contingencias.
- **Traducción a salud:** cambio de emisión → cambio de concentración → efectos evitados con funciones de riesgo publicadas ([capacidades.md](capacidades.md)).
- **Equidad:** emisión y exposición por zona cruzadas con el censo (INEGI): quién emite y quién respira.
- **Clima:** el NOₓ sale de la misma combustión que el CO₂; sus cambios indican cambios de combustión del tráfico y abren fondos climáticos.
- **Separar tráfico e industria con CO:** el cociente CO/NOₓ de las estaciones distingue tipos de fuente; más barato que la mejora 11.

**Productos**
- **Boletín mensual automático:** índice de emisión normalizado, episodios explicados y límite de detección (requiere la mejora 5).
- **Calculadora de límite de detección:** "¿cuántos días necesita mi medida?" con la regla de la sección anterior (CU3), útil sin el resto de la interfaz.
- **Fichas para medios:** el diagnóstico de un episodio en una página citable (CU1, CU7).

**Orden recomendado**

| Prioridad | Qué | Costo | Valor |
|---|---|---|---|
| 1 | Conjunto de datos con DOI y reporte de calidad para la red | 1–2 días | Alto: inmediato, abre colaboraciones |
| 2 | Calculadora de límite de detección | 1 día | Medio–alto: útil sola |
| 3 | Régimen del ozono con formaldehído de TEMPO | 3–5 días | Alto: la pregunta pública más fuerte |
| 4 | Artículo científico | 2–4 semanas | Alto en credibilidad |
| 5 | Traducción a salud y equidad | 3–5 días | Alto para decisión y comunicación |
| 6 | Separar fuentes con CO | 2–3 días | Medio–alto |
| 7 | Boletín mensual | Tras los datos continuos | Alto y continuo |

Antes de publicar el conjunto de datos, revisar la licencia de cada fuente en `data/README.md` (los datos de movilidad de Google y Apple no se pueden redistribuir sin verificar sus términos).
## Otras ciudades (mejora 13)

**Qué dice la investigación:**
- **Los Ángeles,** probada con datos reales por tener el mejor paquete (viento HRRR de 3 km, tráfico PeMS, estudios publicados): con 16–17° de error de viento frente a 28–32° en la Ciudad de México, **un mejor viento no mejoró la inversión** (13.6 → 14.1 ppb en estación oculta). Lo que mejoró fue pasar a puffs, igual que aquí. Su domingo (0.52 frente a 0.67 de la literatura) muestra la misma subestimación.
- **El límite de detección lo fija el modelo de transporte, no la red:** con 24, 15 o 9 estaciones queda en ±0.18–0.19, y empeorar el viento 20–30° no lo cambia. TEMPO pesa para el reparto por zonas.
- **Regla para predecir el límite en una ciudad nueva:** cambio mínimo detectable ≈ 2 · CV · √(1/k + 1/(n − k)), con CV la variación día a día del estimador en días hábiles, k los días con el cambio y n los días totales. Ajusta a la Ciudad de México y Bogotá; en Los Ángeles (no usada para ajustar) resultó conservadora (predijo ±0.20, se midió ±0.14).
- **Bogotá** (sin TEMPO): Día sin carro con CO −23 % y NOₓ sin cambio, placebo ±9 %.

**Dónde vale más:** en Estados Unidos el método rendiría igual o algo mejor, pero allí sobran alternativas (inventarios detallados, HRRR, inversiones con modelos químicos y TEMPO). En ciudades mexicanas dentro de la cobertura de TEMPO rendiría parecido o algo peor, pero casi no hay alternativas; ahí el valor es mayor.

**Por tamaño de ciudad:**

| Tipo | Qué serviría | Qué no |
|---|---|---|
| Metrópoli mediana (1–5 millones, red de 10 o más estaciones; Monterrey, Guadalajara) | Todo el método a nivel ciudad, quizá algunas regiones | Detalle fino |
| Ciudad chica con red mínima (3–9 estaciones) | Cambios de toda la ciudad con E6 y E7 y diagnóstico de episodios, con límites más altos | Regiones, escenarios |
| Ciudad sin estaciones de NOₓ | Solo métodos de satélite y viento, si la pluma se distingue del fondo | Todo lo que necesita estaciones |
| Ciudad con una fuente puntual dominante (Salamanca, Tula) | Satélite y viento para la fuente, estaciones para la ciudad | — |

Limitantes en ciudades chicas: menos señal frente al ruido de TEMPO y al fondo regional (el estimador varía más y el límite crece), pocos píxeles (~2 × 4.5 km) por ciudad, redes con huecos o sin NOₓ, y pocos eventos o datos de tráfico para validar.

**Experimento propuesto (barato, sin construir nada):** listar en SINAICA las ciudades dentro de la cobertura de TEMPO con estaciones de NOₓ y datos horarios completos, calcular el CV del estimador normalizado con unos meses de cada red y aplicar la regla para clasificarlas por el cambio sostenido que podrían detectar en una temporada. Empezar por Monterrey y Guadalajara.

## Riesgos de la ruta

- La mejora 8 (más regiones) puede no ser identificable con ~24 estaciones: hay que medirlo con la validación con estación oculta y el placebo antes de prometer detalle espacial.
- La mejora 5 depende de productos de datos en tiempo casi real que hay que confirmar (latencia y estabilidad de las fuentes).
- Las cifras de límite de detección de una temporada o un año son extrapolaciones hasta que la mejora 4 las mida.
