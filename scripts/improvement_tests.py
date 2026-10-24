"""¿Qué datos existentes acercan la opción A? Experimento gemelo con escenarios.

Parte del escenario pesimista de feasibility_linear.py (errores ×2 y verdad generada con viento
perturbado) y agrega, por separado y combinados:
  - estaciones que solo miden NO₂ (BJU, FAR, GAM);
  - trazadores CO y SO₂ de SIMAT, con cocientes de emisión por tipo de fuente del inventario 2018
    (el CO/NOₓ y el SO₂/NOₓ de la industria y de los vehículos son muy distintos);
  - mejor viento (error de dirección de 10° o 5° en vez de 20°), como el que daría un modelo
    meteorológico de alta resolución;
  - más tiempo (nov–dic 2023 + 15 feb–31 may 2024).

Los fondos por hora se marginalizan analíticamente (covarianza σ²I + σ_b²11ᵀ por bloque).
Uso: .venv/bin/python scripts/improvement_tests.py
"""
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from config import UTM
from feasibility_linear import jacobian_hour, load_inputs

ROOT = Path(__file__).resolve().parents[1]
INT = ROOT / "data/interim"
rng = np.random.default_rng(11)
N_TWIN = 50
F_ERR = 2.0
LEVELS = [20, 10, 5]                      # error de dirección del viento (°, 1σ) en la verdad
PERIODS = [("2023-11-01", "2023-12-31"), ("2024-02-15", "2024-05-31")]
SPECIES = ["NOx", "CO", "SO2"]
MOLAR = {"NOx": 46.0, "CO": 28.0, "SO2": 64.0}
SIG = {"NOx": 8.0, "TEMPO": 3e15, "CO": 100.0, "SO2": 2.0}      # σ de observación nominal (ppb o molec/cm²)
SIG_BG = {"NOx": 5.0, "TEMPO": 3e15, "CO": 200.0, "SO2": 4.0}   # σ del fondo por hora
EST_FACTOR = 1.5
RHO = 0.8                                  # correlación a priori entre especies de una misma fuente
# Cocientes de emisión en masa respecto a NOₓ (inventario ZMVM 2018, Tabla 7) y supuestos
RATIO = {
    "industria": {"CO": 5739.4 / 9506.24, "SO2": 1018.53 / 9506.24},   # fuentes puntuales
    "vial": {"CO": 689254.1 / 124114.6, "SO2": 1058.8 / 124114.6},     # fuentes móviles
    "central eléctrica": {"CO": 0.6, "SO2": 0.005},                     # supuesto: gas natural
    "aeropuerto": {"CO": 1.0, "SO2": 0.08},                             # supuesto: turbosina
}


def catalog_utm():
    cat = pd.read_csv(ROOT / "data/raw/simat/cat_estacion.csv", skiprows=1, encoding="latin1")
    g = gpd.GeoDataFrame(cat, geometry=gpd.points_from_xy(cat.longitud, cat.latitud), crs=4326).to_crs(UTM)
    return g.set_index("cve_estac")[["geometry"]]


def perturb(uv, z, level):
    ang = np.deg2rad(level) * z[0]
    fac = np.exp(0.25 * level / 20 * z[1])
    c, s = np.cos(ang), np.sin(ang)
    return fac * np.array([c * uv[0] - s * uv[1], s * uv[0] + c * uv[1]])


def compute_period(start, end):
    """Por hora: matrices K del modelo y de la verdad (por nivel de error) para cada tipo de observación."""
    cand, prior_pt, sd_pt, cells, prior_rd, sd_rd, st, nox, ratio, wind, pbl, px = load_inputs(start, end, extras=True)
    st_all = catalog_utm()
    tr = pd.read_parquet(INT / "simat_tracers.parquet")
    tr = tr[tr.local.between(start, f"{end} 23:59") & tr.local.dt.hour.between(12, 17) & tr.id_station.isin(st_all.index)]
    tr["h"] = tr.utc - pd.Timedelta(hours=1)
    hours = [h for h in sorted(set(nox.h) & set(wind.index)) if h in pbl.index]
    out = []
    for h in hours:
        z = rng.standard_normal(2)
        nh = nox[nox.h == h]
        ph = px[px.h == h]
        obs = {"NOx": nh, "CO": tr[(tr.h == h) & (tr.id_parameter == "CO")],
               "SO2": tr[(tr.h == h) & (tr.id_parameter == "SO2")]}
        rec = {"est": nh.est.values}
        for lvl in [0] + LEVELS:
            uv = wind.loc[h].values if lvl == 0 else perturb(wind.loc[h].values, z, lvl)
            d = {}
            for kind, b in jacobian_hour(h, uv, pbl.loc[h], cand, cells, st_all, obs["NOx"], ph, ratio):
                d["NOx" if kind == "st" else "TEMPO"] = b
            for sp in ("CO", "SO2"):
                if len(obs[sp]):
                    d[sp] = jacobian_hour(h, uv, pbl.loc[h], cand, cells, st_all, obs[sp], ph.iloc[:0], ratio)[0][1]
            rec[lvl] = d
        out.append(rec)
    return out, cand, prior_pt, sd_pt, prior_rd


def state_layout(cand, prior_pt, sd_pt, prior_rd, species):
    """Media y covarianza a priori: por especie, [puntuales absolutos | 9 α viales relativos]."""
    n_pt = len(cand)
    n_src = n_pt + 9
    types = list(cand.tipo) + ["vial"] * 9
    mean, sd = [], []
    for sp in species:
        r = np.array([1.0 if sp == "NOx" else RATIO[t][sp] for t in types])
        base_m = np.r_[prior_pt, np.ones(9)]
        base_s = np.r_[sd_pt, np.full(9, 0.5)]
        mean.append(np.where(np.arange(n_src) < n_pt, base_m * r, 1.0))
        sd.append(np.where(np.arange(n_src) < n_pt, base_s * r, 0.5))
    mean, sd = np.concatenate(mean), np.concatenate(sd)
    S = np.diag(sd ** 2)
    for i in range(len(species)):
        for j in range(i + 1, len(species)):
            for k in range(n_src):
                a, b = i * n_src + k, j * n_src + k
                S[a, b] = S[b, a] = RHO * sd[a] * sd[b]
    return mean, S, n_src, types


def column_map(sp, species, n_src, n_pt, types):
    """Índices de estado y factor por columna de K (K viene en ppb-NOₓ por t/año NOₓ y α vial)."""
    k = species.index("NOx" if sp == "TEMPO" else sp)
    s_name = "NOx" if sp == "TEMPO" else sp
    conv = 1.0 if sp == "TEMPO" else MOLAR["NOx"] / MOLAR[s_name]
    fac = np.ones(n_src) * conv
    if s_name != "NOx":  # α vial relativo al a priori de esa especie
        fac[n_pt:] *= RATIO["vial"][s_name]
    return k * n_src + np.arange(n_src), fac


def run_scenario(periods_data, cfg, truth):
    cand, prior_pt, sd_pt, prior_rd = periods_data[0][1:]
    species = ["NOx", "CO", "SO2"] if cfg["tracers"] else ["NOx"]
    mean, Sa, n_src, types = state_layout(cand, prior_pt, sd_pt, prior_rd, species)
    n_pt = len(cand)
    n = len(mean)
    N = np.linalg.inv(Sa)
    b = np.repeat((N @ mean)[:, None], N_TWIN, 1)
    x_t = truth[: n] if cfg["tracers"] else truth[:n_src]
    for pi in cfg["periods"]:
        for rec in periods_data[pi][0]:
            for sp in ["NOx", "TEMPO"] + (["CO", "SO2"] if cfg["tracers"] else []):
                if sp not in rec[0]:
                    continue
                Km, Kt = rec[0][sp], rec[cfg["level"]][sp]
                sig = np.full(len(Km), SIG[sp] * F_ERR)
                if sp == "NOx":
                    keep = np.ones(len(Km), bool) if cfg["extras"] else ~rec["est"]
                    sig = np.where(rec["est"], sig * EST_FACTOR, sig)
                    Km, Kt, sig = Km[keep], Kt[keep], sig[keep]
                if not len(Km):
                    continue
                idx, fac = column_map(sp, species, n_src, n_pt, types)
                A, At = Km * fac, Kt * fac
                y = At @ x_t[idx] + SIG_BG[sp] * rng.standard_normal(N_TWIN)[None, :] \
                    + sig[:, None] * rng.standard_normal((len(sig), N_TWIN))
                Dinv = 1 / sig ** 2
                c = SIG_BG[sp] ** 2 / (1 + SIG_BG[sp] ** 2 * Dinv.sum())
                RA = Dinv[:, None] * A - c * np.outer(Dinv, Dinv @ A)
                Ry = Dinv[:, None] * y - c * np.outer(Dinv, Dinv @ y)
                N[np.ix_(idx, idx)] += A.T @ RA
                b[idx] += A.T @ Ry
    S = np.linalg.inv(N)
    xh = S @ b
    err = np.median(np.abs(xh[:n_src] - x_t[:n_src]) / x_t[:n_src], 1)
    return err, types


def main():
    data = [compute_period(*p) for p in PERIODS]
    cand, prior_pt, sd_pt, prior_rd = data[0][1:]
    mean, Sa, n_src, types = state_layout(cand, prior_pt, sd_pt, prior_rd, SPECIES)
    # verdad: NOₓ = a priori × LN(0.5); otras especies = NOₓ verdadero × cociente × LN(0.3)
    truth = np.zeros((len(mean), N_TWIN))
    f_nox = rng.lognormal(0, 0.5, (n_src, N_TWIN))
    truth[:n_src] = mean[:n_src, None] * f_nox
    for k in range(1, len(SPECIES)):
        truth[k * n_src:(k + 1) * n_src] = mean[k * n_src:(k + 1) * n_src, None] * f_nox * rng.lognormal(0, 0.3, (n_src, N_TWIN))

    base = dict(periods=[0], level=20, extras=False, tracers=False)
    scen = {
        "A. Base pesimista (viento ±20°, nov–dic 2023)": base,
        "B. + estaciones solo NO₂": {**base, "extras": True},
        "C. + trazadores CO y SO₂": {**base, "tracers": True},
        "D. Mejor viento (±10°)": {**base, "level": 10},
        "E. Mejor viento (±10°) + trazadores": {**base, "level": 10, "tracers": True},
        "F. Más tiempo (2 periodos, ±20°)": {**base, "periods": [0, 1]},
        "G. Todo con ±10°": dict(periods=[0, 1], level=10, extras=True, tracers=True),
        "H. Todo con ±5° (viento casi perfecto)": dict(periods=[0, 1], level=5, extras=True, tracers=True),
    }
    names = list(cand.nombre) + [f"Vial {r}" for r in ["SO", "S", "SE", "O", "Centro", "E", "NO", "N", "NE"]]
    ind = [i for i, t in enumerate(types) if t == "industria"]
    big = [i for i, t in enumerate(types) if t in ("central eléctrica", "aeropuerto") and "Nonoalco" not in names[i]]
    road = [i for i, t in enumerate(types) if t == "vial"]
    lines = ["# ¿Qué datos existentes acercan la opción A? (experimento gemelo)\n",
             f"- {N_TWIN} gemelos; errores de observación ×{F_ERR}; la verdad usa viento perturbado con el error indicado "
             "y el modelo usa el viento observado.",
             "- Métrica: mediana del error relativo de la emisión de NOₓ recuperada; meta del plan < 25 %.\n",
             "| Escenario | Clústeres industriales: mediana (rango) | Clústeres < 25 % | Fuentes grandes (Acolman, AIFA, AICM) | Vial por región: mediana (máx) |",
             "|---|---|---|---|---|"]
    detail = {}
    for name, cfg in scen.items():
        err, _ = run_scenario(data, cfg, truth)
        detail[name] = err
        e_ind, e_big, e_rd = err[ind], err[big], err[road]
        lines.append(f"| {name} | {np.median(e_ind):.0%} ({e_ind.min():.0%}–{e_ind.max():.0%}) | "
                     f"{(e_ind < 0.25).sum()} de {len(ind)} | " + " / ".join(f"{v:.0%}" for v in e_big)
                     + f" | {np.median(e_rd):.0%} ({e_rd.max():.0%}) |")
        print(lines[-1], flush=True)
    lines += ["\n## Detalle por fuente (error mediano)\n", "| Fuente | " + " | ".join(k.split('.')[0] for k in scen) + " |",
              "|---|" + "---|" * len(scen)]
    for i, nm in enumerate(names):
        lines.append(f"| {nm} | " + " | ".join(f"{detail[k][i]:.0%}" for k in scen) + " |")
    lines.append("\nSupuestos: cocientes CO/NOₓ y SO₂/NOₓ por tipo de fuente del inventario 2018 (industria y vehículos) "
                 "o supuestos (central de gas, aeropuertos); dispersión real de cocientes entre fuentes LN(0.3); "
                 "fondos por hora con σ CO 200 ppb y SO₂ 4 ppb; transporte inerte (sin química).")
    (ROOT / "reports/improvement_tests.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[-len(names) - 4:]))


if __name__ == "__main__":
    main()
