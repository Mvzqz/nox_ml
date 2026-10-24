"""¿El tratamiento del fondo de TEMPO explica el domingo bajo y Valle de México en ~300 t/año?

Síntomas (reports/pinn_prototipo.md, centrales_generacion.md): con TEMPO la inversión deja el domingo/hábil en
0.51–0.54 aun con la restricción de Infovial (0.69 ± 0.02), y Valle de México en ~300 t/año frente a 1,600 ± 650.

En la base (real_check_linear.build) el fondo de TEMPO es un escalar por hora (un escaneo por hora), espacialmente
uniforme, a priori 5e15 ± 5e15, y cada píxel tiene error independiente σ = 5e15. Aquí se prueban variantes del
fondo, de los píxeles usados y del peso de TEMPO, sin tocar los scripts compartidos: se reutilizan las filas
(jacobiano) que arma rcl.build y se reensambla el sistema normal con columnas de fondo adicionales.

Variantes:
  base            fondo uniforme por hora (actual)
  dia             fondo uniforme por día local en vez de por hora
  plano_hora      + gradiente lineal (x, y) libre en cada hora
  plano_fijo      + gradiente lineal fijo en todo el periodo
  region_fija     + desplazamiento fijo por región 3×3 del fondo (patrón estático)
  region_tipo     + desplazamiento por región 3×3 separado por tipo de día (hábil / sábado / domingo)
  sin_valle10     sin píxeles a < 10 km de la central Valle de México
  nucleo          solo píxeles a < 8 km de alguna estación de NOₓ (recorte al núcleo con estaciones)
  amf_cte         columna reescalada a AMF constante por escaneo: vcd · AMF / mediana(AMF)
  valle_sens06    sensibilidad de TEMPO a la pluma de Valle × 0.6 (pluma pegada al suelo, AMF a priori alto)
  tp_x3, tp_x10   σ de TEMPO ×3 y ×10 (errores correlacionados entre píxeles vecinos)
  solo_est        sin TEMPO

Para cada variante: domingo/hábil sin restricción (IC 90 % bootstrap de días) y con la restricción de Infovial
(0.69 ± 0.02, como pinn/invert.py), Valle/Nonoalco/AICM/AIFA, vial/inventario, RMSE LOO en estaciones (modelo e
híbrido) y r con TEMPO.
Gemelo: TEMPO sintético con verdad conocida (Valle 1,600, Nonoalco 100, domingo 0.69) + fondo con el patrón
espacial medio de los residuos reales de la base; se invierte con fondo uniforme y con las variantes de fondo.

Uso: .venv/bin/python scripts/fondo_tempo.py
Salida: reports/fondo_tempo_tablas_2023-11-01_2023-12-31.md (tablas; el análisis va en reports/fondo_tempo.md)
"""
from pathlib import Path

import netCDF4
import numpy as np
import pandas as pd

import feasibility_linear as fl
import puff
import real_check_linear as rcl
from centrales_prior_real import PRIORS, set_priors

ROOT = Path(__file__).resolve().parents[1]
START, END = "2023-11-01", "2023-12-31"
RAW = ROOT / "data/raw/tempo"
L = 20_000.0          # escala del gradiente (m): coeficiente = cambio del fondo cada 20 km
SD_GRAD = 3e15        # a priori del gradiente por 20 km
SD_REG = 3e15         # a priori del desplazamiento regional
SD_DAY = 5e15
RATIO_PRIOR = {1: (0.87, 0.02), 2: (0.69, 0.02)}
N_BOOT = 100
rng = np.random.default_rng(5)
CAP = {}


def capture_load(orig):
    def load(start, end, extras=False):
        out = orig(start, end, extras)
        CAP["inputs"] = out
        return out
    return load


def amf_for(px):
    """AMF troposférico de cada píxel, alineado con el índice de tempo_pixels (mismo orden que qc_tempo.py)."""
    amf, lat = [], []
    for f in sorted(RAW.glob("TEMPO_NO2_L2_V04_*_zmvm.nc")):
        t = pd.Timestamp(f.name.split("_")[4][:15].replace("T", " "))
        if not (pd.Timestamp(START) <= t < pd.Timestamp(END) + pd.Timedelta(days=1)):
            continue
        with netCDF4.Dataset(f) as ds:
            amf.append(ds["support_data/amf_troposphere"][:].filled(np.nan).ravel())
            lat.append(ds["geolocation/latitude"][:].filled(np.nan).ravel())
    amf, lat = np.concatenate(amf), np.concatenate(lat)
    assert np.allclose(lat[px.index.values], px.lat.values), "desalineado"
    return amf[px.index.values]


def setup():
    rcl.load_inputs = capture_load(rcl.load_inputs)
    fl.SIGMA_THETA = puff.SIGMA_THETA = np.deg2rad(30)
    m = rcl.build(START, END, "domain", no_industry=True, extras=True)
    set_priors(m, PRIORS["corregido"])
    cand, *_, st, nox, ratio, wind, pbl, px = CAP["inputs"]
    px = px.copy()
    px["amf"] = amf_for(px)
    groups = []
    for k, h in enumerate(m["hours"]):
        p = px[px.h == h]
        if len(p):
            groups.append((k, h, p))
    assert len(groups) == len(m["tp_rows"])
    m["tp_px"] = groups
    m["st_xy"] = st.geometry
    return m, cand


def region_of(x, y, box):
    x0, x1, y0, y1 = box
    i = np.clip(((x - x0) / (x1 - x0) * 3).astype(int), 0, 2)
    j = np.clip(((y - y0) / (y1 - y0) * 3).astype(int), 0, 2)
    return 3 * j + i


class System:
    """Sistema normal con estado extendido: [estado base | parámetros de fondo extra]."""

    def __init__(self, m, cand, variant, y_tp=None, y_st=None):
        self.m, self.v = m, variant
        n = m["n"]
        H = len(m["hours"])
        n_src = m["n_pt"] + 27
        xs = np.concatenate([p.x.values for *_, p in m["tp_px"]])
        ys = np.concatenate([p.y.values for *_, p in m["tp_px"]])
        xc, yc = xs.mean(), ys.mean()
        box = (xs.min(), xs.max() + 1, ys.min(), ys.max() + 1)
        dlist = sorted({rcl.local_day(h) for h in m["hours"]})
        dpos = {d: i for i, d in enumerate(dlist)}
        extra_xa, extra_sa = [], []

        def new(k, mu, sd):
            base = n + len(extra_xa)
            extra_xa.extend([mu] * k)
            extra_sa.extend([sd] * k)
            return base

        if variant == "dia":
            i_day = new(len(dlist), 5e15, SD_DAY)
        if variant == "plano_hora":
            i_ph = new(2 * H, 0.0, SD_GRAD)
        if variant == "plano_fijo":
            i_pf = new(2, 0.0, SD_GRAD)
        if variant == "region_fija":
            i_rf = new(9, 0.0, SD_REG)
        if variant == "region_tipo":
            i_rt = new(27, 0.0, SD_REG)
        self.n = n + len(extra_xa)
        self.xa = np.r_[m["xa"], extra_xa]
        self.sa = np.r_[m["sa"], extra_sa]
        names = list(cand.nombre)
        self.ix = {k: next(i for i, nm in enumerate(names) if k in nm) for k in ("Valle de México", "Nonoalco", "AICM", "AIFA")}
        valle = cand.geometry.iloc[self.ix["Valle de México"]]
        sxy = m["st_xy"].loc[sorted({s for s, *_ in m["st_rows"]} - m["est_ids"])]

        sig_tp = rcl.SIG_TP * {"tp_x3": 3, "tp_x10": 10}.get(variant, 1)
        self.blocks = []  # (día, idx, A, g)
        self.tp = []      # (idx, D, y, sig) para predicción y gemelo
        if variant != "solo_est":
            for j, ((k, h, p), (idx, Kf, y)) in enumerate(zip(m["tp_px"], m["tp_rows"])):
                if y_tp is not None:
                    y = y_tp[j]
                keep = np.ones(len(p), bool)
                if variant == "sin_valle10":
                    keep = np.hypot(p.x.values - valle.x, p.y.values - valle.y) > 10_000
                if variant == "nucleo":
                    d = np.min(np.hypot(p.x.values[:, None] - sxy.x.values, p.y.values[:, None] - sxy.y.values), 1)
                    keep = d < 8_000
                if not keep.any():
                    continue
                D, y, pp = Kf[keep].copy(), y[keep].copy(), p[keep]
                if variant == "amf_cte":
                    y = y * pp.amf.values / np.nanmedian(pp.amf.values)
                    ok = np.isfinite(y)
                    D, y, pp = D[ok], y[ok], pp[ok]
                if variant == "valle_sens06":
                    D[:, self.ix["Valle de México"]] *= 0.6
                idx = idx.copy()
                dx, dy = (pp.x.values - xc) / L, (pp.y.values - yc) / L
                if variant == "dia":
                    idx[-1] = i_day + dpos[rcl.local_day(h)]
                if variant == "plano_hora":
                    D = np.c_[D, dx, dy]
                    idx = np.r_[idx, i_ph + 2 * k, i_ph + 2 * k + 1]
                if variant == "plano_fijo":
                    D = np.c_[D, dx, dy]
                    idx = np.r_[idx, i_pf, i_pf + 1]
                if variant in ("region_fija", "region_tipo"):
                    r = region_of(pp.x.values, pp.y.values, box)
                    off = i_rf if variant == "region_fija" else i_rt + 9 * rcl.day_type(h)
                    D = np.c_[D, np.eye(9)[r]]
                    idx = np.r_[idx, off + np.arange(9)]
                self.blocks.append((rcl.local_day(h), idx, D.T @ D / sig_tp ** 2, D.T @ y / sig_tp ** 2))
                self.tp.append((idx, D, y))
        self.st_rows = m["st_rows"] if y_st is None else [(s, h, idx, kr, yy) for (s, h, idx, kr, _), yy in zip(m["st_rows"], y_st)]
        for s, h, idx, kr, yy in self.st_rows:
            sg = rcl.SIG_ST * (rcl.EST_FACTOR if s in m["est_ids"] else 1.0)
            self.blocks.append((rcl.local_day(h), idx, np.outer(kr, kr) / sg ** 2, kr * yy / sg ** 2))

    def normal(self, weights=None, drop=None):
        N = np.diag(1 / self.sa ** 2)
        b = self.xa / self.sa ** 2
        for d, idx, A, g in self.blocks:
            w = 1.0 if weights is None else weights.get(d, 0)
            if w:
                N[np.ix_(idx, idx)] += w * A
                b[idx] += w * g
        if drop:
            for s, h, idx, kr, yy in self.st_rows:
                if s == drop:
                    sg = rcl.SIG_ST * (rcl.EST_FACTOR if s in self.m["est_ids"] else 1.0)
                    N[np.ix_(idx, idx)] -= np.outer(kr, kr) / sg ** 2
                    b[idx] -= kr * yy / sg ** 2
        return N, b

    def constraint(self, x_ref):
        n_pt = self.m["n_pt"]
        E = np.zeros((self.n, self.n))
        for dt, (r, sd) in RATIO_PRIOR.items():
            for i in range(9):
                g = np.zeros(self.n)
                g[n_pt + 9 * dt + i] = 1.0
                g[n_pt + i] = -r
                E += np.outer(g, g) / (sd * max(x_ref[n_pt + i], 0.1)) ** 2
        return E

    def sun(self, x):
        t = rcl.road_totals(self.m, x)
        return t[2] / t[0], t[0] / self.m["prior_rd"].sum()


def evaluate(S, full=True):
    N, b = S.normal()
    x = np.linalg.solve(N, b)
    sd = np.sqrt(np.diag(np.linalg.inv(N)))
    sun, inv = S.sun(x)
    xc = np.linalg.solve(N + S.constraint(x), b)
    sun_c, inv_c = S.sun(xc)
    out = dict(sun=sun, sun_c=sun_c, inv=inv, x=x, sd=sd, xc=xc)
    if S.tp:
        out["r_tp"] = np.corrcoef(np.concatenate([D @ x[i] for i, D, _ in S.tp]), np.concatenate([y for *_, y in S.tp]))[0, 1]
    else:
        tp_m = System(S.m, CAND, "base")  # mismo estado (sin parámetros extra): r con TEMPO no usado en el ajuste
        out["r_tp"] = np.corrcoef(np.concatenate([D @ x[i] for i, D, _ in tp_m.tp]), np.concatenate([y for *_, y in tp_m.tp]))[0, 1]
    if not full:
        return out
    days = sorted({d for d, *_ in S.blocks})
    boot = []
    for _ in range(N_BOOT):
        w = pd.Series(1, index=[days[i] for i in rng.choice(len(days), len(days))]).groupby(level=0).sum().to_dict()
        Nb, bb = S.normal(weights=w)
        boot.append(S.sun(np.linalg.solve(Nb, bb))[0])
    out["lo"], out["hi"] = np.percentile(boot, [5, 95])
    # LOO en estaciones de NOₓ medido: modelo e híbrido (modelo + IDW de residuos)
    rows = pd.DataFrame([(s, h, yy) for s, h, *_, yy in S.st_rows], columns=["sid", "h", "obs"])
    xy = S.m["st_xy"]
    se_m, se_h, nn = 0.0, 0.0, 0
    for sid in sorted(set(rows.sid) - S.m["est_ids"]):
        Nl, bl = S.normal(drop=sid)
        xl = np.linalg.solve(Nl, bl)
        pred = np.array([kr @ xl[idx] for _, _, idx, kr, _ in S.st_rows])
        res = rows.obs.values - pred
        mask = (rows.sid == sid).values
        oth = rows[~mask]
        dist = {s: max(xy[sid].distance(xy[s]) / 1000, 0.5) for s in oth.sid.unique()}
        corr = []
        for h in rows.h.values[mask]:
            o = oth[oth.h == h]
            w = 1 / np.array([dist[q] for q in o.sid]) ** 2
            corr.append((w * res[o.index.values]).sum() / w.sum())
        ob, pm = rows.obs.values[mask], pred[mask]
        se_m += ((pm - ob) ** 2).sum()
        se_h += ((pm + np.array(corr) - ob) ** 2).sum()
        nn += mask.sum()
    out["loo_m"], out["loo_h"] = np.sqrt(se_m / nn), np.sqrt(se_h / nn)
    return out


VARIANTS = {
    "base": "fondo uniforme por hora (actual)",
    "dia": "fondo uniforme por día",
    "plano_hora": "+ gradiente lineal libre por hora",
    "plano_fijo": "+ gradiente lineal fijo",
    "region_fija": "+ desplazamiento fijo por región 3×3",
    "region_tipo": "+ desplazamiento por región 3×3 y tipo de día",
    "sin_valle10": "sin píxeles a < 10 km de Valle de México",
    "nucleo": "solo píxeles a < 8 km de una estación",
    "amf_cte": "columna con AMF constante por escaneo",
    "valle_sens06": "sensibilidad a la pluma de Valle × 0.6",
    "tp_x3": "σ TEMPO × 3",
    "tp_x10": "σ TEMPO × 10",
    "solo_est": "sin TEMPO",
}


def main():
    global CAND
    m, cand = setup()
    CAND = cand
    lines = ["# Fondo de TEMPO: tablas (nov–dic 2023, σθ = 30°, a priori corregidos de centrales)\n"]

    # Diagnóstico: AMF y residuos de la base
    px_all = pd.concat([p for *_, p in m["tp_px"]])
    base = System(m, cand, "base")
    rb = evaluate(base, full=False)
    xb = rb["x"]
    res = np.concatenate([y - D @ xb[i] for i, D, y in base.tp])
    px_all = px_all.assign(res=res, bx=(px_all.x // 6000).astype(int), by=(px_all.y // 6000).astype(int))
    v = cand.geometry.iloc[base.ix["Valle de México"]]
    near = np.hypot(px_all.x - v.x, px_all.y - v.y) < 10_000
    dt = np.concatenate([np.full(len(p), rcl.day_type(h)) for k, h, p in m["tp_px"]])
    lines += ["## Diagnóstico\n",
              f"- Píxeles: {len(px_all):,}; escaneos: {len(m['tp_px'])}; AMF troposférico mediano {np.nanmedian(px_all.amf):.2f} "
              f"(a < 10 km de Valle {np.nanmedian(px_all.amf[near]):.2f}; P10–P90 dominio {np.nanpercentile(px_all.amf, 10):.2f}–{np.nanpercentile(px_all.amf, 90):.2f}).",
              f"- Residuo medio de la base (obs − modelo, 1e15 molec/cm²): todo {res.mean() / 1e15:.2f}; a < 10 km de Valle "
              f"{res[near.values].mean() / 1e15:.2f}; hábil {res[dt == 0].mean() / 1e15:.2f}, domingo {res[dt == 2].mean() / 1e15:.2f}.",
              f"- Desviación estándar del residuo medio en celdas de 6 km (patrón espacial persistente): "
              f"{px_all.groupby(['bx', 'by']).res.mean().std() / 1e15:.2f}e15; σ por píxel supuesta {rcl.SIG_TP / 1e15:.0f}e15.\n"]
    for name, sub in (("hábil", dt == 0), ("domingo/festivo", dt == 2)):
        g = px_all[sub].groupby(pd.cut(np.hypot(px_all.x[sub] - v.x, px_all.y[sub] - v.y) / 1000, [0, 5, 10, 20, 40, 80])).res.mean() / 1e15
        lines.append(f"- Residuo medio por distancia a Valle ({name}): " + ", ".join(f"{k}: {val:.2f}" for k, val in g.items()))
    lines.append("")

    lines += ["## Datos reales\n",
              "| Variante | Domingo/hábil libre (IC 90 %) | Con restricción Infovial 0.69 | Valle de México | Nonoalco | AICM | AIFA | "
              "Vial / inventario | LOO modelo / híbrido (ppb) | TEMPO r |", "|---|---|---|---|---|---|---|---|---|---|"]
    post = {}
    for key, label in VARIANTS.items():
        S = base if key == "base" else System(m, cand, key)
        r = evaluate(S)
        post[key] = r
        x, sd, xc = r["x"], r["sd"], r["xc"]
        f = lambda k: f"{x[S.ix[k]]:,.0f} ± {sd[S.ix[k]]:,.0f}"
        line = (f"| {label} | {r['sun']:.2f} ({r['lo']:.2f}–{r['hi']:.2f}) | {r['sun_c']:.2f} (Valle {xc[S.ix['Valle de México']]:,.0f}) | "
                f"{f('Valle de México')} | {f('Nonoalco')} | {f('AICM')} | {f('AIFA')} | {r['inv']:.0%} | "
                f"{r['loo_m']:.2f} / {r['loo_h']:.2f} | {r['r_tp']:.2f} |")
        lines.append(line)
        print(line, flush=True)

    # Gemelo
    xt = rb["xc"].copy()
    n_pt = m["n_pt"]
    xt[base.ix["Valle de México"]], xt[base.ix["Nonoalco"]] = 1600.0, 100.0
    xt[n_pt + 9: n_pt + 18] = 0.87 * xt[n_pt: n_pt + 9]
    xt[n_pt + 18: n_pt + 27] = 0.69 * xt[n_pt: n_pt + 9]
    pattern = px_all.groupby(["bx", "by"]).res.transform("mean").values
    pattern = pattern - pattern.mean()
    sizes = [len(p) for *_, p in m["tp_px"]]
    cuts = np.cumsum(sizes)[:-1]
    truths = {"sin patrón": np.zeros(len(px_all)), "patrón real de residuos": pattern}
    lines += ["\n## Gemelo\n",
              "Verdad: a posteriori real (con restricción) con Valle 1,600, Nonoalco 100, sábado 0.87 y domingo 0.69 del hábil, "
              "fondo por hora de la base; TEMPO + patrón espacial fijo; 10 realizaciones de ruido.\n",
              "| Fondo verdadero | Invertido con | Domingo/hábil libre | Valle de México (mediana, P5–P95) | Vial / verdad |",
              "|---|---|---|---|---|"]
    tot_true = rcl.road_totals(m, xt).sum()
    for tname, pat in truths.items():
        pats = np.split(pat, cuts)
        for inv in ("base", "plano_hora", "region_fija", "region_tipo", "tp_x10"):
            res_t = []
            for _ in range(10):
                y_tp = [Kf @ xt[idx] + pz + rng.normal(0, rcl.SIG_TP, len(Kf)) for (idx, Kf, _), pz in zip(m["tp_rows"], pats)]
                y_st = [kr @ xt[idx] + rng.normal(0, rcl.SIG_ST * (rcl.EST_FACTOR if s in m["est_ids"] else 1))
                        for s, h, idx, kr, _ in m["st_rows"]]
                S = System(m, cand, inv, y_tp=y_tp, y_st=y_st)
                N, b = S.normal()
                x = np.linalg.solve(N, b)
                sun, _ = S.sun(x)
                res_t.append((sun, x[S.ix["Valle de México"]], rcl.road_totals(m, x).sum() / tot_true))
            res_t = np.array(res_t)
            p5, p50, p95 = np.percentile(res_t[:, 1], [5, 50, 95])
            line = (f"| {tname} | {VARIANTS[inv]} | {np.median(res_t[:, 0]):.2f} | {p50:,.0f} ({p5:,.0f}–{p95:,.0f}) | "
                    f"{np.median(res_t[:, 2]):.2f} |")
            lines.append(line)
            print(line, flush=True)

    out = ROOT / f"reports/fondo_tempo_tablas_{START}_{END}.md"
    out.write_text("\n".join(lines) + "\n\nValores en t/año (a posteriori ± σ). Ver reports/fondo_tempo.md.\n")
    print("escrito", out)


if __name__ == "__main__":
    main()
