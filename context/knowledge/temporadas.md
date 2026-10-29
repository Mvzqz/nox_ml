# Temporadas 2024–2026

Fecha: 2026-10-29. Los seis modelos congelados (`configs/experiments/`) corridos sin cambios en cuatro temporadas que no se usaron para elegir nada: nov–dic 2024 (SIMAT), feb–may 2025, nov–dic 2025 y feb–may 2026 (OpenAQ con el viento, la temperatura y la humedad de los aeropuertos). Todas dejan fuera los periodos atípicos (fin de año y Semana Santa, `data.calendar`). Configuraciones: `configs/seasons/<modelo>.<nd2024|fm2025|nd2025|fm2026>.yaml` (`stations: openaq`, `exclude_atypical: true`).

## Domingo ÷ día hábil

| Modelo | nov–dic 2024 | feb–may 2025 | nov–dic 2025 | feb–may 2026 |
|---|---|---|---|---|
| E7 normalizado | 0.57 | 0.64 | 0.57 | 0.47 |
| E6 bosque | 0.67 | 0.59 | 0.56 | 0.56 |
| X4 boosting | 0.57 | 0.57 | 0.57 | 0.58 |
| E2 inversión | 0.61 | 0.57 | 0.47 | 0.56 |
| E5b PINN | 0.50 | 0.49 | 0.36 | 0.49 |

Los placebos de todas las corridas quedan entre 0.91 y 1.11 (elegibles). Tráfico de referencia: 0.76–0.81 (Infovial nov–dic 2018, ponderado por emisión, [sesgo_domingo.md](sesgo_domingo.md)).

- **X4 es el más estable** (0.57–0.58) y es el estimador del ciclo semanal en las fichas (`products.ESTIMATORS`).
- **E7 varía más entre temporadas** (0.47–0.64). Su precisión para un cambio sostenido se mide con el placebo de cada temporada, que es lo que usan las fichas.
- **Las inversiones exageran el domingo** en algunas temporadas (E5b 0.36 en nov–dic 2025): es el sesgo ya conocido.
- **El sábado** no se estima en invierno con una temporada: en nov–dic 2025 sale ≈ 1.0 en todos los modelos, porque ya viene así en las estaciones (6 sábados, cada uno entre 0.76 y 1.34 del día hábil; el más alto, el del Buen Fin).

## Concentración donde no hay estación (error con estación oculta, ppb)

| | nov–dic 2024 | feb–may 2025 | nov–dic 2025 | feb–may 2026 |
|---|---|---|---|---|
| Regresión-kriging | 10.8 | 6.1 | 9.0 | 6.2 |
| E5b | 11.4 | 6.8 | 10.1 | 7.1 |
| IDW | 11.9 | 6.4 | 9.7 | 7.1 |

La regresión-kriging le gana a IDW en las cuatro.

## Variación de un día a otro y mínimo detectable (E7)

| Temporada | Variación (cv) | Mínimo detectable con 9 días |
|---|---|---|
| nov–dic 2023 | 0.44 | 40 % |
| feb–may 2024 | 0.29 | 29 % |
| nov–dic 2024 | 0.28 | 28 % |
| feb–may 2025 | 0.36 | 34 % |
| nov–dic 2025 | 0.41 | 38 % |
| feb–may 2026 | 0.27 | 27 % |

Combinando las seis temporadas, cada una contra sus propios días normales (`ficha-medida` con `--data` repetido): 14 % con 9 días por temporada, 10 % con 20 y 6 % con 60 (80 % de potencia; extrapolación con la regla de los placebos cortos). Solo aplica a medidas presentes en varias temporadas.

## Datos y arreglos

- **OpenAQ frente a SIMAT (nov–dic 2024):** hasta el 16 de noviembre, OpenAQ trae cada hora con una hora de retraso, lo que sube ~6 % el promedio de la tarde. Desde el 17 de noviembre, 99 % de las horas de la tarde son iguales a las de SIMAT y el promedio difiere menos de 1 %. Las temporadas de 2025 y 2026 tienen el pico de la mañana a las 8 h, como SIMAT: no hay retraso que corregir.
- **Viento de los aeropuertos:** en algunas horas los dos aeropuertos soplan exactamente en sentidos opuestos (MMMX desde 170°, Santa Lucía desde 350°, misma velocidad). El promedio no tiene dirección y la pluma de la termoeléctrica alcanzaba todas las estaciones (~66,000 ppb modelados): E7 y E2 se dispararon en feb–may 2025 y el placebo los marcó como no elegibles. Esas horas se descartan (`inputs.airport_wind`).
- **Química de los aeropuertos:** la referencia de abril de SIMAT y la serie de los aeropuertos 2024–2026 duplicaban las horas de 2024; manda SIMAT.
- **TEMPO frente a las estaciones (NO₂, pares hora–estación):** r = 0.61 en feb–may 2025, 0.79 en nov–dic 2025 y 0.60 en feb–may 2026.

## Reproducir

```bash
uv run nox-ml run configs/seasons/gb_deweather.fm2026.yaml
uv run nox-ml ficha-dias --data 2026-02-15:2026-05-31
```
