# Controles con verdad conocida: confinamiento de 2020 y gemelos

Fecha: 2026-10-29. No hay una medición directa de la emisión de NOₓ de la ciudad. Dos controles dan una verdad conocida por caminos distintos:

- **Confinamiento de 2020:** un cambio real, grande y documentado. Valida que el método mide cambios reales, en datos reales. Solo estaciones (TEMPO no existía).
- **Gemelos:** datos simulados sobre las horas, estaciones y píxeles reales de nov–dic 2023, con una emisión elegida. La verdad es exacta, pero la física es la de un modelo. Separan el error del método del de la realidad.

Ninguno sustituye a una medición, pero juntos responden dos preguntas que hasta ahora no tenían respuesta: si el método ve cambios reales (sí: E7 mide ~−50 % en el confinamiento) y si el sesgo del domingo lo pone el método (no: con la verdad conocida, todos los modelos con transporte de puffs y los estadísticos la recuperan).

## 1. Confinamiento de 2020 frente a 2019

Comando: `nox-ml lockdown <config>`. Fases según Hernández-Paniagua et al. (2021): base del 15 de febrero al 15 de marzo, fase 2 (medidas parciales) del 30 de marzo al 20 de abril y fase 3 (confinamiento total) del 21 de abril al 31 de mayo. Para cada año y fase, el modelo se ajusta con los días hábiles de la base y de la fase, y la fase se reetiqueta como domingo: su cociente domingo/hábil es la emisión de la fase sobre la base. 2019, sin confinamiento, es el placebo (debería dar ~1); 2020 ÷ 2019 es el efecto del confinamiento.

Datos: tablas de SIMAT 2019–2020 de la investigación (`val2020_data.py`), viento de la red, capa de mezcla de ERA5. Sin TEMPO ni química de OH, así que E5b no aplica. Festivos oficiales de 2019–2020 agregados al calendario.

| Modelo | Fase 2, 2020 | Fase 2, 2019 (placebo) | **Fase 2, 2020 ÷ 2019** | Fase 3, 2020 | Fase 3, 2019 (placebo) | **Fase 3, 2020 ÷ 2019** |
|---|---|---|---|---|---|---|
| E7 (normalizado) | 0.48 (0.40–0.58) | 0.97 (0.83–1.12) ✓ | **0.50 (0.39–0.63)** | 0.49 (0.41–0.60) | 0.96 (0.85–1.08) ✓ | **0.51 (0.41–0.64)** |
| E6 (bosque aleatorio) | 0.69 (0.64–0.87) | 1.14 (1.08–1.19) ✗ | 0.61 (0.52–0.71) | 0.57 (0.53–0.68) | 0.98 (0.91–1.04) ✓ | 0.58 (0.50–0.67) |
| X4 (gradient boosting) | 0.63 (0.62–0.75) | 1.23 (1.13–1.23) ✗ | 0.51 (0.46–0.57) | 0.57 (0.55–0.66) | 0.97 (0.92–1.09) ✓ | 0.59 (0.52–0.67) |
| Baseline (inversión, sin TEMPO) | 0.54 (0.46–0.67) | 0.83 (0.69–1.01) | 0.64 (0.49–0.85) | 0.41 (0.33–0.54) | 0.58 (0.45–0.80) ✗ | 0.71 (0.49–1.03) |

Referencias independientes del tamaño:

| Referencia | Fase 2 | Fase 3 |
|---|---|---|
| Movilidad de Google, días hábiles (lugares de trabajo / transporte público) | −56 % / −59 % | −60 % / −65 % |
| NO₂ ajustado por meteorología (Hernández-Paniagua et al., 2021) | ≈ −20 % | ≈ −43 % |
| Rango esperado de la emisión vial de NOₓ (`reports/validacion_2020.md` de la investigación) | — | −40 a −60 % |

La movilidad cuenta personas: los vehículos pesados a diésel, que pesan mucho en el NOₓ, bajaron menos. Por eso la emisión vial debe caer menos que la movilidad.

Lectura:
- **E7 pasa el control:** el placebo de 2019 queda en 1 en las dos fases y la caída de 2020 (−49 a −50 %) cae dentro del rango esperado. Es la primera evidencia de que el método mide el tamaño de un cambio real, no solo su dirección. La versión de la investigación del mismo estimador daba −35 %; la del paquete usa la pluma con otro ancho y otro piso de viento.
- **E6 y X4 detectan la caída (−39 a −49 %), pero fallan el placebo de la fase 2 de 2019** (1.14 y 1.23). La fase 2 de 2019 incluye Semana Santa (15–19 de abril), y los bosques confunden la temporada con la emisión.
- **La inversión sin TEMPO falla el placebo** de la fase 3 (0.58), como en la investigación: sin satélite, el fondo por hora y la emisión se intercambian.
- La fase 2 de 2020 también incluye Semana Santa (6–10 de abril); el placebo de 2019 la descuenta.
- Consecuencia: el estimador normalizado (E7) es el que mide cambios entre periodos en este control; la inversión necesita TEMPO, que solo existe desde 2023. Falta repetir el control con E5b, lo que exige un cambio conocido en 2023 en adelante.

## 2. Gemelos

Comando: `nox-ml twin <generador> <estimadores...>`. Sobre los receptores reales de nov–dic 2023, las observaciones se simulan con el transporte del generador (aquí E2, puffs gaussianos), el a priori de las fuentes puntuales y una emisión vial por tipo de día: hábil 1, sábado 0.85, domingo 0.69 (el tráfico medido). El nivel se ajusta para que el NOₓ de los días hábiles del gemelo sea el real. Escenarios:

- **limpio:** fondo constante de 5 ppb y ruido de 5 %;
- **realista:** fondo regional de 10 ppb que persiste varios días (autocorrelación 0.7 de un día a otro, desviación 35 %), variación diaria de la emisión de la ciudad de 15 % y ruido horario de 30 %, del tamaño de los errores de los modelos.

Domingo/hábil recuperado (verdad: 0.69). El escenario realista se corrió con tres semillas del fondo y el ruido; E5b solo con la primera (cada ajuste tarda ~10 min). La última columna es el resultado con los datos reales.

| Estimador | Limpio | Realista, semilla 0 | Semilla 1 | Semilla 2 | Datos reales |
|---|---|---|---|---|---|
| E7 (normalizado) | 0.68 (0.62–0.75) | 0.75 (0.64–0.89) | 0.68 (0.61–0.77) | 0.68 (0.59–0.77) | 0.56 |
| E6 (bosque aleatorio) | 0.71 (0.68–0.74) | 0.77 (0.69–0.89) | 0.67 (0.62–0.75) | 0.67 (0.62–0.76) | 0.53 |
| E2 (misma física que el generador) | 0.69 (0.69–0.69) | 0.76 (0.70–0.82) | 0.63 (0.58–0.68) | 0.62 (0.58–0.67) | 0.52 |
| Baseline (pluma) | 0.58 (0.48–0.70) | 0.65 (0.52–0.81) | 0.51 (0.43–0.60) | 0.52 (0.43–0.63) | 0.42 |
| E5b (PINN con puffs) | 0.66 (0.57–0.80) | 0.73 (0.62–0.87) | — | — | 0.48 |

Lectura:
- **Los estimadores estadísticos (E7, E6) no tienen sesgo en el gemelo:** recuperan 0.67–0.77 para una verdad de 0.69, y la verdad cae en sus intervalos. Con datos reales dan 0.53–0.56. Su sesgo del domingo con datos reales no lo pone el método: viene de algo que el gemelo no tiene. Ya identificamos una parte: los días hábiles de fin de año (sin ellos, E7 sube a 0.63–0.65 y E6 a 0.74–0.75; [verificaciones_nivel1.md](verificaciones_nivel1.md)).
- **E5b recupera la verdad en el gemelo (0.66 y 0.73), pero da 0.48 con datos reales.** El método de E5b, con un transporte distinto al suyo y un fondo que se acumula, no explica ese sesgo. La causa está en algo real que el gemelo no simula: candidatos, el sesgo bajo de TEMPO sobre ciudades (13–23 % en la literatura), un fondo con ciclo semanal, fuentes no viales con ciclo semanal (la industria también baja en domingo, y el modelo carga todo a la emisión vial) o que el domingo real sí esté más bajo que el tráfico de Infovial 2017.
- **Un transporte equivocado sí sesga el domingo hacia abajo:** la pluma estacionaria, con datos generados por puffs, da 0.51–0.65. Es una razón para preferir transportes con memoria (puffs), como E2 y E5b.
- **Los intervalos de las inversiones son demasiado estrechos con fondo persistente:** con la propia física del generador, E2 deja la verdad fuera en dos de tres semillas (0.58–0.68). El bootstrap no ve la correlación de varios días del fondo. Los intervalos de E5b y E2 deben tomarse como optimistas; el placebo (que sí la ve) es la medida honesta de la incertidumbre.
- Siguientes pasos que este resultado ordena: un gemelo con TEMPO sesgado (−20 %) y otro con fuentes no viales con ciclo semanal, para ver cuál reproduce el 0.48 de E5b; y E5b sin TEMPO con datos reales.

## Reproducir

```bash
uv run nox-ml lockdown configs/experiments/normalized_ratio.yaml
uv run nox-ml twin configs/experiments/inversion_puff.yaml configs/experiments/normalized_ratio.yaml configs/experiments/rf_deweather.yaml configs/experiments/baseline.yaml configs/experiments/inversion_puff.yaml configs/experiments/pinn_puff.yaml
```
