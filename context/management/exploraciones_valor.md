# Exploraciones de valor: frentes en paralelo

Fecha: 2026-11-14. Objetivo: evaluar, antes de cerrar el resumen ejecutivo, qué ideas aumentan la utilidad del sistema, qué tan bien funcionan y cuánto valor aportan. Base: [capacidades.md](../knowledge/capacidades.md), [brechas_y_mejoras.md](../knowledge/brechas_y_mejoras.md), [deriva.md](../knowledge/deriva.md), [casos_de_uso.md](../knowledge/casos_de_uso.md) y el artículo final (`docs/entregables/Articulo.39.md`).

## Por qué

El sistema hoy detecta cambios de emisión de ~30 % por temporada, y esos cambios casi no ocurren (el único caso real del periodo es el confinamiento de 2020). Las medidas que interesan mueven 5–10 %. Cada frente prueba una vía para (a) bajar el límite de detección o (b) dar un uso frecuente que no dependa de él. Son exploraciones: la meta es un veredicto con evidencia, no código de producción.

## Reglas comunes

- **Una rama por frente:** `explore/<tema>`, desde `main`, en un worktree propio. Nunca a `main`. Pull request al terminar, aunque el veredicto sea "descartar".
- **Entregable:** una nota `context/knowledge/<tema>.md` en español, con la plantilla de veredicto de abajo, las cifras y cómo reproducirlas. Los scripts de exploración van en el scratchpad de la sesión o en `notebooks/exploraciones/`; **no se agrega código a `nox_ml`** salvo que el veredicto sea "adoptar", y entonces va en otro PR con pruebas según `docs/testing.md`.
- **No tocar** las configuraciones congeladas (`configs/seasons/`), los resultados de los modelos (`results/runs/`) ni el modelo final. No elegir ni ajustar nada con feb–may 2024.
- **Datos:** leer los datos existentes desde el repositorio principal (no hace falta `dvc pull` en cada worktree). Lo que se descargue va a una carpeta nueva propia (`data/raw/<fuente_nueva>/`) y se anota en `data/raw/MANIFEST.md`. No correr `nox-ml update` ni `dvc push` desde un frente.
- **Credenciales:** Earthdata y OpenAQ desde `.netrc` y el entorno; nunca impresas, en logs ni en commits.
- **Presupuesto:** cada frente tiene un tope de tiempo. Si la prueba decisiva sale negativa, se detiene y se documenta; un "no funciona" bien medido es un resultado.
- **Cómputo:** una sola máquina. Las inversiones con E5b (~10 min a 2 h) solo en F4 y en serie; los demás frentes usan E7, el satélite o análisis directos (segundos a minutos).
- `bin/check` pasa en cada PR.

## Plantilla de veredicto (igual para todos)

Cada nota termina con esta tabla, para poder comparar los frentes entre sí:

| Criterio | Escala | Resultado |
|---|---|---|
| **¿Funciona?** | 0 no se probó · 1 no funciona · 2 funciona con condiciones · 3 funciona y está validado de forma independiente | |
| **Evidencia** | La prueba decisiva y su cifra | |
| **Usuario** | Quién lo usaría (rol de [casos_de_uso.md](../knowledge/casos_de_uso.md)) | |
| **Frecuencia** | Usos esperados al año, con su supuesto | |
| **Alternativa** | Ninguna · peor · igual · mejor que lo que existe | |
| **Decisión que cambia** | Qué haría distinto el usuario con el resultado | |
| **Costo de llevarlo a producto** | Días de desarrollo y costo de operación al mes | |
| **Veredicto** | Adoptar · seguir con condiciones (cuáles) · descartar | |

## Frentes

| # | Frente | Pregunta | Tope | Ola |
|---|---|---|---|---|
| F1 | Diseños alternados | ¿Intercalar días con y sin medida cancela la deriva y baja el límite de detección? | 2 días | 1 |
| F2 | Régimen del ozono | ¿El ozono de la ZMVM está limitado por COV o por NOₓ, por zona? | 4 días | 1 |
| F3 | Diagnóstico de episodios | ¿Qué tan seguido acierta `nox-ml episode` en episodios de causa conocida? | 2 días | 1 |
| F4 | Contraste del inventario | ¿El oriente al 7 % (frente a 19 %) resiste pruebas independientes? | 3 días | 1 |
| F6 | Datos de actividad vehicular | ¿Qué fuente semanal de actividad se puede conseguir y explica la deriva? | 2 días | 1 |
| F7 | Control de calidad de redes públicas | ¿Cuántas anomalías por mes encuentra el QC en OpenAQ y SIMAT? | 1.5 días | 1 |
| F5 | Simulador de salud | ¿Cuántas muertes y casos de asma se evitarían con una baja de X % de la emisión vial? | 3 días | 2 (usa F2) |
| F8 | Monterrey | ¿Qué límite de detección tendría el sistema en el área metropolitana de Monterrey? | 2 días | 2 |
| — | Consolidación | Tabla comparativa de los ocho frentes y ajuste del resumen ejecutivo | 1 día | 3 |

La ola 1 corre en paralelo (seis frentes independientes). La ola 2 empieza cuando F2 tenga el efecto de fin de semana (F5) o cuando haya cómputo libre (F8).

### F1. Diseños alternados (`explore/switchback`)

- **Hipótesis.** La deriva dura semanas y es de toda la ciudad ([deriva.md](../knowledge/deriva.md)). Si la medida se enciende y se apaga en días o semanas intercalados, los dos grupos comparten la deriva y esta se cancela, como en el domingo frente al día hábil.
- **Prueba decisiva.** Con E7 y el mecanismo de inyección de las fichas (`ficha-dias`, `nox_ml.validation.products`), inyectar bajas de 5, 10, 15 y 20 % en diseños de igual número de días con medida: (a) días seguidos (el de hoy), (b) días alternos, (c) semanas alternas, (d) bloques de 2 semanas, (e) asignación aleatoria por día. Seis temporadas, días hábiles normales. Medir el mínimo detectable con 80 % de potencia y 90 % de confianza, y las falsas alarmas con 0 %.
- **Funciona si** algún diseño factible para una autoridad (semanas alternas o mejor) baja el mínimo de una temporada a ≤ 15 %. **No funciona si** queda en ≥ 25 %.
- **Cuidado.** Un efecto que se arrastra (la gente cambia de hábito y no vuelve en la semana sin medida) diluye la diferencia: probar una inyección con arrastre del 50 % a la semana siguiente.
- **Valor a estimar.** Autoridad y planeadores (CU3), financiadores (CU8). Qué medidas reales se podrían alternar (Hoy No Circula sabatino, carriles, tarifas) y cuáles no.

### F2. Régimen del ozono (`explore/ozone-regime`)

- **Paso 1 (1 día, sin datos nuevos).** Efecto de fin de semana con SIMAT 2019–2026: cociente domingo ÷ hábil del ozono máximo de 8 h, de Oₓ (O₃ + NO₂) y del NOₓ, por estación, en la temporada de ozono (feb–jun) y en invierno; separar centro y periferia. Controlar por clima con la misma idea de E7 (comparar días con ventilación y temperatura parecidas) o, como mínimo, con días de temperatura máxima similar. Si el NOₓ cae ~50 % en domingo y el ozono no cae (o sube), es evidencia de régimen limitado por COV.
- **Paso 2 (2–3 días).** TEMPO HCHO L2 (misma herramienta de descarga y el mismo recorte que el NO₂, carpeta `data/raw/tempo_hcho/`) para feb–may 2024 y feb–may 2025. Cociente HCHO/NO₂ promediado por píxel y por semana, en las horas de formación (12–16 h). Mapa por temporada: limitado por COV, transición o limitado por NOₓ, con los umbrales de Duncan et al. (2010) y una sensibilidad con umbrales de otros estudios.
- **Funciona si** el mapa del paso 2 coincide en el espacio con el efecto de fin de semana del paso 1 (las estaciones donde el ozono no cae en domingo quedan en la zona de COV). **No funciona si** el HCHO es demasiado ruidoso para separar zonas aun con un mes de promedio, o si los dos pasos se contradicen.
- **Valor a estimar.** CAMe y autoridad: las contingencias son sobre todo por ozono y la medida principal baja NOₓ. Cuántas contingencias al año; qué cambiaría en el programa de contingencias.
- **Comparar con la literatura** de la ZMVM sobre el régimen (campañas MCMA-2003 y MILAGRO-2006) para ver si el resultado es nuevo o confirma lo conocido.

### F3. Diagnóstico de episodios (`explore/episode-validation`)

- **Base.** `nox-ml episode` (`nox_ml.validation.episodes`) solo se probó en diciembre de 2023: 1 acierto claro, 1 falso positivo de emisión (18–22 dic) y 1 normal ([verificaciones_nivel1.md](../knowledge/verificaciones_nivel1.md), sección 2).
- **Conjunto de prueba con causa conocida.**
  - Clima: las semanas más estancadas y las más ventiladas de cada temporada (por capa de mezcla y viento, sin mirar el NOₓ).
  - Emisión baja conocida: festivos con tráfico bajo, Semana Santa, vacaciones escolares, confinamiento de 2020.
  - Acumulación: los fines de año y los episodios con fondo regional alto del recorte amplio de TEMPO.
  - Las contingencias oficiales 2023–2026 (`data/raw/contingencias/`), sin causa conocida, para medir qué diría el sistema.
- **Métricas.** Aciertos en la parte de clima; falsos positivos de emisión; cuántos veredictos quedan "no evaluable".
- **Probar un veredicto más prudente:** "el clima lo explica / lo explica en parte / no lo explica", sin afirmar emisión. Medir si mejora la tasa de error.
- **Funciona si** la parte de clima acierta en ≥ 80 % de los casos con causa conocida y los falsos positivos de emisión quedan en ≤ 10 % con el veredicto prudente.
- **Valor a estimar.** Autoridad y medios (CU1); cuántos episodios por año generan la pregunta.

### F4. Contraste del inventario (`explore/inventory-east`)

- **Base.** El oriente aporta el 7 % de la emisión vial frente al 19 % del inventario de 2018, en seis temporadas y con dos modelos (artículo, sección 4.5).
- **Pruebas.**
  1. **Independiente de las estaciones:** divergencia de flujo de TEMPO (`nox-ml flux-divergence`) agregada por zona.
  2. **Perfil horario:** la fracción del oriente en el inventario solo en 12–17 h (con el perfil horario del inventario o de Infovial), no diaria.
  3. **Sensibilidad:** quitar una a una las estaciones del oriente; mover la frontera de la zona; girar el viento ±20°.
  4. **Composición:** la fracción de carga pesada del oriente en el inventario frente a la caída del domingo por zona.
- **Funciona si** el satélite solo da una fracción del oriente claramente menor a la del inventario (≤ 12 %) y el resultado resiste las sensibilidades.
- **Entregable adicional:** un borrador de reporte de una página para un equipo de inventario.
- **Cómputo:** las corridas de sensibilidad con E5b≥0 van en serie (~10 min cada una); avisar antes de lanzar más de 10.

### F6. Datos de actividad vehicular (`explore/activity-data`)

- **Investigación documental.** Para cada fuente: resolución temporal y espacial, cobertura 2023–2026, cómo se accede, costo y tiempo hasta tener datos. Candidatas: aforos y velocidades de C5 y SEMOVI (solicitud por la Plataforma Nacional de Transparencia), Waze for Cities (requisitos: ente público), TomTom (índice público y acceso académico), Google Environmental Insights Explorer, ventas de gasolina y diésel (SENER/CRE, mensual por estado), aforos de autopistas (CAPUFE), afluencia de transporte público (ya probada: 1–3 % por semana, no explica la deriva).
- **Prueba.** Con cualquier fuente que se pueda descargar ya, correlacionar sus anomalías semanales con la deriva de E7 y del satélite ([deriva.md](../knowledge/deriva.md)). Con la mensual de combustible, al menos el orden de magnitud.
- **Entregables:** la tabla de fuentes; el texto de una solicitud de transparencia lista para enviar (la envía el equipo, no el agente); y la estimación de cuánto bajaría el límite con cada fuente según la parte de la deriva que explique.
- **Funciona si** hay al menos una fuente semanal accesible en ≤ 3 meses.

### F7. Control de calidad de redes públicas (`explore/network-qc`)

- **Prueba.** Correr el QC existente (`nox-ml qc-simat`, `nox_ml.data.qc`) sobre SIMAT 2019–2024 y OpenAQ 2024–2026; catalogar anomalías por tipo (unidades, sensores atascados, desfases de hora, saltos de nivel, huecos) y por mes. Comparar estaciones duplicadas entre SIMAT y OpenAQ en 2024.
- **Valor a estimar.** Cuántas anomalías por mes, cuántas afectarían a un usuario de los datos (por ejemplo, el viento de 2024 en mph). Quién las recibiría (operadores de SIMAT y SINAICA, OpenAQ) y en qué formato (reporte mensual, issue público).
- **Funciona si** encuentra ≥ 1 anomalía relevante al mes que no esté documentada por el operador.

### F5. Simulador de salud (`explore/health-scenarios`, ola 2)

- **Cadena.** Baja de X % de la emisión vial → baja de NO₂ por zona con la matriz de transporte del modelo final y el fondo (la concentración baja menos que la emisión) → exposición con la población por zona del INEGI (`data/raw/inegi/`) → muertes y casos de asma evitados con funciones de riesgo publicadas.
- **Pasos.**
  1. Verificar las funciones de riesgo con la fuente primaria (OMS 2021 y su revisión: Huangfu y Atkinson, 2020; Stieb et al., 2021; Achakulwisut et al., 2019) y las tasas base de mortalidad y asma de la ZMVM (INEGI, Secretaría de Salud). Hoy están en [capacidades.md](../knowledge/capacidades.md), algunas marcadas como pendientes.
  2. Pasar de NOₓ de tarde a NO₂ promedio anual con las estaciones (que miden las 24 h).
  3. Simulación con incertidumbre (función de riesgo, cociente NO₂/NOₓ, respuesta de la concentración).
  4. Con F2: anotar la penalización por ozono si el centro resulta limitado por COV (sin cuantificarla si no hay base).
- **Funciona si** el resultado queda en el orden de magnitud de estimaciones publicadas de carga por NO₂ en la Ciudad de México (buscarlas como control).
- **Valor a estimar.** Autoridad, salud pública, financiadores (CU9): "¿qué ganaríamos si…?" antes de decidir. No depende del límite de detección.

### F8. Monterrey (`explore/monterrey`, ola 2)

- **Prueba.** Aplicar la regla de clasificación de ciudades de [brechas_y_mejoras.md](../knowledge/brechas_y_mejoras.md) ("Otras ciudades"): estaciones del SIMA con NOₓ en OpenAQ (cobertura de horas 2024–2026), cobertura de TEMPO, capa de mezcla, viento de aeropuertos (MMMY, MMAN). Estimar el límite de detección con E7 sin replicar la inversión.
- **Valor a estimar.** El Hub está en el Campus Monterrey; usuarios locales (gobierno de Nuevo León, organizaciones civiles); peso de la industria frente al tráfico.
- **Funciona si** el límite estimado no es peor que el de la ZMVM y hay ≥ 8 estaciones con NOₓ y ≥ 60 % de horas.

## Consolidación (ola 3)

- Una tabla con la plantilla de veredicto de los ocho frentes, ordenada por valor × probabilidad de funcionar ÷ costo.
- Actualizar [capacidades.md](../knowledge/capacidades.md) y [brechas_y_mejoras.md](../knowledge/brechas_y_mejoras.md) con lo que cambió.
- Ajustar el resumen ejecutivo (`docs/entregables/ResumenEjecutivo.39.md`): propuesta de valor, beneficios, fases y recomendación.
- Pasar a [tareas.md](tareas.md) lo que se adopte, como tareas de implementación.

## Instrucción para cada agente

> Lee `CLAUDE.md`, `context/management/exploraciones_valor.md` (reglas comunes y tu frente) y las notas que cita tu frente. Trabaja en la rama `explore/<tema>` en un worktree propio desde `main`. Haz primero la prueba decisiva; si sale negativa, detente y documenta. Entrega `context/knowledge/<tema>.md` con la plantilla de veredicto llena, cifras reproducibles y la lista de lo que no alcanzaste a probar. Abre un pull request; no lo fusiones.
