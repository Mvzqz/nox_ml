# Data

Everything here is versioned with DVC (remote on DagsHub), never with git. Each of `raw/`, `interim/` and `processed/` is one DVC output (`raw.dvc`, `interim.dvc`, `processed.dvc`). Added as it is migrated from the research folder: `uv run dvc add data/<folder>`.

Study domains: Mexico City (CDMX, main case), Los Angeles (control, with TEMPO) and Bogotá (no satellite). Main analysis periods: Nov–Dec 2023 (fit) and Feb–May 2024 (test, reserved for the final model).

## How to access

**From the project (recommended).** With access to the private DagsHub repository (see [`docs/installation.md`](../docs/installation.md)):

```sh
uv run dvc remote modify origin --local auth basic
uv run dvc remote modify origin --local user <dagshub-user>
uv run dvc remote modify origin --local password <dagshub-token>
uv run dvc pull            # all of data/ (about 1.5 GB)
uv run dvc pull data/raw   # only the raw sources
```

**From the original source.** Every source below lists its origin URL. Only NASA TEMPO and MERRA-2 need credentials: a free [NASA Earthdata](https://urs.earthdata.nasa.gov) account, with its login in `~/.netrc` (machine `urs.earthdata.nasa.gov`). The rest is public. Each download is dated in the `MANIFEST.md` files (`data/raw/MANIFEST.md` and the ones inside `bogota/`, `cenace/`, `edgar/`, `igra/`, `la/`, `merra2/`). Raw data is immutable: derived files go to `interim/` or `processed/`.

## Raw data (`data/raw/`)

Sizes are on disk. License notes marked "to verify" were not recorded when the data was downloaded.

### Air quality and meteorology (stations)

| Folder | What it is | Origin | Period | Format | License / attribution | Size |
|---|---|---|---|---|---|---|
| `simat/` | Hourly pollutants (NO, NO₂, NOₓ, CO, O₃…) and meteorology of the CDMX air-quality network (SIMAT), plus station, parameter and unit catalogs | [datosabiertos.aire.cdmx.gob.mx](http://datosabiertos.aire.cdmx.gob.mx:8080/opendata/) (`anuales_horarios_gz/`, `catalogos/`) | 2019, 2020, 2023, 2024 | `*.csv.gz` (actually ZIP), catalogs in latin-1 CSV | CDMX open data, SEDEMA. Cite the source (license to verify) | 48 MB |
| `metar/` | Hourly airport wind (speed in knots, direction) at MMMX (AICM) and MMSM (AIFA) | [IEM ASOS](https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py) (Iowa State University) | 2019–2020 (MMMX), 2023–2024 (both) | CSV | Public data, cite IEM | 1.6 MB |
| `era5_openmeteo/` | ERA5 boundary-layer height and wind for the CDMX cell (19.5 °N, 99.25 °W) | [Open-Meteo archive API](https://archive-api.open-meteo.com/v1/archive) (`models=era5`) | 2019–2020, 2023–2024 | JSON | ERA5 © Copernicus; Open-Meteo CC BY 4.0 | 1.4 MB |
| `merra2/` | MERRA-2 boundary-layer height (PBLH), 3 × 3 cells around CDMX; 547 daily files | NASA GES DISC, collection M2T1NXFLX v5.12.4 (OPeNDAP, Earthdata login) | 2023-01-01 to 2024-06-30 | NetCDF4 (`*_cdmx.nc4`) | NASA open data, cite GMAO/GES DISC | 20 MB |
| `igra/` | Radiosondes of station 76679 (Mexico City airport) | [NOAA NCEI IGRA v2](https://www.ncei.noaa.gov/data/integrated-global-radiosonde-archive/access/data-por/MXM00076679-data.txt.zip) | Full record (to 2024) | ZIP of fixed-width text ([format](https://www.ncei.noaa.gov/data/integrated-global-radiosonde-archive/doc/igra2-data-format.txt)) | Public data (NOAA), cite IGRA v2 | 36 MB |
| `contingencias/` | Dates of the 2024 ozone contingencies | Press reports (El Universal, N+, ADN40, Por Esto); pending check against CAMe bulletins | 2024 | CSV (`fecha`, `fuente`) | Compiled by the team, not an official source | 8 KB |

### Satellite

| Folder | What it is | Origin | Period | Format | License / attribution | Size |
|---|---|---|---|---|---|---|
| `tempo/` | NASA TEMPO tropospheric NO₂ (level 2, V04) clipped to the CDMX domain; 1,068 granules plus `manifest.csv` (granule, time, URL, status) | NASA ASDC, `TEMPO_NO2_L2_V04` ([data.asdc.earthdata.nasa.gov](https://data.asdc.earthdata.nasa.gov)); needs Earthdata login to re-download | Nov 2023 – May 2024, afternoon scans | NetCDF (`*_zmvm.nc`), ~120 KB each after clipping (originals ~150 MB) | NASA open data, cite the TEMPO team | 126 MB |

### Emissions inventories and sources

| Folder | What it is | Origin | Period | Format | License / attribution | Size |
|---|---|---|---|---|---|---|
| `inventario/` | Official emissions inventory of the Mexico City metropolitan zone (ZMVM), Table 7 | [SEDEMA](https://www.sedema.cdmx.gob.mx/storage/app/media/DGCA/InventarioDeEmisionesZMVM2018.pdf) | 2018 | PDF | Public government report, cite SEDEMA | 51 MB |
| `edgar/` | EDGAR v8.1 NOₓ emissions by sector on a 0.1° grid, global originals and clips for CDMX, LA and Bogotá | [JRC EDGAR](https://edgar.jrc.ec.europa.eu/dataset_ap81), FTP `v81_FT2022_AP_new/NOx/` | 2018, 2022 | ZIP and NetCDF | CC BY 4.0, © European Union 1995–2026; [how to cite](https://edgar.jrc.ec.europa.eu/dataset_ap81#howtocite) | 98 MB |
| `cenace/` | Power-plant emissions by facility (Climate TRACE v5.10 for Mexico) and the Valley of Mexico extract. CENACE does not publish per-plant generation, hence no CENACE data | [Climate TRACE](https://downloads.climatetrace.org/latest/country_packages/nox/MEX.zip) | 2021–2026 (monthly) | ZIP and CSV | CC BY 4.0, cite Climate TRACE | 100 MB |
| `powerplants/` | Global Power Plant Database v1.3 (location, fuel and capacity of plants) | [WRI](https://wri-dataportal-prod.s3.amazonaws.com/manual/global_power_plant_database_v_1_3.zip) | Release 2021-06 | CSV, ZIP, PDFs | CC BY 4.0, © World Resources Institute and data contributors | 19 MB |
| `denue/` | Establishments directory (industry, commerce, services) for CDMX (09) and Estado de México (15) | [INEGI DENUE](https://www.inegi.org.mx/contenidos/masiva/denue/) | Cut of 2026-05 | ZIP of CSV | INEGI terms of free use, cite INEGI | 121 MB |

### Traffic and mobility

| Folder | What it is | Origin | Period | Format | License / attribution | Size |
|---|---|---|---|---|---|---|
| `trafico/` | Infovial vehicle counts by road, direction, hour and vehicle type (full file and a sample) | CDMX open data (Infovial). URL not recorded in the manifest | Jan 2017 (counts used as a weekly traffic profile, 2016–2019 available in the source) | CSV | CDMX open data (license to verify) | 132 MB |
| `movilidad_2020/` | Google and Apple mobility reports (driving, transit, walking relative to baseline) | Google COVID-19 Community Mobility Reports; Apple Mobility Trends Reports | 2020 (per file names) | CSV | Subject to Google and Apple terms (to verify before redistributing) | 65 MB |

### Geography

| Folder | What it is | Origin | Period | Format | License / attribution | Size |
|---|---|---|---|---|---|---|
| `inegi/` | CDMX and Estado de México state boundaries | [PhantomInsights/mexico-geojson](https://github.com/PhantomInsights/mexico-geojson) (2022 state boundaries) | 2022 | GeoJSON | INEGI terms of free use | 8.3 MB |
| `osm/` | Roads (motorway to tertiary, with links) and aerodromes in the CDMX domain | OpenStreetMap via the Overpass API | Snapshot 2026-10-19 | JSON | © OpenStreetMap contributors, ODbL | 29 MB |
| `osm_v1/` | Earlier snapshot of the same query, kept for comparison | OpenStreetMap via the Overpass API | Snapshot 2026-10-19 | JSON | © OpenStreetMap contributors, ODbL | 26 MB |

### Los Angeles (control case)

`la/` (296 MB) documents itself in `la/MANIFEST.md`; domain 33.80–34.30 °N, 118.55–117.95 °W, Nov–Dec 2023.

| Contents | Origin | License / attribution |
|---|---|---|
| `hourly_42602_2023.zip`, `hourly_NONOxNOy_2023.zip`, `hourly_WIND_2023.zip`: hourly NO₂, NO/NOₓ/NOy and wind from monitoring sites | [EPA AQS Air Data](https://aqs.epa.gov/aqsweb/airdata/) | US government data, public domain; cite EPA AQS |
| `ca_asos.geojson`, `asos_2023-11-12.csv`: California ASOS stations and airport wind | [IEM](https://mesonet.agron.iastate.edu/) | Public data, cite IEM |
| `roads_bbox.json`, `aerodromes_bbox.json`, `industrial_bbox.json` | OpenStreetMap via Overpass | © OpenStreetMap contributors, ODbL |
| `era5_pbl_2023.json`: boundary layer at 34.05 °N, 118.25 °W | Open-Meteo archive (ERA5) | ERA5 © Copernicus; Open-Meteo CC BY 4.0 |
| `tempo/`: 309 TEMPO NO₂ granules clipped to LA (the `_zmvm` suffix comes from a reused script) | NASA ASDC (Earthdata login) | NASA open data |
| `hrrr_field/`: HRRR 10 m wind, mixed-layer wind and boundary-layer height on a 3 km grid ([manifest](raw/la/hrrr_field/MANIFEST.md)) | NOAA HRRR, [AWS Open Data](https://registry.opendata.aws/noaa-hrrr-pds) | Public data (NOAA) |
| `limites/`: California places 2023, 1:500k | [US Census Cartographic Boundary Files](https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_06_place_500k.zip) | US government data, public domain |

### Bogotá (no-satellite case)

`bogota/` (44 MB), see `bogota/MANIFEST.md`. Bogotá (4.6 °N) is outside TEMPO's field of view.

| Contents | Origin | Period | License / attribution |
|---|---|---|---|
| `rmcab_estaciones.json`: 20 stations of the RMCAB with monitors and coordinates | [RMCAB, Secretaría Distrital de Ambiente](https://rmcab.ambientebogota.gov.co/Report/stationreport) | Catalog | Public data, cite RMCAB (license to verify) |
| `rmcab_{id}_2023-11_2023-12.json`: hourly NO, NO₂, NOₓ, wind and CO at 17 stations | RMCAB public report endpoint (`GetMultiStationsReportNewAsync`) | 2023-11-01 to 2023-12-31 | Same |
| `dsc/`: the same variables around each "Día sin carro" | Same endpoint | 2015–2020, 2022–2024 (windows of ~10 weeks) | Same |
| `era5/openmeteo_era5_bogota_2015_2024.json`: boundary layer, wind, temperature, precipitation | Open-Meteo archive (ERA5) | 2015-01-01 to 2024-11-01 | ERA5 © Copernicus; Open-Meteo CC BY 4.0 |

## Intermediate data (`data/interim/`)

About 260 MB, 174 files derived from `raw/` by the research scripts. Derived tables and diagnostics:

- hourly stagnation tables and diagnostics (`estancamiento_*.parquet/json`) with variants of the inventory, boundary layer and wind settings;
- 2024 contingency series (`contingencias_*`), Sunday and placebo estimates (`sunday_*`, `placebo_*`), 2020 lockdown validation (`val2020_*`), boundary-layer fills (`pbl_*`);
- station, road and municipality geometries (`estaciones.gpkg`, `roads.gpkg`, `municipios.gpkg`) and the observability map;
- case folders: `bogota/` (Día sin carro hourly tables and results), `la/` (AQS and HRRR tables at stations, LA runs), `edgar/` (comparison with the inventory) and `benchmark/` (model comparison tables).

## Processed data (`data/processed/`)

About 6 MB, 45 files: the results the application and reports read.

- `app/`: GeoJSON layers (stations, regions, roads, candidate sites) and the exported results (`resultados.json`, normalized estimates by period, 2024 contingencies by day). The `nox_app` Streamlit interface reads only this folder.
- `pinn/`: the trained transport kernel (`kernel.pt`, `kernel_table.npz`) with its training logs and validation, and the normalized estimates of the linear and PINN inversions for Nov–Dec 2023 and Feb–May 2024.
