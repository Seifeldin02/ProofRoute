def test_normalize_status(normalize_status):
    assert normalize_status(" OK ") == "passed"
    # This intentionally misses the lowercase, error mapping, and type checks.
