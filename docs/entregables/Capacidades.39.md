---
title: Capacidades actuales del sistema de emisión de NOₓ de la ZMVM
subtitle: Qué hace hoy, con qué precisión y para qué alcanza. Proyecto Integrador, equipo 39
author: Isabella Arango Restrepo (A01796305), Isaí Ambrocio (A01625101) y Manuel Alejandro Vázquez Meza (A01796404)
---

<!--
Fecha: 15 de noviembre de 2026. Fuentes: Articulo.39.md, context/knowledge/capacidades.md y las notas de las
exploraciones de valor (context/management/exploraciones_valor_estado.md). Cada cifra remite a su nota.
-->

# Capacidades actuales del sistema

## Qué es

Un sistema que estima la emisión de óxidos de nitrógeno (NOₓ) de la Zona Metropolitana del Valle de México (ZMVM) separándola del clima. Responde una pregunta: **cuando la contaminación sube o baja, ¿fue el clima o fue la ciudad?** Siempre acompaña la respuesta de su incertidumbre: un rango de confianza, una prueba de que no inventa cambios (placebo) y el cambio mínimo que puede detectar.

Funciona con datos públicos y gratuitos, sin captura del usuario:

| Dato | Fuente | Resolución |
|---|---|---|
| NOₓ, NO₂ y ozono en superficie | Red de monitoreo de la CDMX (SIMAT) hasta 2024; desde 2025, las mismas estaciones vía OpenAQ | Horaria, ~24 estaciones |
| Columna de NO₂ y de formaldehído | Satélite TEMPO de la NASA | Horaria de día, píxeles de ~2 × 4.5 km |
| Viento, capa de mezcla, temperatura | Aeropuertos (IEM), ERA5 y MERRA-2 | Horaria |
| Punto de partida de la emisión | Inventario de SEDEMA y red vial de OpenStreetMap | Solo como punto de partida |

El análisis usa las tardes (12–17 h), cuando la capa de mezcla está desarrollada y TEMPO observa. Los datos se actualizan solos cada día (`nox-ml update`) y llegan con ~2 semanas de retraso, el que tiene la publicación de las estaciones.

## Lo que hace hoy

Cada capacidad con su estado, su precisión medida en datos que el sistema no vio y el uso para el que alcanza.

| # | Capacidad | Cómo se usa | Precisión y validación | Para qué alcanza |
|---|---|---|---|---|
| 1 | **Cambio de emisión entre periodos** | `nox-ml ficha-medida` | Confinamiento de 2020: −50 % (esperado −40 a −60 %); placebo en 0.95–1.11 en las 4 temporadas no vistas; rango con 91 % de cobertura y 5 % de falsas alarmas en 960 pruebas | Medidas o choques grandes (≥ 30 % en una temporada) y acotar afirmaciones públicas |
| 2 | **Segunda opinión del satélite** | `nox-ml flux-divergence` | Estimación independiente, solo con TEMPO: domingo ÷ hábil 0.51–0.61, cerca del estimador de estaciones (0.47–0.64), con su propio placebo en 1.00 | Confirmar la dirección y el tamaño de un cambio sin usar las estaciones |
| 3 | **Diagnóstico de episodios** | `nox-ml episode` | Veredicto prudente: dice si el clima explica una semana alta o baja y nunca afirma un cambio de emisión. En 52 episodios de causa conocida se equivoca de causa en 3; las falsas acusaciones a la emisión en semanas sin cambio bajan de 18 % a 9 % | Explicar episodios a la autoridad y a los medios |
| 4 | **Planeación de pilotos** | `nox-ml ficha-dias` | Días necesarios para ver una baja dada. En una temporada, ~30 % con la medida continua; 16–28 % aplicándola en semanas alternas; ~10 % repitiéndola en seis temporadas (diseños alternados, validados con eventos simulados) | Decidir cuánto tiempo y con qué diseño mantener una medida antes de juzgarla |
| 5 | **Régimen del ozono** | Análisis por temporada (exploración F2) | En el centro, recortar NOₓ no baja el ozono: en domingo el NOₓ baja 30 % y el ozono máximo queda igual o sube 3 % (80 domingos, con control por clima); en el confinamiento, NOₓ −33 % y ozono −2 a −4 %. Coincide con la literatura (centro limitado por compuestos orgánicos volátiles) | Orientar el programa de contingencias por ozono |
| 6 | **Calidad de las redes públicas** | Detectores de la exploración F7 | 21 cortes de red sin documentar en 22 meses; OpenAQ pierde un tercio de las horas de la red oficial | Un reporte mensual al operador de la red |
| 7 | **Reparto de la emisión entre zonas** | Inversión física (E5b≥0) | Estable solo como proporción entre 6 zonas. El oriente (Chalco, Ixtapaluca, Chimalhuacán, Texcoco y el oriente de Iztapalapa) aparece con 5–15 % de la emisión vial, frente a 13–17 % del inventario del INECC y de EDGAR | Señal para revisar el inventario, no auditoría |
| 8 | **Concentración donde no hay estación** | Regresión-kriging sobre la inversión | 11.7 ppb de error (interpolación simple 11.6, kriging 10.3, combinado 10.2) | Mapas aproximados; su valor es salir del mismo modelo que estima la emisión |
| 9 | **Traducción a salud (preliminar)** | Simulador de la exploración F5 | Una baja de 10 % de la emisión vial evitaría del orden de cientos de muertes al año (~430, rango 176–760); las funciones de riesgo de asma no están verificadas | Solo orden de magnitud, para dimensionar lo que está en juego |

Las capacidades 1 a 4 son comandos del paquete `nox_ml`, con pruebas automáticas. Las 5, 6 y 9 son exploraciones reproducibles (`notebooks/exploraciones/`) que todavía no son comandos; la 5 y la 6 entran a producción en la fase 1 como secciones del boletín.

## Lo que no hace

- **Verificar una medida de 5–10 % en una temporada.** La emisión estimada oscila ±15 % de semana a semana por causas que el clima no explica (deriva lenta, propia de la ZMVM: otra ciudad como control no la cancela). Es la escala de las medidas reales; se alcanza solo con pilotos alternados y repetidos o con datos de tráfico.
- **Toneladas absolutas.** Cambian al doble según el modelo de transporte; se dan solo como orden de magnitud.
- **Detalle fino.** No separa autos de camiones ni zonas menores a ~18 km.
- **Noche, madrugada y tiempo real.** Solo tardes y con ~2 semanas de retraso: alcanza para un boletín mensual, no para alertas.
- **Pronosticar el ozono.** Diagnostica el régimen; no pronostica contingencias.

## Cuánto tarda cada análisis

| Análisis | Tiempo | En la interfaz |
|---|---|---|
| Ficha de una medida o de días necesarios | 1–2 min | Interactivo |
| Diagnóstico de un episodio | Segundos (un mes completo en 27 s) | Interactivo |
| Segunda opinión del satélite, una temporada | Minutos | Precalculado por temporada |
| Inversión física, una temporada | 1–2 h | Precalculado por temporada |
| Actualización diaria de los datos | Minutos | Automática |

## Productos

- **Hoy (línea de comandos):** las fichas de medida y de días, el diagnóstico de episodios y la segunda opinión del satélite, con salida en Markdown y JSON.
- **Fase 1:** un **boletín mensual público** (emisión corregida por clima, episodios del mes, calidad de las redes y régimen del ozono; un prototipo con octubre de 2026 ya corre) y un **conjunto de datos abierto con DOI**.
- **Fase 2, condicionada:** la interfaz web descrita en *Interfaz y flujos de uso* (`Interfaz.39.md`).
