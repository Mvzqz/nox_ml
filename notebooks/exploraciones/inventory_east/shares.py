"""Reproduce the east share of the road emission: inversion runs vs the inventory prior."""

from pathlib import Path

from nox_ml.validation import report_final as r

RUNS = Path("results/runs")
NAMES = [
    "pinn_puff_nonneg",
    "pinn_puff_nonneg.nd2024",
    "pinn_puff_nonneg.fm2025",
    "pinn_puff_nonneg.nd2025",
    "pinn_puff_nonneg.fm2026",
]

if __name__ == "__main__":
    prior = r.region_prior(Path("data"))
    print(prior / prior.sum())
    shares = r.zone_shares({n: RUNS / n for n in NAMES}, prior)
    print(shares[shares.zone == "Oriente"])
