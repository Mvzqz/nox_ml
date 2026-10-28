# Conocimiento técnico

Se migra por partes desde la carpeta de investigación (`reports/RESUMEN.md`, `reports/PENDIENTES.md`).

- [`antecedentes.md`](antecedentes.md): revisión de literatura verificada (satélite, PINN, normalización meteorológica, ZMVM) y brecha que cubre el proyecto. Referencias en [`referencias.bib`](referencias.bib).
- [`desfase_merra2.md`](desfase_merra2.md): el desfase de una hora de MERRA-2 frente a ERA5 (correlación cruzada, corrección y efecto en los modelos).
- [`capacidades.md`](capacidades.md): qué puede hacer el sistema, con qué precisión y qué no; escala relevante para la salud; costo de cómputo por análisis.
- [`casos_de_uso.md`](casos_de_uso.md): replanteamiento del caso de uso, usuarios, seis casos de uso con entradas, salidas y acciones, principios de la experiencia y mapa de pantallas.
- [`alternativas.md`](alternativas.md): otras formas de responder las mismas preguntas (normalización meteorológica, emisiones de satélite de arriba hacia abajo, modelos químicos con asimilación, econometría cuasi-experimental, mapas de concentración con aprendizaje automático, medición directa) y si son mejores.
- [`brechas_y_mejoras.md`](brechas_y_mejoras.md): los casos de uso más valiosos, qué impide satisfacerlos y trece mejoras ordenadas por factibilidad, costo e impacto.
- [`capa_limite_2024.md`](capa_limite_2024.md): cómo se construye la capa límite de 2024, su error medido en 2023 y la sensibilidad ±20 % (limitaciones del avance 5).
- [`verificaciones_nivel1.md`](verificaciones_nivel1.md): verificaciones y herramientas del nivel 1: convenciones, festivos y días de fin de año (sesgo del domingo), piso de ruido, control con calendario, curva de detección, diagnóstico de episodios y regresión-kriging.
- [`controles_de_verdad.md`](controles_de_verdad.md): controles con verdad conocida: el confinamiento de 2020 frente a 2019 (cambio real) y gemelos con emisión conocida sobre los receptores reales (origen del sesgo del domingo).
