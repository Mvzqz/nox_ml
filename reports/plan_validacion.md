# Plan de validación: separar emisión de concentración

## El problema

No existe una medición directa de la emisión con la cual comparar. El inventario oficial también es una estimación, hecha con factores y actividad. Por eso la separación entre emisión y clima se valida de forma **indirecta**, con varias pruebas que no dependen entre sí. Una sola no basta; el conjunto sí.

## Lo que ya tenemos

| Prueba | Qué demuestra | Resultado | Reporte |
|---|---|---|---|
| Actividad independiente: tráfico | El método recupera un cambio conocido sin haber visto los conteos | Domingo 0.65 frente a 0.65–0.73 de Infovial (día completo, ponderado por emisión) | `sesgo_domingos.md`, `config_final.md` |
| Actividad independiente: movilidad 2020 | Recupera un cambio grande | −35 % frente a −59 a −68 % de movilidad y −40 a −60 % esperado en emisión; la dirección es correcta y el tamaño queda corto | `validacion_2020.md` |
| Placebo 2019 | No confunde clima con emisión entre años | 1.00–1.03 | `validacion_2020.md` |
| Placebo de días al azar | No inventa cambios entre días | ±10–20 % (±0.19 con puffs) | `contingencias_2024.md`, `config_final.md` |
| Dos instrumentos | Estaciones y satélite cuentan la misma historia | La red vial explica el 71 % del mapa de TEMPO; el patrón se mantiene entre periodos (r = 0.90) | `puntos_calientes.html` |
| Gemelos sintéticos | El cálculo recupera emisiones conocidas | Zonas y entidades bien; municipios individuales no | `zonas_admin.md` |
| Coherencia interna | Con el clima descontado, la emisión de días hábiles varía menos que la concentración | CV 0.26 frente a ~0.33 (puffs) | `puffs_cdmx.md` |

## Lo que todavía no está demostrado

1. **Viento débil exagerado (antes descrito como sesgo de días estancados).** El placebo de días estancados sin contingencia ya da 0.94; el problema es una pendiente con la ventilación: el cuartil más estancado sale en 0.86 y el más ventilado en 1.21, porque el modelo exagera el efecto del viento débil (`estancamiento.md`). Subir el piso de viento a 2 m/s la corrige en primavera, pero no en invierno, y falta probarla en la inversión completa.
2. **Cambios entre temporadas.** El NOₓ dura menos en primavera. Sin corregirlo, invierno contra primavera da una baja falsa de ~30 % (`multifisica.md`; corrección en curso en `vida_quimica.md`).
3. **Tamaño de cambios pequeños.** No se distinguen cambios menores a 10–20 %.
4. **Totales absolutos.** Dependen del modelo: los modelos difieren 26–42 %.
5. **Subestimación en cambios grandes.** El confinamiento sale en −35 % frente a −40 a −60 % esperado.

## Pruebas planeadas

Orden por valor y costo. Ninguna prueba usa los datos con los que se hizo la estimación.

| # | Prueba | Datos | Criterio de éxito | Atiende | Costo | Estado |
|---|---|---|---|---|---|---|
| 1 | Placebo entre temporadas con vida química corregida | SIMAT y TEMPO feb–may 2024 y nov–dic 2023 | "Sin cambio" dentro de ±15 % | 2 | Días | **Parcial** (`vida_quimica.md`): dentro de primavera pasa (estaciones 1.01, TEMPO 0.94); invierno frente a primavera sigue fallando (0.87 estaciones, 1.3–1.5 TEMPO y total) |
| 2 | Corregir la pendiente con la ventilación (viento débil) | SIMAT, capa límite, viento, radiosondeos | Placebos estancado y ventilado centrados en 1 (±15 %) en ambas temporadas | 1 | Días | **Adoptado con reserva** (`estancamiento.md`): piso de viento 2 m/s es el estándar; primavera pasa; en invierno el cuartil ventilado queda en 1.15, en el límite, por exceso de efecto de la capa límite (pendiente) |
| 3 | Trazador CO/NOₓ | CO de SIMAT (ya descargado, `simat_tracers.parquet`) | El cociente de cambios de CO y NOₓ es coherente con la mezcla vehicular; el CO viene casi todo de vehículos | 1, 5 | Días | Pendiente |
| 4 | Tráfico actual por hora | Aforos de SEMOVI, C5 o ADIP (solicitudes en `solicitudes_datos.md`) | Ciclos semanal y horario y feriados dentro del rango del tráfico medido | 3, 5 | Gestión | Esperando datos |
| 5 | Ventas de combustible | Ventas mensuales por entidad (SENER/SIE) | La tendencia mensual de emisión sigue a las ventas de diésel y gasolina | 4, tendencias | Días | Pendiente; falta verificar la fuente |
| 6 | Más experimentos naturales | Semana Santa, vacaciones de diciembre, cierres viales, nuevas líneas de transporte | Dirección correcta y tamaño dentro del intervalo esperado | 3, 5 | Días por caso | Pendiente |
| 7 | Segundo satélite | TROPOMI NO₂ (Sentinel-5P) | Mismo patrón espacial y mismos cambios relativos que TEMPO | Instrumento independiente | Días | Pendiente |
| 8 | Control positivo en Los Ángeles | PeMS (tráfico por hora, requiere registro gratuito) e inventario de CARB | Fin de semana dentro del rango de PeMS; si falla en LA, no se confía en la CDMX | Todas | 1–2 semanas | Falta la cuenta de PeMS |
| 9 | Fuentes independientes | Inventario SEDEMA posterior a 2018 por municipio; inversiones de UNAM–LSCE; **EDGAR v8.1** (sustituto público) | Mismo patrón espacial y proporciones por entidad; totales como rango | 4 | Gestión / días | EDGAR hecho (`edgar.md`): patrón por zona Spearman 0.75 con NOₓ total, CDMX/Edomex coherente; no sirve para totales. SEDEMA: esperando datos |

## Reglas para publicar un resultado

- Cada informe incluye su propio placebo con la misma configuración. Si el placebo sale fuera de ±15 %, el resultado no se publica.
- Solo se publica como número lo que coincide entre modelos (lineal con puffs y PINN). Lo demás se da como dirección o como rango.
- Antes de adoptar cualquier cambio (zonas, transporte, química, pesos) se repite el gemelo sintético con emisiones conocidas.
- Los cambios entre temporadas solo se reportan cuando pase la prueba 1.
- Los resultados de contingencias se reportan con la advertencia del sesgo por estancamiento hasta que pase la prueba 2.

## Siguiente paso

Terminar la prueba 1 (en curso) y lanzar la 2 y la 3, que solo usan datos que ya tenemos.
