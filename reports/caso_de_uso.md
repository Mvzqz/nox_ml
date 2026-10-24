# Caso de uso real para la capacidad actual

Fecha: 2026-10-20. Base: resultados en `reports/RESUMEN.md`; contexto institucional con las fuentes al final.

## Resumen

El caso más defendible es **separar la emisión de la meteorología** al evaluar medidas que cambian mucho el tráfico. El ejemplo principal son las restricciones vehiculares de las contingencias ambientales. Hoy se evalúan con concentraciones, y una concentración mezcla dos cosas: cuánto se emite y qué tan estancado está el aire. Nuestro método estima la emisión vial por zona y por tipo de día con datos públicos y gratuitos, sin esperar al inventario.

El caso secundario es **verificar los patrones del inventario entre ediciones**: el reparto de la emisión vial por zona y su ciclo semanal.

**Condición previa.** Los cambios se reportan con el **estimador normalizado por meteorología**, no con la inversión completa. La inversión completa exageraba la baja dominical (0.31–0.47), pero ese número lo fijaba el a priori, no los datos (ver `sesgo_domingos.md`). El estimador normalizado da domingo/hábil 0.65 (IC 90 % 0.55–0.75), coherente con los conteos de Infovial del día completo (0.65–0.73), y pasa los placebos con un margen de ~±10 %. Los totales absolutos siguen dependiendo del modelo (ver `pinn_prototipo.md`).

### Cómo se hace hoy

El gobierno usa cuatro herramientas. Cada una responde una pregunta distinta, y ninguna responde "¿cuánto se emitió esta semana en esta zona?".

**1. El inventario de emisiones (de abajo hacia arriba).** SEDEMA cuenta las fuentes y multiplica su actividad por un factor de emisión. En la edición 2018:
- **Vehículos:** la flota sale de las bases de datos de la verificación vehicular de la CDMX, el Estado de México e Hidalgo, de registros del INEGI y de los aforos de la SCT en las entradas a la ciudad (vehículos federales y foráneos). Los kilómetros recorridos se estiman por tipo de vehículo, año modelo y combustible. Las emisiones se calculan con MOVES-CDMX, una adaptación local del modelo MOVES2014a de la EPA, con apoyo de campañas de sensor remoto.
- **Industria y comercio regulados:** los propios establecimientos reportan sus consumos y emisiones en la Licencia Ambiental Única (CDMX), la Cédula de Operación Integral (Estado de México) y la Cédula de Operación Anual (Hidalgo y federal).
- **Fuentes de área y naturales:** factores de emisión aplicados a datos de actividad como población, consumo de gas o superficie.

El resultado son toneladas por año por tipo de fuente, entidad y jurisdicción, más mapas de distribución espacial. Es la base del ProAire. Sus límites: es una **estimación, no una medición**; depende de supuestos de actividad (cuántos kilómetros recorre cada auto, con qué perfil por hora y por día); sale cada varios años y con retraso (el de 2018 se publicó en agosto de 2021); y no puede decir si una medida aplicada en días concretos cambió las emisiones.

**2. El monitoreo (SIMAT).** Unas 30 estaciones miden concentraciones cada hora. Con ellas se calcula el índice de calidad del aire y se activan las contingencias cuando el ozono o las partículas pasan los umbrales. Mide lo que respira la gente, pero una concentración no separa emisión de ventilación: el mismo tráfico produce concentraciones muy distintas en un día ventoso y en uno estancado.

**3. El pronóstico (AQFS-Mex).** SEDEMA corre un modelo meteorológico y químico (WRF a ~1 km) que predice concentraciones para los días siguientes. Usa el inventario como **entrada**: si el inventario está desactualizado o mal repartido, el pronóstico hereda el error. No estima emisiones; las supone.

**4. La evaluación de políticas.** Se hace con estudios puntuales que comparan concentraciones antes y después de una medida (Davis, 2008; Riveros, UNAM). Cuando la meteorología cambia entre los periodos comparados, el resultado se confunde. Es justo lo que pasa con las contingencias, que se declaran en los días de peor ventilación.

### Cómo lo hacemos nosotros (de arriba hacia abajo)

Partimos de lo que se mide en el aire y vamos hacia atrás:
1. **Mediciones:** NOₓ y NO₂ de unas 20 estaciones de SIMAT cada hora, y NO₂ del satélite TEMPO cada hora sobre toda la ciudad, en píxeles de ~2 × 4.5 km.
2. **Transporte:** con el viento y la altura de mezcla de cada hora, un modelo físico calcula cuánto aportaría cada zona y cada fuente candidata a cada estación y a cada píxel.
3. **Inversión:** buscamos las emisiones por zona y por tipo de día (hábil, sábado, domingo) que mejor explican todas las mediciones a la vez. El resultado viene con su intervalo de confianza. A todos los tipos de día se les da el mismo punto de partida, así que cualquier diferencia entre ellos sale de los datos.
4. **El inventario no se usa para ajustar.** Solo da el punto de partida y sirve para comparar al final, así que la comparación es independiente.

La clave es el paso 2: como el modelo sabe qué tan ventilada estuvo cada hora, una concentración alta en un día estancado no se interpreta como más emisión.

### Lado a lado

| | Inventario | Monitoreo SIMAT | Pronóstico AQFS-Mex | Nuestro método |
|---|---|---|---|---|
| Pregunta que responde | ¿Cuánto emite cada tipo de fuente al año? | ¿Qué concentración hay ahora y dónde? | ¿Qué concentración habrá mañana? | ¿Cuánto se emitió en cada zona y tipo de día? |
| Base | Conteos de actividad × factores de emisión | Medición directa | Inventario + meteorología + química | Mediciones + viento + física |
| Produce | Toneladas por fuente | ppb por estación | Mapas de concentración | Emisión relativa por zona, con intervalo |
| Separa emisión de meteorología | No aplica (no usa meteorología real) | No | Sí, pero con emisiones supuestas | **Sí, con emisiones inferidas** |
| Frecuencia | Cada varios años, con ~3 años de retraso | Cada hora | Diario | Por semana o por temporada |
| Medido o supuesto | Supuesto (estimado) | Medido | Simulado | Inferido de mediciones |
| Detalle por fuente | Muy alto | No | El del inventario | Bajo: zonas de ~18 km y fuentes grandes |
| Incertidumbre explícita | Solo para gases de efecto invernadero | Error del instrumento | Verificación contra estaciones | Sí, intervalo para cada resultado |

### Qué aporta de nuevo

1. **Mide la emisión, no la concentración.** Es lo que hace falta para saber si una medida funcionó: si las concentraciones no bajaron en una contingencia, distingue "no bajó la emisión" de "bajó, pero el aire estaba estancado".
2. **Es independiente del inventario.** El inventario y las políticas comparten los mismos supuestos de actividad. Una estimación basada solo en observaciones los puede verificar desde fuera.
3. **Es frecuente.** Un resultado por semana o por temporada, en lugar de cada varios años con retraso.
4. **Cubre zonas sin estaciones.** TEMPO ve toda la ciudad, incluido el noreste (Ecatepec, Acolman, AIFA), donde las estaciones casi no llegan.
5. **Dice cuánto confiar.** Cada resultado trae su intervalo, así que una autoridad sabe qué tan grande debe ser un cambio para tomarlo en serio.
6. **Es barato.** Usa datos públicos (SIMAT, TEMPO, ERA5, OpenStreetMap) y no requiere campañas.

**No sustituye al inventario; lo complementa.** El inventario da el detalle por fuente que nosotros no alcanzamos. Nosotros comprobamos sus patrones con mediciones y detectamos cambios entre ediciones. Juntos forman un ciclo: el inventario da el punto de partida, las observaciones lo corrigen y la corrección alimenta la siguiente edición y el pronóstico.

## Qué gana el usuario al separar la emisión del estancamiento

La concentración que mide una estación depende de dos factores: **cuánto se emite** y **qué tan ventilado está el aire** (viento y altura de mezcla). El monitoreo mide la suma; nuestro método estima por separado el primer factor.

Ejemplo con nuestros datos: en la primavera de 2024, el NOₓ de la tarde fue casi igual en días de contingencia que en días normales (17.5 frente a 17.9 ppb). Con solo concentraciones caben dos lecturas, y no se pueden distinguir:
- las restricciones no redujeron emisiones, o
- sí las redujeron, pero el aire estaba tan estancado que no se notó.

La decisión correcta es opuesta en cada caso: endurecer o cambiar la medida, o mantenerla y buscar la palanca en otro lado.

### Posibilidades que abre

| Posibilidad | Para quién | Qué cambia en la práctica | Madurez hoy |
|---|---|---|---|
| Evaluar si una medida funcionó: contingencias, Hoy No Circula doble, cierres viales, nuevas líneas de transporte, trabajo en casa | SEDEMA, CAMe | Se evalúa con la emisión, no con una concentración que depende del clima de esos días | Dirección sí; el tamaño exige corregir el sesgo |
| Diagnosticar por qué no baja el ozono | CAMe | Si el NOₓ bajó y el ozono no, el problema es químico y la palanca está en los COV; si el NOₓ no bajó, falló el cumplimiento de la medida | Posible tras corregir el sesgo |
| Reportar el avance del ProAire sin el ruido del clima | SEDEMA, ciudadanía | Responde "¿emitimos menos que el año pasado?" aunque ese año haya sido más caluroso o estancado (2024 tuvo olas de calor) | Requiere varias temporadas |
| Comparar zonas de forma justa | SEDEMA, alcaldías y municipios | Una zona puede tener concentraciones altas porque ahí se acumula el aire, no porque emita más; las medidas se dirigen a donde se emite | Reparto por zona: lo más sólido hoy |
| Mejorar el pronóstico | Equipo de AQFS-Mex | El pronóstico usa emisiones supuestas del inventario; con emisiones corregidas por observación se pronostican mejor las contingencias (menos falsas alarmas y menos sorpresas) | Requiere integración y mejor viento |
| Ajustar una contingencia sobre la marcha | CAMe | Si al primer día la emisión no baja, se refuerza la medida el segundo | Lejano: hoy no es en tiempo real |
| Explicar a la población por qué hay contingencia | Comunicación pública | Decir "hoy el problema es la falta de viento, no más tráfico" (o al revés) da legitimidad a las restricciones | Posible con la dirección del efecto |
| Separar efectos en estudios de salud | Investigadores | Distingue la exposición causada por emisiones de la causada por meteorología, útil para atribuir beneficios a las políticas | Posible a escala de zona |

### Por qué importa más en esta ciudad

- **Las contingencias se declaran justo en los días de peor ventilación.** Comparar concentraciones de esos días con días normales casi siempre esconde el efecto de la medida. Es el caso en que separar ambos factores aporta más.
- **El ozono de la ciudad está limitado por COV.** Bajar el NOₓ no garantiza bajar el ozono, así que saber si el NOₓ bajó es la mitad del diagnóstico, y hoy esa mitad no se mide.

### Límite actual

Con el estimador normalizado separamos la **dirección** y, con margen de ~±10 %, el **tamaño** de un cambio: domingo 0.65 del hábil (Infovial: 0.65–0.73), confinamiento 2020 −35 %. La inversión completa exageraba el domingo (0.31–0.47) porque ahí el cociente lo fija el a priori (`sesgo_domingos.md`). Lo que aún no damos con confianza son totales absolutos ni fuentes puntuales individuales.

## Lo que sabemos hacer hoy (y lo que no)

| Capacidad | Precisión medida | Fuente |
|---|---|---|
| Emisión vial por zona (~18 km), en relativo | 9 % de error mediano (máx. 21 %) en gemelos con viento ±20°; 15 % (máx. 36 %) con el error medido de ~30° | escenario A, `viento.md` |
| Cambio entre tipos de día | Estimador normalizado: domingo/hábil 0.65 (IC 90 % 0.55–0.75), coherente con Infovial del día completo (0.65–0.73). La inversión completa da 0.39–0.47, pero ese cociente lo fija el a priori | `sesgo_domingos.md` |
| Fuentes grandes conocidas | 20–34 % en gemelos con viento ±20°, y 32–37 % con el error de viento medido (~30°). En datos reales, Acolman sale 300 frente a 2,615 t/año a priori y AIFA sale negativo | gemelos, datos reales, `viento.md` |
| Mapa de concentración | Híbrido 11.4 frente a 11.5 ppb de IDW (gana en 16 de 24 estaciones); aporta más donde no hay estaciones | LOO |
| Total absoluto | Entre 35 y 67 % del inventario, según el modelo de transporte: **no confiable** | variantes |
| Fábrica o zona industrial individual | No recuperable con el viento actual (error mediano 51 %) | gemelos |

En la práctica: **detectamos cambios relativos grandes (≥ 20 %) en la emisión vial de una zona entre grupos de días.** No detectamos cambios pequeños, no damos totales absolutos y no atribuimos a instalaciones.

## Caso 1 (principal): ¿bajó la emisión vial cuando se restringió la circulación?

**Quién decide.** La CAMe y la SEDEMA, que en marzo de 2025 revisaban ajustes al Hoy No Circula y al programa de contingencias, sin decisión tomada ([Expansión, 2025](https://politica.expansion.mx/cdmx/2025/03/25/medio-ambiente-analiza-ajustes-al-hoy-no-circula-para-disminuir-contaminantes)). El ProAire ZMVM 2021–2030 fija metas de reducción de emisiones (hasta 25 % frente al escenario tendencial), pero la nota de presentación no describe cómo se medirá el avance ([Milenio, 2021](https://www.milenio.com/politica/cdmx-hidalgo-edomex-actualizan-proaire-reducir-emisiones)).

**Qué decisión.** Mantener, endurecer o cambiar las restricciones vehiculares en las contingencias y el Hoy No Circula.

**Pregunta exacta que respondemos.** En los días de contingencia, ¿bajó la emisión vial de NOₓ de cada zona frente a días hábiles comparables, y cuánto? Se responde con intervalo de confianza y por zona (centro, norte, oriente…).

**Por qué hace falta.** Las evaluaciones disponibles usan concentraciones medidas:
- El estudio clásico de Davis (2008) no encontró mejora en la calidad del aire atribuible al Hoy No Circula; los conductores se adaptaron comprando más autos ([resumen RFF](https://www.resources.org/common-resources/driving-restriction-and-air-quality-in-mexico-city/)).
- Riveros (UNAM) tampoco observa reducciones asociadas ([análisis](https://www.fisica.unam.mx/personales/hgriveros/docu/RAMAmayojulio2007.295192214.pdf)).

Las concentraciones no distinguen entre "la medida no redujo emisiones" y "redujo emisiones, pero la atmósfera estaba más estancada". Nuestros datos muestran exactamente ese problema: en primavera de 2024, el NOₓ de la tarde en días de contingencia fue casi igual al de días hábiles (17.5 frente a 17.9 ppb). Las contingencias se declaran justo en días de mala ventilación. Un método que estima la **emisión**, condicionada al viento y a la mezcla de cada hora, ataca ese sesgo directamente.

**Hay un segundo matiz.** La mayor parte de la ciudad está en un régimen de ozono limitado por COV: durante el confinamiento de 2020, el NOₓ bajó ~30 % y el ozono no bajó ([Peralta et al., UNAM](https://www.siicsalud.com/dato/resiiccompleto.php/164904)). Por eso, saber si la emisión de NOₓ bajó es la mitad del diagnóstico que necesita la CAMe:
- Si la emisión no bajó, la medida no funciona como se diseñó: falla de cumplimiento o de adaptación.
- Si bajó y el ozono no, el problema es químico y la palanca está en los COV.

Hoy no se puede distinguir entre esas dos explicaciones; con nuestro resultado, sí.

**¿Alcanza la precisión?**
- **Contingencias: ya probado con 2024.** Con el estimador normalizado, en las tardes de los 23 días de contingencia de 2024 no se ve una baja de emisión de NOₓ (1.13, IC 90 % 1.05–1.22; hábiles 1.07). Los placebos con días falsos dan ±10 %, así que una baja de ≥10–15 % se habría detectado (ver `contingencias_2024.md`). Es justamente la evaluación que hoy no existe: muestra que la concentración no bajó y que no fue por el clima. Falta confirmar fechas con la CAMe y corregir un sesgo positivo en episodios largos.
- **Hoy No Circula ordinario, no.** Las autoridades estiman que solo ~4 % del parque está sujeto a él ([Expansión, 2025](https://politica.expansion.mx/cdmx/2025/03/25/medio-ambiente-analiza-ajustes-al-hoy-no-circula-para-disminuir-contaminantes)). Un efecto de unos puntos porcentuales queda por debajo de nuestra resolución. Es mejor decirlo que prometerlo.

**Qué aporta frente a lo que existe.**

| | Hoy | Con nuestro método |
|---|---|---|
| Qué mide | Concentración (mezcla emisión y meteorología) | Emisión vial por zona |
| Frecuencia | Inventario cada ~2+ años, publicado con ~3 años de retraso (el de 2018 salió en agosto de 2021) | Cada temporada, o cada semana con TEMPO |
| Independencia | El inventario se construye con los mismos supuestos de actividad que las políticas | Basado solo en observaciones |
| Costo | Estudios ad hoc | Datos públicos (SIMAT, TEMPO, ERA5, OSM) |

**Riesgos.**
- **Sesgo de escala del transporte.** Por eso se reportan cocientes (contingencia/hábil), que cancelan buena parte del sesgo, no toneladas.
- **Sesgo de magnitud de los cambios.** Aun en cocientes, el modelo exagera la baja dominical frente a los conteos de tráfico. Se corrige con mejor viento (error medido ~30°) y con el perfil de Infovial; mientras tanto solo se reporta la dirección.
- **Meteorología extrema en contingencias** (capa de mezcla baja, calma). Es justo donde el modelo es más débil, así que hay que validarlo antes de usarlo.
- **Falta la capa límite ERA5 de ene–jun 2024** en nuestra fuente actual. Hay que bajarla del CDS o de MERRA-2.
- **La tarde (12–17 h)** no cubre el pico matutino. El efecto en hora pico se extrapola.

**Cómo se validaría un piloto** (unas 6 semanas, con la temporada de ozono 2024):
1. **Prueba con signo conocido:** Semana Santa 2024 debe salir con baja (IC 90 % por debajo de 1). Si no la detecta, el caso se cae.
2. **Placebo:** días hábiles normales asignados al azar como "contingencia" no deben mostrar baja. Mide los falsos positivos.
3. **Robustez:** el resultado debe tener el mismo signo con transporte estacionario y no estacionario, como ya ocurre con el domingo.
4. **Contraste independiente:** la caída de NO₂ en TEMPO y de CO en estaciones debe ir en la misma dirección.
5. **Hipótesis por escrito antes de correr**, y entrega a SEDEMA y CAMe con intervalos, no con cifras puntuales.

## Caso 2 (secundario): verificar los patrones del inventario entre ediciones

**Quién.** La Dirección General de Calidad del Aire de SEDEMA, al preparar la siguiente edición del inventario, y quienes modelan pronósticos de calidad del aire.

**Pregunta.** ¿El reparto de la emisión vial entre zonas y su perfil semanal coinciden con lo que supone el inventario? El perfil semanal requiere antes corregir el sesgo de magnitud; el reparto por zona es la parte más sólida hoy.

**Por qué ahora.** El inventario más reciente que pudimos abrir es el de 2018. La prensa menciona uno de 2020, afectado por la pandemia, que no pudimos verificar ni descargar. Los perfiles temporales y espaciales alimentan los modelos de pronóstico de contingencias. Afuera ya se usa este enfoque:
- El estado de Georgia (EUA) usa NO₂ de TEMPO y TROPOMI en sus reportes de excedencias, base de sus planes de control, y planea desarrollar inventarios top-down propios ([Georgia EPD, 2025](https://haqast.wisc.edu/wp-content/uploads/sites/688/2025/11/Byeong-Kim-Georgia-Department-of-Natural-Resources.pdf)).
- A escala global, Rey-Pommier et al. publican emisiones de NOₓ top-down desde TROPOMI precisamente porque los inventarios llegan con 3 o más años de retraso ([ESSD, 2025](https://essd.copernicus.org/articles/17/3329/2025/essd-17-3329-2025.html)).

**Precisión.** El reparto por zona se recupera en gemelos con 3–9 % de error. El absoluto no, así que se comparan **porcentajes y perfiles**, no toneladas.

**Límite.** Sin NOₓ por municipio en el inventario público no se puede hacer la comparación municipal del plan original. Se necesitan los anexos de SEDEMA.

## Usos que NO son defendibles hoy

| Uso | Por qué no |
|---|---|
| Atribuir emisiones a una fábrica o zona industrial | Error mediano de 51 % con el viento actual; solo mejora con viento de ±5° |
| Dar totales en toneladas para sustituir el inventario | La escala absoluta varía de 35 a 67 % del inventario según el modelo |
| Evaluar el Hoy No Circula ordinario | El efecto esperado (~4 % del parque) está por debajo de la resolución |
| Cuantificar las emisiones del AIFA | Sale negativo con datos reales, aunque el AIFA crece (7.08 millones de pasajeros en 2025, [Milenio](https://www.milenio.com/politica/aifa-suma-mas-de-18-millones-de-pasajeros-a-cuatro-anos-de-operaciones)). Se necesita mejor viento al norte |
| Decidir medidas contra el ozono directamente | Régimen limitado por COV: el NOₓ es solo una parte; no estimamos COV |
| Operación en tiempo real o vigilancia normativa | No está construido ni validado |

Como referencia de cómo se ve una evaluación institucional: Londres reporta el efecto de su zona de bajas emisiones contra un escenario "sin ULEZ" estimado, no medido directamente ([GLA, 2022](https://www.london.gov.uk/programmes-and-strategies/environment-and-climate-change/environment-publications/expanded-ultra-low-emission-zone-six-month-report)). Un contrafactual explícito y con incertidumbre, como el nuestro, es el estándar de práctica, no un lujo.

## Fuentes (páginas abiertas)

- [Milenio (29 dic 2021): CDMX, Hidalgo y Edomex actualizan ProAire](https://www.milenio.com/politica/cdmx-hidalgo-edomex-actualizan-proaire-reducir-emisiones)
- [Expansión (25 mar 2025): Medio Ambiente analiza ajustes al Hoy No Circula](https://politica.expansion.mx/cdmx/2025/03/25/medio-ambiente-analiza-ajustes-al-hoy-no-circula-para-disminuir-contaminantes)
- [Resources for the Future: Driving restriction and air quality in Mexico City (Davis)](https://www.resources.org/common-resources/driving-restriction-and-air-quality-in-mexico-city/)
- [Riveros, H. G., Instituto de Física UNAM: Análisis de El Hoy no circula](https://www.fisica.unam.mx/personales/hgriveros/docu/RAMAmayojulio2007.295192214.pdf)
- [Peralta, Ortínez-Alvarez y Ruiz-Suárez: Ozono sobre la Ciudad de México y la COVID-19 (resumen SIIC)](https://www.siicsalud.com/dato/resiiccompleto.php/164904)
- [Georgia EPD (6 nov 2025): Use of Satellite Data at Georgia EPD, HAQAST](https://haqast.wisc.edu/wp-content/uploads/sites/688/2025/11/Byeong-Kim-Georgia-Department-of-Natural-Resources.pdf)
- [Rey-Pommier et al., ESSD 17, 3329 (2025): emisiones globales de NOₓ top-down desde TROPOMI](https://essd.copernicus.org/articles/17/3329/2025/essd-17-3329-2025.html)
- [Greater London Authority (2022): Expanded ULEZ six-month report](https://www.london.gov.uk/programmes-and-strategies/environment-and-climate-change/environment-publications/expanded-ultra-low-emission-zone-six-month-report)
- [Milenio (1 abr 2026): AIFA suma más de 18 millones de pasajeros](https://www.milenio.com/politica/aifa-suma-mas-de-18-millones-de-pasajeros-a-cuatro-anos-de-operaciones)
- [SEDEMA: Inventario de Emisiones ZMVM 2018 (agosto 2021)](https://www.sedema.cdmx.gob.mx/storage/app/media/DGCA/InventarioDeEmisionesZMVM2018.pdf)
