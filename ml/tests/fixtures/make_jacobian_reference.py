"""Rebuilds ``jacobian_reference.npz``: a small synthetic scene and what the research code computes for it.

Usage: git worktree add /tmp/research research-archive
       uv run python ml/tests/fixtures/make_jacobian_reference.py /tmp/research

The reference is ``puffs_cdmx.jacobian_puff_mx`` of the research-archive branch in the standard configuration
of ``scripts/pinn/invert.py``: 24 h puffs, OH-based lifetime, transport speed floor of 2 m/s, wind direction
uncertainty of 30 degrees, and the road profile ``vida_quimica.extended_profile``. The scene has 3 point
sources, 30 road cells in 4 zones (the last one empty), 5 stations and 7 TEMPO pixels; the target hours cover
the three day types, a night hour, an hour without pixels, an hour without stations, and puffs older than
the wind record. The infovial profile is read from ``data/interim/puffs_cdmx`` (needs `dvc pull`).
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).with_name("jacobian_reference.npz")
N_ZONES = 4
RATIO = 0.8  # NO2/NOx
# (hour, stations present, pixels present). Mon 20 Nov 2023 is a holiday.
TARGETS = [
    ("2023-11-17 19:00", True, True),  # Friday, 19 h of wind record before it
    ("2023-11-18 19:00", True, True),  # Saturday
    ("2023-11-19 19:00", True, True),  # Sunday
    ("2023-11-20 19:00", True, True),  # holiday Monday
    ("2023-11-20 07:00", True, False),  # 01 h local, no TEMPO at night
    ("2023-11-19 20:00", False, True),  # Sunday, stations missing
]


def scene(rng: np.random.Generator) -> dict:
    hours = pd.date_range("2023-11-17 00:00", "2023-11-21 00:00", freq="h")
    u = 2.5 * np.sin(np.arange(len(hours)) / 7) + rng.normal(0, 0.7, len(hours))
    v = 1.5 * np.cos(np.arange(len(hours)) / 9) + rng.normal(0, 0.7, len(hours))
    u[40:43], v[40:43] = 0.0, 0.0  # calm
    u[60:62], v[60:62] = np.nan, np.nan  # gap, interpolated
    local = (hours + pd.Timedelta(hours=-6)).hour.to_numpy()
    sun = np.clip(np.sin(np.pi * (local - 6) / 12), 0, None)
    x0, y0 = 480_000.0, 2_130_000.0  # UTM-like metres
    cells_x, cells_y = x0 + rng.uniform(0, 20_000, 30), y0 + rng.uniform(0, 20_000, 30)
    return dict(
        hours=hours,
        u=u,
        v=v,
        pbl=rng.uniform(300, 1500, len(hours)),
        loss_rate=4.7e-5 * sun * rng.uniform(0.7, 1.3, len(hours)),  # 1/s, like the OH-based loss
        point_x=x0 + rng.uniform(0, 20_000, 3),
        point_y=y0 + rng.uniform(0, 20_000, 3),
        cell_x=cells_x,
        cell_y=cells_y,
        cell_prior=rng.uniform(5, 50, 30),
        cell_zone=rng.integers(0, N_ZONES - 1, 30),  # zone 3 stays empty
        station_x=x0 + rng.uniform(0, 20_000, 5),
        station_y=y0 + rng.uniform(0, 20_000, 5),
        pixel_x=x0 + rng.uniform(0, 20_000, 7),
        pixel_y=y0 + rng.uniform(0, 20_000, 7),
    )


def main(research: Path) -> None:
    sys.path.insert(0, str(research / "scripts"))
    import feasibility_linear as fl  # type: ignore
    import puff  # type: ignore
    import puffs_cdmx as pc  # type: ignore
    import real_check_linear as rcl  # type: ignore
    import vida_quimica as vq  # type: ignore

    s = scene(np.random.default_rng(2024))
    wind = pd.DataFrame({"u": s["u"], "v": s["v"]}, index=s["hours"])
    cand = gpd.GeoDataFrame(geometry=gpd.points_from_xy(s["point_x"], s["point_y"]))
    cells = pd.DataFrame({"x": s["cell_x"], "y": s["cell_y"], "w": s["cell_prior"], "region": s["cell_zone"]})
    cells.attrs["n_reg"] = N_ZONES
    ids = [f"S{i}" for i in range(5)]
    st = gpd.GeoDataFrame(geometry=gpd.points_from_xy(s["station_x"], s["station_y"]), index=ids)

    # standard configuration, as `vida_quimica.apply_variant(STANDARD)` leaves the research modules
    puff.MAX_AGE_H, puff.TAU_CHEM_H = 24, 4.0
    puff.LOSS_RATE = pd.Series(s["loss_rate"], s["hours"])
    puff._loss_cache.clear()
    puff.SIGMA_THETA = fl.SIGMA_THETA
    assert fl.U_MIN == 2.0 and np.isclose(fl.SIGMA_THETA, np.deg2rad(30))
    tr = pc.Transport("domain", vq.extended_profile(), traj=puff.Trajectories(wind))

    out = {k: v for k, v in s.items() if k not in ("hours",)}
    out.update(
        t0=str(s["hours"][0]),
        ratio=RATIO,
        holidays=np.array(sorted(rcl.HOLIDAYS)),
        infovial=np.array([[pc.infovial_profile()[d][h] for h in range(24)] for d in range(3)]),
        targets=np.array([t for t, _, _ in TARGETS]),
        stations_present=np.array([a for _, a, _ in TARGETS]),
        pixels_present=np.array([b for _, _, b in TARGETS]),
    )
    for k, (hour, with_st, with_px) in enumerate(TARGETS):
        h = pd.Timestamp(hour)
        nox_h = pd.DataFrame({"id_station": ids if with_st else []})
        px_h = pd.DataFrame({"x": s["pixel_x"], "y": s["pixel_y"]}).iloc[: 7 if with_px else 0]
        blocks = dict(
            pc.jacobian_puff_mx(
                h,
                tr,
                wind.loc[h].values,
                s["pbl"][s["hours"].get_loc(h)],
                cand,
                cells,
                st,
                nox_h,
                px_h,
                RATIO,
            )
        )
        out[f"stations_{k}"] = blocks.get("st", np.zeros((0, 3 + N_ZONES)))
        out[f"pixels_{k}"] = blocks.get("tp", np.zeros((0, 3 + N_ZONES)))
    np.savez_compressed(OUT, **out)
    print(f"{len(TARGETS)} hours -> {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
