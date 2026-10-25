# pyright: reportArgumentType=false, reportAttributeAccessIssue=false, reportIndexIssue=false, reportCallIssue=false, reportGeneralTypeIssues=false
import pandas as pd
import pytest

from nox_ml.models.base import EmissionEstimate

DAYS = ["weekday", "saturday", "sunday_holiday"]


def absolute(**changes) -> EmissionEstimate:
    table = pd.DataFrame(
        {"zone": [0, 0, 0, 1, 1, 1], "day_type": DAYS * 2, "mean": [10, 8, 5, 20, 16, 9.0], "sd": [1.0] * 6}
    )
    return EmissionEstimate("absolute", table.assign(**changes))


def relative() -> EmissionEstimate:
    table = pd.DataFrame(
        {
            "zone": [pd.NA] * 3,
            "day_type": DAYS,
            "mean": [1.0, 0.8, 0.5],
            "lo": [1.0, 0.7, 0.4],
            "hi": [1.0, 0.9, 0.6],
        }
    )
    return EmissionEstimate("relative", table)


def test_absolute_ratio_pools_the_zones():
    assert absolute().day_type_ratio("sunday_holiday") == pytest.approx(14 / 30)


def test_absolute_has_no_interval_unless_the_model_gives_one():
    assert absolute().day_type_interval("sunday_holiday") is None


def test_relative_ratio_and_interval_come_from_the_table():
    estimate = relative().validate()

    assert estimate.day_type_ratio("sunday_holiday") == 0.5
    assert estimate.day_type_interval("sunday_holiday") == (0.4, 0.6)


@pytest.mark.parametrize(
    ("estimate", "message"),
    [
        (absolute(sd=0.0), "sd must be positive"),
        (absolute(mean=float("nan")), "means must be finite"),
        (absolute(day_type="monday"), "day_type"),
        (EmissionEstimate("relative", absolute().table), "needs columns"),
    ],
)
def test_validate_rejects_a_table_that_breaks_the_schema(estimate, message):
    with pytest.raises(ValueError, match=message):
        estimate.validate()


def test_validate_rejects_an_inverted_interval():
    estimate = relative()
    table = estimate.table.assign(lo=[1.0, 0.95, 0.4])

    with pytest.raises(ValueError, match="lo must not exceed hi"):
        EmissionEstimate("relative", table).validate()


def test_to_frame_stores_the_kind_and_a_nullable_zone():
    frame = relative().to_frame()

    assert set(frame["kind"]) == {"relative"}
    assert frame["zone"].isna().all()
