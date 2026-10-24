"""Transporte no estacionario para la inversión lineal: pluma de la hora actual + puffs de horas previas.

- Hora actual: pluma gaussiana truncada a lo emitido en la última hora (along ≤ u·3600 s).
- Horas previas (hasta MAX_AGE_H): sub-puffs cada 15 min que viajan con la secuencia real de
  vientos horarios (vector del dominio), se dispersan con la distancia recorrida, se mezclan en la
  capa límite de la hora objetivo y decaen químicamente (vida media TAU_CHEM_H).
- La emisión vial sigue un perfil horario típico (supuesto); las fuentes puntuales son constantes.
"""
import numpy as np
import pandas as pd

import feasibility_linear as fl
from feasibility_linear import (MOLEC_CM2_PER_GM2, PPB_PER_GM3, SIGMA_THETA, T_PER_YR_TO_GS, U_MIN, plume)

MAX_AGE_H = 6
SUB_PER_H = 4
TAU_CHEM_H = 4.0
# Vida química variable (vida_quimica.py): serie horaria UTC de la tasa de pérdida de NOₓ (1/s). Con None se usa la
# vida constante TAU_CHEM_H (comportamiento original).
LOSS_RATE = None
_loss_cache = {}
SIGMA0 = 500.0
# Perfil horario de tráfico (hora local -> factor relativo a la media diaria). Supuesto típico urbano.
PROFILE = {6: 0.9, 7: 1.5, 8: 1.6, 9: 1.4, 10: 1.2, 11: 1.2, 12: 1.2, 13: 1.25, 14: 1.3, 15: 1.3, 16: 1.35, 17: 1.45}


class Trajectories:
    """Desplazamiento y distancia recorrida integrando el viento horario del dominio."""

    def __init__(self, wind):
        idx = pd.date_range(wind.index.min(), wind.index.max(), freq="h")
        full = wind.reindex(idx).interpolate(limit=3).fillna(0.0)
        self.t0 = idx[0]
        sp = np.hypot(full.u.values, full.v.values)
        self.cx = np.r_[0, np.cumsum(full.u.values * 3600)]
        self.cy = np.r_[0, np.cumsum(full.v.values * 3600)]
        self.cs = np.r_[0, np.cumsum(fl.speed(sp) * 3600)]
        self.k = np.arange(len(self.cx))

    def t(self, h):
        return (h - self.t0) / pd.Timedelta(hours=1)

    def between(self, t_from, t_to):
        f = lambda c, t: np.interp(t, self.k, c)
        return (f(self.cx, t_to) - f(self.cx, t_from), f(self.cy, t_to) - f(self.cy, t_from),
                f(self.cs, t_to) - f(self.cs, t_from))


def _decay(clock, t_rel, t_target, age_h):
    """Fracción de NOₓ que sobrevive entre t_rel y t_target (horas desde clock.t0)."""
    if LOSS_RATE is None:
        return np.exp(-age_h / TAU_CHEM_H)
    key = (id(LOSS_RATE), clock.t0)
    if key not in _loss_cache:
        idx = pd.date_range(clock.t0 - pd.Timedelta(hours=1), periods=len(clock.k) + 2, freq="h")
        k = LOSS_RATE.reindex(idx).interpolate(limit_direction="both").fillna(0.0).values
        _loss_cache[key] = np.r_[0, np.cumsum(k * 3600)]          # Λ en horas -1, 0, 1, …
    lam = _loss_cache[key]
    f = lambda t: np.interp(t + 1, np.arange(len(lam)), lam)
    return np.exp(-(f(t_target) - f(t_rel)))


def _puffs(xs, ys, xr, yr, traj, t_target, pbl_h, weights_fn, extra_sy):
    """Suma de sub-puffs de edades 1–MAX_AGE_H h. Devuelve (suelo g/m³, columna g/m²) por 1 g/s."""
    g = np.zeros((len(xr), len(xs)))
    c = np.zeros((len(xr), len(xs)))
    dt = 3600 / SUB_PER_H
    ages = 1 + (np.arange(MAX_AGE_H * SUB_PER_H) + 0.5) / SUB_PER_H
    for a in ages:
        t_rel = t_target - a
        dx, dy, L = traj.between(t_rel, t_target)
        w = weights_fn(t_rel)  # perfil de emisión en el momento de liberación (escalar o por fuente)
        sy2 = (0.32 * L / np.sqrt(1 + 0.0004 * L)) ** 2 + (SIGMA_THETA * L) ** 2 + SIGMA0 ** 2 + extra_sy ** 2
        sz = 0.24 * L * np.sqrt(1 + 0.001 * L)
        zeff = min(np.sqrt(np.pi / 2) * sz, pbl_h)
        r2 = (xr[:, None] - (xs[None, :] + dx)) ** 2 + (yr[:, None] - (ys[None, :] + dy)) ** 2
        col = w * dt * np.exp(-r2 / (2 * sy2)) / (2 * np.pi * sy2) * _decay(traj, t_rel, t_target, a)
        c += col
        g += col / zeff
    return g, c


def jacobian_hour_puff(h, traj, wind_h, pbl_h, cand, cells, st, nox_h, px_h, ratio, local_offset_h=-6):
    """Igual que feasibility_linear.jacobian_hour, con transporte no estacionario."""
    t_target = traj.t(h) + 0.5
    xs_p, ys_p = cand.geometry.x.values, cand.geometry.y.values
    xs_c, ys_c = cells.x.values, cells.y.values
    u, v = wind_h
    reach = float(fl.speed(np.hypot(u, v))) * 3600
    prof_now = PROFILE.get((h + pd.Timedelta(hours=local_offset_h)).hour, 1.0)

    def road_profile(t_rel):
        hr = (traj.t0 + pd.Timedelta(hours=float(np.floor(t_rel))) + pd.Timedelta(hours=local_offset_h)).hour
        return PROFILE.get(hr, 1.0)

    blocks = []
    for kind, rows in (("st", nox_h), ("tp", px_h)):
        if not len(rows):
            continue
        if kind == "st":
            sxy = st.loc[rows.id_station.values].geometry
            xr, yr, extra = sxy.x.values, sxy.y.values, 0.0
        else:
            xr, yr, extra = rows.x.values, rows.y.values, 1300.0
        gp, cp = plume(xs_p, ys_p, xr, yr, u, v, pbl_h, extra_sy=extra, x_max=reach)
        gr, cr = plume(xs_c, ys_c, xr, yr, u, v, pbl_h, extra_sy=extra, x_max=reach)
        gp2, cp2 = _puffs(xs_p, ys_p, xr, yr, traj, t_target, pbl_h, lambda t: 1.0, extra)
        gr2, cr2 = _puffs(xs_c, ys_c, xr, yr, traj, t_target, pbl_h, road_profile, extra)
        if kind == "st":
            f = T_PER_YR_TO_GS * PPB_PER_GM3
            kp = (gp + gp2) * f
            kr = (gr * prof_now + gr2) * cells.w.values * f
        else:
            f = T_PER_YR_TO_GS * MOLEC_CM2_PER_GM2 * ratio
            kp = (cp + cp2) * f
            kr = (cr * prof_now + cr2) * cells.w.values * f
        kr = np.stack([kr[:, cells.region.values == g].sum(1) for g in range(fl.n_reg(cells))], 1)
        blocks.append((kind, np.hstack([kp, kr])))
    return blocks
