"""Transporte con el núcleo PINN (kernel.py) en el mismo formato que la inversión lineal.

`jacobian_hour_pinn` tiene la firma de feasibility_linear.jacobian_hour, así que se enchufa en
real_check_linear.build sin tocar los scripts compartidos. Diferencias con la pluma gaussiana:
  - horizontal: columna de la ecuación de advección–difusión aprendida por la red (difusión K = κ|u|
    en lugar del ancho de Briggs + σθ; hay algo de difusión contra el viento; pérdida con vida τ);
  - vertical: igual que la pluma (altura de mezcla efectiva min(√(π/2)·σz, capa límite)), para que
    la comparación aísle el cambio de física horizontal.
"""
import sys
from pathlib import Path

import numpy as np
import torch
from scipy.ndimage import map_coordinates

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import feasibility_linear as fl  # noqa: E402
import kernel as kn  # noqa: E402

TAU_H = 12.0            # vida media de NOₓ en la columna (h); 12 h ≈ sin pérdida en 40 km, como la pluma
_TAB = None


def _table():
    global _TAB
    if _TAB is None:
        z = np.load(kn.OUT / "kernel_table.npz")
        _TAB = (z["a"], z["c"], np.log(z["g"]), z["T"])
    return _TAB


def frame(dx, dy, u, v, tau_h=TAU_H):
    """Coordenadas adimensionales (A, |C|), γ y rapidez efectiva para un viento uniforme."""
    mag = np.hypot(u, v)
    s = fl.speed(mag)
    ex, ey = u / max(mag, 1e-6), v / max(mag, 1e-6)
    a = dx * ex + dy * ey
    c = -dx * ey + dy * ex
    gamma = kn.L / (s * tau_h * 3600)
    return a, c, gamma, s


def column(dx, dy, u, v, tau_h=TAU_H):
    """Columna (g/m²) por 1 g/s y distancia a lo largo del viento (m), con la tabla de la red."""
    a_ax, c_ax, lg_ax, T = _table()
    a, c, gamma, s = frame(dx, dy, u, v, tau_h)
    A, C = a / kn.L, np.abs(c) / kn.L
    gi = np.clip((np.log(gamma) - lg_ax[0]) / (lg_ax[1] - lg_ax[0]), 0, len(lg_ax) - 1)
    ai = (A - a_ax[0]) / (a_ax[1] - a_ax[0])
    ci = C / (c_ax[1] - c_ax[0])
    coords = np.stack([np.full(A.size, gi), ai.ravel(), ci.ravel()])
    F = map_coordinates(T, coords, order=1, mode="constant", cval=0.0).reshape(A.shape)
    return F / (s * kn.L), a


def zeff(a, pbl):
    a = np.maximum(a, 300.0)
    sz = 0.24 * a * np.sqrt(1 + 0.001 * a)
    return np.minimum(np.sqrt(np.pi / 2) * sz, pbl)


def jacobian_hour_pinn(h, uv, pbl_h, cand, cells, st, nox_h, px_h, ratio):
    """Igual que feasibility_linear.jacobian_hour (viento del dominio), con el núcleo PINN."""
    u, v = uv
    xs_p, ys_p = cand.geometry.x.values, cand.geometry.y.values
    blocks = []
    if len(nox_h):
        sxy = st.loc[nox_h.id_station.values].geometry
        xr, yr = sxy.x.values, sxy.y.values
        G, a = column(xr[:, None] - xs_p[None], yr[:, None] - ys_p[None], u, v)
        kp = G / zeff(a, pbl_h) * fl.T_PER_YR_TO_GS * fl.PPB_PER_GM3
        G, a = column(xr[:, None] - cells.x.values[None], yr[:, None] - cells.y.values[None], u, v)
        kr = G / zeff(a, pbl_h) * cells.w.values * fl.T_PER_YR_TO_GS * fl.PPB_PER_GM3
        kr = np.stack([kr[:, cells.region.values == g].sum(1) for g in range(fl.n_reg(cells))], 1)
        blocks.append(("st", np.hstack([kp, kr])))
    if len(px_h):
        xr, yr = px_h.x.values, px_h.y.values
        f = fl.T_PER_YR_TO_GS * fl.MOLEC_CM2_PER_GM2 * ratio
        kp = column(xr[:, None] - xs_p[None], yr[:, None] - ys_p[None], u, v)[0] * f
        kr = column(xr[:, None] - cells.x.values[None], yr[:, None] - cells.y.values[None], u, v)[0] * cells.w.values * f
        kr = np.stack([kr[:, cells.region.values == g].sum(1) for g in range(fl.n_reg(cells))], 1)
        blocks.append(("tp", np.hstack([kp, kr])))
    return blocks


class JointPairs:
    """Pares estación–fuente de una hora para el entrenamiento conjunto (red viva, no la tabla)."""

    def __init__(self, h, uv, pbl_h, cand, cells, st, nox_h, n_pt):
        u, v = uv
        sxy = st.loc[nox_h.id_station.values].geometry
        xr, yr = sxy.x.values, sxy.y.values
        xs = np.r_[cand.geometry.x.values, cells.x.values]
        ys = np.r_[cand.geometry.y.values, cells.y.values]
        a, c, gamma, s = frame(xr[:, None] - xs[None], yr[:, None] - ys[None], u, v)
        A, C = a / kn.L, c / kn.L
        keep = (A > kn.A_RANGE[0]) & (A < kn.A_RANGE[1]) & (np.abs(C) < kn.C_MAX)
        w = np.r_[np.ones(n_pt), cells.w.values]  # puntos en t/año; celdas × a priori (factor α)
        coef = w[None] * fl.T_PER_YR_TO_GS * fl.PPB_PER_GM3 / (s * kn.L * zeff(a, pbl_h))
        col = np.r_[np.arange(n_pt), n_pt + cells.region.values]  # columna local: punto o región
        ri, si = np.nonzero(keep)
        self.A = torch.tensor(A[ri, si], dtype=torch.float32)
        self.C = torch.tensor(C[ri, si], dtype=torch.float32)
        self.g = torch.full((len(ri),), float(gamma))
        self.coef = torch.tensor(coef[ri, si], dtype=torch.float32)
        self.row = torch.tensor(ri)
        self.col = torch.tensor(col[si])
        self.n_rows, self.n_cols = len(xr), n_pt + fl.n_reg(cells)

    def jac(self, model):
        F = model(self.A, self.C, self.g) * self.coef
        K = torch.zeros(self.n_rows * self.n_cols)
        K.index_add_(0, self.row * self.n_cols + self.col, F)
        return K.view(self.n_rows, self.n_cols)
