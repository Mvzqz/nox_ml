"""Banco datos-vs-desempeño, parte 3: síntesis, regla para ciudades nuevas y figuras (reports/banco_datos.md).

Lee data/interim/fichas_datos.json y data/interim/benchmark/{twin,real,bogota}.json, más los resultados de LA
(data/interim/la/la_estandar_zonas_tp3.json). Imprime las tablas en Markdown y guarda reports/figs/banco_*.png.

Regla para el estimador normalizado (cambio mínimo detectable = ancho del placebo):
    placebo ≈ c · CV · √(1/k + 1/(n − k))
con CV = variación día a día del cociente observado/modelo en los hábiles, k = domingos y n = hábiles del periodo.
c se ajusta con todas las configuraciones medidas (CDMX y sus degradaciones, Bogotá) y se valida en LA.
"""
import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
B = ROOT / "data/interim/benchmark"
FIG = ROOT / "reports/figs"


def load(p):
    return json.loads(p.read_text()) if p.exists() else None


def pct(v):
    return f"{100 * v:.0f} %"


def seeds_mean(res, prefix, key, sub=None):
    vals = []
    for k, r in res.items():
        if k.startswith(prefix + "_s") and k[len(prefix) + 2:].isdigit():
            v = r[sub][key] if sub else r[key]
            vals.append(v)
    return (float(np.mean(vals)), float(np.min(vals)), float(np.max(vals))) if vals else (np.nan, np.nan, np.nan)


def rule_x(r):
    k, n = r["n_domingos"], r["n_habiles"]
    return r["norm_cv_habiles"] * np.sqrt(1 / k + 1 / (n - k))


def main():
    fichas = load(ROOT / "data/interim/fichas_datos.json")
    twin = load(B / "twin.json")
    real = load(B / "real.json")
    bog = load(B / "bogota.json")
    la = load(ROOT / "data/interim/la/la_estandar_zonas_tp3.json")
    L = []

    # ---------------- fichas
    L += ["## Fichas\n", "| | CDMX | Los Ángeles | Bogotá |", "|---|---|---|---|"]
    c = list(fichas)
    def f(path):
        keys = [k.strip("'") for k in path.strip("[]").split("][")]
        out = []
        for x in c:
            v = fichas[x]
            for k in keys:
                v = v[k]
            out.append(v)
        return out
    L.append("| Estaciones de NOₓ | " + " | ".join(str(v) for v in f("['estaciones_nox']['n']")) + " |")
    L.append("| Densidad (por 1,000 km² del dominio) | " + " | ".join(f"{v} ({d:,} km²)" for v, d in zip(
        f("['estaciones_nox']['densidad_por_1000km2']"), f("['estaciones_nox']['dominio_km2']"))) + " |")
    L.append("| Distancia al vecino más cercano (mediana) | " + " | ".join(f"{v} km" for v in f("['estaciones_nox']['vecino_mas_cercano_km']")) + " |")
    L.append("| Satélite | " + " | ".join(f"{s['tipo']} ({s['pixeles_por_escaneo_mediana']} píxeles/escaneo)" if s["pixeles_por_escaneo_mediana"] else s["tipo"]
                                         for s in f("['satelite']")) + " |")
    L.append("| Error de dirección del viento (validación cruzada): vector medio / IDW / modelo | " + " | ".join(
        f"{w['mean']:.0f}° / {w['idw']:.0f}°" + (f" / {w['hrrr']:.0f}° (HRRR)" if "hrrr" in w else "")
        for w in f("['viento']['error_direccion_loo_grados']")) + " |")
    L.append("| Referencia de tráfico | " + " | ".join(f"{t['fuente']}" + (f" ({t['año']})" if t["año"] else "") for t in f("['trafico']")) + " |")
    L.append("| Capa límite | " + " | ".join(f("['capa_limite']")) + " |")
    L.append("| Inventario | " + " | ".join(f("['inventario']")) + " |")

    # ---------------- gemelos
    if twin:
        R = twin["resultados"]
        L += ["\n## Gemelos\n", "| Verdad | Viento σ | Configuración | Error por zona | p90 zona | Error total | Error domingo | Error CDMX/Edomex | |corr| máx. | σ post/prior |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for key, r in R.items():
            if any(key.endswith(f"_s{s}") for s in range(1, 10)):
                continue
            L.append(f"| {r['verdad']} | {r['sigma_viento']}° | {r['config']} | {pct(r['error_zona'])} | {pct(r['error_zona_p90'])} | "
                     f"{pct(r['error_total'])} | {pct(r['error_domingo'])} | {pct(r['error_cdmx_edomex'])} | {r['corr_max']:.2f} | {r['sd_rel_mediana']:.2f} |")
        L += ["\nSubconjuntos de estaciones (media de 5; rango):\n",
              "| Verdad | Configuración | Error por zona | Error total | Error domingo | |corr| máx. |", "|---|---|---|---|---|---|"]
        for truth in ("ideal", "realista"):
            for pre in ("est15", "est15_sin_tempo", "est9", "est9_sin_tempo"):
                sub = {k.split("|")[2]: v for k, v in R.items() if k.startswith(f"{truth}|30|")}
                cells = []
                for met in ("error_zona", "error_total", "error_domingo", "corr_max"):
                    mu, lo, hi = seeds_mean(sub, pre, met)
                    cells.append(f"{mu:.2f} ({lo:.2f}–{hi:.2f})" if met == "corr_max" else f"{pct(mu)} ({pct(lo)}–{pct(hi)})")
                L.append(f"| {truth} | {pre} | " + " | ".join(cells) + " |")

    # ---------------- datos reales
    if real:
        R = real["resultados"]
        L += ["\n## Datos reales CDMX\n", f"Configuración: {json.dumps({k: v for k, v in real['configuracion'].items() if k != 'estaciones_nox'}, ensure_ascii=False)}\n",
              "| Configuración | Fuera de muestra: modelo / IDW / híbrido (ppb) | Normalizado domingo (IC) | Placebo ± | CV hábiles | Domingo inversión libre / restringida | Vial/a priori | Spearman EDGAR |",
              "|---|---|---|---|---|---|---|---|"]
        for k in ("base", "sin_tempo", "sin_restriccion", "viento+20", "viento+30"):
            if k not in R:
                continue
            r = R[k]
            o = r["fuera_de_muestra"]
            lo, hi = r["norm_domingo_ic"]
            L.append(f"| {k} | {o['model']:.1f} / {o['idw']:.1f} / {o['hybrid']:.1f} | {r['norm_domingo']:.2f} ({lo:.2f}–{hi:.2f}) | "
                     f"±{r['placebo_mitad_ancho']:.2f} | {r['norm_cv_habiles']:.2f} | {r['domingo_libre']:.2f} / {r['domingo_inversion']:.2f} | "
                     f"{r['vial_habil_sobre_apriori']:.0%} | {r['spearman_edgar_total']:.2f} |")
        if "caja" in R:
            r = R["caja"]
            L.append(f"| caja (sin transporte) | – | {r['norm_domingo']:.2f} | ±{r['placebo_mitad_ancho']:.2f} | {r['norm_cv_habiles']:.2f} | – | – | – |")
        L += ["\nSubconjuntos (media de 5 y rango). Fuera de muestra = estaciones no usadas; referencia = la red completa (LOO) en esas mismas estaciones.\n",
              "| Configuración | Modelo | IDW | Híbrido | Referencia red completa: modelo / híbrido | Placebo ± | CV | Domingo libre | Spearman EDGAR |",
              "|---|---|---|---|---|---|---|---|---|"]
        for pre in ("est15", "est15_sin_tempo", "est9", "est9_sin_tempo"):
            m_ = seeds_mean(R, pre, "model", "fuera_de_muestra")
            i_ = seeds_mean(R, pre, "idw", "fuera_de_muestra")
            h_ = seeds_mean(R, pre, "hybrid", "fuera_de_muestra")
            ref = (seeds_mean(R, pre.replace("_sin_tempo", ""), "model", "referencia_red_completa_mismas_estaciones"),
                   seeds_mean(R, pre.replace("_sin_tempo", ""), "hybrid", "referencia_red_completa_mismas_estaciones"))
            pl = seeds_mean(R, pre, "placebo_mitad_ancho")
            cv = seeds_mean(R, pre, "norm_cv_habiles")
            dl = seeds_mean(R, pre, "domingo_libre")
            sp_ = seeds_mean(R, pre, "spearman_edgar_total")
            L.append(f"| {pre} | {m_[0]:.1f} ({m_[1]:.1f}–{m_[2]:.1f}) | {i_[0]:.1f} | {h_[0]:.1f} ({h_[1]:.1f}–{h_[2]:.1f}) | "
                     f"{ref[0][0]:.1f} / {ref[1][0]:.1f} | ±{pl[0]:.2f} ({pl[1]:.2f}–{pl[2]:.2f}) | {cv[0]:.2f} | {dl[0]:.2f} ({dl[1]:.2f}–{dl[2]:.2f}) | "
                     f"{sp_[0]:.2f} ({sp_[1]:.2f}–{sp_[2]:.2f}) |")
        for n in (15, 9):
            pl = seeds_mean(R, f"caja_est{n}", "placebo_mitad_ancho")
            cv = seeds_mean(R, f"caja_est{n}", "norm_cv_habiles")
            if not np.isnan(pl[0]):
                L.append(f"| caja, {n} estaciones | – | – | – | – | ±{pl[0]:.2f} ({pl[1]:.2f}–{pl[2]:.2f}) | {cv[0]:.2f} | – | – |")

    # ---------------- regla
    pts = []  # (nombre, x, placebo, grupo)
    if real:
        R = real["resultados"]
        for k, r in R.items():
            if "placebo_mitad_ancho" in r and "norm_cv_habiles" in r:
                pts.append(("CDMX " + k, rule_x(r), r["placebo_mitad_ancho"], "CDMX"))
    if bog:
        for k, r in bog.items():
            pts.append(("Bogotá " + k, rule_x(r), r["placebo_mitad_ancho"], "Bogotá"))
    if pts:
        x = np.array([p[1] for p in pts])
        y = np.array([p[2] for p in pts])
        cfit = float((x * y).sum() / (x * x).sum())
        resid = y / (cfit * x) - 1
        L += ["\n## Regla\n", f"c ajustado = {cfit:.2f} con {len(pts)} configuraciones (CDMX y Bogotá); error relativo mediano "
              f"{np.median(np.abs(resid)):.0%}, máximo {np.max(np.abs(resid)):.0%}."]
        if la:
            pred = cfit * rule_x(la)
            L.append(f"Validación en LA (no usada en el ajuste): predicho ±{pred:.2f}, medido ±{la['placebo_mitad_ancho']:.2f} "
                     f"(CV {la['norm_cv_habiles']:.2f}, {la['n_domingos']} domingos, {la['n_habiles']} hábiles).")
        # figura 2: regla
        FIG.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(5.2, 4.2))
        col = {"CDMX": "#1d5f8f", "Bogotá": "#9c4a24"}
        for g in col:
            ii = [i for i, p in enumerate(pts) if p[3] == g]
            ax.scatter(x[ii], y[ii], s=18, color=col[g], label=g, alpha=.8)
        if la:
            ax.scatter([rule_x(la)], [la["placebo_mitad_ancho"]], marker="*", s=140, color="#2c7a4b", label="Los Ángeles (validación)")
        xx = np.linspace(0, max(x.max(), rule_x(la) if la else 0) * 1.1, 10)
        ax.plot(xx, cfit * xx, color="gray", lw=1, ls="--", label=f"placebo = {cfit:.1f} · CV · √(1/k + 1/(n−k))")
        ax.set_xlabel("CV de los hábiles · √(1/k + 1/(n−k))")
        ax.set_ylabel("Placebo ± (cambio mínimo detectable)")
        ax.legend(fontsize=7.5, frameon=False)
        ax.set_title("Regla para predecir el cambio mínimo detectable", fontsize=10)
        fig.tight_layout()
        fig.savefig(FIG / "banco_regla.png", dpi=150)

    # figura 1: gemelos, error por zona vs viento
    if twin:
        R = twin["resultados"]
        fig, axs = plt.subplots(1, 2, figsize=(9.6, 3.8))
        for truth, ls in (("ideal", "--"), ("realista", "-")):
            for cfg, colr in (("base", "#1d5f8f"), ("sin_tempo", "#9c4a24")):
                s_ = sorted({r["sigma_viento"] for r in R.values() if r["verdad"] == truth and r["config"] == cfg})
                axs[0].plot(s_, [100 * R[f"{truth}|{s}|{cfg}"]["error_zona"] for s in s_], ls=ls, color=colr, marker="o", ms=4,
                            label=f"{truth}, {'con' if cfg == 'base' else 'sin'} TEMPO")
        axs[0].set_xlabel("Error de dirección del viento simulado (σ, grados)")
        axs[0].set_ylabel("Error mediano por zona (%)")
        axs[0].set_title("Gemelo: ¿cuánto importa el viento?", fontsize=10)
        axs[0].legend(fontsize=7.5, frameon=False)
        sub = {k.split("|")[2]: v for k, v in R.items() if k.startswith("realista|30|")}
        labels, vals = [], []
        for name, pre in (("Base (24 est. + TEMPO)", "base"), ("Sin TEMPO", "sin_tempo"), ("Sin restricción", "sin_restriccion"),
                          ("15 est. + TEMPO", "est15"), ("15 est., sin TEMPO", "est15_sin_tempo"), ("9 est. + TEMPO", "est9"),
                          ("9 est., sin TEMPO", "est9_sin_tempo")):
            if pre in sub:
                v = [sub[pre]["error_zona"], sub[pre]["error_total"], sub[pre]["error_domingo"]]
            else:
                v = [seeds_mean(sub, pre, m_)[0] for m_ in ("error_zona", "error_total", "error_domingo")]
            labels.append(name)
            vals.append(v)
        vals = 100 * np.array(vals)
        yy = np.arange(len(labels))
        for j, (nm, colr) in enumerate((("por zona", "#1d5f8f"), ("total", "#9c4a24"), ("domingo", "#2c7a4b"))):
            axs[1].barh(yy + (j - 1) * 0.27, vals[:, j], height=0.26, color=colr, label=nm)
        axs[1].set_yticks(yy, labels, fontsize=8)
        axs[1].invert_yaxis()
        axs[1].set_xlabel("Error mediano (%) — verdad realista, viento σ = 30°")
        axs[1].set_title("Gemelo: qué pasa al quitar datos", fontsize=10)
        axs[1].legend(fontsize=7.5, frameon=False)
        fig.tight_layout()
        FIG.mkdir(parents=True, exist_ok=True)
        fig.savefig(FIG / "banco_gemelos.png", dpi=150)
    print("\n".join(L))


if __name__ == "__main__":
    main()
