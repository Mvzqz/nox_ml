"""Gemelo pesimista con el error de viento medido (ver wind_loo.py): ±20°, ±30° y ±40°.

Reutiliza improvement_tests.py sin modificarlo; solo nov–dic 2023 y sin datos extra.
Uso: .venv/bin/python scripts/wind_scenarios.py
"""
import numpy as np

import improvement_tests as it

it.LEVELS = [40, 30, 20, 10]
it.PERIODS = it.PERIODS[:1]


def main():
    data = [it.compute_period(*p) for p in it.PERIODS]
    cand, prior_pt, sd_pt, prior_rd = data[0][1:]
    mean, Sa, n_src, types = it.state_layout(cand, prior_pt, sd_pt, prior_rd, it.SPECIES)
    truth = np.zeros((len(mean), it.N_TWIN))
    truth[:n_src] = mean[:n_src, None] * it.rng.lognormal(0, 0.5, (n_src, it.N_TWIN))
    ind = [i for i, t in enumerate(types) if t == "industria"]
    big = [i for i, t in enumerate(types) if t in ("central eléctrica", "aeropuerto") and "Nonoalco" not in cand.nombre.iloc[i]]
    road = [i for i, t in enumerate(types) if t == "vial"]
    print("| Error de dirección del viento (1σ) | Clústeres: mediana | Clústeres < 25 % | Acolman / AIFA / AICM | Vial por región: mediana (máx) |")
    print("|---|---|---|---|---|")
    for lvl in it.LEVELS:
        err, _ = it.run_scenario(data, dict(periods=[0], level=lvl, extras=False, tracers=False), truth)
        e_ind, e_big, e_rd = err[ind], err[big], err[road]
        print(f"| ±{lvl}° | {np.median(e_ind):.0%} | {(e_ind < .25).sum()} de {len(ind)} | "
              + " / ".join(f"{v:.0%}" for v in e_big) + f" | {np.median(e_rd):.0%} ({e_rd.max():.0%}) |", flush=True)


if __name__ == "__main__":
    main()
