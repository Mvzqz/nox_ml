# ¿Fue el clima o fue la ciudad? · Preguntas y respuestas

Equipo 39 · NOx·ML · Hub de Ciencia de Datos · Tec de Monterrey

Preguntas probables del público después de la presentación, agrupadas por la parte que las responde. Cada una trae una **respuesta corta** para decir en voz alta (unos 20 segundos) y un **respaldo** con las cifras por si piden más detalle. Las cifras vienen del resumen ejecutivo y del artículo final del proyecto.

Reglas para responder:

- Responde quien presentó la parte; si la pregunta cruza partes, contesta primero el presentador 2 (el que conoce el método).
- Empezar por la respuesta, luego el porqué. Volver a la tina cuando ayude.
- Nunca dar toneladas exactas ni muertes evitadas como cifra firme: siempre rango u orden de magnitud.
- Si no sabemos algo, decirlo y ofrecer el dato después.

## Resumen

| # | Pregunta | Responde |
|---|---|---|
| 1 | ¿Por qué no basta con las estaciones? | Presentador 1 |
| 2 | ¿El inventario oficial está mal? | Presentador 1 |
| 3 | ¿Por qué medir NOₓ y no otro contaminante? | Presentador 1 |
| 4 | ¿Qué es exactamente "el clima" en este sistema? | Presentador 2 |
| 5 | ¿Qué tan confiable es? | Presentador 2 |
| 6 | ¿Qué es una PINN y por qué no otra inteligencia artificial? | Presentador 2 |
| 7 | ¿Para qué sirve el satélite si ya hay estaciones? | Presentador 2 |
| 8 | ¿Por qué no ve medidas pequeñas? | Presentador 2 |
| 9 | ¿Puede decir cuántas toneladas emite cada zona? | Presentador 2 |
| 10 | ¿Qué pasa si una estación falla o da datos malos? | Presentador 2 |
| 11 | ¿Entonces el Hoy No Circula no sirve? | Presentador 3 |
| 12 | ¿El hallazgo del ozono es definitivo? | Presentador 3 |
| 13 | ¿Cuánto cuesta y quién lo opera? | Presentador 3 |
| 14 | ¿Quién lo usaría? | Presentador 3 |
| 15 | ¿Qué es el asistente para pilotos medibles? | Presentador 3 |
| 16 | ¿Se puede usar en otras ciudades? | Presentador 3 |
| 17 | ¿De dónde sale "cientos de muertes evitadas"? | Presentador 3 |
| 18 | ¿Cuáles son los riesgos de que se use mal? | Presentador 3 |
| 19 | ¿Qué sigue después del curso? | Presentador 3 |

---

## Parte 1 · El problema

### 1. ¿Por qué no basta con las estaciones?

**Responde:** Presentador 1

**Respuesta corta:** Las estaciones miden el nivel del agua, no la llave. Lo que respiramos sube o baja tanto por lo que emitimos como por el clima: una semana con viento y lluvia limpia el aire aunque la ciudad emita igual. Mirando solo el nivel no se sabe quién lo movió.

**Respaldo:** por eso el antes y después de una medida puede dar "funcionó" o "fracasó" con la misma emisión. El sistema corrige por clima antes de comparar.

### 2. ¿El inventario oficial está mal?

**Responde:** Presentador 1

**Respuesta corta:** No, es un trabajo valioso y lo seguimos necesitando. El problema es que es una estimación hecha con estadísticas de actividad, no una medición del aire, y llega tarde: el de 2018 se publicó en 2021. Nosotros no lo reemplazamos; damos una señal cada semana para saber si algo cambió mientras llega el siguiente.

### 3. ¿Por qué medir NOₓ y no otro contaminante?

**Responde:** Presentador 1

**Respuesta corta:** Por tres razones: daña por sí solo, es la huella de la combustión (sale junto con CO₂, hollín y partículas) y forma ozono y partículas finas. Además es el contaminante que mejor ve el satélite TEMPO, lo que nos da una segunda opinión independiente de las estaciones.

---

## Parte 2 · La solución

### 4. ¿Qué es exactamente "el clima" en este sistema?

**Responde:** Presentador 2

**Respuesta corta:** Todo lo que mueve la contaminación sin que la ciudad emita más o menos: el viento, la lluvia, la temperatura y, sobre todo, la altura de la capa de aire donde se mezcla el humo. Si esa capa es baja, el humo se concentra; si es alta, se diluye.

**Respaldo:** usamos meteorología pública (ERA5 por Open-Meteo y MERRA-2) y analizamos las tardes, de 12 a 17 h, cuando la capa de mezcla está desarrollada y el satélite observa.

### 5. ¿Qué tan confiable es?

**Responde:** Presentador 2

**Respuesta corta:** Lo probamos con datos que nunca vio y con cuatro pruebas. Le escondemos una estación y adivina lo que mide 14 % mejor que nuestra línea base. Cuando no hubo ningún cambio, no inventó uno. Su rango de confianza contiene el valor real 91 de cada 100 veces. Y vio la caída del confinamiento de 2020: −50 %, justo en el −40 a −60 % que esperaban los expertos.

**Respaldo:**

- **Estación oculta:** escondemos cada una de las 24 estaciones, ajustamos con las demás y predecimos la oculta. Error de 11.7 ppb, frente a 13.6 de la línea base; igual que interpolar (11.6) y, combinado con kriging, el mejor de todos (10.2). La interpolación solo rellena el mapa; nuestro modelo además estima la emisión.
- **Placebo:** días hábiles sin cambio, partidos al azar en dos grupos falsos. Da 0.95–1.11, con 1 como ideal, en las cuatro temporadas ciegas.
- **Rango honesto:** en 960 pruebas con cambios conocidos de 0 % y 20 %, el rango contuvo el valor real el 91 % de las veces (meta: 90 %), con 5 % de falsas alarmas.
- **Episodios:** acertó la causa en 49 de 52 episodios reales.
- **Si preguntan por el ancho del rango:** que el rango sea honesto no significa que sea angosto. Con solo 9 días, una baja real de 20 % se detecta el 46 % de las veces; con más días o varias temporadas el rango se angosta (con dos temporadas, 78 %).

### 6. ¿Qué es una PINN y por qué no otra inteligencia artificial?

**Responde:** Presentador 2

**Respuesta corta:** Es una red neuronal que aprende la ley física de cómo el viento arrastra y diluye el humo, en lugar de aprender de miles de ejemplos. Con solo 24 estaciones, una red común memorizaría. La PINN se entrena solo con la ecuación, así que no puede hacer trampa copiando la respuesta de la estación que escondemos para evaluarla.

**Respaldo:** comparamos 8 modelos y 6 combinaciones. Lo que más mejoró el resultado fue seguir el humo con memoria (las bocanadas); la PINN suma una mejora menor pero real. Somos honestos con eso: no es magia, es una pieza que respeta la física.

### 7. ¿Para qué sirve el satélite si ya hay estaciones?

**Responde:** Presentador 2

**Respuesta corta:** Las estaciones ven puntos; el satélite ve toda la ciudad, una foto por hora en la tarde, con píxeles de unos 2 × 4.5 km. Nos da una segunda opinión independiente: si las estaciones y el satélite dicen lo mismo, confiamos más.

### 8. ¿Por qué no ve medidas pequeñas?

**Responde:** Presentador 2

**Respuesta corta:** Porque la emisión estimada oscila unos ±15 % de semana a semana. Un cambio de 5–10 % en una sola temporada se pierde en ese ruido. Pero se puede ver con un piloto bien diseñado.

**Respaldo:** el cambio mínimo detectable es ~30 % en una temporada, 16–28 % si la medida se aplica en semanas alternas, y ~10 % repitiéndola en seis temporadas. Por eso proponemos el asistente para pilotos medibles.

### 9. ¿Puede decir cuántas toneladas emite cada zona?

**Responde:** Presentador 2

**Respuesta corta:** No con la precisión para publicarlo como toneladas. Lo que sí da con confianza es cuánto cambió la emisión, en porcentaje y con su rango, y qué zonas pesan más. Para toneladas sigue siendo mejor el inventario.

### 10. ¿Qué pasa si una estación falla o da datos malos?

**Responde:** Presentador 2

**Respuesta corta:** El sistema revisa la calidad de los datos cada día y detecta cortes de red. De hecho, encontró 21 cortes sin documentar en 22 meses. Si la prueba de "cambio falso" sale de rango, no se publica.

---

## Parte 3 · Impacto y futuro

### 11. ¿Entonces el Hoy No Circula no sirve?

**Responde:** Presentador 3

**Respuesta corta:** Sí sirve para bajar el NOₓ, que es bueno para los pulmones. Lo que encontramos es que en el centro de la ciudad bajar el NOₓ no baja el ozono, que es el contaminante de las contingencias. Para el ozono, la evidencia apunta a atacar los vapores: gasolina que se evapora, solventes y gas LP.

**Respaldo:** en 80 domingos comparados con días hábiles de clima parecido, el NOₓ cae 30 % y el ozono máximo queda igual o sube 3 %. En el confinamiento de 2020 el NOₓ bajó 33 % y el ozono solo 2–4 %, sin significancia.

### 12. ¿El hallazgo del ozono es definitivo?

**Responde:** Presentador 3

**Respuesta corta:** No lo presentamos como definitivo, pero no estamos solos: coincide con lo que encontraron otros investigadores con otro satélite (Vazquez Santiago et al., 2021). Y la ventaja es que el sistema lo puede revisar cada temporada casi sin costo.

### 13. ¿Cuánto cuesta y quién lo opera?

**Responde:** Presentador 3

**Respuesta corta:** Operarlo cuesta unos 6 mil pesos al mes. El primer año, con la puesta en marcha, son unos 137 mil pesos. Necesita una persona responsable 12 horas al mes. Los datos son públicos y gratuitos.

**Respaldo:** se paga con unos 6 análisis al año, comparado con hacerlos a mano (~40 horas cada uno frente a ~2 con el sistema).

### 14. ¿Quién lo usaría?

**Responde:** Presentador 3

**Respuesta corta:** La autoridad ambiental para evaluar medidas y explicar contingencias, el operador de la red de monitoreo para detectar fallas, la academia para investigar y los medios para verificar afirmaciones como "la medida funcionó". Por eso lo entregamos como bien público: un boletín mensual abierto y datos citables.

### 15. ¿Qué es el asistente para pilotos medibles?

**Responde:** Presentador 3

**Respuesta corta:** Antes de lanzar una medida, le dice a la ciudad cómo diseñar la prueba para que sí se pueda medir: cuántas semanas necesita y cómo alternar semanas con y sin la medida, como en un ensayo clínico. Así el clima no confunde el resultado.

### 16. ¿Se puede usar en otras ciudades?

**Responde:** Presentador 3

**Respuesta corta:** Sí. TEMPO cubre toda Norteamérica y las demás fuentes son públicas. Se necesitarían estaciones en tierra y ajustar la configuración por ciudad; es una de las mejoras que proponemos.

### 17. ¿De dónde sale "cientos de muertes evitadas"?

**Responde:** Presentador 3

**Respuesta corta:** Es un orden de magnitud preliminar, no una cifra exacta: aplicamos la relación publicada entre exposición a NO₂ y mortalidad (Huangfu y Atkinson, 2020) a una baja de 10 % en la emisión del tráfico. Lo decimos así para dimensionar lo que está en juego, nunca como una predicción.

### 18. ¿Cuáles son los riesgos de que se use mal?

**Responde:** Presentador 3

**Respuesta corta:** El principal es leer "no detectado" como "no funcionó", o citar las cifras como exactas. Por eso cada número sale con su rango y su límite de detección, y habrá una guía para usuarios. El otro riesgo es que nadie lo use: por eso proponemos un responsable y buscar un primer usuario externo antes del sexto mes.

### 19. ¿Qué sigue después del curso?

**Responde:** Presentador 3

**Respuesta corta:** Se entrega al Hub listo para operar: el código con sus pruebas automáticas, los datos versionados y la actualización diaria. La propuesta es una fase 1 de 12 meses; en el mes 6 se decide si continúa según si hay un usuario externo, datos de tráfico y audiencia para el boletín.
