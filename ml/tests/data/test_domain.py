from nox_ml.data.qc import Check, render


def test_check_renders_status_marks():
    checks = [Check(True, "a"), Check(False, "b"), Check(None, "c")]

    assert render(checks) == "[ok] a\n[FAIL] b\n[info] c"
