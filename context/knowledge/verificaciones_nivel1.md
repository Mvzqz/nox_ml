# Verificaciones y herramientas del nivel 1

Fecha: 2026-10-28. Primeras seis mejoras de [brechas_y_mejoras.md](brechas_y_mejoras.md) (las de alto retorno y poco esfuerzo). Todas las decisiones usan noviembre–diciembre de 2023. Febrero–mayo de 2024 solo aparece en Semana Santa, con E7 como referencia, igual que en las contingencias.

## Resumen

| Tarea | Resultado | Consecuencia |
|---|---|---|
| 1. Alineación horaria de TEMPO con SIMAT | Correlación máxima con desfase 0 (r 0.77, frente a 0.69 con −1 h y 0.73 con +1 h) | La convención es correcta; no hay nada que corregir |
| 1. Festivos incompletos (2 de noviembre y 12 de diciembre) | Quitarlos no mueve el domingo/hábil (E7 0.56 → 0.56; E6 0.53 → 0.53–0.56; E5b 0.48 → 0.48) | Sin efecto |
| 1. Días hábiles de fin de año (18–29 de diciembre) | **Quitarlos sube el domingo/hábil**: E7 0.56 → 0.63–0.65, E6 0.53 → 0.74–0.75, E5b solo 0.48 → 0.53 | Explica buena parte del sesgo del domingo en los estimadores estadísticos, poco en E5b (ver abajo) |
| 5. Piso de ruido | ~4 ppb entre estaciones casi en el mismo punto; 11–13 ppb a la distancia típica de la red (5–8 km) | Ningún modelo puede bajar de ~4 ppb; el margen entre 4 y ~10 ppb es estructura a escala menor que la red |
| 3. Control positivo con calendario | Fin de año 2023: la emisión **sube** (E7 1.38, E6 1.23); Semana Santa 2024: baja 8 % (E7 0.92, 0.74–1.12), no significativa | Sin confirmación positiva todavía; el fin de año no es un control limpio |
| 4. Curva de detección | Con E7 en nov–dic: 28 % con 9 días (la mitad de las veces), 37 % con 80 % de potencia; extrapolado: 19 % con una temporada, 10 % con un año. Sin los días de fin de año, igual | Más pesimista que en feb–may (20 % con 9 días): el invierno varía más; el límite depende de la temporada |
| 2. Diagnóstico de episodios | Herramienta nueva (`nox-ml episode`): separa clima, emisión, fondo regional y parte urbana; en diciembre de 2023 sus veredictos tienen sentido físico | Primera capacidad del caso de uso replanteado (CU1) |
| 6. Regresión-kriging | Sobre E5b: **10.2 ppb**, el mejor de la tabla (E5b 11.87, kriging 10.33, híbrido con IDW 10.40), con las emisiones y el placebo de E5b | Candidato a modelo final en concentración sin cambiar la emisión |

## 1. Errores de convención

**Alineación horaria.** SIMAT marca el fin de la hora (se corrige con −1 h) y TEMPO se asigna a la hora en que empezó su barrido (los píxeles caen entre el minuto 3 y el 59). Se correlacionó la columna media de los píxeles a menos de 4 km de cada estación con el NO₂ de la estación, desplazando la hora de SIMAT. Con desfase 0 la correlación es máxima, tanto cruda (0.78) como en anomalías por estación y hora (0.77) y por estación (mediana 0.77). Los desfases de ±1 h bajan a 0.69–0.73.

**Festivos incompletos.** En 2023 el 24 y el 31 de diciembre caen en domingo, así que ya cuentan como domingos. Los candidatos son el 2 de noviembre y el 12 de diciembre (días hábiles con menos actividad en parte de la ciudad). Quitarlos no cambia el domingo/hábil de ningún modelo.

**Días hábiles de fin de año.** La semana del 18 de diciembre tiene NOₓ de tarde de 49 ppb frente a ~28 ppb en las semanas normales, con ventilación normal (capa de mezcla de 1074 m y viento típico), y la columna de TEMPO también sube (18 frente a 9–12 × 10¹⁵ moléculas/cm²). Dos mediciones independientes coinciden: el NO₂ sí subió. Esos días entran en la referencia de día hábil y la inflan, así que el domingo/hábil baja:

| Modelo | Todos los días | Sin 18–29 de diciembre | Sin 12 y 18–31 de diciembre |
|---|---|---|---|
| E7 (normalizado) | 0.56 (0.46–0.71) | 0.63 (0.53–0.80) | 0.65 (0.50–0.79) |
| E6 (bosque aleatorio) | 0.53 (0.42–0.57) | 0.75 (0.63–0.89) | 0.74 (0.60–0.81) |
| E5b (PINN con puffs) | 0.48 (0.36–0.62) | 0.53 (0.44–0.67) | 0.53 (0.44–0.68) |

El rango esperado por el tráfico es 0.65–0.73. Sin los días de fin de año, E7 y E6 quedan dentro o cerca; E5b sube solo 0.05 y sigue lejos. Es la primera causa concreta del sesgo del domingo en los estimadores estadísticos, que no tienen término de fondo y cargan el aumento de fin de año a la referencia de día hábil. En E5b explica una parte menor: la inversión estima un fondo por hora que absorbe parte del aumento, y su sesgo restante debe tener otra causa (supuesto inicial, química, peso de TEMPO), que es el experimento de techo 3. El diagnóstico de episodios (sección 2) indica que en la semana del 18 de diciembre subió la parte de la columna que agrega la ciudad, no solo el fondo regional: hubo más emisión (compras, traslados y actividad de diciembre), además de algo de acumulación.

Consecuencias:
- Para el avance 5, reportar el domingo/hábil también sin los días de fin de año, como sensibilidad, sin cambiar el modelo ni la selección.
- En feb–may 2024 no hay fin de año, así que la corrida única no tiene este problema; sí lo tiene la comparación con nov–dic.
- Para el producto, la referencia de día hábil debe excluir periodos atípicos (fin de año, vacaciones) o modelarlos aparte.

## 5. Piso de ruido

Diferencia horaria de NOₓ entre pares de estaciones (tardes de nov–dic 2023). La mitad del cuadrado medio de la diferencia crece con la distancia; su valor extrapolado a 0 km (el nugget) es el ruido que ninguna estación vecina puede explicar: medición y fuentes a menos de ~1 km.

| Distancia entre estaciones | Pares | Diferencia cuadrática media (mediana) | Sesgo medio absoluto |
|---|---|---|---|
| 0–5 km | 4 | 11.4 ppb | 4.9 ppb |
| 5–8 km | 17 | 12.7 ppb | 4.5 ppb |
| 8–12 km | 27 | 14.4 ppb | 8.4 ppb |
| 12–16 km | 40 | 17.6 ppb | 9.8 ppb |
| 16–25 km | 81 | 19.7 ppb | 10.7 ppb |

- Piso absoluto: ~4 ppb (nugget de 13–16 ppb² con pares a menos de 10–15 km). El único par a menos de 3 km (CCA–PED) difiere 4.6 ppb.
- A la separación típica de la red (5–8 km) dos estaciones ya difieren 11–13 ppb: el kriging (10.3 ppb) aprovecha casi toda la información espacial de la red.
- Lectura: E5b (11.9 ppb) está a ~1.5 ppb del kriging y a ~8 ppb del piso absoluto. Bajar de ~10 ppb exige resolver estructura a escala menor que la red (vialidades, viento local), no mejor estadística.

## 3. Control positivo con eventos de calendario

Comando nuevo: `nox-ml calendar <config> --days INICIO:FIN --label NOMBRE [--period test] [--inject ...]`. Mismo análisis que las contingencias (días del evento reetiquetados frente a días hábiles normales, placebos al azar y mal ventilados), con los días de contingencia fuera de la referencia.

| Evento | Modelo | Días hábiles | Evento / normal | Placebo al azar | Placebo mal ventilado |
|---|---|---|---|---|---|
| Fin de año 2023 (18–29 dic) | E7 | 9 | 1.38 (1.15–1.73) | 1.03 (0.71–1.28) | 0.88 (0.64–1.16) |
| Antes de Navidad (18–22 dic) | E7 | 5 | 1.39 (1.09–1.79) | 1.00 (0.68–1.37) | 0.83 (0.56–1.18) |
| Después de Navidad (26–29 dic) | E7 | 4 | 1.22 (1.09–1.41) | 1.04 (0.69–1.38) | 0.92 (0.59–1.37) |
| Fin de año 2023 | E6 | 9 | 1.23 (1.14–1.48) | 0.97 (0.80–1.15) | 1.10 (0.90–1.29) |
| Semana Santa y Pascua 2024 (25–27 mar, 1–5 abr) | E7 | 8 | 0.92 (0.74–1.12) | 0.99 (0.81–1.23) | 0.97 (0.81–1.16) |

Inyección en Semana Santa (E7): 10 % no detectado, 20 % y 30 % detectados, recuperados completos. En fin de año, solo 30 % se detecta (la variación de nov–dic es mayor).

Lectura:
- **Fin de año no es un control positivo:** la emisión sube, y dos modelos coinciden. El diagnóstico de episodios (sección 2) apunta a emisión real en la semana previa a Navidad: sube la parte urbana de la columna de TEMPO, no solo el fondo. Sin datos de tráfico de 2023 no se puede confirmar con una fuente independiente.
- **Semana Santa apunta en la dirección esperada (−8 %), pero dentro del límite de detección (~20 %).** Los días con más baja de tráfico (jueves y viernes santos) son festivos y quedan fuera del análisis de días hábiles; lo que queda es el efecto de las vacaciones escolares, más chico.
- Conclusión honesta: todavía no hay un cambio real conocido que el método detecte. El control positivo sigue pendiente; un mejor candidato es un periodo largo con cambio conocido (el confinamiento de 2020, fuera de esta entrega) o datos de tráfico recientes.

## 4. Curva de detección por número de días

Comando nuevo: `nox-ml detection <config> [--days k ...]`. Para cada duración k sortea k días falsos entre los días hábiles normales (placebo) y calcula la baja que se detecta: una baja d multiplica el cociente, así que se detecta cuando `(1 − d) · r` cae bajo el límite inferior del placebo. La prueba de inyección respalda la forma multiplicativa (las bajas inyectadas se recuperan completas).

E7, nov–dic 2023, 300 sorteos por duración:

| Días hábiles | Placebo | Baja detectada la mitad de las veces | Baja detectada el 80 % de las veces |
|---|---|---|---|
| 3 | 1.05 (0.60–1.43) | 43 % | 51 % |
| 5 | 1.01 (0.66–1.40) | 34 % | 46 % |
| 9 | 1.03 (0.74–1.32) | 28 % | 37 % |
| 15 | 1.01 (0.77–1.30) | 23 % | 34 % |
| 20 | 0.99 (0.77–1.26) | 22 % | 31 % |

Variación día a día ajustada: 0.46. Extrapolado contra un periodo de referencia del mismo tamaño (antes y después), con 80 % de potencia: 30 % con 20 días, 19 % con 60 (una temporada), 14 % con 120 y 10 % con 250 (un año).

Lectura:
- Más pesimista que la prueba de inyección en feb–may 2024 (20 % con 9 días). No es por los días de fin de año: sin ellos (`--exclude 2023-12-18:2023-12-29`) la curva y la variación (0.46) no cambian. El invierno, con estancamientos, varía más de un día a otro; el límite depende de la temporada y debe medirse en cada una.
- Las cifras anteriores de [capacidades.md](capacidades.md) (~6–8 % con una temporada, ~3–4 % con un año) eran optimistas; con 80 % de potencia y la variación de nov–dic son 19 % y 10 %. Ya se corrigieron ahí, en [casos_de_uso.md](casos_de_uso.md) y en [brechas_y_mejoras.md](brechas_y_mejoras.md).

## 2. Diagnóstico de episodios

Comando nuevo: `nox-ml episode --days INICIO:FIN --data INICIO:FIN`. No ajusta ningún modelo (corre en segundos). Compara los días del episodio con días de referencia del mismo día de la semana a ±4 semanas:

- **concentración:** NOₓ observado por hora;
- **clima:** NOₓ modelado con la emisión fija (pluma del baseline): el efecto de la ventilación;
- **emisión:** concentración ÷ clima (el estimador normalizado, familia de E7);
- **fondo regional:** el percentil 10 de las columnas de TEMPO de cada hora, lo que la ciudad no emite; sube cuando la contaminación se acumula varios días;
- **parte urbana:** la columna media de TEMPO por encima de ese fondo, lo que agrega la ciudad; sube con la emisión.

Cada cociente tiene un intervalo nulo del 95 % de 500 episodios falsos con los mismos días de la semana (con 90 %, uno de cada diez episodios sin nada especial salía "inusual" por azar). El veredicto: emisión, clima, ambos, acumulación, normal o, si suben a la vez la emisión y el fondo con clima inusual, emisión o acumulación. Cuando suben la emisión y el fondo con clima normal, la parte urbana decide: si también sube, es emisión (con la nota de que el fondo subió); si no, acumulación.

Diciembre de 2023 (entre paréntesis, el intervalo de los días normales):

| Semana | Concentración | Clima | Emisión | Fondo regional | Parte urbana | Veredicto |
|---|---|---|---|---|---|---|
| 11–15 dic (estancada) | 1.55 (0.77–1.31) | 2.20 (0.77–1.33) | 0.70 (0.80–1.23) | 1.56 (0.58–1.66) | 0.71 (0.64–1.46) | Clima; la emisión sale en contra |
| 18–22 dic | 1.36 (0.75–1.34) | 1.02 (0.68–1.76) | 1.34 (0.63–1.28) | 1.78 (0.57–1.73) | 1.65 (0.67–1.47) | Emisión, con el fondo arriba |
| 26–29 dic | 0.81 (0.71–1.43) | 0.72 (0.64–1.79) | 1.12 (0.62–1.36) | 0.77 (0.47–1.92) | 1.21 (0.65–1.57) | Normal |

Lectura:
- La semana estancada es clima, pero la emisión sale baja (0.70): en estancamientos fuertes la normalización sobrecorrige la ventilación, un sesgo ya conocido del estimador. El veredicto lo marca (`emission_against_weather`) en lugar de reportar una baja de emisión. La parte urbana de la columna también baja: con la capa de mezcla baja el NO₂ se concentra en superficie, pero la columna no crece igual.
- La semana del 18 de diciembre no se explica por el clima. Subió el fondo regional, pero también la parte que agrega la ciudad (+65 %): hubo más emisión, no solo acumulación. Es consistente con el aumento de actividad de diciembre.
- El veredicto es una pista, no una prueba; para afirmar un cambio de emisión sostenido hace falta un periodo más largo (sección 4).

## Decisión para la corrida única del sábado

Los periodos atípicos inflan la referencia de día hábil (sección 1). En feb–may 2024 el periodo atípico conocido son las vacaciones de Semana Santa y Pascua. Se decide antes de ver resultados: en el análisis de contingencias con el modelo final, los días hábiles del 25 al 27 de marzo y del 1 al 5 de abril de 2024 quedan fuera de los días normales (`nox-ml contingencies ... --exclude 2024-03-25:2024-03-27 --exclude 2024-04-01:2024-04-05`). Se reporta también sin excluirlos, como sensibilidad.

## 6. Regresión-kriging

Modelo nuevo del registro: `residual_kriging`. Un modelo base (por defecto E5b) da la concentración que explica la física y un kriging de sus residuos entre estaciones corrige cada hora. La forma del variograma (alcance y nugget relativo) es una para todo el periodo, elegida por máxima verosimilitud agrupando todas las horas, solo con las estaciones de entrenamiento; cada hora conserva su media y su escala. Las emisiones son las del modelo base.

| Base | Base sola | Base + IDW de residuos (híbrido) | Regresión-kriging | Kriging solo |
|---|---|---|---|---|
| Baseline (inversión con pluma) | 13.59 | 11.69 | 11.6 | 10.33 |
| E5b | 11.87 | 10.40 | **10.2** | 10.33 |

La forma del variograma se elige por validación cruzada dejando una estación fuera dentro de las estaciones de entrenamiento, agrupando todas las horas. La primera versión la elegía por máxima verosimilitud y daba 10.9 ppb sobre E5b: la verosimilitud premia describir el campo, no predecir la estación que falta.

Lectura:
- Con E5b de base es el mejor modelo en concentración de la tabla: 1.7 ppb mejor que E5b y 0.1 ppb mejor que el kriging solo. La diferencia con el kriging está dentro del ruido (~±0.5 ppb): empatan en concentración, pero la regresión-kriging además explica la emisión.
- Emisiones, domingo/hábil (0.48) y placebo (1.01 ± 0.12) son los de E5b: no resuelve el sesgo del domingo.
- Cuesta lo mismo que E5b (~8 min por ajuste); el kriging agrega segundos.

## Reproducir

```bash
uv run nox-ml calendar configs/experiments/normalized_ratio.yaml --days 2023-12-18:2023-12-29 --label year_end --refits 200 --inject 0.1 --inject 0.2 --inject 0.3
uv run nox-ml calendar configs/experiments/normalized_ratio.yaml --period test --days 2024-03-25:2024-03-27 --days 2024-04-01:2024-04-05 --label easter --refits 200 --inject 0.1 --inject 0.2 --inject 0.3
uv run nox-ml detection configs/experiments/normalized_ratio.yaml --refits 300
uv run nox-ml detection configs/experiments/normalized_ratio.yaml --refits 300 --exclude 2023-12-18:2023-12-29 --label no_year_end
uv run nox-ml episode --days 2023-12-18:2023-12-22 --data 2023-11-01:2023-12-31 --label pre_christmas
uv run nox-ml run configs/experiments/residual_kriging.yaml
```

La alineación horaria, los festivos y el piso de ruido son análisis de una sola vez; sus guiones no forman parte del paquete.
