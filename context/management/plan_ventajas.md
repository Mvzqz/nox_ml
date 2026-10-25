# Ventajas posibles del proyecto y plan para estudiarlas

Hipótesis a confirmar con la revisión de literatura verificada (`context/knowledge/antecedentes.md`, cuando exista). Hasta entonces se reportan como "posibles", nunca como hechos.

## Ventajas posibles frente a lo existente

1. **Cambios de emisión hora a hora y por zona, sin el efecto del clima.** Con TEMPO (horario) y estaciones horarias, frente a métodos con una pasada diaria (OMI, TROPOMI) que promedian semanas o meses.
2. **Satélite y estaciones en una sola estimación**, con validación honesta dejando estaciones fuera.
3. **Barato y reproducible:** corre en una laptop en minutos (código abierto, datos versionados, pruebas), frente a inversiones con modelos químicos completos que requieren supercómputo.
4. **PINN extensible:** permite agregar física (terreno, viento variable, capa de mezcla, química) sin fórmulas nuevas; ya se reentrenó con otra difusión (κ).
5. **Validación con placebos y experimentos naturales** (confinamiento 2020, contingencias, Día sin carro) en cada resultado.
6. **CDMX con TEMPO**, posiblemente poco estudiada (opera desde 2023; la ciudad está en el borde sur de su cobertura).

Limitaciones frente a lo existente: la química y la estructura vertical de los modelos completos son más realistas; los totales absolutos y las fuentes individuales son inciertos.

## Plan

| # | Estudio | Cómo | Datos | Costo | Cuándo |
|---|---|---|---|---|---|
| 1 | Revisión de literatura verificada | Sesión con búsqueda web; solo referencias verificables | Web | ~1 h | En curso |
| 2 | **Comparación con un modelo químico completo (GEOS-CF)** | NO₂ en superficie y columna de GEOS-CF (NASA, ~25 km, horario, abierto) contra estaciones (mismas métricas, incluida la de estación oculta) y contra nuestra predicción; comparar el patrón espacial | GEOS-CF por OPeNDAP, nov–dic 2023 | ~1 día | Después del avance 5 |
| 3 | Emisiones frente a los inventarios de esos modelos | Nuestras emisiones por zona frente a CAMS-GLOB-ANT, EDGAR (ya integrado) y el inventario de SEDEMA | CAMS (Copernicus ADS), EDGAR, SEDEMA | ~0.5 día | Después del avance 5 |
| 4 | Costo y reproducibilidad | Tiempos medidos de nuestras corridas frente a lo reportado por estudios con modelos completos | Revisión + `runs/` | ~2 h | Con el resumen ejecutivo |
| 5 | Resolución temporal (TEMPO frente a una pasada diaria) | Repetir el domingo y el placebo usando solo la pasada de ~13:30 (como TROPOMI) frente a todas las horas | TEMPO ya integrado | ~0.5 día | Avance 5 o después |
| 6 | Comparación con AQFS-Mex (WRF-Chem de SEDEMA) | Si SEDEMA comparte salidas: concentraciones y emisiones | Solicitud a SEDEMA (no pública) | Depende de SEDEMA | Cuando haya respuesta |

Criterio para afirmar una ventaja: que el estudio correspondiente la muestre con números y, si es frente a la literatura, con una referencia verificada.
