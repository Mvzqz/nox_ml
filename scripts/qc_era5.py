"""QC de ERA5 (capa límite y viento 10 m) vía Open-Meteo, y contraste con REDMET.

Uso: .venv/bin/python scripts/qc_era5.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
d = json.loads((ROOT / "data/raw/era5_openmeteo/pbl_wind_center_2023-2024.json").read_text())
e = pd.DataFrame(d["hourly"])
e["utc"] = pd.to_datetime(e.time)
e["local_h"] = (e.utc - pd.Timedelta(hours=6)).dt.hour
lines = [f"# QC ERA5 (Open-Meteo, celda {d['latitude']}, {d['longitude']})\n"]


def check(ok, msg):
    lines.append(f"- {'✅' if ok else '❌'} {msg}")


prof = e.groupby("local_h").boundary_layer_height.median()
day = prof.loc[12:17]
night = prof.loc[[0, 1, 2, 3, 4, 5, 22, 23]]
check(day.between(1000, 3000).all(), f"PBL 12–17 h: {day.min():.0f}–{day.max():.0f} m (meta 1,000–3,000)")
check((night < 600).all(), f"PBL nocturna: máx {night.max():.0f} m (meta < 600)")
check(14 <= prof.idxmax() <= 16, f"Máximo de PBL a las {prof.idxmax()} h local (meta 14–16)")


def vec_dir(ws, wd):
    r = np.deg2rad(wd)
    return (np.rad2deg(np.arctan2((ws * np.sin(r)).mean(), (ws * np.cos(r)).mean())) + 360) % 360


ea = e[e.local_h.between(12, 17)]
w = pd.read_parquet(ROOT / "data/interim/simat_wind.parquet")
w = w[w.utc.between(e.utc.min(), e.utc.max()) & w.local.dt.hour.between(12, 17)].dropna(subset=["WSP", "WDR"])
de, dr = vec_dir(ea.wind_speed_10m, ea.wind_direction_10m), vec_dir(w.WSP, w.WDR)
diff = abs((de - dr + 180) % 360 - 180)
check(diff < 45, f"Dirección dominante tarde: ERA5 {de:.0f}°, REDMET {dr:.0f}° (dif {diff:.0f}°)")
# por mes
lines.append("\n| Mes | ERA5 ° | REDMET ° | ERA5 m/s | REDMET m/s |\n|---|---|---|---|---|")
for m, g in ea.groupby(ea.utc.dt.to_period("M")):
    gw = w[w.utc.dt.to_period("M") == m]
    lines.append(f"| {m} | {vec_dir(g.wind_speed_10m, g.wind_direction_10m):.0f} | {vec_dir(gw.WSP, gw.WDR):.0f} | "
                 f"{g.wind_speed_10m.mean():.1f} | {gw.WSP.mean():.1f} |")
lines.append("\nPerfil diario mediano de PBL (m, hora local): " + ", ".join(f"{h}h={v:.0f}" for h, v in prof.items()))
(ROOT / "reports/qc_era5.md").write_text("\n".join(lines) + "\n")
print("\n".join(lines))
