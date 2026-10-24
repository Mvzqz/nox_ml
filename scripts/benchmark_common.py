"""Utilidades del banco datos-vs-desempeño (reports/banco_datos.md).

La inversión se reescribe en forma dispersa a partir de las filas que guarda real_check_linear.build
(st_rows, tp_rows) para poder quitar estaciones o el satélite sin reconstruir el Jacobiano:
    N = Sₐ⁻¹ + Gₑᵀ Wₑ Gₑ / σₑ² + Gₜᵀ Gₜ / σₜ²,   b = Sₐ⁻¹ xₐ + Gₑᵀ Wₑ y / σₑ² + Gₜᵀ y / σₜ²
con Wₑ = 1/1.5² para las estaciones de NO₂ con NOₓ estimado (como rcl.solve). Da lo mismo que rcl.solve.
"""
import numpy as np
import pandas as pd
import scipy.sparse as sp

import real_check_linear as rcl


def sparse_rows(m):
    """Matrices dispersas de estaciones y TEMPO, en el orden de m['st_rows'] y m['tp_rows']."""
    n = m["n"]
    r, c, v = [], [], []
    sid, hrs, y = [], [], []
    for k, (s, h, idx, kr, yy) in enumerate(m["st_rows"]):
        r.append(np.full(len(idx), k))
        c.append(idx)
        v.append(kr)
        sid.append(s)
        hrs.append(h)
        y.append(yy)
    Gs = sp.csr_matrix((np.concatenate(v), (np.concatenate(r), np.concatenate(c))), shape=(len(sid), n))
    r, c, v, yt, k0 = [], [], [], [], 0
    for idx, Kf, yy in m["tp_rows"]:
        nk = len(Kf)
        r.append(np.repeat(np.arange(k0, k0 + nk), len(idx)))
        c.append(np.tile(idx, nk))
        v.append(Kf.ravel())
        yt.append(yy)
        k0 += nk
    Gt = sp.csr_matrix((np.concatenate(v), (np.concatenate(r), np.concatenate(c))), shape=(k0, n)) if k0 else None
    return dict(Gs=Gs, Gt=Gt, sid=np.array(sid), h=np.array(hrs), ys=np.array(y, float),
                yt=np.concatenate(yt) if yt else np.zeros(0), est=np.isin(sid, list(m["est_ids"])))


def station_weights(R, keep=None):
    w = np.where(R["est"], rcl.EST_FACTOR ** -2, 1.0)
    if keep is not None:
        w = w * np.isin(R["sid"], list(keep))
    return w


def normal_matrix(m, R, keep=None, tempo=True, E=None):
    w = station_weights(R, keep)
    N = sp.diags(1 / m["sa"] ** 2) + R["Gs"].T @ sp.diags(w / rcl.SIG_ST ** 2) @ R["Gs"]
    if tempo and R["Gt"] is not None:
        N = N + R["Gt"].T @ R["Gt"] / rcl.SIG_TP ** 2
    N = N.toarray()
    if E is not None:
        N = N + E
    return N


def rhs(m, R, ys, yt, keep=None, tempo=True):
    w = station_weights(R, keep)
    b = m["xa"] / m["sa"] ** 2 + R["Gs"].T @ (w * ys / rcl.SIG_ST ** 2)
    if tempo and R["Gt"] is not None:
        b = b + R["Gt"].T @ (yt / rcl.SIG_TP ** 2)
    return np.asarray(b).ravel()


def zone_totals(m, x):
    """Emisión vial por zona y tipo de día (t/año): α̂ · a priori de la zona. Forma (3, nr)."""
    n_pt, nr = m["n_pt"], m["n_reg"]
    return np.array([x[n_pt + nr * d: n_pt + nr * (d + 1)] * m["prior_rd"] for d in range(3)])


def posterior_corr(N, m):
    n_pt, nr = m["n_pt"], m["n_reg"]
    S = np.linalg.inv(N)[n_pt:n_pt + nr, n_pt:n_pt + nr]
    sd = np.sqrt(np.diag(S))
    C = S / np.outer(sd, sd)
    return C, sd


def fixed_model(m, R):
    """Modelo con emisión fija (a priori) en cada fila de estación, sin fondo."""
    n_pt, nr = m["n_pt"], m["n_reg"]
    out = []
    for s, h, idx, kr, yy in m["st_rows"]:
        out.append(float(kr[:n_pt] @ m["prior_pt"] + kr[n_pt:n_pt + nr].sum()))
    return np.array(out)


def normalized(R, fixed, keep=None, n_placebo=2000, seed=3):
    """Estimador normalizado (Σ observado ÷ Σ modelo fijo por día) con las estaciones de `keep` (sin las de NO₂
    estimado incluidas, como la_real.metrics). Devuelve domingo/hábil, IC 90 %, placebo ±, CV hábiles."""
    rng = np.random.default_rng(seed)
    msk = np.ones(len(R["sid"]), bool) if keep is None else np.isin(R["sid"], list(keep))
    d = pd.DataFrame({"h": R["h"][msk], "obs": R["ys"][msk], "fixed": fixed[msk]})
    hr = d.groupby("h")[["obs", "fixed"]].mean()
    hr = hr.assign(day=[rcl.local_day(h) for h in hr.index], dt=[rcl.day_type(h) for h in hr.index])
    dd = hr.groupby("day").agg(obs=("obs", "sum"), fixed=("fixed", "sum"), dt=("dt", "first"), n=("obs", "size"))
    dd = dd[dd.n >= 4]

    def nr(q, a=0, bset=2):
        g = q.groupby("dt")
        v = g.obs.sum() / g.fixed.sum()
        return v.get(bset, np.nan) / v[a]
    out = {"norm_domingo": float(nr(dd))}
    bs = [nr(dd.iloc[rng.integers(0, len(dd), len(dd))]) for _ in range(1000)]
    out["norm_domingo_ic"] = np.nanpercentile(bs, [5, 95]).tolist()
    wk = dd[dd.dt == 0]
    q = wk.obs / wk.fixed
    out["norm_cv_habiles"] = float(q.std() / q.mean())
    k = int((dd.dt == 2).sum())
    pl = []
    for _ in range(n_placebo):
        fake = np.zeros(len(wk), bool)
        fake[rng.choice(len(wk), k, replace=False)] = True
        a, b2 = wk[~fake], wk[fake]
        pl.append((b2.obs.sum() / b2.fixed.sum()) / (a.obs.sum() / a.fixed.sum()))
    out["placebo_mitad_ancho"] = float((np.percentile(pl, 95) - np.percentile(pl, 5)) / 2)
    out["n_domingos"], out["n_habiles"] = k, int(len(wk))
    return out


def heldout(m, R, x_of, eval_ids, keep=None):
    """Error en estaciones no usadas: modelo, IDW (de las estaciones usadas) e híbrido (modelo + IDW de residuos).

    x_of(sid) -> estado a posteriori sin la estación sid (LOO) o el mismo estado para todas (estaciones fuera
    del subconjunto). Pondera por número de horas, como la_real.metrics."""
    st = m["st"]
    obs, sid, hrs = R["ys"], R["sid"], R["h"]
    use = np.ones(len(sid), bool) if keep is None else np.isin(sid, list(keep))
    agg = []
    for s in eval_ids:
        x = x_of(s)
        pred = R["Gs"] @ x
        res = obs - pred
        mk = sid == s
        others = use & ~mk
        dist = {o: max(st.geometry[s].distance(st.geometry[o]) / 1000, 0.5) for o in np.unique(sid[others])}
        oh = pd.DataFrame({"h": hrs[others], "sid": sid[others], "obs": obs[others], "res": res[others]})
        oh["w"] = 1 / oh.sid.map(dist) ** 2
        g = oh.assign(wo=oh.w * oh.obs, wr=oh.w * oh.res).groupby("h")[["w", "wo", "wr"]].sum()
        hh = pd.Index(hrs[mk])
        ok = hh.isin(g.index)
        pm, ob = pred[mk][ok], obs[mk][ok]
        gi = g.loc[hh[ok]]
        pi = (gi.wo / gi.w).values
        ph = pm + (gi.wr / gi.w).values
        agg.append((s, len(ob), *[np.sqrt(np.mean((p - ob) ** 2)) for p in (pm, pi, ph)]))
    ag = pd.DataFrame(agg, columns=["sid", "n", "model", "idw", "hybrid"])
    wr = lambda c: float(np.sqrt((ag.n * ag[c] ** 2).sum() / ag.n.sum()))
    return {"model": wr("model"), "idw": wr("idw"), "hybrid": wr("hybrid"),
            "hibrido_gana": f"{int((ag.hybrid < ag.idw).sum())} de {len(ag)}", "n_eval": int(len(ag)),
            "por_estacion": ag.round(3).to_dict("records")}


def aggregate(rows, ids):
    """RMSE ponderado por horas de una tabla por estación (por_estacion) restringida a `ids`."""
    ag = pd.DataFrame([r for r in rows if r["sid"] in set(ids)])
    wr = lambda c: float(np.sqrt((ag.n * ag[c] ** 2).sum() / ag.n.sum()))
    return {"model": wr("model"), "idw": wr("idw"), "hybrid": wr("hybrid"), "n_eval": int(len(ag))}


def rotate_wind(wind, z, sig_deg):
    """Rota el viento horario por e = σ·z grados (z: serie AR(1) estandarizada)."""
    th = np.deg2rad(sig_deg * z)
    w = wind.copy()
    w["u"] = wind.u * np.cos(th) - wind.v * np.sin(th)
    w["v"] = wind.u * np.sin(th) + wind.v * np.cos(th)
    w.attrs = wind.attrs
    return w


def ar1(n, rho, rng):
    e = np.zeros(n)
    e[0] = rng.normal()
    for k in range(1, n):
        e[k] = rho * e[k - 1] + rng.normal(0, np.sqrt(1 - rho ** 2))
    return e
