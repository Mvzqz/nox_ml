# Actualización automática de la temporada en curso

Fecha: 2026-11-05. Un solo comando, `nox-ml update`, mantiene al día los insumos de la temporada en curso y las salidas de monitoreo, para que una interfaz futura muestre resultados frescos. Código: `ml/src/nox_ml/monitor.py` (orquestación) y `nox-ml fetch-tempo` (`data/tempo.py`).

## Qué corre

En orden, para la ventana de la temporada hasta `--through`:

| Paso | Qué hace | Escribe |
|---|---|---|
| `openaq` | Estaciones (NOx, NO, NO2, O3 por hora) desde 7 días antes de la última hora del sensor vivo más atrasado (ver «Retrasos») | `raw/openaq/openaq_<ini>_<fin+1>.parquet`, `interim/openaq_nox_<ini>_<fin+1>.parquet` |
| `weather` | METAR de MMMX y MMSM y ERA5 (Open-Meteo) de toda la ventana, fusionados en los archivos 2024-2026 | `raw/metar/*_2024-2026.csv`, `raw/era5_openmeteo/pbl_wind_center_2024-2026.json` |
| `tempo` | Descarga y recorta los gránulos TEMPO (18–23 UTC) que faltan (`nox-ml fetch-tempo`) | `raw/tempo/*_zmvm.nc`, `raw/tempo/manifest.csv` |
| `qc_tempo` | Píxeles de la ventana contra la tabla de estaciones | `interim/tempo_pixels_<ini>_<fin>.parquet` |
| `flux_divergence` | Emisión diaria de la ciudad desde el satélite y su placebo | `runs/flux_divergence/<ini>_<fin>.{json,csv}` |
| `weekly_index` | Índice semanal de E7 (ver abajo) | `runs/monitor/weekly_index_<ini>_<fin>.csv` |

Si un paso falla, se omiten solo los que dependen de él (`qc_tempo` necesita `openaq` y `tempo`; `flux_divergence`, además `weather`; `weekly_index`, `openaq` y `weather`) y el comando termina con código 1. Cada paso es idempotente: repetir el comando no duplica ni pierde datos. Sin mediciones nuevas, `openaq` termina bien («0 new hours»). Solo si además la temporada aún no tiene tabla de estaciones, `openaq` queda «bloqueado»: avisa y los pasos que la necesitan (`qc_tempo`, `flux_divergence`, `weekly_index`) se omiten con un detalle claro, sin que cuente como falla.

Al final se escribe `runs/monitor/status.json`: ventana, `through`, último día con estaciones y con TEMPO, resultado y duración de cada paso, archivos escritos y hora (UTC).

### Estado honesto (`status.json`)

- Cada paso lleva `level`: `ok`, `warn` (funcionó, pero con avisos), `skipped` (espera a un paso sin datos todavía) o `failed`. `ok` (booleano, por paso y global) es falso **solo** si algo falló; los avisos no lo cambian ni cambian el código de salida.
- `warnings`: lista de `{season, step, message}` con las verificaciones de `qc_tempo` que fallan, los gránulos TEMPO que fallaron o que estaban en el manifiesto sin su archivo (se bajan de nuevo), los sensores de OpenAQ omitidos y la falta de tabla de estaciones.
- `stale_days`: por fuente (`stations`, `tempo`), días entre `through` y el último día con datos. Una interfaz debe mostrar esto, no `through`.
- `closing`: el estado de la temporada anterior que se está cerrando (mismos campos).

### Candado y escrituras

`update` toma un candado `runs/monitor/update.lock` (`fcntl.flock`, sin esperar): una segunda corrida termina con código 3 y un mensaje, sin hacer nada; el sistema lo libera si el proceso muere. Todo archivo que crece en el lugar (OpenAQ, METAR, ERA5, píxeles, salidas y `status.json`) se escribe a un temporal en la misma carpeta y se mueve con `os.replace` (`nox_ml/atomic.py`), así que una falla a medias deja intacto el archivo anterior. Los METAR se escriben con `float_format="%.2f"`, el formato que ya tienen los archivos de 2024-2026 (verificado). TEMPO limpia al inicio los `tmp*` y `.part` de más de una hora que dejó una corrida interrumpida.

### Índice semanal

`products.weekly_index`: para cada semana (lunes a domingo) con días hábiles con datos, el cambio de emisión (cociente − 1) de E7 (`products.estimator("change")`) de esos días frente a los demás días hábiles normales de la temporada (sin contingencias ni periodos atípicos). No incluye rango ni veredicto: el rango de una ficha sale del placebo (`measure_result`, cientos de reajustes) y aquí solo se quiere la tendencia. Las primeras semanas de una temporada tienen pocos días de referencia y el índice es ruidoso (la variación día a día de E7 es de 0.3–0.4 y la deriva lenta, 0.15; [deriva.md](deriva.md)): hay que leerlo con el rango de la ficha, no solo el punto. No hay índice diario: E7 estima por tipo de día, no por día.

## Convención de nombres

Todo archivo lleva el nombre de la ventana **completa** de la temporada (nov–dic: `11-01..12-31`; feb–may: `02-15..05-31`; lluvias: `06-01..10-31`), aunque los datos lleguen a mitad de temporada. Es el nombre que leen `inputs.openaq_sources` y `products.sources_for`, así que las fichas y los análisis funcionan sin cambios sobre una temporada a medias. Los archivos crecen en el mismo lugar: OpenAQ fusiona las horas nuevas (y vuelve a bajar desde 7 días antes de la última hora del sensor vivo más atrasado, porque el servicio revisa valores y hay sensores que van detrás de los demás; un sensor sin datos hace más de 21 días no cuenta; un valor faltante nuevo nunca sustituye a uno guardado), el clima se baja de nuevo completo (la capa límite de ERA5 llega días después del viento y la fusión solo llena huecos) y TEMPO agrega los gránulos que el manifiesto no tiene. Los productos derivados (píxeles, flujo, índice) se recalculan. Una temporada cerrada queda con los mismos archivos que las bajadas manuales.

Enero y la primera mitad de febrero no pertenecen a ninguna temporada: `update` no hace nada. Con `--season INI:FIN` se fija otra ventana (años posteriores a 2024); entonces no se cierra la anterior.

## Retrasos

- `--through` por defecto: hoy − 3 días (`monitor.PUBLICATION_LAG_DAYS`, opción `--lag`). OpenAQ (SINAICA) y TEMPO publican con unos días de retraso; un día reciente puede estar incompleto y se completa en la corrida siguiente (OpenAQ: la ventana de re-descarga de 7 días; TEMPO: el listado de CMR se consulta completo cada vez y baja lo que falta).
- ERA5 de Open-Meteo llega con ~5 días de retraso: la capa límite de los últimos días puede quedar vacía hasta la corrida siguiente.
- Cambio de temporada: el `through` (hoy − 3) aún cae en la temporada anterior los primeros días de la nueva. Además OpenAQ va ~13 días atrás, así que la temporada que termina no recibe sus últimos días hasta después de su fin. Por eso, durante `monitor.CLOSING_DAYS` = 21 días después del fin de una temporada, `update` corre también la anterior con `through` = su fin (`status.json`, `closing`), y entre temporadas (enero–mitad de febrero) corre solo esa. Pasados los 21 días queda como está. Ejemplo: el 2026-11-05 la temporada de lluvias (fin 2026-10-31) se sigue actualizando hasta el 2026-11-21, y la de nov–dic arranca aunque OpenAQ aún no tenga datos de noviembre (`openaq` bloqueado, avisa).

## Cómo programarla

Una corrida diaria basta. No está instalada; ejemplo de temporizador de systemd de usuario (`~/.config/systemd/user/`):

```ini
# nox-ml-update.service
[Unit]
Description=Actualizar la temporada en curso de nox-ml

[Service]
Type=oneshot
WorkingDirectory=%h/code/nox_ml
EnvironmentFile=%h/.config/nox-ml.env        # OPENAQ_API_KEY=... (permisos 600)
ExecStart=/usr/bin/flock -n /tmp/nox-ml-update.lock %h/.local/bin/uv run --project ml nox-ml update
```

```ini
# nox-ml-update.timer
[Unit]
Description=Actualización diaria de nox-ml

[Timer]
OnCalendar=*-*-* 07:30:00
Persistent=true

[Install]
WantedBy=timers.target
```

`systemctl --user enable --now nox-ml-update.timer`. Con cron: `30 7 * * * cd ~/code/nox_ml && flock -n /tmp/nox-ml-update.lock uv run --project ml nox-ml update >> runs/monitor/update.log 2>&1` (con `OPENAQ_API_KEY` definida en el crontab o en un archivo que se cargue antes). Las credenciales de Earthdata van en `~/.netrc`. `flock` evita dos corridas a la vez (cada una puede ocupar varios GB); `update` ya trae su propio candado, el externo es opcional.

## Fallas conocidas

- **Sin `OPENAQ_API_KEY`**: falla `openaq` y se omiten `qc_tempo`, `flux_divergence` y `weekly_index`; el resto corre.
- **Sin credenciales de Earthdata o sin curl**: cada gránulo falla (`status: error: ...` en `manifest.csv`) y `tempo` falla; el siguiente intento reintenta solo los que fallaron.
- **Límite de CMR**: una consulta con 2000 gránulos o más se corta; por eso se consulta mes por mes (~600 gránulos al mes) y, si aun así se llega al límite, el paso falla con un mensaje en lugar de bajar una lista incompleta.
- **Servicios caídos o con límite de peticiones** (OpenAQ: 60 por minuto; IEM y Open-Meteo responden 429 si se les pide mucho seguido): se reintenta con espera y, si sigue fallando, el paso falla y se recupera en la corrida siguiente. La descarga de OpenAQ parte de 7 días antes de la última hora del sensor vivo más atrasado, así que una falla de varios días deja huecos que la corrida siguiente llena.
- **OpenAQ llega más tarde que 3 días**: el 2026-11-05 la última hora con datos de las estaciones era el 2026-10-22 (13 días de retraso; la tabla de la temporada de lluvias descargada antes termina igual). `status.json` lo muestra en `last_day_stations` y `stale_days.stations`; el índice y el flujo solo cubren hasta ahí. Una interfaz debe mostrar ese campo, no `through`.
- **Sin datos aún** (principio de temporada): `qc_tempo` falla con «No TEMPO granules» y `flux_divergence`/`weekly_index` pueden fallar con muy pocos días; se recuperan solos al juntarse datos.
- **Gránulo sin píxeles en el dominio**: queda en el manifiesto con `no pixels` y no se vuelve a bajar.
- **Memoria**: cada gránulo original (~150 MB) se baja a un temporal y se borra; con `--workers 2` por defecto. Dos `update` a la vez no se pueden (candado, código 3).
- **Gránulo con una falla inesperada**: se anota `error: <Tipo>: <mensaje>` en el manifiesto y no aborta el paso; se reintenta en la siguiente corrida. `curl` solo habla https (también en las redirecciones), con TLS verificado y su mensaje de error en el manifiesto.
- **Archivos compartidos**: `update` modifica en el lugar los METAR y ERA5 de 2024-2026 y los archivos de la temporada; con DVC, hay que registrar los cambios (`dvc add`) cuando se quieran versionar.
