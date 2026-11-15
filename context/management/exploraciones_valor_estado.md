# Exploraciones de valor: estado al 15 de noviembre de 2026

Resultado de la noche del 14 al 15 de noviembre. Cada frente probó una vía para bajar el límite de detección (~30 % por temporada, fijado por la deriva lenta) o para dar un uso frecuente que no dependa de él. Los veredictos usan criterios fijados antes de correr cada prueba. Las notas completas están en `context/knowledge/`.

## Tabla de estado

| Frente | PR | Veredicto | Confianza | Cifra clave | Siguiente paso |
|---|---|---|---|---|---|
| F1. Diseños alternados | #93 (fusionado), #99 (confianza) | Seguir con condiciones | Media–alta | Semanas alternas: deriva de 0.137 a 0.054; mínimo detectable de 16–28 % por temporada, ~10 % con seis temporadas. E7 + satélite calibrado: 3–4 % de falsas alarmas y 91–93 % de cobertura. Con arrastre del 50 %, ≥ 19–26 % | Que `ficha-medida` y `ficha-dias` acepten diseños alternados (~2–3 días); tabla de días × diseño para planeadores en la nota |
| F2. Régimen del ozono | #92 (fusionado), #101 (confianza) | Seguir con condiciones | Media para el régimen, baja para el cambio dentro de la temporada | El NOₓ cae en domingo (0.70) y el ozono no (1.00–1.03); confinamiento: NOₓ −33 %, ozono −2 a −4 %. El cociente HCHO/NO₂ sube de febrero a mayo en 3 de 3 años, pero el ozono de domingo no lo sigue (1 de 3) | Presentar el centro como limitado por COV en temporada de ozono, sin afirmar el cambio de régimen; no hay estudios previos con TEMPO para la ZMVM |
| F3. Diagnóstico de episodios | #90 (fusionado) | Seguir con condiciones | Media | Clima acierta en 56–63 % (meta ≥ 80 %); con el veredicto prudente, los falsos positivos de emisión bajan de 18 % a 9 % | Implementar el veredicto prudente en `nox_ml.validation.episodes` con pruebas (~1 día) |
| F4. Contraste del inventario | #97, #100 (abiertos) | Seguir con condiciones; la confianza sube en parte | Media | Oriente: inversión 4.8–9.5 %, satélite 9–15 %, MOVES-México 13–15 %, EDGAR 16.5 %. El "19 %" era el reparto vial de OSM, no el inventario | **Corregir el artículo:** la columna este no incluye a Ecatepec ni a Nezahualcóyotl (es Chalco, Ixtapaluca, Chimalhuacán, Texcoco y el oriente de Iztapalapa); decir "5–15 % frente a 13–17 % de las fuentes oficiales" |
| F5. Simulador de salud | #98 (abierto) | Seguir con condiciones | Baja–media | 10 % menos de emisión vial: ~430 muertes (176–760) y ~155 casos de asma infantil (69–295) evitados al año | Verificar las funciones de riesgo y las tasas base con la fuente primaria antes de citar cifras |
| F7. Control de calidad de redes | #91 (fusionado) | Seguir con condiciones | Media | OpenAQ pierde 33 % de las horas de SIMAT; 21 cortes de red sin documentar en 22 meses | Detectores de red en `nox-ml update` (~3 días); un primer reporte al operador |
| F9. Ciudad de control | #95 (abierto) | **Descartar** | Alta (negativo) | Puebla cancela la deriva solo en 1 de 3 temporadas; mínimo detectable de 40 % a 34 % | Ninguno: la deriva es sobre todo propia de la ZMVM |
| F6. Datos de tráfico | — | Detenido | — | No se espera acceso a tiempo | Solicitud de transparencia cuando el equipo lo decida |
| F8. Monterrey | — | No se lanzó | — | F9: solo 4 semanas útiles por nubes en nov–dic 2024 | — |

## Qué cambia para la propuesta de valor

- **Medir medidas reales:** sigue sin alcanzarse 5–10 % en una temporada. Lo más cerca es un piloto con semanas alternas: ~16–20 % en una temporada de feb–may, o ~10 % repitiendo la medida en varias temporadas. La ciudad de control no ayuda.
- **Usos frecuentes que no dependen del límite:** explicar el clima en un episodio (con el veredicto prudente), el régimen del ozono para las contingencias y el control de calidad de las redes públicas.
- **Afirmaciones que hay que corregir en el artículo y en el resumen ejecutivo:**
  1. El oriente: nombres de municipios y la cifra del inventario (F4).
  2. El régimen del ozono: no afirmar el cambio dentro de la temporada (F2).
  3. Las cifras de salud: solo como orden de magnitud y con las fuentes verificadas (F5).

## Pendientes del equipo

- Revisar y fusionar #95, #97, #98, #99, #100 (apilado sobre #97) y #101.
- Versionar con DVC los datos nuevos de `data/raw/` (`tempo_hcho/`, `tempo_{monterrey,puebla,toluca}/`, `era5_openmeteo_cities/`, `inventario_2020/`, `censo2020/`) y el `MANIFEST.md`. Tu `data/raw.dvc` ya tenía cambios sin commit en `ensembles/corrections`.
- Reescribir el resumen ejecutivo (`docs/entregables/ResumenEjecutivo.39.md`) con esta tabla.
