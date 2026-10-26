# Antecedentes: revisión de literatura verificada

Revisión para el proyecto de estimación de **cambios de emisión de NOₓ por zona** en la Zona Metropolitana del Valle de México (ZMVM), con estaciones, TEMPO y un modelo de transporte (ver `README.md` y `docs/models.md`).

**Criterio de inclusión.** Solo se incluyen referencias comprobadas el 2026-10-26 contra Crossref (por DOI) o la API de arXiv: autores completos, título, año, revista, volumen y páginas. Lo que no se pudo comprobar se dejó fuera. Las entradas en formato BibTeX están en [`referencias.bib`](referencias.bib). Los resúmenes de cada trabajo se basan en su resumen (abstract) publicado; no se leyeron los textos completos, así que los detalles metodológicos que no aparecen en el resumen no se afirman.

## 1. Emisiones de NOₓ desde observaciones satelitales

**Beirle et al. (2011).** Con datos de OMI, ordena las columnas de NO₂ por dirección del viento y analiza la evolución de la pluma corriente abajo para obtener a la vez emisiones y vida media del NOₓ de varias megaciudades. Reporta vidas medias diurnas cercanas a 4 h en latitudes bajas y medias, y emisiones en general cercanas a los inventarios (con Riad como excepción notable). Es el origen del enfoque de ajuste de pluma con vida química que nuestros modelos de pluma y de *puff* (E1, E2) replican con física explícita en vez de un ajuste empírico.

**Lu et al. (2015).** Aplica un ajuste de gaussiana modificada exponencialmente (EMG) que considera el viento a columnas de OMI sobre 35 áreas urbanas de EE. UU. (2005–2014), y compara con inventarios y con cargas de NO₂ con viento débil. Reporta que las vidas medias efectivas del ajuste quedan sesgadas a la baja frente a las de verano. Difiere de nuestro trabajo en que estima un nivel de emisión absoluto por ciudad, no cambios por zona dentro de ella.

**Beirle et al. (2019).** Propone la divergencia del flujo horizontal de NO₂ con datos de TROPOMI y viento para localizar fuentes puntuales, y lo demuestra identificando centrales eléctricas en la región de Riad. Es la alternativa "sin transporte químico explícito" a las inversiones con modelo; nuestro dominio urbano mezcla fuentes de área y de punto a una resolución en la que esa técnica no se ha probado en este proyecto.

**Goldberg et al. (2019).** Reprocesa NO₂ de TROPOMI con un factor de masa de aire mejorado y estima NOₓ de ciudades de Norteamérica y dos centrales eléctricas; reporta acuerdo con las emisiones reportadas de las centrales (dentro de 10 %) y emisiones en días hábiles en Chicago cerca de 45 % mayores que en fin de semana. Es un antecedente directo de nuestra pregunta día hábil/domingo, aunque con una sola columna satelital diaria y sin separar el efecto del clima en las series de estaciones.

**Fioletov et al. (2025).** Usa NO₂ horario de TEMPO en 32 áreas urbanas para separar fondo, aporte urbano y fuentes industriales puntuales, y estudiar su ciclo diurno. Reporta que los domingos el NO₂ urbano baja entre 30 % y 60 % respecto de los días laborales. Es el antecedente más cercano que encontramos de TEMPO aplicado a ciclos de actividad urbana; trabaja con columnas, sin estaciones de superficie ni inversión de emisiones por zona.

**Hsu et al. (2026).** Compara el uso de TEMPO y TROPOMI para restringir emisiones antropogénicas de NOₓ de EE. UU. con WRF-Chem/Chem-DART. Con datos de mediodía, las emisiones estimadas quedan 5 %–20 % por debajo del inventario GRA²PES 2021; asimilar datos de la mañana y la tarde empeora las estimaciones por sesgos negativos de la columna. Es el único estudio de emisiones basado en TEMPO que encontramos; su dominio es EE. UU. y usa un modelo químico de transporte completo, no el esquema ligero y con incertidumbre por zona que usamos aquí.

*Sobre "primeros estudios con TEMPO":* en las búsquedas no encontramos un trabajo que se declare explícitamente el primero; Fioletov et al. (2025) y Hsu et al. (2026) son los que identificamos.

## 2. Redes neuronales informadas por la física (PINN)

**Raissi et al. (2019).** Introduce las PINN: redes entrenadas con datos y con el residuo de una ecuación diferencial parcial como término de pérdida, para problemas directos e inversos (estimar parámetros de la ecuación). Es la base de nuestros modelos E5 (`pinn_plume`, `pinn_puff`, `pinn_joint`; ADR 0004 y 0005), donde la red aprende el núcleo de advección–difusión y la inversión bayesiana estima las emisiones.

**Chuprov et al. (2025), *preprint*.** Aplica PINN al problema inverso de advección–difusión para localizar fuentes de contaminación, con escenarios de viento débil y fuerte y varias fuentes, y encuentra que la exactitud depende mucho de los hiperparámetros. Es un preprint de arXiv (v1) sin versión revisada por pares que hayamos podido comprobar. Estima posición de fuentes; nosotros fijamos la malla de zonas y estimamos su intensidad con incertidumbre, usando la PINN solo como matriz fuente–receptor.

## 3. Normalización meteorológica y confinamiento por COVID-19

**Grange et al. (2018).** Entrena bosques aleatorios para 31 sitios suizos con meteorología, capa límite y variables de tiempo para explicar PM₁₀ diario, y calcula tendencias normalizadas por meteorología. Es el método que sigue nuestro modelo `rf_deweather` (ADR 0006). Se aplicó a PM₁₀ y tendencias de largo plazo, no a NOₓ por tipo de día ni a un contraste con modelos de transporte.

**Petetin et al. (2020).** Estima con modelos de aprendizaje automático el NO₂ "sin confinamiento" en estaciones urbanas de España y lo compara con lo observado; reporta una reducción media de 50 % del NO₂ por las medidas entre el 14 de marzo y el 23 de abril de 2020. Nuestro uso del confinamiento 2020 como evento de respuesta conocida (`docs/models.md`, sección 5) sigue esta lógica, pero lo contrastamos con estimaciones de emisión de modelos físicos, no solo con un modelo de aprendizaje automático.

**Goldberg et al. (2020).** Descuenta meteorología y ángulo solar de las columnas de NO₂ de TROPOMI durante el confinamiento y obtiene caídas de 9.2 %–43.4 % en 20 ciudades norteamericanas (mediana 21.6 %), con las mayores en San José, Los Ángeles y Toronto. Incluye Los Ángeles, nuestra ciudad de control; usa columnas satelitales, mientras que nuestro banco combina estaciones y satélite.

## 4. Calidad del aire y emisiones en la ZMVM

**Molina et al. (2007).** Panorama de la campaña MCMA-2003: meteorología, emisiones primarias, precursores y formación de oxidantes y aerosol secundario en la ZMVM, con más de 40 trabajos revisados. Es el contexto científico de la ciudad, no una estimación de emisiones por zona.

**Molina et al. (2010).** Panorama de la campaña MILAGRO 2006 (marzo de 2006): emisiones de la ZMVM y su transporte y transformación, con sitios en superficie, aviones y satélites. Marca la última gran campaña de referencia para comparar inventarios; nuestro periodo (2023–2024) es posterior.

**Zavala et al. (2009).** Con un laboratorio móvil en MILAGRO/MCMA-2006, evalúa el inventario oficial de fuentes móviles: encuentra posibles sobreestimaciones de 14 %–20 % para NO y 20 %–28 % para CO, dentro de la incertidumbre, y diferencias importantes en COV y aldehídos. Es una verificación "de abajo hacia arriba" de una fuente (vehículos de gasolina); nosotros estimamos cambios de emisión totales por zona desde las concentraciones.

**Ojeda Lerma et al. (2021).** Evalúa las columnas de NO₂ de OMI (producto DOMINO) con cuatro instrumentos MAX-DOAS dentro de la ZMVM, con más de cinco años de datos; obtiene r ≈ 0.6 global. Documenta la calidad de los datos satelitales sobre la ciudad y es relevante porque el sesgo de columna sobre la ciudad afecta cualquier comparación con TEMPO (OMI y TEMPO son instrumentos distintos; este trabajo no evalúa TEMPO).

*Sobre TEMPO en la Ciudad de México:* TEMPO cubre la ZMVM, pero no encontramos en las búsquedas un estudio verificado de emisiones de NOₓ de la ZMVM con TEMPO ni con inversión por zonas.

## Brecha y aporte

Con la salvedad de que la búsqueda fue acotada (varias consultas en Crossref y arXiv, sin revisión sistemática) y de que no leímos los textos completos:

- **Cambios de emisión por zona y tipo de día en una megaciudad latinoamericana, con TEMPO y estaciones a la vez.** Los estudios satelitales verificados dan emisiones por ciudad (Beirle 2011, Lu 2015, Goldberg 2019) o ciclos diurnos de columnas (Fioletov 2025) y los de TEMPO que encontramos se centran en EE. UU. (Hsu 2026). No encontramos un trabajo que haga la inversión por zonas para la ZMVM.
- **Comparación bajo un mismo protocolo.** Los trabajos citados aplican un método cada uno. Aquí se comparan inversiones físicas, PINN y normalización con bosque aleatorio con validación por estación omitida, pruebas placebo y un filtro de elegibilidad (`docs/models.md`, sección 3). No encontramos una comparación así en la literatura verificada.
- **Respuesta conocida como control.** El cociente domingo/día hábil frente a conteos de tráfico (0.65–0.73) y el confinamiento 2020 funcionan como pruebas con respuesta conocida; los trabajos de confinamiento revisados (Petetin 2020, Goldberg 2020) comparan contra un contrafactual meteorológico, pero no contra la estimación de otros modelos de emisión.
- **PINN en inversión de emisiones urbanas.** Las PINN verificadas localizan fuentes o estiman parámetros (Raissi 2019, Chuprov 2025). No encontramos aplicaciones a la estimación de emisiones por zona con datos reales de una ciudad.

Límite importante: no podemos afirmar que estos trabajos no existan; solo que no los encontramos con estas búsquedas.

## Referencias (APA 7)

Beirle, S., Boersma, K. F., Platt, U., Lawrence, M. G., & Wagner, T. (2011). Megacity emissions and lifetimes of nitrogen oxides probed from space. *Science, 333*(6050), 1737–1739. https://doi.org/10.1126/science.1207824

Beirle, S., Borger, C., Dörner, S., Li, A., Hu, Z., Liu, F., Wang, Y., & Wagner, T. (2019). Pinpointing nitrogen oxide emissions from space. *Science Advances, 5*(11), Article eaax9800. https://doi.org/10.1126/sciadv.aax9800

Chuprov, I., Derkach, D., Efremenko, D., & Kychkin, A. (2025). *Application of physics-informed neural networks for solving the inverse advection-diffusion problem to localize pollution sources* [Preprint]. arXiv. https://arxiv.org/abs/2503.18849

Fioletov, V., Griffin, D., McLinden, C. A., Zhao, X., Nowlan, C., & González Abad, G. (2025). Diurnal variations in background and urban NO₂ estimated from TEMPO. *Geophysical Research Letters, 52*(21), Article e2025GL117360. https://doi.org/10.1029/2025GL117360

Goldberg, D. L., Anenberg, S. C., Griffin, D., McLinden, C. A., Lu, Z., & Streets, D. G. (2020). Disentangling the impact of the COVID-19 lockdowns on urban NO₂ from natural variability. *Geophysical Research Letters, 47*(17), Article e2020GL089269. https://doi.org/10.1029/2020GL089269

Goldberg, D. L., Lu, Z., Streets, D. G., de Foy, B., Griffin, D., McLinden, C. A., Lamsal, L. N., Krotkov, N. A., & Eskes, H. (2019). Enhanced capabilities of TROPOMI NO₂: Estimating NOₓ from North American cities and power plants. *Environmental Science & Technology, 53*(21), 12594–12601. https://doi.org/10.1021/acs.est.9b04488

Grange, S. K., Carslaw, D. C., Lewis, A. C., Boleti, E., & Hueglin, C. (2018). Random forest meteorological normalisation models for Swiss PM₁₀ trend analysis. *Atmospheric Chemistry and Physics, 18*(9), 6223–6239. https://doi.org/10.5194/acp-18-6223-2018

Hsu, C.-H., Henze, D. K., Mizzi, A. P., Harkins, C., Lyu, C., Cooper, O. R., Schwantes, R. H., He, J., Li, M., Wang, S., Stockwell, C. E., Warneke, C., Rollins, A. W., Waxman, E. M., Zuraski, K., Peischl, J., Kondragunta, S., Li, F., Xu, C., … McDonald, B. C. (2026). Top-down estimates of U.S. NOₓ emissions using TEMPO and TROPOMI NO₂ remote sensing observations with WRF-Chem/Chem-DART. *Journal of Geophysical Research: Atmospheres, 131*(2), Article e2025JD044223. https://doi.org/10.1029/2025JD044223

Lu, Z., Streets, D. G., de Foy, B., Lamsal, L. N., Duncan, B. N., & Xing, J. (2015). Emissions of nitrogen oxides from US urban areas: Estimation from Ozone Monitoring Instrument retrievals for 2005–2014. *Atmospheric Chemistry and Physics, 15*(18), 10367–10383. https://doi.org/10.5194/acp-15-10367-2015

Molina, L. T., Kolb, C. E., de Foy, B., Lamb, B. K., Brune, W. H., Jimenez, J. L., Ramos-Villegas, R., Sarmiento, J., Paramo-Figueroa, V. H., Cardenas, B., Gutierrez-Avedoy, V., & Molina, M. J. (2007). Air quality in North America's most populous city – overview of the MCMA-2003 campaign. *Atmospheric Chemistry and Physics, 7*(10), 2447–2473. https://doi.org/10.5194/acp-7-2447-2007

Molina, L. T., Madronich, S., Gaffney, J. S., Apel, E., de Foy, B., Fast, J., Ferrare, R., Herndon, S., Jimenez, J. L., Lamb, B., Osornio-Vargas, A. R., Russell, P., Schauer, J. J., Stevens, P. S., Volkamer, R., & Zavala, M. (2010). An overview of the MILAGRO 2006 campaign: Mexico City emissions and their transport and transformation. *Atmospheric Chemistry and Physics, 10*(18), 8697–8760. https://doi.org/10.5194/acp-10-8697-2010

Ojeda Lerma, Z., Rivera Cardenas, C., Friedrich, M. M., Stremme, W., Bezanilla, A., Arellano, E. J., & Grutter, M. (2021). Evaluation of OMI NO₂ vertical columns using MAX-DOAS observations over Mexico City. *Remote Sensing, 13*(4), Article 761. https://doi.org/10.3390/rs13040761

Petetin, H., Bowdalo, D., Soret, A., Guevara, M., Jorba, O., Serradell, K., & Pérez García-Pando, C. (2020). Meteorology-normalized impact of the COVID-19 lockdown upon NO₂ pollution in Spain. *Atmospheric Chemistry and Physics, 20*(18), 11119–11141. https://doi.org/10.5194/acp-20-11119-2020

Raissi, M., Perdikaris, P., & Karniadakis, G. E. (2019). Physics-informed neural networks: A deep learning framework for solving forward and inverse problems involving nonlinear partial differential equations. *Journal of Computational Physics, 378*, 686–707. https://doi.org/10.1016/j.jcp.2018.10.045
