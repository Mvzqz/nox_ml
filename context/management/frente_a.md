# Frente A: transporte

Antes de empezar: [arranque](arranque.md) (preparar la máquina, credenciales, comprobar el baseline). Contrato de modelos: [`docs/models.md`](../../docs/models.md). Plan general: [plan_avances.md](plan_avances.md).

## Objetivo

Que el modelo físico principal deje de ser una pluma fija y pase a seguir la contaminación hora por hora (puffs) con una química que cambia por temporada. En la investigación esto fue lo que más mejoró los resultados: correlación con el satélite de 0.50 a 0.65, emisión vial más cercana al inventario y placebo más estrecho. Es el candidato más probable a modelo final.

## Tareas

| # | Modelo | Qué es | Estado |
|---|---|---|---|
| E1 | `inversion_plume` | Baseline: inversión bayesiana con pluma estacionaria | Hecho y registrado |
| E2 | `inversion_puff` | La misma inversión, pero con la tabla de transporte de puffs (24 h) y la vida química del NOₓ calculada con OH | **Por hacer** |
| E7 | `normalized_ratio` | Estimador normalizado: observado ÷ esperado con emisión fija. Da cambios relativos (domingo/hábil), no toneladas | **Por hacer** (envolver lo existente) |

## Código relevante

- `ml/src/nox_ml/models/inversion_plume.py`: **el ejemplo a copiar.** `InversionPlume` implementa el contrato; E2 debería heredar de ella y cambiar solo `transport()` y `transport_key()`, igual que hace `models/pinn/model.py` (`PinnPlume`).
- `ml/src/nox_ml/inversion/jacobian.py`:
  - `jacobian_hour_puff`: la tabla de transporte con puffs, ya migrada y verificada contra la investigación (diferencia máxima 3e-15).
  - `standard_transport`: la configuración estándar (puffs de 24 h y pérdida por OH).
- `ml/src/nox_ml/physics/puff.py`: trayectorias, supervivencia (`fixed_lifetime`, `variable_lifetime`, `cumulative_loss`) y perfil horario del tráfico.
- `ml/src/nox_ml/physics/chemistry.py`: `nox_loss_rate`, `lifetime_h` (OH a partir del sol, ozono, temperatura y humedad).
- `ml/src/nox_ml/inversion/normalized.py`: `index`, `ratio`, `bootstrap_ratio`, `interval`, para E7.
- `ml/src/nox_ml/data/inputs.py`: `Inputs` (el `Dataset` del contrato; incluye `chemistry` y `loss_rate`) y la caché `Inputs.jacobians(...)`.

## Cuándo está listo

1. E2 y E7 registrados en `REGISTRY`, con `configs/experiments/inversion_puff.yaml` y `normalized_ratio.yaml`.
2. `bin/check` pasa; la prueba de contrato (`ml/tests/models/test_contract.py`) los incluye sola.
3. `nox-ml run` de cada uno en nov–dic 2023, y su fila de `nox-ml compare runs/*` pegada en el pull request.
4. Referencia esperada para E2 (investigación, configuración parecida): error en estación oculta ~12–13 ppb, híbrido ≤ 11.6, correlación con TEMPO ~0.8, domingo ~0.5–0.65. Si sale muy distinto, revisar antes de abrir el pull request.

## Cómo funcionan las pruebas relevantes

- **Prueba de contrato** (`ml/tests/models/test_contract.py`, datos sintéticos en `ml/tests/models/synthetic.py`): para cada modelo del registro revisa columnas, que la misma semilla dé lo mismo, que cambiar los datos de la estación excluida no cambie el modelo (fuga de información), que los parámetros se guarden y lean en YAML, que se recupere la emisión sintética y que el placebo quede centrado en 1. No hay que escribirla: basta con registrar el modelo.
- **Pruebas de física** (`ml/tests/physics/test_puff.py`, `test_chemistry.py`): propiedades que ya pasan. Si tocas `physics/`, deben seguir pasando.
- **Prueba de la tabla de puffs** (`ml/tests/inversion/test_jacobian.py`): compara con la investigación a 1e-9. No debe cambiar.
- **Caché** (`ml/tests/inversion/test_jacobian_cache.py`): el modelo con caché debe dar exactamente lo mismo que sin ella. Agrega una prueba igual para E2.

## Trampas y riesgos

- **Química: ya está en `Inputs`, solo falta usarla.** `load_inputs` llena `Inputs.chemistry` (O₃, TMP y RH horarios, promedio de las estaciones del dominio, de `nox_ml.data.simat.load_chemistry`) e `Inputs.loss_rate` (pérdida de NOₓ en 1/s, de `physics.chemistry.nox_loss_rate`) para el periodo del experimento más el día anterior (historia de los puffs de 24 h); fuera de `load_inputs` valen `None` (los datos sintéticos no cambian). **No hay que descargar ni leer nada más.** E2 solo debe pasar `inputs.loss_rate` a `standard_transport(wind, loss_rate, road_profile)`; la referencia de OH usa abril de 2023 (no abril de 2024, que cae en el periodo de prueba; la diferencia es ~7 % en la escala de la pérdida). Referencia de la investigación: `scripts/vida_quimica.py` en la rama `research-archive`.
- **Reutilizar `HistoryTransport` (llega con el pull request #19, E5b).** Los puffs necesitan el viento de las horas anteriores, que una función de transporte normal no recibe. E5b ya resolvió eso para todos: `HistoryTransport` y `History` en `inversion/linear.py` (`hour_jacobians` llama a `for_hours` si el transporte lo tiene), y `Inputs.wind` (viento horario del periodo) e `Inputs.infovial` llenados por `load_inputs`. **E2 debe usar ese mecanismo, no crear otro**; ver `models/pinn/puff.py` (`PinnPuffTransport`) como ejemplo y el ADR 0005. Si tu rama empezó antes de que se fusionara #19, actualízala sobre `main` antes de tocar `linear.py` o `inputs.py`. E5b ya puede usar la pérdida por OH de `Inputs.loss_rate` con el parámetro `lifetime: oh` (por defecto `fixed`: vida fija `tau_h`).
- **Caché obligatoria.** E2 debe definir su propia `transport_key()` (duración del puff, vida química, σθ, viento mínimo). Sin ella cada reajuste recalcula la tabla: horas en lugar de minutos.
- **Cómputo.** Construir la tabla de puffs para 366 horas tarda ~5–10 min. El ajuste fino de E2 debe hacerse en dos niveles: grilla chica (2–3 valores) para lo que cambia la tabla, búsqueda amplia para lo que no.
- **E7 es relativo.** Su `EmissionEstimate` es de tipo `relative` (índice por tipo de día). No tiene totales; no intentes inventarlos.
- **No usar feb–may 2024** para nada: es el periodo de prueba del avance 5.
- **Horas.** Las etiquetas de SIMAT marcan el fin de la hora (`h = utc − 1 h`) y la hora local es UTC−6 sin horario de verano. Usa `nox_ml.time`; no lo reimplementes.
- **Conflictos.** `models/__init__.py` (registro) lo tocan los tres frentes: conflictos triviales, resolver conservando todas las entradas.

## Tiempo estimado

Trabajo con agentes: E2 ~1.5–2 h (incluida la química), E7 ~30–45 min. Cómputo: minutos por corrida con la caché.
