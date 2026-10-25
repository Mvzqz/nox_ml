# Arranque para el avance 4

## Preparar la máquina (una vez)

1. Aceptar las invitaciones de GitHub y de DagsHub.
2. Clonar y preparar:
   ```sh
   git clone https://github.com/Mvzqz/nox_ml.git
   cd nox_ml
   bin/uptodate
   ```
3. Credenciales de DagsHub (token en DagsHub → Settings → Tokens), solo en tu máquina:
   ```sh
   uv run dvc remote modify origin --local auth basic
   uv run dvc remote modify origin --local user <tu-usuario-dagshub>
   uv run dvc remote modify origin --local password <tu-token>
   uv run dvc pull
   ```
4. Comprobar: `bin/check` pasa y `uv run nox-ml run configs/experiments/baseline.yaml` da LOO 13.6 / 11.6 / 11.7 y domingo 0.42 (~4 min).

Si usas sesiones en la nube de Claude Code: crea tu propio entorno con `DAGSHUB_USER`, `DAGSHUB_TOKEN`, `GIT_USER_NAME` y `GIT_USER_EMAIL` (tu nombre y correo de GitHub), y acceso de red a `dagshub.com`. `CLAUDE.md` ya tiene las reglas para la sesión.

## Qué leer

- `docs/models.md`: el contrato que debe cumplir tu modelo.
- `context/management/plan_avances.md`: qué modelos hay, quién hace cada uno y cómo se compara.
- `docs/experiments.md`: cómo correr un experimento.

## Reparto

| Rol | Modelos | Toca sobre todo |
|---|---|---|
| A: transporte | E1 baseline (ya existe, registrar), E2 inversión con puffs y química, E7 estimador normalizado | `inversion/`, `physics/` |
| B: estadística | E3 mínimos cuadrados regularizados, E4 inversión log-normal; referencias IDW y kriging | `models/`, `inversion/linear.py` |
| C: ML | E5 PINN (con pluma, con puffs, entrenamiento conjunto), E6 normalización meteorológica con bosque aleatorio | `models/pinn.py`, `models/` |

## Cómo se entrega un modelo

1. Rama `models/<nombre>` desde `main` (sin "claude" en el nombre).
2. El modelo cumple el contrato y queda registrado; agrega `configs/experiments/<nombre>.yaml`.
3. `bin/check` pasa (las pruebas de contrato corren solas).
4. Corre `uv run nox-ml run configs/experiments/<nombre>.yaml` en nov–dic 2023 y pega en la descripción del pull request la fila de `uv run nox-ml compare runs/*`.
5. **No uses feb–may 2024** para nada del avance 4: es el periodo de prueba del avance 5.
6. Commits a tu nombre, sin líneas de coautoría de IA; el pull request lo revisa y fusiona el dueño del repositorio.

## Lo que ya existe en `main`

- Contrato y registro: `nox_ml.models` (`Model`, `EmissionEstimate`, `REGISTRY`). Ejemplos registrados: `inversion_plume` (E1, baseline) y `pinn_plume` (E5a).
- Prueba de contrato parametrizada sobre `REGISTRY`: tu modelo se prueba solo al registrarlo (`ml/tests/models/test_contract.py`).
- `nox-ml run`, `nox-ml compare runs/*` (tabla con métricas de emisión, filtro de elegibilidad y tiempos) y `nox-ml tune <search.yaml>`.
- Caché de la tabla de transporte (`Inputs.jacobians`, clave por parámetros de transporte): el baseline corre en ~30 s. Un transporte nuevo (puffs, otra PINN) debe definir su propia clave (`transport_key`), como `pinn_plume`.

## Notas por rol

- **A:** E2 necesita su clave de caché para puffs (duración, vida química, σθ, viento mínimo); sin ella es lento. E7 envuelve `nox_ml.inversion.normalized`.
- **B:** registrar IDW y kriging como `role: reference` (sin métricas de emisión). Kriging hora por hora, solo espacial (un proceso gaussiano espacio-tiempo con ~7,500 filas es caro).
- **C:** E5a ya está. Faltan E5b (núcleo de la PINN aplicado a cada tramo de puff) y E5c (entrenamiento conjunto; validar con 4 grupos de estaciones en vez de 24 por costo). E6 con características justificadas (hora y día cíclicos, ventilación y su acumulado, dirección del viento con seno y coseno, tipo de día).
- **Todos:** `nox-ml tune` usa validación simple (no anidada): el error ajustado es algo optimista; se dice en el notebook. Ajuste en dos niveles: grilla chica para parámetros que cambian la tabla de transporte, búsqueda aleatoria amplia para los que no.

## Integración

Cada pull request trae su fila de `compare`. Quien coordina corre al final `nox-ml compare runs/*` con todos los modelos, ajusta los dos mejores con `nox-ml tune` y arma `deliverables/Avance4.39.ipynb`.
