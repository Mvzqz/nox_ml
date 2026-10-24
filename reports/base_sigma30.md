# Nueva base: viento con incertidumbre de ±30° (σθ = 30°)

Periodo nov–dic 2023, dominio extendido, horas de 12 a 17 h. Fecha: oct 2026.

## Qué cambió

Cada hora el modelo usa un solo viento medido, y en la CDMX ese viento se equivoca de dirección por unos 28–32° (`viento.md`). Hasta ahora la pluma suponía un error de solo 15°. Ahora supone 30°: la pluma de cada fuente se abre más y el modelo deja de "apostar" a una dirección exacta.

- `scripts/feasibility_linear.py`: `SIGMA_THETA` vale 30° por defecto. La configuración anterior sigue disponible:
  - `SIGMA_THETA_LEGACY` (15°);
  - la variable de entorno `SIGMA_THETA_DEG=15`.
- `scripts/real_check_linear.py`:
  - nueva opción `--sigma-theta` (30 por defecto; `--sigma-theta 15` reproduce lo anterior);
  - los reportes nuevos llevan el sufijo `_sigma30`;
  - los reportes sin sufijo son de la configuración de 15°.
- `improve_real.py` e `improve_twin.py` ahora toman 15° de `SIGMA_THETA_LEGACY`, así que sus resultados no cambian.
- **Ojo:** los scripts de gemelos que usan el valor por defecto (`feasibility_linear.py`, `improvement_tests.py`, `dilution_test.py`, `val2020_*`) generarán su "verdad" con 30° si se vuelven a correr. Para reproducir los reportes anteriores, usa `SIGMA_THETA_DEG=15`.

## Antes y después

Siglas de la tabla:
- **LOO:** se deja fuera cada estación y se predice con las demás.
- **Híbrido:** el modelo más una corrección IDW de sus residuos.
- **Sesgo:** el error que se repite siempre en la misma estación.
- **Var. horaria:** el error que cambia hora a hora.

| Configuración | σθ | r estaciones (en muestra) | r TEMPO | RMSE LOO modelo / IDW / híbrido (ppb) | Sesgo / var. horaria del híbrido | Híbrido gana a IDW | Sábado / hábil | Domingo / hábil (IC 90 %) |
|---|---|---|---|---|---|---|---|---|
| Viento del dominio | 15° | 0.77 | 0.74 | 14.1 / 11.6 / 12.2 | 5.5 / 11.0 | 13 de 24 | 0.76 | 0.39 (0.31–0.50) |
| | **30°** | 0.78 | 0.75 | 14.1 / 11.6 / 12.4 | 5.3 / 11.2 | **15 de 24** | 0.75 | 0.35 (0.27–0.47) |
| Dominio, sin industria | 15° | 0.77 | 0.74 | 13.6 / 11.6 / 11.7 | 6.1 / 10.0 | 15 de 24 | 0.78 | 0.42 (0.35–0.54) |
| | **30°** | 0.78 | 0.75 | 13.4 / 11.6 / 11.5 | 5.9 / 9.9 | **16 de 24** | 0.78 | 0.41 (0.34–0.51) |
| **Dominio, sin industria + extras** (la mejor) | 15° | 0.77 | 0.74 | 13.6 / 11.5 / 11.4 | 5.8 / 9.8 | 16 de 24 | 0.79 | 0.43 (0.36–0.54) |
| | **30°** | 0.78 | 0.75 | 13.4 / 11.5 / **11.2** | 5.6 / 9.7 | **18 de 24** | 0.79 | 0.42 (0.34–0.53) |
| Campo de viento IDW | 15° | 0.76 | 0.73 | 14.0 / 11.6 / 12.0 | 5.9 / 10.4 | 13 de 24 | 0.83 | 0.31 (0.23–0.43) |
| | **30°** | 0.77 | 0.75 | 13.8 / 11.6 / 11.7 | 5.6 / 10.3 | **14 de 24** | 0.79 | 0.27 (0.17–0.40) |
| Campo IDW, sin industria + extras | 15° | 0.76 | 0.73 | 13.9 / 11.5 / 11.7 | 6.0 / 10.0 | 13 de 24 | 0.77 | 0.30 (0.23–0.41) |
| | **30°** | 0.76 | 0.75 | 13.7 / 11.5 / 11.4 | 5.7 / 9.9 | **14 de 24** | 0.74 | 0.30 (0.23–0.42) |
| Puff (no estacionario) | 15° | 0.75 | 0.83 | 15.1 / 11.6 / 14.6 | 6.5 / 13.0 | 11 de 24 | 0.76 | 0.47 (0.39–0.56) |
| | **30°** | 0.78 | 0.84 | 14.2 / 11.6 / 13.4 | 6.0 / 12.0 | **13 de 24** | 0.75 | 0.47 (0.39–0.56) |

La fila "sin industria + extras" con 30° reproduce exactamente el caso S2 de `mejoras.md` (híbrido 11.2 ppb, 18 de 24 estaciones), así que el cambio de valor por defecto quedó bien aplicado.

### Factor vial por región (α, viento del dominio, días hábiles)

| Región | SO | S | SE | O | Centro | E | NO | N | NE |
|---|---|---|---|---|---|---|---|---|---|
| 15° | 0.00 | 0.40 | 0.23 | 0.40 | 0.58 | 0.19 | 0.61 | 0.49 | 0.43 |
| 30° | 0.06 | 0.35 | 0.23 | 0.38 | 0.44 | 0.39 | 0.54 | 0.54 | 0.26 |

El total vial de días hábiles sube un 6 % (34,900 → 36,900 t/año equivalente), dentro del IC.

Con 30° el reparto entre regiones vecinas cambia hasta ±0.2:
- el Centro y el NE bajan;
- el E sube.

Un cambio así en el reparto fino es justo lo que esperamos si el viento no alcanza para separar regiones vecinas. Por eso solo damos los factores por región como indicativos.

### Fuentes puntuales (viento del dominio)

- **Valores negativos:** con 15°, cinco fuentes salían negativas (físicamente imposible). Con 30° queda solo una, el AIFA (−201 ± 41), que ya sabíamos inestable.
- **Grandes, sin cambios:**
  - la central Valle de México da 300 → 391 t/año (sigue muy por debajo de las 2,615 del inventario);
  - el AICM, 293 → 351.
- **Nonoalco:** sube de 90 a 359 t/año (a priori 277).
- **Clústeres industriales:** cambian mucho (por ejemplo, Naucalpan de −103 a 32 y Tlalnepantla, equipo de transporte, de 366 a 655). Confirma que no son identificables uno por uno y que hay que agruparlos por región.

## Conclusiones

1. **Adoptado: σθ = 30° como estándar.** Mejora todas las configuraciones sin costo:
   - el híbrido gana a IDW en 1–2 estaciones más;
   - el RMSE del híbrido baja hasta 0.3 ppb (1.2 en puff);
   - casi no quedan emisiones negativas.

   No empeora nada medible, salvo el caso del viento del dominio con industria (híbrido 12.2 → 12.4 ppb, aunque gana en más estaciones).
2. **La mejora en datos reales es modesta.** El modelo solo sigue sin superar a la interpolación IDW por estación: sigue faltando un mejor viento. El gemelo de `mejoras.md` sí mostraba una mejora grande en fuentes grandes (por ejemplo, el error de Acolman bajó de 33 % a 13 %).
3. **El sesgo de los domingos no se corrige con esto.** Domingo/hábil queda en 0.27–0.47, contra 0.6–0.9 en Infovial. Hay que atacarlo por separado (fondo y emisión por tipo de día).
4. **Configuración de referencia** para los siguientes análisis: viento del dominio, σθ = 30°, sin clústeres industriales sueltos y con extras (estaciones NO₂ y trazadores).
   - RMSE LOO del híbrido: 11.2 ppb, contra 11.5 de IDW.
   - Gana en 18 de 24 estaciones.
   - Domingo/hábil: 0.42 (0.34–0.53).

Reportes completos: `real_check_linear_*_sigma30_2023-11-01_2023-12-31.md`.
