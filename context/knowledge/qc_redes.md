# F7. Control de calidad de redes públicas (SIMAT y OpenAQ/SINAICA)

Fecha: 2026-11-14. Frente F7 de [exploraciones_valor.md](../management/exploraciones_valor.md). Rama `explore/network-qc`. Código y catálogo: `notebooks/exploraciones/network_qc/`.

## Qué se hizo

1. **QC existente.** `nox-ml qc-simat 2023 2024`: todo pasa salvo las 59 horas de NOₓ atascado ya conocidas (ACO 9, MON 14, PED 7, TAH 29). `nox-ml qc-simat 2019 2020` **falla** (`BadZipFile`): los archivos de 2019 y 2020 son gzip real, con fechas `dd/mm/aaaa` y encabezado distinto; el cargador solo conoce el formato ZIP de 2023–2024. El script de esta nota carga los cuatro años. Los chequeos de `nox_ml.monitor` miden la descarga y la cobertura de los pasos del `update`, no el valor de las mediciones; no se usaron.
2. **Detectores nuevos** (umbrales fijados antes de ver los datos, en `qc_catalog.py`): atascados (≥ 8 lecturas iguales, NO/NO₂/NOₓ/O₃/viento, sobre un piso), NO₂ > NOₓ y NO + NO₂ ≠ NOₓ, negativos, huecos de estación ≥ 72 h, cortes de toda la red, congelamientos simultáneos de la red, saltos de nivel de una estación frente a las demás (ventanas de 14 días, factor ≥ 2; ≥ 4 se llama salto de escala), escalones de la red entera (≥ 1.8), unidad distinta a la habitual, desfase de hora por correlación (−2…+2 h) con las demás estaciones, y la comparación SIMAT contra OpenAQ de las 21–22 estaciones comunes en nov–dic 2024.
3. **Datos:** SIMAT 2019, 2020, 2023, 2024 (contaminantes y viento); OpenAQ nov 2024 – oct 2026 (22 meses con datos). SIMAT local solo llega a 2024, así que 2025–2026 solo se puede revisar en OpenAQ.

## Resumen del catálogo

593 eventos (`catalog.csv`). Estado: *known* (ya documentado por el proyecto: viento en mph 2024, NOₓ atascado de SIMAT 2023–24, desfase de 1 h de OpenAQ), *new* o *candidate* (puede ser clima o estacionalidad, no se confirmó). "Relevante" = ≥ 12 h atascadas, hueco ≥ 7 días, corte de red ≥ 6 h o ≥ 5 estaciones congeladas a la vez.

Nuevas y relevantes desde 2024 (`summary_by_month.csv`): **137** en 34 meses-fuente (4.0 por mes):

| Tipo | SIMAT 2024 | OpenAQ nov 2024 – oct 2026 | Comentario |
|---|---|---|---|
| Hueco de estación ≥ 7 días | 36 | 77 | mediana 379 h en OpenAQ, máximo 3,606 h; mantenimiento normal, pero sin aviso |
| Corte de toda la red (< 20 % de estaciones) | 1 | 21 (727 h) | 8 de ≥ 24 h; el mayor, 20–27 nov 2024 (164 h) |
| Red congelada (≥ 22 estaciones con el mismo valor ~9 h) | 0 | 2 | 6 abr 2025 y 5 abr 2026 |
| Valores (unidades, NO₂ > NOₓ, negativos, saltos de escala, desfase por estación) | 0 | 0 | las redes están limpias en el valor |

- Meses con ≥ 1 anomalía nueva relevante: OpenAQ 20 de 22, SIMAT 2024 11 de 12 (sin ella: SIMAT jun 2024, OpenAQ mar y ago 2026). **Solo con anomalías de red** (cortes y congelamientos, sin contar huecos de estación): OpenAQ 11 de 22, SIMAT 1 de 12.
- Candidatas sin confirmar (7): escalones de O₃ en jun 2024 (×0.54) y jun 2025 (×0.33) coinciden con el inicio de lluvias; NOₓ ×1.9 en nov 2024 y ×0.55 en sep 2026 coinciden con cambio de estación; VIF (SIMAT, dic 2023, ×2.1) y AJM (OpenAQ, mar 2025, ×0.48) con datos ralos. El único atascado nuevo de SIMAT: viento en INN, 24 h con 3.7 m/s (31 jul 2024).
- **Rechazado:** el desfase de hora por estación con NO₂ marcaba siempre CUA, AJM, CHO y MON, en todos los años y fuentes: es geografía (fuentes locales), no reloj. Con O₃ no marca ninguna estación.
- **Detectores que funcionan** (control): recupera el viento en mph (escalón ×2.12 el 2024-01-01) y el desfase de 1 h de OpenAQ (a nivel de estación solo se ve contra SIMAT).

## Evidencia de las anomalías nuevas

**1. Cortes de la red en OpenAQ/SINAICA, con datos presentes en SIMAT.** En nov–dic 2024, de las horas-estación con NOₓ que SIMAT tiene para las 22 estaciones comunes, OpenAQ trae 18,400 de 27,663 (falta 33 %). Del 20 al 27 nov hay cero horas en OpenAQ y SIMAT está completo; días sueltos de diciembre (5, 7, 13, 17) faltan 57–88 %. En 2025–2026 hay 15 cortes más (el mayor, 99 h, 3–7 jul 2025). Cuando OpenAQ sí tiene la hora, coincide con SIMAT (97.7 % dentro de 1 ppb después del 17 nov): el problema es de cobertura, no de valor. Completitud mensual de OpenAQ: 54–88 % (`completeness_by_month.csv`), frente a 83 % mediano de SIMAT 2024. *Efecto:* quien arme series, promedios semanales o líneas base solo con OpenAQ pierde un tercio de las horas, y los cortes se concentran en días enteros, así que sesgan el promedio por día de la semana; en `nox-ml update` se refleja en menos horas de tarde por semana. Como SIMAT local solo llega a 2024, no se pudo ver si el hueco se rellena después en SIMAT.

**2. Red congelada el primer domingo de abril.** El 6 abr 2025 y el 5 abr 2026, de 06:00 a 15:00 UTC (00:00–09:00 locales), 22–24 estaciones repiten el mismo valor 9 h seguidas (media de NO₂ fija en 23.4 ppb en 2025 y 20.4 ppb en 2026, la misma en todas las estaciones). En SIMAT 2024 el primer domingo de abril (7 abr) hay un corte de 8 h de toda la red. Es la fecha en que empezaba el horario de verano que México abolió en 2022; es una hipótesis, no está probada. No pasa en otoño (26 oct 2025 normal). *Efecto:* 9 h inventadas por estación, justo la rampa de la mañana y el pico de 07–09 h; sin efecto en la tarde (12–17 h) que usa el modelo, pero sí en quien use perfiles horarios. Una vez al año.

**3. (Confirmación) Desfase de 1 h de OpenAQ.** Antes del 17 nov 2024, el mejor desfase es +1 h en 19–22 de 21–25 series estación-parámetro (correlación 0.80–0.94 en lag 0, 0.95–0.97 en +1; coincidencia dentro de 1 ppb: 34–48 %). Con el desfase diario de la red, +1 hasta el 15 nov y 0 desde el 17 nov; después, 98 % de coincidencia. Confirma lo conocido; no es nuevo.

## Veredicto

| Criterio | Escala | Resultado |
|---|---|---|
| **¿Funciona?** | 0 no se probó · 1 no funciona · 2 funciona con condiciones · 3 funciona y está validado de forma independiente | **2.** Cumple el criterio con huecos incluidos (31 de 34 meses con ≥ 1 anomalía nueva relevante); con solo anomalías de red, 12 de 34. No hay errores de valor nuevos. Sin validar con el operador. |
| **Evidencia** | La prueba decisiva y su cifra | OpenAQ pierde 33 % de las horas que SIMAT sí tiene (nov–dic 2024, 22 estaciones), 21 cortes de red en 22 meses (727 h), y 2 congelamientos de red el primer domingo de abril. Control: el detector recupera el viento en mph y el desfase de 1 h. |
| **Usuario** | Quién lo usaría | Operadores de SIMAT (SEDEMA) y de SINAICA (INECC), equipo de OpenAQ; analistas y académicos que bajan OpenAQ (cobertura); el propio `nox-ml update` (CU del monitoreo). |
| **Frecuencia** | Usos esperados al año | ~12 reportes mensuales; ~1–2 hallazgos de red al mes (≈ 0.7 por mes de cortes y congelamientos; ≈ 3 huecos de estación ≥ 7 días). Supuesto: el patrón de 2024–2026 continúa. |
| **Alternativa** | Ninguna · peor · igual · mejor | Igual o mejor que lo que hay para huecos (el operador no publica avisos de cortes que se encuentren); peor que el QC propio del operador para valores, que no podemos ver. |
| **Decisión que cambia** | Qué haría distinto el usuario | El operador revisa el corte y el relleno retroactivo; los usuarios de OpenAQ excluyen días con cortes en vez de promediar con huecos; el proyecto marca esas horas como no evaluables en `update`. |
| **Costo de llevarlo a producto** | Días y costo mensual | ~3 días (pasar los detectores de red a `nox_ml.data` con pruebas, y arreglar `qc-simat` para 2019–2020); costo de operación cercano a cero (corre con el `update`). Revisar y enviar el reporte: ~1 h al mes. |
| **Veredicto** | Adoptar · seguir con condiciones · descartar | **Seguir con condiciones:** (1) adoptar solo los detectores de red (cortes, congelamientos) en el `update`; (2) enviar un primer reporte y ver si el operador responde antes de hacerlo mensual; (3) confirmar con el operador que los cortes y el congelamiento no están documentados. Valor de investigación moderado; el beneficio es la fiabilidad de la entrada del proyecto más que un producto nuevo. |

## Cómo reproducir

Desde la raíz, con `data/raw` enlazado (SIMAT y OpenAQ ya descargados):

```
uv run python notebooks/exploraciones/network_qc/qc_catalog.py --cache <carpeta_temporal>
```

Salidas junto al script: `catalog.csv`, `summary_by_month.csv`, `completeness_by_month.csv`, `duplicates.csv` (SIMAT contra OpenAQ por estación y parámetro, antes y después del 17 nov), `duplicates_daily.csv`. Tarda ~1 min (más la primera lectura, que se guarda en `--cache`). El QC del repositorio: `uv run nox-ml qc-simat 2023 2024 --out-dir <carpeta_temporal>`.

## Lo que faltó

- No hay SIMAT de 2025–2026 local, así que no se pudo comparar con OpenAQ más allá de nov–dic 2024 ni ver si SIMAT rellena los cortes.
- No se midió la sensibilidad de los detectores de salto y de escala (no se inyectaron anomalías); que den cero errores de valor puede ser calma real o baja sensibilidad. Solo el viento en mph y el desfase de 1 h sirven de control.
- La causa del congelamiento de abril (horario de verano) es hipótesis; no se revisó el código de SINAICA ni la API de OpenAQ (fechas de ingesta).
- No se revisó la meteorología de OpenAQ (no la trae) ni los siete candidatos contra ERA5.
- "No documentado por el operador" se supone: no se buscó en los avisos de SEDEMA/INECC.
- No se comparó con SINAICA directo, ni se midió el efecto de los cortes en el índice semanal.

## Borrador de reporte mensual para el operador (una página)

> **Asunto: Reporte mensual de calidad de datos, red automática de monitoreo, mes AAAA-MM**
>
> **Qué es.** Revisión automática de las mediciones horarias de NO, NO₂, NOₓ y O₃ publicadas en OpenAQ (proveedor SINAICA) y, cuando hay, en datos abiertos de SIMAT. Detecta huecos, congelamientos, valores atascados, cambios de unidad o escala, saltos de nivel y desfases de hora. Es una revisión de consistencia, no una validación metrológica.
>
> **Resumen del mes.** Estaciones con datos: __. Completitud de NOₓ: __ % (mes anterior: __ %). Anomalías de red: __. Huecos de estación ≥ 7 días: __.
>
> **1. Cortes de toda la red** (menos del 20 % de las estaciones reportando). Tabla: inicio, fin, horas, estaciones habituales. Ejemplo del periodo anterior: 20 nov 2024 21:00 UTC al 27 nov 16:00 UTC, 164 h; SIMAT tiene esas horas completas. Pregunta: ¿se rellenan después en SINAICA/OpenAQ?
>
> **2. Valores repetidos en varias estaciones a la vez.** Tabla: inicio, fin, estaciones. Ejemplo: 6 abr 2025 06:00–15:00 UTC, 24 estaciones con el mismo valor; 5 abr 2026 igual (22 estaciones). Ambos son el primer domingo de abril; pedimos revisar el manejo de horario.
>
> **3. Huecos de estación ≥ 7 días.** Estación, inicio, fin, horas. Sin juicio de causa.
>
> **4. Valores atascados** (≥ 8 lecturas iguales sobre un piso) y **saltos de nivel** frente a las vecinas (≥ 2×). Estación, parámetro, fecha, factor. Se marcan como candidatas.
>
> **5. Estado de lo ya reportado.** Resuelto / sin respuesta. Con la corrección de hora de OpenAQ del 17 nov 2024, SIMAT y OpenAQ coinciden dentro de 1 ppb en 98 % de las horas comunes.
>
> **Cómo reproducir.** Código y criterios en el repositorio (`notebooks/exploraciones/network_qc/qc_catalog.py`); todos los umbrales están al inicio. Anexo: `catalog.csv` del mes.
>
> **Contacto:** (equipo). Se agradece confirmar cuáles hallazgos ya están documentados por el operador.
