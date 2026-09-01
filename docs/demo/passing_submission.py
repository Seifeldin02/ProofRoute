def test_normalize_status(normalize_status):
    assert normalize_status(" OK ") == "passed"
    assert normalize_status("Error") == "failed"
    try:
        normalize_status(123)
    except TypeError:
        pass
    else:
        raise AssertionError()
