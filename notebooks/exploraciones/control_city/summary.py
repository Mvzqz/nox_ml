# ruff: noqa: E501
"""Print the tables of `context/knowledge/ciudad_control.md` from the `compare_*.json` files in `out/`.

Usage: .venv/bin/python notebooks/exploraciones/control_city/summary.py
"""

import json
from pathlib import Path

OUT = Path(__file__).parent / "out"


def f(x: object, d: int = 2) -> str:
    return "—" if x is None or x != x else f"{x:.{d}f}"  # type: ignore[operator]


def main() -> None:
    print(
        "| Temporada | Serie | Días normales | Semanas | Deriva semanal | Deriva 9 días | CV diario | Domingo | Placebo 9 d | MDC temporada |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|")
    files = sorted(OUT.glob("compare_*_tau_2h.json"))
    for p in files:
        d = json.loads(p.read_text())
        s = f"{d['start'][:7]}–{d['end'][:7]}"
        for name, r in d["cities"].items():
            print(
                f"| {s} | {name} | {r['n_days']} | {r['n_weeks']} | {f(r['drift'])} | {f(r['block_drift'])} "
                f"| {f(r['cv'])} | {f(r['sunday'])} | {f(r['placebo_9d'])} | {f(r['mdc_season'] * 100, 0)} % |"
            )
    print()
    print(
        "| Temporada | Control | Referencia ZMVM | r semanal | r diario | Días pareados | Deriva semanal ZMVM (pareados) | Deriva semanal diferencia | Deriva 9 días ZMVM (pareados) | Deriva 9 días diferencia | MDC temporada diferencia |"
    )
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for p in files:
        d = json.loads(p.read_text())
        s = f"{d['start'][:7]}–{d['end'][:7]}"
        for name, r in d["cities"].items():
            for ref in ("zmvm", "zmvm_official"):
                x = r.get(f"diff_{ref}")
                if not x:
                    continue
                print(
                    f"| {s} | {name} | {ref} | {f(r[f'r_weekly_{ref}'])} | {f(x['r_daily'])} | {x['n_paired_days']} "
                    f"| {f(x['ref_weekly_drift_paired'])} | {f(x['weekly_drift_paired'])} "
                    f"| {f(x['ref_block_drift_paired'])} | {f(x['block_drift'])} | {f(x['mdc_season'] * 100, 0)} % |"
                )


if __name__ == "__main__":
    main()
