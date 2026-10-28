# Casos de uso y experiencia de usuario

Fecha: 2026-10-28. Para diseñar la experiencia de usuario y la interfaz. Qué puede hacer el sistema y con qué precisión: [capacidades.md](capacidades.md).

## Decisión: el caso de uso se replantea

La investigación proponía evaluar si cada contingencia ambiental redujo la emisión (`reports/caso_de_uso.md` de la investigación). Los resultados del avance 5 cambian el enfoque:

- Con las 9 jornadas hábiles con medidas de 2024, el sistema detecta bajas de ~20 % o más y no detecta 10 % (prueba de inyección). El efecto esperado del Doble Hoy No Circula (5–10 %) queda por debajo: **una contingencia no se puede evaluar por sí sola.**
- Lo que sí puede: separar el clima de la emisión en cada episodio y evaluar cambios **sostenidos**, donde el límite de detección baja con el número de días. Esa es también la escala que importa para la salud (exposición de largo plazo).

| Antes | Ahora |
|---|---|
| "Evaluar si cada contingencia redujo la emisión" | "Diagnosticar cada episodio (¿fue clima o emisión?) y evaluar medidas sostenidas" |
| Emisión en toneladas | Cambios relativos, con su intervalo |
| Un número | Un número con su límite de detección y su placebo |

Documentos por actualizar con este enfoque: el notebook del avance 5 (contingencias y limitaciones), el planteamiento y el resumen ejecutivo del proyecto, y el diseño de la app.

## Usuarios

El sistema no depende de una institución: usa datos públicos (SIMAT, TEMPO, ERA5) y cualquiera puede correrlo. Por eso los usuarios son roles, no organizaciones; los ejemplos son posibles, no acuerdos.

| Usuario | Ejemplos posibles | Qué necesita | Frecuencia |
|---|---|---|---|
| Autoridad ambiental o de movilidad | Gobiernos de la ciudad, del estado o de alcaldías; comisiones metropolitanas; agencias de movilidad; INECC | Explicar episodios, saber si una medida funciona y cuánto tiempo darle | Semanal o por decisión |
| Evaluador independiente | Organizaciones civiles de aire limpio y movilidad, observatorios ciudadanos | Verificar con datos públicos si una medida anunciada cambió la emisión | Por medida o por anuncio |
| Periodista de datos | Medios con secciones de datos o de medio ambiente | Contrastar afirmaciones ("la medida redujo la contaminación") y explicar episodios al público | Por episodio o por nota |
| Financiador de proyectos | Bancos de desarrollo, fondos de aire limpio o de clima, redes de ciudades | Medir, reportar y verificar el efecto de proyectos que financian (corredores de transporte, zonas de bajas emisiones, renovación de flotas) | Por proyecto, al inicio y al cierre |
| Planeador urbano o de transporte | Operadores y planeadores de transporte público, consultoras de movilidad | Saber cuánto tiempo y qué zonas medir para evaluar un proyecto | Al diseñar y al evaluar |
| Equipo de inventario de emisiones | Quien elabore o revise un inventario (gobierno, academia, consultoras) | Contrastar los patrones del inventario con lo que miden el aire y el satélite | Por edición del inventario |
| Investigador | Salud pública, ciencias de la atmósfera, ciencia de datos | Series de emisión y concentración con su incertidumbre, reproducibles | Ocasional |
| Otras ciudades | Ciudades dentro de la cobertura de TEMPO (Norteamérica) | Replicar el análisis con su red de monitoreo | Por proyecto |

## Principios de la experiencia

1. **Toda cifra con su incertidumbre.** Ningún cociente sin intervalo; ningún resultado de evento sin placebo ni límite de detección.
2. **Veredicto en lenguaje llano, con tres estados:** "detectado", "no detectado (menor a X %)" y "no evaluable (pocos días o pocos datos)". Nunca "no tuvo efecto".
3. **Cocientes antes que toneladas.** Las toneladas, si aparecen, van como orden de magnitud y con la advertencia de la capacidad 8.
4. **La cobertura de datos a la vista:** cuántas estaciones, cuántas horas de TEMPO y qué días se usaron, y por qué se descartaron otros (fines de semana, días sin datos).
5. **Lento en segundo plano, rápido en primer plano:** el estimador normalizado responde en minutos; la inversión completa se precalcula por periodo o corre como tarea.
6. **Todo exportable:** cada resultado se descarga como reporte (PDF) y como datos (CSV), con la versión del código y de los datos.

## Casos de uso

### CU1. Diagnosticar un episodio: ¿fue el clima o la emisión?

- **Usuario:** autoridad ambiental (analista técnico) o periodista de datos.
- **Pregunta:** "Ayer y antier la concentración de NOₓ fue muy alta. ¿Se emitió más o el aire estuvo estancado?"
- **Entrada:**
  - rango de fechas del episodio (o elegir una contingencia de la lista);
  - opcional: región de interés.
- **Qué hace el sistema:** compara el episodio con días comparables (mismo día de la semana, ±4 semanas, sin el evento) y descompone el cambio: concentración = clima × emisión, más el fondo regional. Calibra con placebos.
- **Salida:**
  - veredicto: "fue el clima", "fue la emisión", "ambos" o "fondo o acumulación";
  - gráfica de cascada: cambio de concentración repartido entre clima, emisión y fondo, con la banda del placebo;
  - serie horaria de NOₓ observado y del esperado con emisión fija, del episodio y de sus días de referencia;
  - mapa de ventilación (viento × capa de mezcla) del episodio;
  - días usados y descartados.
- **Acciones:** exportar el reporte; comparar con otro episodio; anotar el episodio (causa conocida, medidas activas).

### CU2. Evaluar una medida sostenida

- **Usuario:** autoridad ambiental o de movilidad, evaluador independiente o financiador del proyecto.
- **Pregunta:** "Desde marzo restringimos la circulación en el centro los sábados. ¿Bajó la emisión?"
- **Entrada:**
  - fecha de inicio (y fin, si ya terminó);
  - días de la semana en que aplica;
  - regiones afectadas;
  - periodo de comparación (por defecto, el mismo número de semanas antes).
- **Qué hace el sistema:** estima el cociente de emisión de los días con la medida frente a los comparables, con placebo y prueba de inyección para dar el límite de detección con esos días.
- **Salida:**
  - cambio de emisión (%) con intervalo y veredicto en tres estados;
  - límite de detección con los días acumulados (texto de ejemplo: "con 34 días, este análisis detecta bajas de X % o más");
  - serie del índice de emisión normalizado por semana, antes y después del inicio;
  - si no es evaluable todavía: cuántos días faltan para alcanzar el efecto esperado (ver CU3).
- **Acciones:** decidir si se mantiene, se amplía o se termina la medida; programar una revisión automática cuando se acumulen los días necesarios; exportar.

### CU3. Planear la evaluación de un piloto

- **Usuario:** autoridad o planeador de transporte antes de lanzar una medida, o financiador al diseñar el monitoreo de un proyecto.
- **Pregunta:** "Si la medida reduce la emisión 8 %, ¿cuánto tiempo hay que mantenerla para poder demostrarlo?"
- **Entrada:** efecto esperado (%); días de la semana en que aplica; regiones; temporada.
- **Qué hace el sistema:** inyecta el efecto en datos históricos de la misma temporada con distintos números de días y mide cuándo se detecta.
- **Salida:** curva de "probabilidad de detectar frente a días de duración" y el número mínimo de días recomendado.
- **Acciones:** fijar la duración del piloto; registrar la medida para que CU2 la evalúe al terminar.

### CU4. Seguimiento de la emisión

- **Usuario:** autoridad ambiental, evaluador independiente u observatorio ciudadano.
- **Pregunta:** "¿Cómo va la emisión este mes frente al anterior y frente al mismo mes del año pasado?"
- **Entrada:** ninguna (tablero); opcional: periodo y región.
- **Salida:**
  - índice de emisión normalizado por mes, por región y por tipo de día, con intervalos;
  - cambios sostenidos que superan el límite de detección, marcados;
  - cobertura de datos del periodo.
- **Acciones:** abrir un cambio marcado como episodio (CU1) o como medida (CU2); exportar el resumen mensual.

### CU5. Contrastar el inventario

- **Usuario:** equipo de inventario de emisiones o investigador.
- **Pregunta:** "¿El reparto por región y el ciclo semanal del inventario coinciden con lo que mide el aire?"
- **Entrada:** edición del inventario (por defecto, la vigente).
- **Salida:**
  - reparto relativo de la emisión vial por región: inventario frente a estimado, con intervalos;
  - cocientes sábado ÷ hábil y domingo ÷ hábil: perfil del inventario frente al estimado;
  - regiones donde la diferencia supera la incertidumbre.
- **Acciones:** priorizar regiones o supuestos de actividad para revisar en la siguiente edición; exportar.

### CU6. Concentración donde no hay estación (secundario)

- **Usuario:** investigador de salud pública, planeador urbano o periodista.
- **Pregunta:** "¿Qué NOₓ hubo en esta colonia, que no tiene estación?"
- **Entrada:** punto o zona en el mapa; fechas.
- **Salida:** serie estimada con su error típico (~12 ppb) y la parte atribuible a la emisión vial frente al fondo.
- **Acciones:** exportar. Advertencia en la interfaz: para concentración sola, interpolar estaciones es más exacto; el valor del modelo es explicar de dónde viene.

### CU7. Verificar una afirmación pública

- **Usuario:** periodista de datos o evaluador independiente.
- **Pregunta:** "Se anunció que una medida redujo la contaminación 15 %. ¿Lo respaldan los datos, una vez descontado el clima?"
- **Entrada:** la medida (fechas, días, zonas) y la cifra anunciada.
- **Qué hace el sistema:** lo mismo que CU2, más la comparación con la cifra anunciada: ¿cae dentro del intervalo?, ¿el cambio de concentración se explica por el clima?
- **Salida:** veredicto ("compatible con los datos", "no compatible", "no evaluable con estos días"), con la descomposición clima × emisión y el límite de detección; un texto corto citable con su intervalo.
- **Acciones:** exportar una ficha para publicar con la metodología y los datos; enlazar el análisis reproducible.

### CU8. Medir, reportar y verificar un proyecto financiado

- **Usuario:** financiador o ejecutor de un proyecto (corredor de transporte, zona de bajas emisiones, renovación de flota).
- **Pregunta:** "El proyecto prometía reducir la emisión de NOₓ de su zona. ¿Lo hizo, y con qué certeza?"
- **Entrada:** zona del proyecto, fecha de inicio, efecto comprometido; periodo base.
- **Qué hace el sistema:** al inicio, CU3 (cuánto tiempo medir); durante y al cierre, CU2 para la región del proyecto, con el índice normalizado por mes.
- **Salida:** línea base, cambio de emisión con intervalo, límite de detección y advertencia de escala: con regiones de ~18 km, un proyecto que afecta una zona pequeña puede quedar diluido.
- **Acciones:** reporte de verificación periódico; decidir continuidad o pagos por resultados con la incertidumbre explícita.

## Qué tan bien se satisface cada caso hoy

Con los resultados de los avances 4 y 5. Escala: alto, medio, bajo. Las brechas y las mejoras para cerrarlas están en [brechas_y_mejoras.md](brechas_y_mejoras.md).

| Caso | Confianza | Detalle espacial | Detalle temporal | Tiempo para obtenerlo | Construido | Satisfacción |
|---|---|---|---|---|---|---|
| CU1. Diagnosticar un episodio | Media: con 1–3 días el intervalo de la parte de emisión es amplio (±20–30 % con E7); el sesgo de acumulación en episodios es conocido (~0.94–1.09) | Toda la ciudad (E7) o 9 regiones (inversión) | Por episodio | Días por la publicación de los datos; minutos de cálculo | Parcial: existe el análisis de eventos, falta la descomposición y el veredicto | Media |
| CU2. Evaluar una medida sostenida | Alta en toda la ciudad con una temporada o más (límite estimado ~6–8 %); baja por región | Ciudad: sí; región de ~18 km: débil; corredor o colonia: no | Mensual o por temporada | Meses (lo exige la medida); minutos a horas de cálculo | Parcial: el análisis existe para contingencias; falta aceptar cualquier conjunto de días | Media |
| CU3. Planear un piloto | Media: la inyección está validada con E7 en un periodo; falta la curva por duración | Ciudad | — | Minutos | Parcial: existe `--inject`, falta la curva | Media |
| CU4. Seguimiento de la emisión | Media: un mes (~20 días hábiles) da ~±8–10 % en toda la ciudad (estimado) | Ciudad; 9 regiones con intervalos amplios | Mensual | Días por los datos; el flujo se arma por periodo | No: no hay corridas mensuales automáticas ni ingesta continua | Baja |
| CU5. Contrastar el inventario | Media para el perfil semanal (domingo, sábado); baja para el reparto espacial (intervalos amplios, regiones negativas) | 9 regiones frente al detalle de calles del inventario | Tipo de día | Horas (inversión) | Parcial: los cocientes existen; falta la comparación directa con el inventario | Baja–media |
| CU6. Concentración sin estación | Baja–media: ~12 ppb de error, peor que interpolar (10.3 ppb) | Cualquier punto, con un viento uniforme en todo el dominio | Horaria (tardes) | Horas | Parcial: predicción por estación, no en malla | Baja |
| CU7. Verificar una afirmación | Alta si la afirmación es de toda la ciudad y de un periodo largo; baja si es local o de pocos días | Ciudad | Periodo de la medida | Minutos con los datos ya publicados | No: falta la comparación con la cifra anunciada y la ficha | Media |
| CU8. Proyecto financiado | Baja para proyectos locales: un corredor queda diluido en una región de ~18 km | Insuficiente para la escala de un proyecto | Mensual | Meses | No | Baja |

Lectura: el sistema ya sirve para preguntas de **toda la ciudad y de periodos largos** (CU2, CU7) y, con poco trabajo, para explicar episodios (CU1) y planear pilotos (CU3). Lo que más falta es **detalle espacial** (CU5, CU8, CU2 local), **ingesta continua de datos** (CU4, CU1) y **un nivel absoluto anclado** (CU5, CU8).

## Mapa de pantallas propuesto

| Pantalla | Casos de uso | Elementos principales |
|---|---|---|
| Inicio / seguimiento | CU4 | Índice de emisión por mes y región, cambios marcados, cobertura de datos |
| Episodio | CU1 | Selector de fechas o contingencia, veredicto, cascada, series, mapa de ventilación |
| Evaluar medida | CU2, CU7, CU8 | Formulario de la medida, veredicto con límite de detección, serie antes y después |
| Planear piloto | CU3 | Efecto esperado y duración, curva de detección |
| Inventario | CU5 | Reparto por región y perfil semanal, inventario frente a estimado |
| Mapa | CU6, apoyo de CU1 y CU5 | Regiones, estaciones, píxeles de TEMPO, concentración estimada |
| Datos y método | Todos | Cobertura, fuentes, versión, limitaciones (de [capacidades.md](capacidades.md)) |

## Pendiente para construirlo

- El comando de diagnóstico de episodios (CU1): `diagnose_episode` y `nox-ml diagnose` (ver `tareas.md`).
- La curva de detección por número de días (CU3) generaliza la prueba de inyección (`--inject`).
- Más años de datos (temporadas 2025 y 2026) para afinar los límites de detección (`tareas.md`).
- Validar el flujo con usuarios potenciales de varios perfiles (autoridad, organización civil, periodista, financiador, investigador) antes de construir la interfaz completa.
