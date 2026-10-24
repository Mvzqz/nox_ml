import json

from nox_ml.data.traffic import read_infovial_profile


def test_infovial_profile_reads_integer_day_types_and_hours(tmp_path):
    path = tmp_path / "perfil.json"
    path.write_text(json.dumps({"0": {"0": 0.25, "13": 1.5}, "2": {"0": 0.5}}))

    assert read_infovial_profile(path) == {0: {0: 0.25, 13: 1.5}, 2: {0: 0.5}}
