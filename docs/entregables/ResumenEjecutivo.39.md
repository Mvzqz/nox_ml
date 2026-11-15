---
title: ¿Fue el clima o fue la ciudad? Separar la emisión de NOₓ del clima en la Ciudad de México con datos públicos y el satélite TEMPO
subtitle: Resumen ejecutivo del Proyecto Integrador, equipo 39
author: Isabella Arango Restrepo (A01796305), Isaí Ambrocio (A01625101) y Manuel Alejandro Vázquez Meza (A01796404)
---

<!--
Borrador en Markdown para pasar a la plantilla LaTeX del curso (Overleaf).
Extensión: el cuerpo (del título a las referencias) debe caber en 3 páginas carta,
11 pt, márgenes de 2.5 cm, interlineado 1.15. Los anexos no cuentan.
Cifras de desempeño: Articulo.39.md (tablas 7 a 10). Cifras de las exploraciones de valor:
context/management/exploraciones_valor_estado.md y las notas de context/knowledge/
(diseños_alternados, validacion_episodios, regimen_ozono, qc_redes, inventario_oriente, salud_escenarios).
-->

# Resumen ejecutivo

**El problema.** Cuando la contaminación de la Zona Metropolitana del Valle de México (ZMVM) sube o baja, se atribuye a una medida o a un culpable, casi nunca al clima. Pero la concentración que miden las estaciones depende tanto de lo que se emite como de la ventilación, y el inventario oficial de emisiones sale cada varios años (la edición 2018 se publicó en 2021). Así, una medida puede parecer un éxito o un fracaso según el clima de esos días.

**La solución.** Para el Hub de Ciencia de Datos del Tecnológico de Monterrey desarrollamos un sistema que estima la emisión de óxidos de nitrógeno (NOₓ, el contaminante del tráfico) y la separa del clima, con 24 estaciones, el satélite TEMPO de la NASA y la meteorología. Responde **¿fue el clima o fue la ciudad?** y siempre dice qué tan seguro está. Usa solo fuentes públicas y gratuitas, y se entrega como un **bien público**: un boletín mensual y datos abiertos citables, además de análisis a pedido.

**¿Qué tan bien funciona?** Se probó en datos que no vio durante su desarrollo: un periodo de prueba, cuatro temporadas de 2024 a 2026 y 52 episodios de causa conocida (Tabla 1).

Tabla 1. Resultados clave del sistema y su significado.

| Indicador | Resultado | Qué significa |
|---|---|---|
| Cambio real conocido: confinamiento de 2020 | −50 % (esperado −40 a −60 %) | Mide bien un cambio grande cuando ocurre |
| Prueba de "cambio falso" y rango de confianza | Placebo 0.95–1.11 (ideal = 1); el rango contiene el valor real el 91 % de las veces (meta: 90 %), con 5 % de falsas alarmas | No inventa cambios y sus rangos son honestos |
| Diagnóstico de episodios | En 52 episodios de causa conocida se equivoca de causa en 3; las falsas acusaciones a la emisión en semanas sin cambio bajan de 18 % a 9 % | Dice si el clima explica un episodio sin culpar a la emisión de lo que fue clima o acumulación |
| Error donde no hay estación | 11.7 ppb (interpolación: 11.6; kriging: 10.3; combinado: 10.2) | Iguala a las interpolaciones y, además, estima la emisión |
| Cambio mínimo detectable | ~30 % en una temporada; 16–28 % si la medida se aplica en semanas alternas; ~10 % repitiéndola en seis temporadas | No ve una medida de 5–10 % en una temporada; sí con un piloto bien diseñado y repetido |

**Un hallazgo para las contingencias.** Las contingencias de la ZMVM son sobre todo por ozono (5–10 activaciones al año), y su medida principal, el Doble Hoy No Circula, recorta sobre todo NOₓ. En el centro de la ciudad, recortar NOₓ no baja el ozono: en 80 domingos de temporada, comparados con días hábiles de clima parecido, el NOₓ cae 30 % y el ozono máximo queda igual o sube 3 %; en el confinamiento de 2020 el NOₓ bajó 33 % y el ozono solo 2–4 % (no significativo). El centro está limitado por compuestos orgánicos volátiles (COV), como concluyeron con otro satélite Vazquez Santiago et al. (2021): las medidas eficaces serían sobre COV (vapores de combustible, solventes, gas LP). El sistema actualiza este diagnóstico cada temporada a costo casi nulo.

**¿Está listo para producción?** Sí, con alcance acotado, en tres productos: (1) un **boletín mensual público** con la emisión corregida por clima, los episodios del mes explicados, la calidad de las redes y el régimen del ozono (un prototipo con octubre de 2026 se generó en menos de un minuto; sale ~2 semanas después del mes); (2) un **conjunto de datos abierto con DOI** con las correcciones de calidad, los recortes de TEMPO y los cortes de red; y (3) **análisis a pedido**: acotar afirmaciones públicas y diseñar pilotos medibles con semanas alternas. No verifica en una temporada una medida de 5–10 %, la escala habitual, porque la emisión estimada oscila ±15 % de semana a semana; tampoco da toneladas por zona.

**Beneficios para la organización y la sociedad.** El valor principal es información que hoy no existe y errores que se evitan. Para cuantificar, usamos como piso el tiempo que evita quien haría a mano los análisis (~40 h frente a ~2 h) con un volumen realista de **~12 al año**: 6 episodios, 3 afirmaciones públicas, 2 pilotos y un contraste del inventario (Tabla 2; Anexo A).

Tabla 2. Beneficios cuantificables mensuales estimados.

| Indicador | Valor estimado | Base de cálculo |
|---|---|---|
| Ahorro de tiempo | 38 h/mes (−95 % por análisis) | 1 análisis al mes × (40 − 2) h |
| Ahorro en costos operativos | 13,300 MXN/mes | 38 h × 350 MXN/h de un científico de datos |
| Incremento en capacidad de procesamiento | De 0.03 a 4 actualizaciones de emisión al mes; 1 boletín público al mes; ~1 corte de red detectado al mes | Inventario cada ~3 años frente a un índice semanal; 21 cortes sin documentar en 22 meses |
| Reducción de eventos de riesgo | Falsas acusaciones a la emisión en episodios: de 18 % a 9 %; falsas alarmas en las fichas: 5 % | Medidas en 34 semanas sin cambio de emisión y en 960 pruebas con cambios simulados |

Entre los beneficios intangibles destacan cinco. **Mejores contingencias:** el diagnóstico del ozono, actualizado cada temporada. **Datos abiertos:** citas y colaboraciones con la academia y con el operador de la red. **Información honesta:** toda cifra lleva rango y límite de detección. **Señal para el inventario:** el oriente (Chalco, Ixtapaluca, Chimalhuacán, Texcoco y el oriente de Iztapalapa) aparece con 5–15 % de la emisión vial, frente a 13–17 % del inventario del Instituto Nacional de Ecología y Cambio Climático (INECC, 2018) y de EDGAR (European Commission, Joint Research Centre, 2024). **Lo que está en juego:** como orden de magnitud preliminar, bajar 10 % la emisión vial evitaría cientos de muertes al año (Huangfu y Atkinson, 2020). **Innovación para el Hub:** hasta donde sabemos, el primer sistema abierto que estima la emisión de NOₓ con TEMPO en la ZMVM y el primero en medir con TEMPO el régimen del ozono de la ciudad.

**¿Qué implica implementarlo?** El desarrollo hecho es costo hundido. La **fase 1** opera el sistema con poco personal, arma el boletín, publica los datos y agrega pilotos con semanas alternas y detectores de cortes de red. Su costo total de propiedad (TCO) a 12 meses es de **~137,000 MXN** (Tabla 3; Anexo B). La **fase 2** (interfaz, datos de tráfico y una cuarta parte de un analista; ~198,000 MXN al año) queda condicionada.

Tabla 3. Costo total de propiedad de la fase 1, primeros 12 meses.

| Concepto | Monto (MXN) |
|---|---|
| Implementación (una vez): despliegue en la nube y alertas, boletín mensual, datos con DOI, semanas alternas en las fichas, detectores de cortes de red, guía y capacitación | 50,400 |
| Operación (12 meses): nube y almacenamiento (1,950 al mes) y un responsable 12 h al mes (4,200 al mes) | 73,800 |
| Contingencia (10 %) | 12,420 |
| **Total** | **136,620** |

La operación cuesta ~6,150 MXN al mes y se paga con **~6 análisis al año**. Con ~12 al año y beneficios desde el mes 3, el ahorro en horas (~133,000 MXN) casi iguala el TCO (0.97 veces), sin contar el boletín ni los datos abiertos, que son el valor adicional y la vía para conseguir esos usuarios.

**Recomendación.** Aprobar la fase 1 por ~137,000 MXN con cuatro condiciones: (1) un responsable 12 horas al mes, que revise las alertas, publique el boletín a mediados de cada mes y produzca las fichas; (2) publicar solo lo que el sistema respalda: nunca toneladas, y la salud solo como orden de magnitud; (3) llevar el diagnóstico del ozono a la Comisión Ambiental de la Megalópolis y a la autoridad ambiental, y proponerles un piloto con semanas alternas; y (4) gestionar datos de actividad vehicular (SEMOVI, C5 o Waze for Cities). En el mes 6: con un usuario externo y datos de tráfico, aprobar la fase 2; si el boletín no tiene audiencia (descargas, citas o menciones), hay menos de 3 análisis o el placebo sale de 1 ± 0.15, dejarlo como activo académico.

**Riesgos y condiciones para avanzar** (Tabla 4).

Tabla 4. Principales riesgos y medidas de mitigación.

| Riesgo | Tipo | Mitigación |
|---|---|---|
| Deriva lenta de ±15 %: no se ven medidas de 5–10 % en una temporada | Modelo | Publicar el límite de detección; pilotos con semanas alternas; recalibrar si la deriva pasa de 0.15 |
| Periodos atípicos (fin de año, Semana Santa, acumulación regional) que parecen cambios de emisión | Modelo | Excluirlos de las referencias; veredicto prudente; no afirmar emisión con un solo episodio |
| Datos: estaciones sin validar, cortes de red, cambios de versión de TEMPO; licencia de SIMAT sin registrar | Datos | Detectores de cortes; DVC; no publicar con el placebo fuera de 1 ± 0.15; sin licencia, publicar solo las correcciones |
| Leer "no detectado" como "no funcionó", o citar toneladas o salud como exactas | Uso | Rango y límite de detección en cada cifra; guía para usuarios |
| Que nadie lo use o que se pierda al terminar el curso | Operación | Boletín público desde el mes 3; usuario externo antes del mes 6; responsable asignado; pruebas automáticas, guía y capacitación |

**Transferencia y continuidad.** Se entregará al Hub: (1) el paquete `nox_ml`, con 1,190 pruebas automáticas que corren en cada cambio (`bin/check`); (2) los datos versionados en DagsHub y las configuraciones por temporada; (3) la actualización diaria (`nox-ml update`) con su archivo de estado; (4) los comandos de análisis y la plantilla del boletín; (5) el conjunto de datos con DOI; (6) el artículo y las notas de las exploraciones; y (7) una guía de operación con dos sesiones de capacitación (Anexo C).

# Referencias

<!-- MOVES-México: verificado con la portada del informe (data/raw/inventario_2020/moves2016.pdf).
EDGAR: título, año y PID verificados en el catálogo de datos del JRC. La lista completa de autores (Crippa, Guizzardi, Pagani, Banja, Muntean, Schaaf, Becker, ... Vignati) no se pudo leer; si se obtiene, sustituir el autor institucional por ella. -->

European Commission, Joint Research Centre. (2024). *EDGAR v8.1 global air pollutant emissions* [Conjunto de datos]. http://data.europa.eu/89h/a3af16e4-21ac-420a-b98c-b78a9b7723be

Huangfu, P., & Atkinson, R. (2020). Long-term exposure to NO₂ and O₃ and all-cause and respiratory mortality: A systematic review and meta-analysis. *Environment International, 144*, 105998. https://doi.org/10.1016/j.envint.2020.105998

Instituto Nacional de Ecología y Cambio Climático. (2018). *Elementos para inventario de fuentes móviles: Inventario de emisiones de fuentes móviles carreteras, 2016* [Informe final]. https://www.gob.mx/cms/uploads/attachment/file/427685/INFORME_FINAL_MOVES-IE2016f.pdf

Secretaría del Medio Ambiente de la Ciudad de México. (2021). *Inventario de emisiones de la Zona Metropolitana del Valle de México 2018*. https://www.sedema.cdmx.gob.mx/storage/app/media/DGCA/InventarioDeEmisionesZMVM2018.pdf

Vazquez Santiago, J., Inoue, K., & Tonokura, K. (2021). Diagnosis of ozone formation sensitivity in the Mexico City Metropolitan Area using HCHO/NO₂ column ratios from the ozone monitoring instrument. *Environmental Advances, 6*, Artículo 100138. https://doi.org/10.1016/j.envadv.2021.100138

Vázquez Meza, M. A., Arango Restrepo, I., & Ambrocio, I. (2026). *Estimación de cambios de emisión de NOₓ en la Zona Metropolitana del Valle de México con inversión física, redes informadas por la física y el satélite TEMPO* [Artículo final, Proyecto Integrador]. Tecnológico de Monterrey. https://github.com/Mvzqz/nox_ml

Zoogman, P., Liu, X., Suleiman, R. M., Pennington, W. F., Flittner, D. E., Al-Saadi, J. A., Hilton, B. B., Nicks, D. K., Newchurch, M. J., Carr, J. L., Janz, S. J., Andraschko, M. R., Arola, A., Baker, B. D., Canova, B. P., Chan Miller, C., Cohen, R. C., Davis, J. E., Dussault, M. E., … Chance, K. (2017). Tropospheric emissions: Monitoring of pollution (TEMPO). *Journal of Quantitative Spectroscopy and Radiative Transfer, 186*, 17–39. https://doi.org/10.1016/j.jqsrt.2016.05.008

**Declaración de uso de herramientas de IA.** TODO: agregar herramienta, modelo y finalidad en formato APA 7 (por ejemplo: Anthropic. (2026). *Claude Code* (Claude Opus 5.5) [Modelo de lenguaje grande], utilizado para la revisión de redacción. https://claude.com/claude-code).

# Anexos

## Anexo A. Cálculo de los beneficios cuantificables

**Supuestos generales.**

- **Volumen:** ~12 análisis al año, alrededor de 1 al mes (Tabla A1). Es una estimación de demanda, no una cifra medida; la sensibilidad está en la Tabla A4.
- **Tarifa:** 350 MXN/h, costo para la organización de un científico de datos en México (~45,000 MXN brutos al mes × 1.3 de cargas sociales ÷ 168 h).
- **Inicio:** los beneficios se cuentan desde el mes 3, cuando están listas la guía y las mejoras de la fase 1; los comandos ya funcionan hoy.
- El beneficio es el costo que se evita quien analiza (autoridad, operador de la red, academia o medios), no un ingreso del Hub. El escenario contra el que se compara es hacer el mismo análisis a mano; en la práctica hoy suele no hacerse, así que la cifra es un piso del valor y no incluye los errores evitados.

Tabla A1. Análisis esperados al año.

| Uso | Para quién | Veces al año | Base |
|---|---|---|---|
| Explicar un episodio (¿fue el clima?) | Autoridad ambiental, medios | 5–10 (base 6) | Semanas altas de invierno y contingencias de ozono (11 en feb–may 2024) |
| Acotar una afirmación pública | Periodistas, organizaciones civiles, evaluadores | 3–5 (base 3) | Anuncios de reducciones por medidas o programas |
| Diseñar o evaluar un piloto | Autoridad, planeadores, financiadores | 1–3 (base 2) | Días y diseño (semanas alternas) para detectar un efecto dado |
| Contrastar el inventario | Equipo de inventario, academia | 1 | Una vez por edición del inventario |
| **Total** | | **10–19 (base 12)** | |

Además, el responsable publica el boletín mensual (con la calidad de las redes, que también se envía al operador). Su tiempo está en la operación y su beneficio se cuenta como capacidad, no como horas: hoy nadie lo produce, así que no hay horas que ahorrar.

**Prototipo del boletín.** Con los datos de junio a octubre de 2026 y el código actual (`load_inputs` con las tablas de OpenAQ y `diagnose_episode`), el diagnóstico de las cuatro semanas evaluables de octubre tardó 27 s en total; las cuatro salieron "normal" y la última semana del mes no tenía datos aún (OpenAQ llegaba al 22 de octubre). El catálogo de calidad de F7 ya cubre octubre: 21 estaciones, 81 % de las horas completas y 6 huecos. Un boletín de un mes normal dirá sobre todo "nada inusual por clima ni por emisión"; su valor está en publicarlo siempre, con el mismo método, y en las secciones de calidad y de ozono.

Tabla A2. Tiempo por análisis, sin y con el sistema.

| Actividad | Sin el sistema (h) | Con el sistema (h) |
|---|---|---|
| Descarga y control de calidad de estaciones, meteorología y satélite | 12 | 0 (actualización diaria automática) |
| Corrección por meteorología (modelo de lo esperado con el clima real) | 16 | 0 (cálculo en minutos) |
| Incertidumbre, placebo y límite de detección | 8 | 0 (incluidos en la ficha) |
| Revisión e informe | 4 | 2 |
| **Total** | **40** | **2** |

Tabla A3. Beneficios mensuales y su base de cálculo.

| Indicador | Unidad | Valor | Cálculo | Supuestos |
|---|---|---|---|---|
| Ahorro de tiempo | h/mes | 38 (−95 % por análisis) | 1 × (40 − 2) | Tablas A1 y A2 |
| Ahorro en costos operativos | MXN/mes | 13,300 | 38 × 350 | Tarifa de 350 MXN/h |
| Incremento en capacidad de procesamiento | Actualizaciones de emisión/mes | De 0.03 a 4 | Inventario: 1 cada ~36 meses; sistema: índice semanal | Edición 2018 publicada en 2021 |
| Incremento en capacidad de procesamiento | Cortes de red detectados/mes | ~1 | 21 cortes sin documentar en 22 meses | Hoy nadie los reporta; OpenAQ además pierde 33 % de las horas de la red oficial |
| Reducción de eventos de riesgo | Falsas acusaciones a la emisión por episodio | De 18 % a 9 % | 3 de 34 semanas sin cambio de emisión con el veredicto prudente, frente a 6 de 34 con el anterior | Validación en 52 episodios de causa conocida, 8 temporadas |
| Reducción de eventos de riesgo | Falsas alarmas por ficha | 5 % | 960 pruebas con cambios simulados en 4 temporadas | El antes/después sin corregir por clima no tiene una tasa conocida |

Tabla A4. Sensibilidad al número de análisis.

| Análisis al año | Ahorro (MXN/mes) | Operación (MXN/mes) | Resultado neto (MXN/mes) |
|---|---|---|---|
| 3 | 3,325 | 6,150 | −2,825 |
| 6 | 6,650 | 6,150 | +500 |
| 12 (base) | 13,300 | 6,150 | +7,150 |
| 24 | 26,600 | 6,150 | +20,450 |

Punto de equilibrio de la operación: 6,150 ÷ 13,300 ≈ 0.46 análisis al mes, ~6 al año. Ahorro de 12 meses con el escenario base: 10 meses × 13,300 = 133,000 MXN, 0.97 veces el TCO de la fase 1 (136,620 MXN), sin contar el boletín ni los datos abiertos.

## Anexo B. Desglose del costo total de propiedad (12 meses)

**Supuestos.** Tipo de cambio de 18.5 MXN por dólar; precios de lista bajo demanda de un proveedor de nube pública, sin descuentos por compromiso; tarifa de 350 MXN/h (Anexo A). El desarrollo (avances 0 a 6) es costo hundido y no se incluye. Si el sistema corre en un servidor del Hub, la nube se elimina y la operación baja a ~4,200 MXN al mes.

Tabla B1. Fase 1: desglose por servicio.

| Fase | Servicio | Base | Mensual (MXN) | 12 meses (MXN) |
|---|---|---|---|---|
| Implementación | Despliegue en la nube, temporizador y alertas | 40 h × 350 | — | 14,000 |
| Implementación | Semanas alternas en `ficha-medida` y `ficha-dias` | 20 h × 350 | — | 7,000 |
| Implementación | Detectores de cortes de red en `nox-ml update` | 24 h × 350 | — | 8,400 |
| Implementación | Boletín mensual: plantilla, secciones de episodios, calidad y ozono, publicación automática | 24 h × 350 | — | 8,400 |
| Implementación | Conjunto de datos con DOI: licencias, correcciones, documentación y publicación en Zenodo | 12 h × 350 | — | 4,200 |
| Implementación | Guía de operación y dos sesiones de capacitación | 24 h × 350 | — | 8,400 |
| Operación | Máquina virtual de 4 vCPU y 16 GB de RAM | ~US$100 al mes | 1,850 | 22,200 |
| Operación | Almacenamiento de objetos (~50 GB; hoy 2.4 GB de datos) y respaldos | ~US$5 al mes | 100 | 1,200 |
| Operación | Datos (SIMAT, OpenAQ, TEMPO, Open-Meteo, IEM) | Públicos y gratuitos | 0 | 0 |
| Operación | Responsable, 12 h al mes: alertas, boletín, fichas y contingencias | 12 h × 350 | 4,200 | 50,400 |
| | **Subtotal** | | | **124,200** |
| | Contingencia (10 %) | | | 12,420 |
| | **Total** | | | **136,620** |

Tabla B2. Fase 2, condicionada (no incluida en el TCO de la fase 1).

| Servicio | Base | 12 meses (MXN) |
|---|---|---|
| Interfaz mínima (`nox_app`): fichas, diagnóstico de episodios y calculadora de días | 120 h × 350 | 42,000 |
| Integración de datos de actividad vehicular | 80 h × 350 | 28,000 |
| Ampliar el responsable a 0.25 de tiempo completo (de 12 a ~42 h al mes) | 30 h × 350 × 12 | 126,000 |
| Hospedaje de la interfaz y dominio | ~US$10 al mes | 2,220 |
| **Total** | | **~198,200** |

Se aprueba en el mes 6 solo si hay un usuario externo comprometido y acceso a datos de tráfico.

## Anexo C. Elementos de la transferencia

Tabla C1. Qué se entrega y para qué sirve.

| Entregable | Contenido | Uso en la operación |
|---|---|---|
| Repositorio (<https://github.com/Mvzqz/nox_ml>) | Paquete `nox_ml`, 1,190 pruebas, `bin/check` | Base de todo cambio futuro |
| Datos versionados | DVC con remoto en DagsHub; `configs/seasons/` | Reproducir cualquier cifra; agregar temporadas |
| Actualización diaria | `nox-ml update` con temporizador; `status.json` por fuente | Ingesta y monitoreo sin intervención |
| Comandos de análisis | `nox-ml episode`, `ficha-medida`, `ficha-dias`, `flux-divergence`, `evaluate` | Explicar episodios, producir fichas y la segunda opinión del satélite |
| Boletín mensual | Plantilla y publicación automática; prototipo con octubre de 2026 | Comunicar cada mes la emisión, los episodios, la calidad de las redes y el ozono |
| Conjunto de datos con DOI | Correcciones de calidad, recortes de TEMPO, contingencias y cortes de red | Citas, colaboraciones y reuso por terceros |
| Resultados | `results/runs/` | Contrastar cada nueva corrida |
| Documentación | Artículo final, cuadernos de los avances 1–5, `context/knowledge/` con las notas de las exploraciones | Entender el método, sus límites y lo que se probó |
| Guía de operación (por entregar) | Instalación, credenciales, actualización, alertas y umbrales de no publicación, cómo producir y leer una ficha y un diagnóstico de episodio | Que el responsable opere sin el equipo |
| Capacitación | Dos sesiones con el responsable asignado | Transferir criterio, no solo código |
