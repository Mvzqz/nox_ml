"""A priori corregidos para las centrales (Valle de México en Acolman, Nonoalco) y su efecto en la inversión real.

A priori original (point_candidates.py): 2 % del NOₓ total repartido por capacidad de WRI GPPD, que incluye las
unidades de vapor de Valle de México (450 MW, retiradas en 2021–2022) y no el ciclo combinado Valle de México II
(615 MW, 2018). A priori corregido: generación y factor de emisión de Climate TRACE v5.10 (ver
reports/centrales_generacion.md).

Se reutiliza la base de improve_real (industria agrupada + estaciones extra, nov–dic 2023). El jacobiano no
depende del a priori, así que solo se cambian xa y sa de las centrales.

Uso: .venv/bin/python scripts/centrales_prior_real.py
Salida: reports/centrales_prior_real_2023-11-01_2023-12-31.md (tabla)
"""
from pathlib import Path

import numpy as np

import improve_real as ir
import real_check_linear as rcl

ROOT = Path(__file__).resolve().parents[1]
START, END = ir.START, ir.END

# (media, σ) en t/año
PRIORS = {
    "original": {"Valle de México": (2615, 2615), "Nonoalco": (277, 277)},
    "corregido": {"Valle de México": (1600, 650), "Nonoalco": (100, 100)},
    "débil (solo datos)": {"Valle de México": (1600, 16000), "Nonoalco": (100, 1000)},
}
CONFIGS = [
    ("S2", "σθ = 30°", dict(sigma30=True)),
    ("S5", "σθ = 30° + viento ponderado + Acolman elevada 200 m", dict(sigma30=True, weighted=True, stack=True)),
]


def set_priors(m, pri):
    names = list(m["cand"].nombre)
    for key, (mu, sd) in pri.items():
        i = next(i for i, nm in enumerate(names) if key in nm)
        m["xa"][i], m["sa"][i] = mu, sd


def main():
    lines = ["| Configuración | A priori | Valle de México (Acolman) | Nonoalco | AICM | AIFA | Vial / inventario | "
             "RMSE LOO modelo / híbrido (ppb) | Domingo/hábil |",
             "|---|---|---|---|---|---|---|---|---|"]
    for code, label, cfg in CONFIGS:
        ir.configure(**cfg)
        m = rcl.build(START, END, "domain", no_industry=True, extras=True)
        names = list(m["cand"].nombre)
        for pname, pri in PRIORS.items():
            set_priors(m, pri)
            N, b = rcl.solve(m)
            x = np.linalg.solve(N, b)
            sd = np.sqrt(np.diag(np.linalg.inv(N)))
            f = lambda key: (lambda i: f"{x[i]:,.0f} ± {sd[i]:,.0f}")(next(i for i, nm in enumerate(names) if key in nm))
            r = ir.evaluate(m)
            line = (f"| {code}. {label} | {pname} | {f('Valle de México')} | {f('Nonoalco')} | {f('AICM')} | {f('AIFA')} | "
                    f"{r['inv']:.0%} | {r['rm']:.1f} / {r['rh']:.1f} | {r['sun']:.2f} ({r['lo']:.2f}–{r['hi']:.2f}) |")
            lines.append(line)
            print(line, flush=True)
    ir.configure()
    out = ROOT / f"reports/centrales_prior_real_{START}_{END}.md"
    out.write_text("# Centrales con a priori corregido (datos reales)\n\n" + "\n".join(lines) +
                   "\n\nValores en t/año (posterior ± σ posterior). Ver reports/centrales_generacion.md.\n")


if __name__ == "__main__":
    main()
