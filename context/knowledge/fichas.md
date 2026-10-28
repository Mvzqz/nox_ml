# Fichas: cada pregunta con su estimador, y su validación

Fecha: 2026-10-29. Las capacidades únicas del sistema ([capacidades.md](capacidades.md), filas 1–3) ya existían en la línea de comandos; las fichas las presentan en una página en español, para alguien fuera del equipo. Código: `nox_ml.validation.products`.

## Qué estimador responde cada pregunta

| Pregunta | Estimador | Por qué |
|---|---|---|
| ¿Cambió la emisión entre periodos? (una medida, un anuncio) | E7, normalizado por meteorología | Midió el confinamiento de 2020 (−50 %, esperado −40 a −60 %) con el placebo de 2019 en 1; las inversiones sin TEMPO fallan ese placebo y con TEMPO tienen el sesgo del domingo ([sesgo_domingo.md](sesgo_domingo.md)). Solo usa estaciones: corre también donde falta TEMPO |
| Ciclo semanal (domingo ÷ hábil) | E6, bosque aleatorio | Sin fin de año y en nov–dic 2024 queda en el rango del tráfico |
| Concentración donde no hay estación | Regresión-kriging sobre E5b | 10.2 ppb, la mejor de la tabla |

## Las fichas

- `nox-ml ficha-medida --days INICIO:FIN --data INICIO:FIN --title "..." [--claim -0.2]`: ¿cambió la emisión en esos días?, con el cambio, su rango, el cambio mínimo detectable con esos días, el veredicto (baja, aumento o no detectable) y, si se da, si el cambio anunciado cabe en el rango. Advierte cuando los días caen en un periodo atípico.
- `nox-ml ficha-dias --data INICIO:FIN [--drops 0.1 ...]`: cuántos días hábiles necesita una medida para mostrar una baja dada, con la variación de la temporada.

El rango sale de eventos falsos de la misma duración sacados de días normales (placebo). Cuando la medida dura tanto como la referencia o más (una medida sostenida de meses), no hay suficientes días para el placebo: el rango y el mínimo detectable se extrapolan con la variación de un día a otro de la temporada, con la regla que siguen los placebos cortos (desviación ∝ √(1/k + 1/n), con k días de la medida y n de referencia). La ficha dice cuál de los dos usó.

## Validación

| Lo que afirma la ficha | Prueba | Resultado | ¿Pasa? |
|---|---|---|---|
| El rango contiene el cambio real | 200 conjuntos de 9 días normales de nov–dic 2023, con bajas inyectadas de 0, 10, 20, 30 y 36 % | Lo contiene 84–87 % de las veces (nominal 90 %) | En el borde: la ficha dice "~85 %" |
| El cambio mínimo detectable | Las mismas inyecciones, con la baja igual al mínimo que reporta la ficha (36 % con 9 días) | Se detecta 78 % de las veces (prometido: 80 %) | Sí |
| Falsas alarmas | Inyección de 0 % | 4 % de "baja detectada" (esperado ~5 %) | Sí |
| Veredicto en un cambio real | Confinamiento de 2020 (fases 2 y 3 frente a la base; 42 días contra 29, modo extrapolado) | Baja detectada: −50 % (−57 a −41 %) | Sí |
| Veredicto sin cambio | Mismas fechas de 2019 | No detectable: −7 % (−17 a +3 %) | Sí |
| ¿El anuncio cabe? | Confinamiento con anuncios de −50 % y −10 % | −50 % cabe; −10 % no | Sí |
| Periodos atípicos | Vacaciones de fin de año de 2023 | La ficha mide +40 % y advierte que es un periodo donde el método confunde acumulación con emisión | Sí, con la advertencia |
| Pruebas automáticas | Datos sintéticos con baja impuesta y sin cambio; modo extrapolado; advertencia; inversión de la calculadora | 9 pruebas | Sí |

### Varias temporadas

`ficha-medida` acepta varias temporadas (`--data` repetido): cada una se compara con sus propios días normales y los cambios se combinan pesando cada temporada por su precisión (inverso de la varianza en escala logarítmica). Validación con inyecciones en nov–dic 2023 y nov–dic 2024 (150 repeticiones, 9 días por temporada):

| Baja inyectada | El rango combinado contiene la verdad | Se detecta la baja |
|---|---|---|
| 0 % | 87 % | 6 % (falsa alarma) |
| 10 % | 88 % | 37 % |
| 20 % (el mínimo que reporta la ficha combinada) | 89 % | 78 % |
| 30 % | 87 % | 99 % |

Con dos temporadas, el mínimo detectable con 9 días por temporada baja de 36 % y 26 % (cada una sola) a 20 %. Las temporadas desde 2025 leen las estaciones de OpenAQ y el viento de los aeropuertos (`sources_for`).

Pendiente: la prueba de comprensión con tres personas fuera del equipo; protocolo, fichas y registro en `context/management/prueba_fichas/`.

## Lo que muestran las fichas de ejemplo

- **Días necesarios en invierno (nov–dic 2023):** 19 días hábiles para una baja de 30 %, 48 para 20 %, 214 para 10 % y ~900 para 5 %. Con la variación del invierno, las medidas de 5–10 % no se pueden evaluar en una temporada; en feb–may la variación es menor. Es el argumento cuantitativo para sumar temporadas (2024–2026).
- La cobertura del modo extrapolado no se pudo validar con inyecciones en datos reales (justo porque no hay días normales suficientes); se apoya en la regla de los placebos cortos y en el confinamiento, que la ficha reproduce.

## Reproducir

```bash
uv run nox-ml ficha-dias --data 2023-11-01:2023-12-31
uv run nox-ml ficha-medida --days 2023-12-18:2023-12-29 --data 2023-11-01:2023-12-31 --title "Vacaciones de fin de año 2023"
```
