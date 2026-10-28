# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false
# pyright: reportOperatorIssue=false, reportReturnType=false, reportAssignmentType=false, reportGeneralTypeIssues=false
# (pandas typing infers unions for `df[...]`; behavior is covered by the tests instead)
"""Contingency days against normal days with a model of the registry: known answers on synthetic stations."""

import ast
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml
from typer.testing import CliRunner
from ventilation_synthetic import ventilation_inputs

from nox_ml import cli
from nox_ml.data.calendar import atypical_days
from nox_ml.data.inputs import Inputs
from nox_ml.inversion.linear import BACKGROUND_STATION
from nox_ml.models import REGISTRY
from nox_ml.models.rf_deweather import RfDeweather, RfDeweatherParams
from nox_ml.time import local_day
from nox_ml.validation import events, tune
from nox_ml.validation.events import day_list
from nox_ml.validation.experiment import EVALUATION_PERIOD, Placebo, normalized_days

FAST = RfDeweatherParams(n_estimators=30, bootstrap_n=3)
PLACEBO = Placebo(refits=3, seed=2)

# From Monday 2023-11-06 (the ventilation fixture), holiday on 11-20. Measure days 15-16, 22-26 and 12-06;
# 25 and 26 are a weekend: 6 business measure days.
EPISODES = pd.DataFrame(
    {
        "episode": [1, 2, 3],
        "activation": pd.to_datetime(["2023-11-14", "2023-11-21", "2023-12-05"]),
        "suspension": pd.to_datetime(["2023-11-16", "2023-11-26", "2023-12-06"]),
    }
)
BUSINESS_MEASURES = pd.to_datetime(
    ["2023-11-15", "2023-11-16", "2023-11-22", "2023-11-23", "2023-11-24", "2023-12-06"]
)
ACTIVATIONS = pd.to_datetime(EPISODES["activation"])


def make_model():
    return RfDeweather(FAST)


def scaled(inputs: Inputs, factors: dict[pd.Timestamp, float]) -> Inputs:
    """The same stations with the NOx above the background multiplied by a factor on some days."""
    background = BACKGROUND_STATION[0]
    hours = [
        replace(h, nox=background + (h.nox - background) * factors.get(local_day(h.hour), 1.0))
        for h in inputs.hours
    ]
    return replace(inputs, hours=hours, jacobian_cache={})


@pytest.fixture(scope="module")
def base() -> Inputs:
    return ventilation_inputs(n_days=56, sunday=1.0, noise=0.1)


def effect(inputs: Inputs, **kwargs):
    return events.contingency_effect(inputs, make_model, EPISODES, PLACEBO, **kwargs)


def test_split_days_keeps_business_measure_days_and_leaves_the_activation_days_out(base):
    active = pd.DatetimeIndex(
        sorted(set(BUSINESS_MEASURES) | set(ACTIVATIONS) | {pd.Timestamp("2023-11-25")})
    )

    groups = events.split_days(
        base, BUSINESS_MEASURES.union(pd.to_datetime(["2023-11-25", "2023-11-26"])), active
    )

    assert list(groups.event) == list(BUSINESS_MEASURES)
    assert list(groups.left_out) == list(ACTIVATIONS)
    assert groups.not_business.strftime("%m-%d").tolist() == ["11-25", "11-26"]
    assert groups.normal.intersection(active).empty
    assert groups.normal.intersection(pd.to_datetime(["2023-11-18", "2023-11-20"])).empty  # weekend, holiday
    assert groups.without_data.empty


def test_days_without_data_are_reported(base):
    active = pd.DatetimeIndex(["2024-03-07"])

    groups = events.split_days(base, active, active)

    assert list(groups.without_data) == list(active) and groups.event.empty


@pytest.fixture(scope="module")
def unchanged(base):
    return effect(base)["measures"]


def test_without_a_change_the_ratio_is_one_and_so_are_the_placebos(unchanged):
    result = unchanged

    assert result["ratio"] == pytest.approx(1.0, abs=0.12)
    assert result["lo"] <= result["ratio"] <= result["hi"]
    for placebo in result["placebos"].values():
        assert placebo["center"] == pytest.approx(1.0, abs=0.12)
        assert placebo["lo"] <= placebo["center"] <= placebo["hi"]
        assert placebo["n_fake_days"] == 6 and len(placebo["ratios"]) == PLACEBO.refits


def test_an_imposed_drop_on_the_measure_days_is_recovered_and_the_placebos_stay_at_one(base):
    # the activation days and the weekend measure days are made wild: they must not move the ratio
    wild = {d: 3.0 for d in [*ACTIVATIONS, pd.Timestamp("2023-11-25"), pd.Timestamp("2023-11-26")]}
    data = scaled(base, wild | dict.fromkeys(BUSINESS_MEASURES, 0.7))

    result = effect(data)["measures"]

    assert result["ratio"] == pytest.approx(0.7, abs=0.1)
    assert result["hi"] < 0.95
    for placebo in result["placebos"].values():
        assert placebo["center"] == pytest.approx(1.0, abs=0.12)
        assert result["ratio"] < placebo["lo"]


def test_activation_days_enter_neither_group_but_the_sensitivity_counts_them(base):
    data = scaled(base, dict.fromkeys(ACTIVATIONS, 0.5))

    both = effect(data, sensitivity=True)

    measures, active = both["measures"], both["all_active"]
    assert measures["ratio"] == pytest.approx(1.0, abs=0.12)
    assert measures["days"]["left_out"] == [d.date().isoformat() for d in ACTIVATIONS]
    assert set(active["days"]["event"]) == set(measures["days"]["event"]) | set(measures["days"]["left_out"])
    assert active["days"]["left_out"] == []
    assert active["ratio"] < measures["ratio"] - 0.03  # the halved activation days pull it down
    assert active["days"]["n_normal"] == measures["days"]["n_normal"]


def test_weekend_and_holiday_measure_days_are_listed_not_used(unchanged):
    result = unchanged["days"]

    assert result["not_business"] == ["2023-11-25", "2023-11-26"]
    assert set(result["event"]).isdisjoint(result["not_business"])


def test_no_real_event_day_is_a_fake_day_or_a_reference(base):
    seen = []

    def spy():
        model = make_model()
        fit = model.fit
        model.fit = lambda data, **kw: (
            seen.append(set(map(local_day, (h.hour for h in data.hours)))) or fit(data, **kw)
        )
        return model

    events.contingency_effect(base, spy, EPISODES, PLACEBO)

    active = set(ACTIVATIONS) | set(BUSINESS_MEASURES)
    assert set(BUSINESS_MEASURES) <= seen[0] and not seen[0] & set(ACTIVATIONS)  # the real fit
    assert len(seen) == 1 + 2 * PLACEBO.refits
    assert all(not days & active for days in seen[1:])  # the placebo fits see no event or activation day


def test_the_poorly_ventilated_pool_is_normal_and_at_least_as_stagnant_as_the_events(base):
    daily = normalized_days(base, base.jacobians(*events.plume_transport(events.SIGMA_THETA, events.U_MIN)))
    active = pd.DatetimeIndex(sorted(set(BUSINESS_MEASURES) | set(ACTIVATIONS)))
    groups = events.split_days(base, BUSINESS_MEASURES, active)

    pool = events.poorly_ventilated_pool(daily, groups)

    threshold = daily.loc[groups.event, "stagnation"].quantile(0.25)
    assert 0 < len(pool) <= len(groups.normal) and set(pool) <= set(groups.normal)
    assert (daily.loc[pool, "stagnation"] >= threshold).all()


def test_a_reference_is_refused(base):
    with pytest.raises(ValueError, match="estimates emissions"):
        events.contingency_effect(base, lambda: REGISTRY["idw"](), EPISODES, PLACEBO)


def test_without_business_measure_days_there_is_nothing_to_measure(base):
    weekend = pd.DataFrame(
        {
            "episode": [1],
            "activation": [pd.Timestamp("2023-11-24")],
            "suspension": [pd.Timestamp("2023-11-26")],
        }
    )

    with pytest.raises(ValueError, match="no event day"):
        events.contingency_effect(base, make_model, weekend, PLACEBO)


def test_the_placebo_needs_more_normal_days_than_fake_days(base):
    groups = events.split_days(base, BUSINESS_MEASURES, BUSINESS_MEASURES)
    small = replace(groups, normal=groups.normal[:5])

    with pytest.raises(ValueError, match="placebo needs"):
        events.fake_event_ratios(base, make_model, small, small.normal, 2, 1)


def test_the_draws_of_a_placebo_share_one_set_of_days_and_its_matrices(base, monkeypatch):
    """`on_days` starts an empty Jacobian cache: calling it once per draw rebuilt the matrices every time."""
    calls = []
    on_days = Inputs.on_days

    def counted(self, days):
        calls.append(len(days))
        return on_days(self, days)

    monkeypatch.setattr(Inputs, "on_days", counted)
    groups = events.split_days(base, BUSINESS_MEASURES, BUSINESS_MEASURES)

    events.fake_event_ratios(base, make_model, groups, groups.normal, 4, 1)

    assert calls == [len(groups.normal)]


def test_an_injected_drop_lowers_only_the_city_part_of_the_event_days(base):
    groups = events.split_days(base, BUSINESS_MEASURES, BUSINESS_MEASURES)
    injected = events.inject_drop(base, groups.event, 0.3)
    background = BACKGROUND_STATION[0]

    for before, after in zip(base.hours, injected.hours, strict=True):
        factor = 0.7 if local_day(before.hour) in set(groups.event) else 1.0
        assert after.nox == pytest.approx(background + (before.nox - background) * factor)
        if len(before.no2):
            floor = np.quantile(before.no2, events.PIXEL_BACKGROUND_QUANTILE)
            assert after.no2 == pytest.approx(floor + (before.no2 - floor) * factor)
    assert injected.jacobian_cache is base.jacobian_cache  # the matrices do not depend on the values


def test_the_injected_drops_are_recovered_on_data_without_a_change(base):
    groups = events.split_days(base, BUSINESS_MEASURES, BUSINESS_MEASURES)

    rows = events.injection_recovery(base, make_model, groups, [0.2, 0.4])

    assert [r["drop"] for r in rows] == [0.0, 0.2, 0.4]
    assert rows[0]["recovered"] == 0
    assert rows[1]["recovered"] == pytest.approx(0.2, abs=0.1)
    assert rows[2]["recovered"] == pytest.approx(0.4, abs=0.1)
    assert rows[2]["recovered"] > rows[1]["recovered"]
    assert rows[0]["detected"] is None


def test_an_injected_drop_must_be_a_fraction(base):
    with pytest.raises(ValueError, match="drop must be"):
        events.inject_drop(base, events.data_days(base)[:1], 1.0)


# --- The command -------------------------------------------------------------------------------------------


@pytest.fixture
def config(tmp_path):
    episodes = tmp_path / "data" / "raw" / "contingencias"
    episodes.mkdir(parents=True)
    lines = [f"{i},{r.activation:%Y-%m-%d},,{r.suspension:%Y-%m-%d},,test" for i, r in EPISODES.iterrows()]
    (episodes / "contingencias_ozono_2024_episodios.csv").write_text(
        "episodio,activacion_fecha,activacion_hora,suspension_fecha,suspension_hora,fuente\n"
        + "\n".join(lines)
        + "\n"
    )
    path = tmp_path / "frozen.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "name": "frozen.test",
                "period": {"start": "2023-11-06", "end": "2023-12-31"},
                "data_dir": str(tmp_path / "data"),
                "model": {"name": "rf_deweather", "params": FAST.model_dump()},
                "placebo": {"refits": 2},
            }
        )
    )
    return path


def scaled_base():
    return ventilation_inputs(n_days=56, sunday=1.0, noise=0.1)


@pytest.fixture
def loaded(monkeypatch, base):
    asked = []

    def load(data_dir, start, end, hours):
        asked.append((start, end))
        return scaled(base, dict.fromkeys(BUSINESS_MEASURES, 0.7))

    monkeypatch.setattr(events, "load_inputs", load)
    return asked


def contingencies(config, tmp_path, *extra):
    return CliRunner().invoke(
        cli.app, ["contingencies", str(config), "--runs-dir", str(tmp_path / "runs"), *extra]
    )


def test_the_command_writes_the_ratio_its_interval_and_the_placebos_for_the_test_period(
    config, tmp_path, loaded
):
    result = contingencies(config, tmp_path, "--period", "test")

    assert result.exit_code == 0, result.output
    assert loaded == [(EVALUATION_PERIOD[0].isoformat(), EVALUATION_PERIOD[1].isoformat())]
    out = tmp_path / "runs" / "frozen.contingencies"
    assert sorted(p.name for p in out.iterdir()) == ["code_version.json", "config.yaml", "contingencies.json"]
    saved = json.loads((out / "contingencies.json").read_text())
    measures = saved["scenarios"]["measures"]
    assert saved["model"] == "rf_deweather" and list(saved["scenarios"]) == ["measures"]
    assert saved["period"] == {"start": "2024-02-15", "end": "2024-05-31"}
    assert measures["ratio"] == pytest.approx(0.7, abs=0.12)
    assert set(measures) >= {"lo", "hi", "days", "placebos"}
    assert set(measures["placebos"]) == {"random", "poorly_ventilated"}
    assert "event / normal" in result.output


def test_the_sensitivity_option_adds_the_scenario_with_every_active_day(config, tmp_path, loaded):
    result = contingencies(config, tmp_path, "--period", "test", "--sensitivity")

    saved = json.loads((tmp_path / "runs" / "frozen.contingencies" / "contingencies.json").read_text())
    assert result.exit_code == 0 and list(saved["scenarios"]) == ["measures", "all_active"]


def test_the_inject_option_adds_the_recovery_to_the_measures_scenario(config, tmp_path, loaded):
    result = contingencies(config, tmp_path, "--period", "test", "--inject", "0.2", "--inject", "0.4")

    saved = json.loads((tmp_path / "runs" / "frozen.contingencies" / "contingencies.json").read_text())
    rows = saved["scenarios"]["measures"]["injection"]
    assert result.exit_code == 0, result.output
    assert [r["drop"] for r in rows] == [0.0, 0.2, 0.4]
    assert "injected 20%" in result.output


def test_the_refits_option_sets_the_number_of_fake_day_draws(config, tmp_path, loaded):
    result = contingencies(config, tmp_path, "--period", "test", "--refits", "5")

    out = tmp_path / "runs" / "frozen.contingencies"
    saved = json.loads((out / "contingencies.json").read_text())
    assert result.exit_code == 0, result.output
    assert len(saved["scenarios"]["measures"]["placebos"]["random"]["ratios"]) == 5
    assert yaml.safe_load((out / "config.yaml").read_text())["placebo"]["refits"] == 5


def test_the_command_needs_the_test_period_and_a_valid_config(config, tmp_path, loaded):
    bad = tmp_path / "bad.yaml"
    bad.write_text(
        yaml.safe_dump(
            {"name": "bad", "period": {"start": "2023-11-06", "end": "2023-11-19"}, "model": {"name": "nope"}}
        )
    )

    assert contingencies(config, tmp_path).exit_code == 2
    assert contingencies(config, tmp_path, "--period", "tuning").exit_code == 2
    assert contingencies(bad, tmp_path, "--period", "test").exit_code == 2
    assert loaded == []


def test_tune_cannot_reach_the_contingencies(config, tmp_path, loaded):
    contingencies(config, tmp_path, "--period", "test")
    stored = tmp_path / "runs" / "frozen.contingencies" / "config.yaml"
    search = tmp_path / "runs" / "frozen.contingencies" / "search.yaml"
    search.write_text(
        yaml.safe_dump(
            {
                "model": "rf_deweather",
                "config": stored.name,
                "search": "grid",
                "space": {"n_estimators": [10]},
            }
        )
    )

    with pytest.raises(ValueError, match="test period"):
        tune.read_search(search)
    tuning_imports = {
        n.module if isinstance(n, ast.ImportFrom) else a.name
        for n in ast.walk(ast.parse(Path(tune.__file__).read_text()))
        if isinstance(n, ast.Import | ast.ImportFrom)
        for a in (n.names if isinstance(n, ast.Import) else [n])
    }
    assert not any("events" in name or "contingencies" in name for name in tuning_imports)
    assert "contingencies" not in CliRunner().invoke(cli.app, ["tune", "--help"]).output


def test_running_it_again_on_its_own_output_keeps_one_folder(config, tmp_path, loaded):
    contingencies(config, tmp_path, "--period", "test")
    again = contingencies(
        tmp_path / "runs" / "frozen.contingencies" / "config.yaml", tmp_path, "--period", "test"
    )

    assert again.exit_code == 0
    assert [p.name for p in (tmp_path / "runs").iterdir()] == ["frozen.contingencies"]


# --- Calendar events ---------------------------------------------------------------------------------------

HOLIDAY_WEEK = pd.date_range("2023-12-11", "2023-12-15")  # Monday to Friday, no contingency


def test_a_calendar_drop_is_found_and_the_contingency_days_are_not_normal(base):
    drop = dict.fromkeys(HOLIDAY_WEEK, 0.7)
    calm = events.calendar_effect(scaled(base, drop), make_model, HOLIDAY_WEEK, BUSINESS_MEASURES, PLACEBO)

    wild = scaled(base, drop | dict.fromkeys(BUSINESS_MEASURES, 3.0))
    result = events.calendar_effect(wild, make_model, HOLIDAY_WEEK, BUSINESS_MEASURES, PLACEBO, inject=[0.2])

    assert result["days"]["event"] == [d.date().isoformat() for d in HOLIDAY_WEEK]
    assert result["ratio"] == pytest.approx(
        calm["ratio"]
    )  # the contingency days are neither event nor reference
    assert result["hi"] < 0.9 < result["placebos"]["random"]["lo"]  # the forest shrinks 5 days of 0.7 a bit
    assert result["placebos"]["random"]["center"] == pytest.approx(1.0, abs=0.12)
    assert [r["drop"] for r in result["injection"]] == [0.0, 0.2]


def test_a_calendar_analysis_refuses_a_reference(base):
    with pytest.raises(ValueError, match="estimates emissions"):
        events.calendar_effect(base, lambda: REGISTRY["idw"](), HOLIDAY_WEEK, BUSINESS_MEASURES, PLACEBO)


def test_day_spans_are_parsed_inclusive_and_merged():
    days = cli.parse_days(["2023-12-18:2023-12-20", "2023-12-19", "2023-12-26"])

    assert days.strftime("%m-%d").tolist() == ["12-18", "12-19", "12-20", "12-26"]


def calendar(config, tmp_path, *extra):
    return CliRunner().invoke(
        cli.app,
        ["calendar", str(config), "--runs-dir", str(tmp_path / "runs"), "--label", "holidays", *extra],
    )


def test_the_calendar_command_runs_on_the_config_period_by_default(config, tmp_path, loaded):
    result = calendar(config, tmp_path, "--days", "2023-12-11:2023-12-15", "--days", "2023-12-16")

    assert result.exit_code == 0, result.output
    assert loaded == [("2023-11-06", "2023-12-31")]
    out = tmp_path / "runs" / "frozen.calendar-holidays"
    assert sorted(p.name for p in out.iterdir()) == ["calendar.json", "code_version.json", "config.yaml"]
    saved = json.loads((out / "calendar.json").read_text())
    assert saved["label"] == "holidays" and list(saved["scenarios"]) == ["holidays"]
    scenario = saved["scenarios"]["holidays"]
    assert len(scenario["days"]["event"]) == 5
    assert set(scenario["days"]["event"]).isdisjoint(d.date().isoformat() for d in BUSINESS_MEASURES)
    assert "event / normal" in result.output


def test_the_calendar_command_can_run_on_the_test_period(config, tmp_path, loaded):
    result = calendar(config, tmp_path, "--days", "2023-12-11:2023-12-15", "--period", "test")

    stored = yaml.safe_load((tmp_path / "runs" / "frozen.calendar-holidays" / "config.yaml").read_text())
    assert result.exit_code == 0, result.output
    assert loaded == [(EVALUATION_PERIOD[0].isoformat(), EVALUATION_PERIOD[1].isoformat())]
    assert stored["period"] == {"start": "2024-02-15", "end": "2024-05-31"}


def test_the_calendar_command_refuses_bad_days(config, tmp_path, loaded):
    assert calendar(config, tmp_path, "--days", "2023-13-40").exit_code == 2
    assert loaded == []


# --- Detection curve ---------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def curve(base):
    # the fixture has no day-to-day variation of the emission, which is what limits a detection: add 20 %
    days = events.data_days(base)
    rng = np.random.default_rng(5)
    varied = scaled(base, dict(zip(days, rng.lognormal(0, 0.2, len(days)), strict=True)))
    normal = events.split_days(varied, pd.DatetimeIndex([]), BUSINESS_MEASURES).normal
    return events.detection_curve(varied, make_model, normal, [3, 9], Placebo(refits=20, seed=2))


def test_the_detectable_drop_shrinks_with_more_days(curve):
    short, long = curve["rows"]

    assert (short["days"], long["days"]) == (3, 9)
    assert 0 < long["mdc_half"] < short["mdc_half"] < 1
    assert long["mdc_half"] <= long["mdc"]  # more power needs a larger drop
    assert curve["cv"] > 0
    extrapolated = [e["mdc"] for e in curve["extrapolated"]]
    assert extrapolated == sorted(extrapolated, reverse=True) and extrapolated[-1] > 0


def test_the_detection_command_writes_the_curve(config, tmp_path, loaded):
    result = CliRunner().invoke(
        cli.app,
        ["detection", str(config), "--runs-dir", str(tmp_path / "runs"), "--days", "3", "--days", "5"],
    )

    assert result.exit_code == 0, result.output
    assert loaded == [("2023-11-06", "2023-12-31")]
    saved = json.loads((tmp_path / "runs" / "frozen.detection" / "detection.json").read_text())
    assert [r["days"] for r in saved["rows"]] == [3, 5] and len(saved["rows"][0]) == 7
    assert saved["model"] == "rf_deweather" and "extrapolated" in result.output


def test_the_detection_command_keeps_the_excluded_days_out_of_the_normal_ones(config, tmp_path, loaded):
    args = ["detection", str(config), "--runs-dir", str(tmp_path / "runs"), "--days", "3"]

    result = CliRunner().invoke(cli.app, [*args, "--exclude", "2023-12-11:2023-12-15", "--label", "calm"])

    assert result.exit_code == 0, result.output
    saved = json.loads((tmp_path / "runs" / "frozen.detection-calm" / "detection.json").read_text())
    active = events.contingencies.active_days(EPISODES).union(atypical_days("2023-11-06", "2023-12-31"))
    full = events.split_days(scaled_base(), pd.DatetimeIndex([]), active).normal
    assert saved["excluded"][0] == "2023-12-11" and len(saved["excluded"]) == 5
    assert saved["n_normal"] == len(full) - 1  # 12-15 Dec are year-end days already: only the 11th is new


def test_atypical_days_are_left_out_of_the_reference(config, tmp_path, loaded):
    result = contingencies(config, tmp_path, "--period", "test", "--exclude", "2023-12-11:2023-12-13")

    saved = json.loads((tmp_path / "runs" / "frozen.contingencies" / "contingencies.json").read_text())
    measures = saved["scenarios"]["measures"]
    assert result.exit_code == 0, result.output
    easter = day_list(atypical_days(*EVALUATION_PERIOD))  # the calendar's, for the test period
    assert saved["atypical"] == sorted(["2023-12-11", "2023-12-12", "2023-12-13", *easter])
    assert {"2023-12-11", "2023-12-12", "2023-12-13"} <= set(measures["days"]["left_out"])
    full = events.split_days(scaled_base(), BUSINESS_MEASURES, events.contingencies.active_days(EPISODES))
    assert measures["days"]["n_normal"] == len(full.normal) - 3
