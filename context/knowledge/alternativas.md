# Otras formas de responder nuestras preguntas, y si son mejores

Fecha: 2026-10-28. Búsqueda en la literatura de los métodos que responden las mismas preguntas que el sistema ([capacidades.md](capacidades.md)). "Mejor" depende de la pregunta: ninguna alternativa domina en todas. Las fuentes están al final; las cifras de otros estudios no siempre son comparables con las nuestras (otra métrica, otra resolución, otra ciudad).

## Resumen

| Pregunta | Alternativa principal | ¿Es mejor? | Qué hacemos con eso |
|---|---|---|---|
| ¿Cuánto cambió la emisión, descontado el clima? (cambios relativos) | Normalización meteorológica con bosque aleatorio (rmweather) sobre concentraciones | Equivalente para toda la ciudad, más simple y más aceptada; no da emisión por zona ni límite de detección | Ya la tenemos (E6, X4) y el estimador normalizado (E7) es de la misma familia |
| ¿Cuánto emite la ciudad? (nivel absoluto) | Satélite de arriba hacia abajo: divergencia de flujo o ajuste de la pluma (EMG) con TROPOMI o TEMPO | Para el total de la ciudad, sí: método publicado, automatizable, incertidumbre declarada de ~20–30 % y comparable entre ciudades | Usarlo como ancla del nivel absoluto (nuestra brecha B4) |
| ¿Cuánto emite cada zona y cada hora? | Inversión con un modelo químico de transporte y asimilación de datos (p. ej., WRF-Chem con TEMPO) | En física sí (viento variable, química completa); en costo y accesibilidad, no | Referencia de comparación; nuestra ventaja es el costo |
| ¿Una medida funcionó? | Econometría cuasi-experimental sobre concentraciones (antes y después, diferencias en diferencias, discontinuidad) | Más aceptada en evaluación de políticas; pero mide concentraciones con controles del clima simples | Complementaria: nosotros aportamos la física del transporte y el límite de detección |
| ¿Qué concentración hay donde no hay estación? | Modelos de aprendizaje automático con satélite y uso de suelo | Sí, claramente | No competir (CU6 es secundario); usar sus salidas si se necesitan mapas de exposición |
| ¿Cuánto emite un sector o una fuente? | Inventario de abajo hacia arriba, mediciones directas (covarianza de remolinos, sensores remotos de escape, DOAS móvil) | Sí, en detalle por fuente; con más costo y en campañas puntuales | Complementarias: el sistema contrasta sus patrones, no los sustituye |

## Detalle por alternativa

### 1. Normalización meteorológica estadística

- **Qué es:** un bosque aleatorio aprende la concentración a partir del clima y del calendario; al fijar el clima, lo que queda es el efecto del calendario o de la intervención (Grange y Carslaw, 2019; paquete rmweather). Es la técnica estándar en estudios de tendencias y de intervenciones de tráfico, y se usó mucho en el confinamiento de 2020.
- **Frente a nosotros:** E6 y X4 son exactamente esto, y E7 es un estimador de la misma familia con un modelo de transporte. En la investigación de este proyecto, E7 pasó el placebo de 2019 y E6 queda detrás de las inversiones en error con estación oculta (14.6 frente a 11.9 ppb).
- **Advertencia de la literatura:** distintas variantes dan magnitudes distintas. En Buenos Aires, durante el confinamiento, la normalización dio hasta −36 % de NO₂ y un contrafactual con el mismo bosque dio hasta −46 %.
- **Veredicto:** no es mejor ni peor; es la base de nuestros cocientes. Lo que añadimos es la emisión por zona, la calibración con placebos y el límite de detección.

### 2. Emisiones de arriba hacia abajo con satélite (sin modelo químico)

- **Qué es:** a partir de las columnas de NO₂ y del viento, estimar la emisión de una ciudad. Dos familias: el ajuste de una gaussiana exponencialmente modificada a la pluma de la ciudad (Beirle et al., 2011; Goldberg et al., 2019 con TROPOMI, de mensual a una sola pasada) y la divergencia de flujo (emisión = divergencia del flujo de NOₓ + pérdida química), que da mapas de emisión. En ciudades grandes de Estados Unidos con TROPOMI, la incertidumbre declarada es de ~20 %; en otras evaluaciones, ~30 %.
- **Frente a nosotros:** comparte la idea (satélite + viento + pérdida química) y es más directo para el **total de la ciudad**; además ya hay trabajos que estiman tendencias de NOₓ urbano en cientos de ciudades. No encontramos un estudio con TEMPO que estime la emisión de la Ciudad de México por tipo de día; sí uno que separa el NO₂ urbano del de fondo con TEMPO en 32 ciudades, incluida la Ciudad de México (Fioletov et al., 2025, el mismo que citamos en el avance 4).
- **Veredicto:** para el nivel absoluto, mejor que nuestro modelo, que cambia hasta un factor de 2 según el transporte. **Es la ancla externa que nos falta** y la amenaza más directa: alguien con TEMPO puede producir series de emisión de la ciudad casi automáticas. Nuestra ventaja: las estaciones de superficie, la separación por tipo de día y por región, y la validación (estación oculta, placebo, inyección).

### 3. Inversión con un modelo químico de transporte

- **Qué es:** un modelo meteorológico y químico completo (WRF-Chem, GEOS-Chem) con asimilación de las columnas del satélite; en Estados Unidos ya se usa con TEMPO y TROPOMI, y se reporta que TEMPO al mediodía restringe mejor las fuentes que el paso único diario de TROPOMI.
- **Frente a nosotros:** física mucho más completa (viento variable, química del ozono, transporte en tres dimensiones), que corrige nuestras brechas B3 y B6. Cuesta semanas de cómputo, equipo especializado y un inventario de partida.
- **Veredicto:** mejor en física, peor en costo y en accesibilidad. Es la referencia contra la que nos deberíamos comparar (mejora 7 de [brechas_y_mejoras.md](brechas_y_mejoras.md)).

### 4. Econometría cuasi-experimental para evaluar políticas

- **Qué es:** comparar concentraciones antes y después de una medida, con grupos de control y controles de clima. Es la literatura de referencia del Hoy No Circula (Davis, 2008: sin evidencia de mejora del aire y con más vehículos y más contaminantes en circulación; un reanálisis posterior muestra que cambios razonables de método alteran la conclusión). En la Ciudad de México hay estudios recientes del mismo tipo sobre límites de velocidad y sobre el Cablebús.
- **Frente a nosotros:** más aceptada en evaluación de políticas y con diseños causales explícitos. Trabaja con concentraciones y controla el clima con regresión, no con física del transporte, y no reporta un límite de detección.
- **Veredicto:** complementaria. La combinación más sólida es su diseño causal con nuestra variable de emisión normalizada por clima. Que el reanálisis de Davis cambie la conclusión con el método refuerza nuestra insistencia en placebos y límites de detección.

### 5. Concentración en alta resolución con aprendizaje automático

- **Qué es:** modelos que combinan columnas de satélite, meteorología, uso de suelo y estaciones para estimar NO₂ diario por kilómetro cuadrado. En la Ciudad de México, un modelo de varias etapas (bosque aleatorio, XGBoost y GAM) reporta un R² de validación cruzada de 0.87 y un error de 3.95 µg/m³ en promedios diarios; también hay modelos de regresión de uso de suelo espacio-temporales con tráfico por hora.
- **Frente a nosotros:** las métricas no son comparables (promedios diarios frente a horas de la tarde en una estación oculta), pero su objetivo es la concentración y lo hacen mejor. Nuestro modelo es mejor para explicar de dónde viene, no para mapearla.
- **Veredicto:** mejor para CU6. No competir; usar sus salidas para exposición si un caso de uso lo pide.

### 6. Medición directa y de abajo hacia arriba

- **Covarianza de remolinos:** mide el flujo de emisión de un barrio desde una torre. En la Ciudad de México se midieron CO₂ y compuestos orgánicos (campañas MCMA-2003 y MILAGRO 2006); el flujo de CO₂ siguió el patrón del tráfico. Es la medición más directa, pero cubre ~1 km alrededor de la torre y se hace en campañas.
- **Sensores remotos de escape:** miden la emisión de miles de vehículos reales (hay una campaña reciente de autos particulares y taxis en la Ciudad de México); dan factores de emisión por tipo de vehículo, la base de un inventario.
- **DOAS móvil:** mide columnas de NO₂ y SO₂ alrededor de fuentes puntuales (por ejemplo, el complejo industrial de Tula).
- **Inventario:** detalle por fuente y por calle, cada varios años.
- **Veredicto:** mejores para el detalle por fuente y como verdad local; caros y puntuales. Son la validación ideal de nuestros resultados en una zona, no un sustituto.

## Emisión o solo concentración: ¿cuánto vale medir la emisión?

Los resultados del avance 4 (noviembre–diciembre de 2023) muestran que, para detectar si la emisión de **toda la ciudad** cambió, la concentración normalizada por el clima es igual de buena o mejor:

| Modelo | Qué mide | Domingo ÷ hábil (IC 90 %) | Placebo |
|---|---|---|---|
| E6, bosque aleatorio | Concentración normalizada por clima, sin física | 0.53 (0.42–0.57) | 0.97 ± 0.09 |
| E7, estimador normalizado | Concentración ÷ lo que predice el transporte con emisión fija | 0.56 (0.46–0.71) | 0.88 ± 0.22 |
| E5b, inversión | Emisión por región y tipo de día | 0.48 (0.36–0.62) | 1.01 ± 0.12 |

Lo que la emisión aporta y la concentración no:

1. **Origen espacial:** qué región causa la concentración en otra (las estaciones mezclan lo que llega de varias zonas con el viento). Es la base de la equidad y de evaluar proyectos locales.
2. **Escenarios:** con emisión y transporte se puede simular "si la región X reduce 10 %, ¿cuánto baja la concentración en cada lugar y con qué clima?" (CU9 en [casos_de_uso.md](casos_de_uso.md)).
3. **Usar el satélite:** TEMPO mide columnas, no lo que se respira; la emisión es la variable común con las estaciones.
4. **Comparar con inventarios y compromisos,** que están en emisión.
5. **Climas no vistos:** la normalización estadística falla cuando el tipo de día y el clima no se cruzan o cuando aparece un régimen nuevo (ADR 0006); la física generaliza mejor.

Hoy esas ventajas son en buena parte **potenciales**: el origen espacial tiene 9 regiones con intervalos amplios (brecha B2) y los escenarios necesitan un nivel absoluto anclado (B4). La que más usamos es la 3. Se vuelven reales con las mejoras 8, 14 y 7 de [brechas_y_mejoras.md](brechas_y_mejoras.md). Para el producto: concentración normalizada para la respuesta rápida de toda la ciudad (CU1, CU2, CU7) e inversión de emisión para el origen espacial y los escenarios.

## Conclusión

- **Nuestro nicho:** emisión (no concentración), por tipo de día y por región, separada del clima con física, validada con estación oculta y placebo, con límite de detección, a bajo costo y con datos públicos. Ninguna alternativa reúne todo eso, pero varias son mejores en una parte.
- **Dónde no debemos competir:** el mapa de concentración (CU6) y el detalle por fuente.
- **Qué deberíamos adoptar:**
  1. La divergencia de flujo o el ajuste de pluma con TEMPO como **ancla del total de la ciudad** y como comparación independiente (nueva mejora en [brechas_y_mejoras.md](brechas_y_mejoras.md)).
  2. Los **diseños cuasi-experimentales** de la econometría para CU2, CU7 y CU8, con nuestra emisión normalizada como variable de resultado.
  3. Una **comparación con un modelo químico con asimilación** cuando exista para la región.

## Fuentes

- Grange, S. K. y Carslaw, D. C. (2019). Using meteorological normalisation to detect interventions in air quality time series. *Science of the Total Environment*, 653, 578–588.
- Estudio de Buenos Aires sobre el confinamiento con normalización y contrafactual: *Earth System Science Data*, 15, 189 (2023).
- Goldberg, D. L. et al. (2019). Enhanced capabilities of TROPOMI NO₂: estimating NOₓ from North American cities and power plants. *Environmental Science & Technology*.
- Mapeo de emisiones de NOₓ en ciudades grandes de Estados Unidos con TROPOMI (divergencia de flujo): *Atmospheric Chemistry and Physics*, 24, 3717 (2024).
- Evaluación del método de divergencia de flujo en Chipre con TROPOMI (PMC11775050).
- Hsu et al. (2026). Top-down estimates of U.S. NOₓ emissions using TEMPO and TROPOMI with WRF-Chem/Chem-DART. *Journal of Geophysical Research: Atmospheres*.
- Fioletov et al. (2025). Diurnal variations in background and urban NO₂ estimated from TEMPO. *Geophysical Research Letters*.
- Davis, L. W. (2008). The effect of driving restrictions on air quality in Mexico City. *Journal of Political Economy*; reanálisis de Salas (Pontificia Universidad Católica de Chile).
- Estudios cuasi-experimentales en la Ciudad de México: límites de velocidad (*Science of the Total Environment*, 2024) y Cablebús (*Journal of Transport Geography*, 2024).
- Modelo de NO₂ diario de 1 km en la Ciudad de México con satélite y aprendizaje automático (PMC10168642); regresión de uso de suelo espacio-temporal (Son et al., 2018).
- Velasco et al. Flujos de CO₂ y compuestos orgánicos por covarianza de remolinos en la Ciudad de México (*Atmospheric Environment*, 2005; *ACP*, 9, 7325, 2009).
- Iniciativa TRUE (2024). Emisiones reales de autos particulares y taxis en la Ciudad de México (sensores remotos).
- Medición de NO₂ y SO₂ con DOAS móvil en el complejo industrial de Tula (PMC12227472).
