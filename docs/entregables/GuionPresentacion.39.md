# ¿Fue el clima o fue la ciudad? · Guion de la presentación

Equipo 39 · NOx·ML · Hub de Ciencia de Datos · Tec de Monterrey

Guion de 12 minutos en tres partes, una por presentador. Cada bloque indica la diapositiva, su título en pantalla, quién habla y en qué minuto. «(Clic.)» marca cuándo avanzar la animación.

## Resumen

| Diapositiva | Título | Parte | Presentador | Tiempo |
|---|---|---|---|---|
| 1 | ¿fue el clima o fue la emisión? | El problema | 1 | 0:00–0:45 |
| 2 | por qué importa el NOx | El problema | 1 | 0:45–2:10 |
| 3 | cómo se mide hoy | El problema | 1 | 2:10–3:10 |
| 4 | la tina de baño | El problema | 1 | 3:10–4:00 |
| 5 | la solución | La solución | 2 | 4:00–4:45 |
| 6 | el gemelo del clima | La solución | 2 | 4:45–5:45 |
| 7 | la pinn: de dónde viene | La solución | 2 | 5:45–6:50 |
| 8 | la evaluación: el confinamiento | La solución | 2 | 6:50–7:25 |
| 9 | acierta, no inventa y da rangos de confianza | La solución | 2 | 7:25–8:00 |
| 10 | si quitamos coches, ¿baja el ozono? | Impacto y futuro | 3 | 8:00–9:30 |
| 11 | qué cambia | Impacto y futuro | 3 | 9:30–10:20 |
| 12 | posibles mejoras | Impacto y futuro | 3 | 10:20–11:00 |
| 13 | riesgos y lo que está en juego | Impacto y futuro | 3 | 11:00–12:00 |
| 14 | fuentes de las fotos | Apoyo | — | No se presenta |

---

## Parte 1 · El problema

*Parte 1, el problema: no sabemos si una medida funcionó porque el clima lo confunde todo.*

### Diapositiva 1 · ¿fue el clima o fue la emisión?

**Presentador 1 · 0:00–0:45**

Miren estas dos fotos. Es la misma ciudad en dos días distintos. En una el cielo está limpio y se ven los volcanes; en la otra, una capa amarillenta borra el horizonte y no se ve ni un volcán. ¿Qué cambió? ¿Fue el clima… o fue la ciudad?

Hoy nadie puede responder eso. Las estaciones nos dicen cuánta contaminación respiramos, pero no cuánta produce la ciudad, ni por qué cambió.

### Diapositiva 2 · por qué importa el NOx

**Presentador 1 · 0:45–2:10**

¿Por qué nos importa tanto el NOₓ, los óxidos de nitrógeno? Por tres razones.

Primera: daña por sí solo. Irrita los pulmones y agrava el asma; en niños, respirarlo por años se asocia con que más desarrollen asma.

Segunda: delata la combustión. Sale de cada motor que quema gasolina o diésel, siempre acompañado de dióxido de carbono, hollín, monóxido de carbono y partículas finas. Por eso, si vemos bajar el NOₓ, sabemos que bajó la quema de combustible: es la huella del escape de la ciudad.

Tercera: se transforma. Con el sol forma ozono, el contaminante de las contingencias, y en el aire forma partículas finas que le dan a la ciudad ese tono café.

Y el daño no se queda en la salud: lluvia ácida que daña bosques y edificios, cosechas más pobres, y cada contingencia detiene la ciudad y cuesta dinero.

Por eso la ciudad invierte tanto en reducirlo. Pero lo que no se mide no se puede mejorar.

### Diapositiva 3 · cómo se mide hoy

**Presentador 1 · 2:10–3:10**

¿Cómo se mide hoy lo que emite la ciudad? Con el inventario oficial de emisiones. Es una gran suma: cuántos coches hay, cuántos kilómetros recorren, cuánto contamina cada motor, más fábricas y comercios. Es un trabajo enorme y valioso, pero es una estimación en papel, no una medición del aire, y tarda años: el de 2018 se publicó en 2021.

Mientras tanto, se hace lo más sencillo: comparar la contaminación antes y después de una medida. Imaginen la misma medida, aplicada igual. (Clic.) Si después llega una semana con viento y lluvia, el nivel baja y decimos: «¡funcionó!». (Clic.) Si llega una semana quieta y fría, sube y decimos: «fracasó». (Clic.) Pero en los dos casos la emisión bajó exactamente igual. Lo único que cambió fue el clima.

### Diapositiva 4 · la tina de baño

**Presentador 1 · 3:10–4:00**

¿Por qué pasa esto? Piensen en el aire como una tina de baño. Uno, la llave: es lo que emitimos. Tres, el desagüe: es el clima; una semana con viento y lluvia lo destapa, una quieta y fría lo tapa. Y dos, el nivel del agua: es lo que respiramos.

Las estaciones solo miden el nivel del agua. (Clic.) Podemos cerrar la llave… (clic) y si el clima tapa el desagüe, el agua sube igual. (Clic.) Por eso, mirando solo el nivel, nunca sabemos quién lo movió.

Entonces la pregunta es: ¿se puede ver la llave, cada semana, separándola del clima? Eso es lo que construimos, y mi compañero les va a contar cómo.

---

## Parte 2 · La solución

*Parte 2, la solución: separar el clima de la ciudad con estaciones, satélite y una PINN, y probar que funciona.*

### Diapositiva 5 · la solución

**Presentador 2 · 4:00–4:45**

Gracias. Para ver la llave usamos tres fuentes que ya existen y que cualquiera puede descargar gratis. 24 estaciones que miden el aire a nivel de calle. TEMPO, un satélite de la NASA que desde el espacio toma una foto de la contaminación sobre la ciudad cada hora. Y el clima: viento, lluvia, temperatura. Cada una sola cuenta una parte de la historia; juntas, la cuentan completa. Todos los días las limpiamos y las pasamos por dos piezas que les voy a mostrar: el gemelo del clima, que dice cuánto cambió la emisión, y la PINN, que dice de dónde viene. Juntas responden la pregunta de cada semana: ¿fue el clima o fue la ciudad?, siempre con su rango.

### Diapositiva 6 · el gemelo del clima

**Presentador 2 · 4:45–5:45**

¿Cómo separamos el clima de la ciudad? Construimos un gemelo del clima. El sistema aprende, año tras año, cuánta contaminación debería haber con cada tipo de clima si la ciudad se comportara igual que siempre. Esa es la banda punteada.

Luego lo comparamos con lo que realmente pasó. (Clic.) Si la línea se queda dentro de la banda, fue el clima. (Clic.) Si se sale, el clima ya no lo explica: algo cambió en la llave. Y lo vemos cada semana, no cada tres años.

### Diapositiva 7 · la pinn: de dónde viene

**Presentador 2 · 5:45–6:50**

Saber cuánto cambió no basta; también queremos saber de dónde viene. Para eso usamos una PINN, una red neuronal informada por la física. Una red neuronal común aprende de miles de ejemplos. Nosotros solo tenemos 24 estaciones: con tan pocos datos, memorizaría en lugar de entender. Por eso a la nuestra no le enseñamos datos, le enseñamos la ley física de cómo el viento arrastra y dispersa el humo.

Miren el mapa: una sola bocanada que sale de esta zona se estira con el viento y llega a tres estaciones a la vez, cada vez más diluida. Y cada estación, a su vez, recibe humo de varias zonas. Con la PINN seguimos todas esas bocanadas y luego hacemos la pregunta al revés: ¿cuánto tuvo que emitir cada zona para explicar lo que miden las estaciones? Es como deducir qué llave está abierta viendo dónde se moja el piso. Es la opción adecuada porque respeta la física, funciona con pocos datos y no puede hacer trampa copiando la respuesta.

### Diapositiva 8 · la evaluación: el confinamiento

**Presentador 2 · 6:50–7:25**

¿Cómo sabemos que funciona? Le pusimos un examen con la respuesta conocida: el confinamiento de 2020, cuando la ciudad se detuvo. Tiene que ver una caída enorme en la llave. Y la vio: menos 50 %, justo en el rango que esperaban los expertos.

### Diapositiva 9 · acierta, no inventa y da rangos de confianza

**Presentador 2 · 7:25–8:00**

¿Cómo sabemos que podemos confiar en él? Con tres pruebas. Primero, que acierte: le escondemos una estación, el modelo no la ve y tiene que adivinar qué mide con las demás. Lo hace 14 % mejor que nuestra línea base, y además nos dice cuánto se emite. Segundo, que no invente: le damos días en los que no pasó nada, los partimos al azar como si fueran una medida, y responde que no cambió nada. Y tercero, nunca da un número solo: siempre lo acompaña de un rango, y ese rango es honesto. Lo probamos con cambios simulados: el valor real cayó dentro del rango 91 de cada 100 veces, justo lo que promete.

Pero un sistema que funciona no sirve de nada si no cambia algo. Y aquí viene lo más interesante: lo que descubrimos al usarlo.

---

## Parte 3 · Impacto y futuro

*Parte 3, impacto y futuro: el hallazgo del ozono, qué cambia, posibles mejoras y riesgos.*

### Diapositiva 10 · si quitamos coches, ¿baja el ozono?

**Presentador 3 · 8:00–9:30**

Gracias. Les hago una pregunta: si quitamos coches de la calle, ¿baja el ozono, el contaminante de las contingencias? La intuición dice que sí. Por eso la medida principal en una contingencia es el Doble Hoy No Circula. Usamos el sistema para revisarlo con un experimento que la ciudad hace sola cada semana: el domingo. Comparamos 80 domingos con días hábiles de clima parecido. (Clic.) El NOₓ cae 30 %. (Clic.) Y el ozono… se queda igual. En el confinamiento pasó lo mismo. (Clic.) ¿Por qué? Porque en el centro de la ciudad el ozono no depende tanto de los escapes, sino de otros vapores: gasolina que se evapora, solventes, gas LP. Esto sugiere que las contingencias podrían atacarse mejor por otro lado. No es una conclusión nuestra sola: coincide con lo que encontraron otros investigadores con otro satélite. Y ahora la ciudad puede revisarlo cada temporada, casi sin costo.

### Diapositiva 11 · qué cambia

**Presentador 3 · 9:30–10:20**

¿Qué cambia con esto? Pasamos de ver la llave cada tres años a verla cada semana. Antes de lanzar una medida, un asistente le dice a la ciudad cómo diseñar el piloto para que sí se pueda medir: cuántas semanas necesita y cómo alternarlas. Y lo entregamos como un bien público: un boletín mensual abierto y datos que cualquiera puede citar. Miren septiembre: la concentración cayó 11 %, pero sin el efecto del clima la emisión quedó igual. El boletín marca las dos semanas raras y dice cuál explicó el clima y cuál no. Para un periodista, un funcionario o un investigador, significa poder preguntar «¿fue el clima?» y tener una respuesta con evidencia. Operarlo cuesta unos 6 mil pesos al mes.

### Diapositiva 12 · posibles mejoras

**Presentador 3 · 10:20–11:00**

¿Y qué sigue? Ordenamos las mejoras por impacto y por esfuerzo. Arriba a la izquierda está lo primero, lo barato que más ayuda: diseñar pilotos en semanas alternas, cruzar la emisión con salud y con quién la respira en cada zona, y usar el monóxido de carbono para separar el tráfico de la industria. Con más esfuerzo: conseguir datos de tráfico y repartir la emisión por alcaldía. Y la gran apuesta es un viento más fino sobre el valle, que mejora todo lo demás. Además, el mismo método puede llevarse a otras ciudades que cubre el satélite.

### Diapositiva 13 · riesgos y lo que está en juego → cierre: ¿fue el clima o fue la ciudad?

**Presentador 3 · 11:00–12:00**

Queremos ser honestos con los límites. Una medida que baje la emisión 5 o 10 % no se nota en una sola temporada, por eso no damos toneladas exactas y siempre publicamos el rango. El otro riesgo es más humano: que nadie lo use; por eso proponemos un responsable y un primer usuario externo antes del sexto mes.

Y lo que está en juego no es menor: una baja de 10 % en las emisiones del tráfico podría evitar, como orden de magnitud, cientos de muertes al año.

(Clic: cierre.) Volvamos a las dos fotos del inicio. Hasta hoy, nadie podía decirles qué cambió entre una y otra. Ahora sí. La pregunta ya no es si podemos saberlo, sino qué vamos a hacer con lo que sabemos. Gracias.

---

## Apoyo

### Diapositiva 14 · fuentes de las fotos

Diapositiva de apoyo, no se presenta. Créditos de las fotografías usadas en la presentación.
