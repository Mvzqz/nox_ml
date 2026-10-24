"""Gemelo con viento ±30°: ¿ayuda representar ese error en el modelo (σθ = 30° en la dispersión)?

La verdad se genera con el viento perturbado ±30° y la dispersión normal (σθ = 15°). El modelo usa el
viento observado con σθ = 15° (actual) o σθ = 30° (error de viento representado). Nov–dic 2023, sin
datos extra. Reutiliza improvement_tests.py sin modificarlo.
Uso: .venv/bin/python scripts/improve_twin.py
"""
import numpy as np

import feasibility_linear as fl
import improvement_tests as it

LEVEL = 30
SIG15 = fl.SIGMA_THETA_LEGACY


def compute(start, end):
    cand, prior_pt, sd_pt, cells, prior_rd, sd_rd, st, nox, ratio, wind, pbl, px = fl.load_inputs(start, end)
    hours = [h for h in sorted(set(nox.h) & set(wind.index)) if h in pbl.index]
    recs = {15: [], 30: []}
    for h in hours:
        z = it.rng.standard_normal(2)
        nh, ph = nox[nox.h == h], px[px.h == h]
        fl.SIGMA_THETA = SIG15
        truth = {("NOx" if k == "st" else "TEMPO"): K for k, K in
                 fl.jacobian_hour(h, it.perturb(wind.loc[h].values, z, LEVEL), pbl.loc[h], cand, cells, st, nh, ph, ratio)}
        for s in (15, 30):
            fl.SIGMA_THETA = np.deg2rad(s)
            model = {("NOx" if k == "st" else "TEMPO"): K for k, K in
                     fl.jacobian_hour(h, wind.loc[h].values, pbl.loc[h], cand, cells, st, nh, ph, ratio)}
            recs[s].append({"est": nh.est.values, 0: model, LEVEL: truth})
    fl.SIGMA_THETA = SIG15
    return recs, cand, prior_pt, sd_pt, prior_rd


def main():
    recs, cand, prior_pt, sd_pt, prior_rd = compute("2023-11-01", "2023-12-31")
    mean, Sa, n_src, types = it.state_layout(cand, prior_pt, sd_pt, prior_rd, ["NOx"])
    truth = mean[:, None] * it.rng.lognormal(0, 0.5, (n_src, it.N_TWIN))
    ind = [i for i, t in enumerate(types) if t == "industria"]
    big = [i for i, t in enumerate(types) if t in ("central eléctrica", "aeropuerto") and "Nonoalco" not in cand.nombre.iloc[i]]
    road = [i for i, t in enumerate(types) if t == "vial"]
    print("| Modelo (verdad con viento ±30°) | Clústeres: mediana | Clústeres < 25 % | Acolman / AIFA / AICM | Vial por región: mediana (máx) |")
    print("|---|---|---|---|---|")
    for s, label in ((15, "σθ = 15° (actual)"), (30, "σθ = 30° (error representado)")):
        err, _ = it.run_scenario([(recs[s], cand, prior_pt, sd_pt, prior_rd)],
                                 dict(periods=[0], level=LEVEL, extras=False, tracers=False), truth)
        e_ind, e_big, e_rd = err[ind], err[big], err[road]
        print(f"| {label} | {np.median(e_ind):.0%} | {(e_ind < .25).sum()} de {len(ind)} | "
              + " / ".join(f"{v:.0%}" for v in e_big) + f" | {np.median(e_rd):.0%} ({e_rd.max():.0%}) |", flush=True)


if __name__ == "__main__":
    main()
