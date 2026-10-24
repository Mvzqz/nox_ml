"""Rebuilds ``baseline_reference.npz``: a tiny synthetic scene and what the research code computes for it.

Usage: git worktree add /tmp/research research-archive
       uv run python ml/tests/fixtures/make_baseline_reference.py /tmp/research

The reference is the baseline configuration of the research-archive branch:
``feasibility_linear.jacobian_hour`` (stationary plume, domain-mean wind, wind-direction uncertainty of
15 degrees, speed floor of 1 m/s) and
``real_check_linear.build`` + ``solve`` (TEMPO sigma x1, no industry clusters, one factor per region and day
type, one background unknown per hour and kind), with ``load_inputs`` replaced by the scene. The research
solves for the backgrounds as unknowns; the package integrates them out, so the posterior of the sources must
agree. The scene has 4 point sources (plus 2 industry clusters that the baseline drops), 18 road cells in 4
regions (the last one empty), 5 stations and 6 TEMPO pixels; the hours cover the three day types, a holiday,
a night hour, hours without stations or pixels and winds under the speed floor. The research solves only the
hours that have station rows (``used_hours``), so an hour with TEMPO pixels but no station is left out of its
posterior.
"""

import os
import sys
from pathlib import Path

# the baseline configuration of the research modules is read from the environment at import time
os.environ.update(SIGMA_THETA_DEG="15", U_MIN="1.0", TEMPO_SIGMA_MULT="1")

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).with_name("baseline_reference.npz")
N_REGIONS = 4
N_STATIONS = 5
N_PIXELS = 6
RATIO = 0.8  # NO2/NOx
HOURS = [  # UTC; Mon 20 Nov 2023 is a holiday, local time is UTC-6
    *(f"2023-11-{d} {h}:00" for d in (17, 18, 19, 20) for h in (18, 19, 20, 21)),
    "2023-11-20 05:00",  # 23 h local on Sunday
    "2023-11-21 19:00",  # Tuesday
]
X0, Y0 = 480_000.0, 2_130_000.0  # UTM-like metres


def scene(rng: np.random.Generator) -> dict:
    n = len(HOURS)
    speed = rng.uniform(0.2, 4.0, n)  # some under the 1 m/s floor
    angle = rng.uniform(0, 2 * np.pi, n)
    present = rng.random((n, N_STATIONS)) < 0.8
    present[3] = False  # an hour without stations
    pixels_in = rng.random(n) < 0.6
    pixels_in[5] = False
    pixels_in[0] = True
    return dict(
        u=speed * np.cos(angle),
        v=speed * np.sin(angle),
        pbl=rng.uniform(300, 1500, n),
        station_present=present,
        pixels_present=pixels_in,
        point_x=X0 + rng.uniform(0, 20_000, 4),
        point_y=Y0 + rng.uniform(0, 20_000, 4),
        point_prior=np.array([277.0, 2615.0, 500.0, 500.0]),
        point_sd=np.array([277.0, 2615.0, 1000.0, 1000.0]),
        cell_x=X0 + rng.uniform(0, 20_000, 18),
        cell_y=Y0 + rng.uniform(0, 20_000, 18),
        cell_prior=rng.uniform(5, 50, 18),
        cell_region=rng.integers(0, N_REGIONS - 1, 18),  # region 3 stays empty
        station_x=X0 + rng.uniform(0, 20_000, N_STATIONS),
        station_y=Y0 + rng.uniform(0, 20_000, N_STATIONS),
        pixel_x=X0 + rng.uniform(0, 20_000, N_PIXELS),
        pixel_y=Y0 + rng.uniform(0, 20_000, N_PIXELS),
        nox=rng.uniform(5, 80, (n, N_STATIONS)),
        vcd=rng.uniform(2e15, 2e16, (n, N_PIXELS)),
    )


def main(research: Path) -> None:
    sys.path.insert(0, str(research / "scripts"))
    import feasibility_linear as fl  # type: ignore
    import real_check_linear as rcl  # type: ignore

    s = scene(np.random.default_rng(2026))
    hours = pd.DatetimeIndex(HOURS)
    ids = [f"S{i}" for i in range(N_STATIONS)]
    # two industry clusters first, which `no_industry` drops
    x = np.r_[X0 + 3_000, X0 + 9_000, s["point_x"]]
    y = np.r_[Y0 + 4_000, Y0 + 7_000, s["point_y"]]
    cand = gpd.GeoDataFrame(
        {
            "tipo": [
                "industria",
                "industria",
                "central eléctrica",
                "central eléctrica",
                "aeropuerto",
                "aeropuerto",
            ],
            "nombre": [f"P{i}" for i in range(6)],
        },
        geometry=gpd.points_from_xy(x, y),
    )
    prior_pt = np.r_[100.0, 200.0, s["point_prior"]]
    sd_pt = np.r_[100.0, 200.0, s["point_sd"]]
    cells = pd.DataFrame(
        {"x": s["cell_x"], "y": s["cell_y"], "w": s["cell_prior"], "region": s["cell_region"]}
    )
    cells.attrs["n_reg"] = N_REGIONS
    prior_rd = cells.groupby("region").w.sum().reindex(range(N_REGIONS)).fillna(0.0).to_numpy()
    st = gpd.GeoDataFrame(geometry=gpd.points_from_xy(s["station_x"], s["station_y"]), index=ids)

    nox = pd.DataFrame(
        [
            {"h": h, "id_station": ids[j], "NOX": s["nox"][k, j], "est": False}
            for k, h in enumerate(hours)
            for j in range(N_STATIONS)
            if s["station_present"][k, j]
        ]
    )
    px = pd.DataFrame(
        [
            {"h": h, "x": s["pixel_x"][j], "y": s["pixel_y"][j], "vcd": s["vcd"][k, j]}
            for k, h in enumerate(hours)
            for j in range(N_PIXELS)
            if s["pixels_present"][k]
        ]
    )
    wind = pd.DataFrame({"u": s["u"], "v": s["v"]}, index=hours)
    pbl = pd.Series(s["pbl"], index=hours)

    out = {k: v for k, v in s.items()}
    out.update(hours=np.array(HOURS), ratio=RATIO, holidays=np.array(sorted(rcl.HOLIDAYS)))
    # Jacobian of every hour, as `feasibility_linear.jacobian_hour` returns it (points | regions)
    for k, h in enumerate(hours):
        blocks = dict(
            fl.jacobian_hour(
                h,
                wind.loc[h].values,
                pbl.loc[h],
                cand.iloc[2:].reset_index(drop=True),
                cells,
                st,
                nox[nox.h == h],
                px[px.h == h],
                RATIO,
            )
        )
        out[f"stations_{k}"] = blocks.get("st", np.zeros((0, 4 + N_REGIONS)))
        out[f"pixels_{k}"] = blocks.get("tp", np.zeros((0, 4 + N_REGIONS)))

    # posterior of the sources, with the backgrounds as unknowns
    rcl.load_inputs = lambda *_args, **_kw: (  # type: ignore
        cand,
        prior_pt,
        sd_pt,
        cells,
        prior_rd,
        0.5 * prior_rd,
        st,
        nox,
        RATIO,
        wind,
        pbl,
        px,
    )
    m = rcl.build("2023-11-01", "2023-12-31", "domain", no_industry=True)
    n_src = m["n_pt"] + 3 * m["n_reg"]
    precision, rhs = rcl.solve(m)
    cov = np.linalg.inv(precision)
    out.update(
        mean=(cov @ rhs)[:n_src], cov=cov[:n_src, :n_src], used_hours=np.array([str(h) for h in m["hours"]])
    )
    np.savez_compressed(OUT, **out)
    print(f"{len(HOURS)} hours -> {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
