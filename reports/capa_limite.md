# Capa límite ene–jun 2024: relleno con MERRA-2

Fecha: 2026-10-20. Script: `scripts/pbl_fill.py`. Datos: `data/raw/merra2/` (ver su MANIFEST). Salida: `data/interim/pbl_2023_2024.parquet`.

## Resumen

- Open-Meteo no tiene la capa límite (PBL) de ERA5 de enero a junio de 2024. La conseguimos de **MERRA-2 de NASA** (PBLH horaria, celda 19.5 N, 99.375 O) con la cuenta de Earthdata, sin autorizaciones adicionales. Solo se bajó un recorte de 3 × 3 celdas: 20 MB en total.
- En los mismos meses de 2023, MERRA-2 sigue a ERA5 razonablemente por la tarde: **r = 0.68**, con MERRA-2 **224 m más alta** en la mediana (unos 9 %).
- La serie nueva usa ERA5 donde existe y MERRA-2 corregida en el hueco. Ya no hay horas sin dato entre 2023-11 y 2024-06. Esto desbloquea el análisis real de primavera 2024 (contingencias, Semana Santa).
- Incertidumbre que queda en el hueco: un error típico de **12–14 %** (unos 340 m) en la PBL de la tarde frente a lo que habría dado ERA5.

## Comparación MERRA-2 contra ERA5

Tarde (12–17 h local), ene–jun 2023, misma celda aproximada (ERA5 de Open-Meteo en 19.5 N, 99.25 O):

| Hora local | ERA5 mediana (m) | MERRA-2 mediana (m) | Sesgo MERRA-2 − ERA5 (m) | r | Factor ERA5/MERRA-2 |
|---|---|---|---|---|---|
| 12 | 2,025 | 2,224 | +139 | 0.78 | 0.93 |
| 13 | 2,345 | 2,509 | +96 | 0.72 | 0.96 |
| 14 | 2,600 | 2,795 | +125 | 0.73 | 0.96 |
| 15 | 2,655 | 2,970 | +230 | 0.65 | 0.92 |
| 16 | 2,650 | 2,970 | +250 | 0.67 | 0.91 |
| 17 | 2,290 | 2,817 | +495 | 0.69 | 0.84 |

- En invierno (nov–dic 2023) la concordancia es peor: r = 0.56 y sesgo de +409 m por la tarde. MERRA-2 sobreestima más a las 17 h, cuando la capa empieza a colapsar.
- De noche las diferencias son grandes (MERRA-2 entre 2 y 9 veces más alta), pero el proyecto solo usa la tarde.

## Corrección aplicada

- Factor multiplicativo por hora local, igual a la mediana de ERA5/MERRA-2 en **ene–jun 2023** (los mismos meses del hueco): 0.84–0.96 por la tarde.
- **Validación fuera de muestra:** ajustamos el factor con ene–mar 2023 y lo aplicamos a abr–jun 2023. El error absoluto mediano de la tarde fue de 12 % sin corregir y de 14 % corregido. El factor no se transfiere bien entre meses, así que su efecto es pequeño y no mejora el error típico. Lo mantenemos porque quita el sesgo medio de los mismos meses del año, pero la incertidumbre real es de ~12–14 %.
- Comprobación: la PBL de la tarde rellenada para 2024 (medianas mensuales de 1,640 m en enero a 2,934 m en mayo) está en el mismo rango que ERA5 en 2023 (1,985–2,998 m).
- Frente al relleno anterior (climatología mes-hora en `feasibility_linear.py`), MERRA-2 sí sigue la variación de cada día (r ≈ 0.7). La climatología solo repetía el promedio y no servía para datos reales.

## Cómo usarlo

La serie cubre 2023-11-01 a 2024-06-30 en UTC horario (`pbl_m`, `fuente` = "ERA5" o "MERRA-2 corregido"). Para usarla, en `scripts/feasibility_linear.py` (función `load_inputs`) hay que sustituir la serie `pbl` que se construye desde el JSON de Open-Meteo, junto con su relleno por climatología, por:

```python
pbl = pd.read_parquet(INT / "pbl_2023_2024.parquet").pbl_m
```

y conservar la línea siguiente, que promedia a la hora y aplica el mínimo de 200 m. No hicimos el cambio porque otras tareas importan ese módulo mientras corren.

## Alternativa no usada

ERA5 completo desde Copernicus CDS daría la misma fuente que el resto de la serie, pero requiere una clave de CDS (`~/.cdsapirc`), que no existe en esta máquina. Si se consigue, conviene reemplazar el hueco con ERA5 y dejar MERRA-2 como respaldo.
