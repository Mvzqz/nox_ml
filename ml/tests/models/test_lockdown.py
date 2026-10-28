# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""The lockdown validation: phase over base by year, difference in differences and the mobility reference."""

from dataclasses import replace

import pandas as pd
import pytest
from typer.testing import CliRunner
from ventilation_synthetic import ventilation_inputs

from nox_ml import cli
from nox_ml.inversion.linear import BACKGROUND_STATION
from nox_ml.models.rf_deweather import RfDeweather, RfDeweatherParams
from nox_ml.time import local_day
from nox_ml.validation import lockdown

FAST = RfDeweatherParams(n_estimators=30, bootstrap_n=5)


def make_model():
    return RfDeweather(FAST)


@pytest.fixture(scope="module")
def dropped():
    """Eight weeks from 2023-11-06 where the city's NOx falls by 40 % from 4 December."""
    base = ventilation_inputs(n_days=56, sunday=1.0, noise=0.1)
    background = BACKGROUND_STATION[0]
    hours = [
        replace(
            h,
            nox=background
            + (h.nox - background) * (0.6 if local_day(h.hour) >= pd.Timestamp("2023-12-04") else 1),
        )
        for h in base.hours
    ]
    return replace(base, hours=hours, jacobian_cache={})


def test_the_phase_over_the_base_recovers_the_drop(dropped, monkeypatch):
    monkeypatch.setattr(lockdown, "BASE", ("11-06", "12-01"))

    result = lockdown.phase_ratio(dropped, make_model, 2023, ("12-04", "12-29"))

    assert result["ratio"] == pytest.approx(0.6, abs=0.12)
    assert result["hi"] < 0.9
    assert result["n_base"] == 19 and result["n_phase"] == 19  # business days: 20 Nov and 25 Dec are holidays


def test_a_phase_without_data_is_refused(dropped):
    with pytest.raises(ValueError, match="no business days"):
        lockdown.phase_ratio(dropped, make_model, 2019, lockdown.PHASES["phase3"])


def test_the_difference_in_differences_divides_the_years_and_widens_the_interval():
    lockdown_year = {"ratio": 0.5, "lo": 0.4, "hi": 0.625}
    placebo = {"ratio": 1.0, "lo": 0.8, "hi": 1.25}

    did = lockdown.difference_in_differences(lockdown_year, placebo)

    assert did["ratio"] == pytest.approx(0.5)
    assert did["lo"] < 0.4 and did["hi"] > 0.625
    assert did["lo"] * did["hi"] == pytest.approx(0.25)  # symmetric in log
    assert lockdown.difference_in_differences(lockdown_year, placebo | {"lo": None})["lo"] is None


def test_the_mobility_is_the_mean_of_the_business_days_of_each_phase(tmp_path):
    days = pd.date_range("2020-02-15", "2020-05-31")
    weekday = days.day_of_week < 5
    table = pd.DataFrame(
        {
            "sub_region_1": "Mexico City",
            "sub_region_2": None,
            "date": days,
            "workplaces_percent_change_from_baseline": [
                (-60 if d >= pd.Timestamp("2020-04-21") else 0) if w else 99
                for d, w in zip(days, weekday, strict=True)
            ],
            "transit_stations_percent_change_from_baseline": -10,
        }
    )
    other = table.assign(sub_region_1="Jalisco", workplaces_percent_change_from_baseline=50)
    path = tmp_path / "mobility.csv"
    pd.concat([table, other]).to_csv(path, index=False)

    result = lockdown.mobility(path)

    assert result["phase3"]["workplaces"] == pytest.approx(-0.6)
    assert result["base"]["workplaces"] == pytest.approx(0.0)  # weekends (99) and Jalisco are left out
    assert result["phase2"]["transit"] == pytest.approx(-0.1)


def test_the_command_refuses_an_invalid_config(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: bad\nmodel: {name: nope}\n")

    assert CliRunner().invoke(cli.app, ["lockdown", str(bad)]).exit_code == 2
