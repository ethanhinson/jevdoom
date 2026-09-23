from jevdoom.run import JEVIEW_LABEL, JEVIEW_URL, jeview_base_url, parse_args


def test_jeview_is_off_by_default():
    assert parse_args([]).jeview is None
    assert jeview_base_url(None) is None


def test_bare_jeview_flag_uses_the_default_address():
    assert parse_args(["--jeview"]).jeview == JEVIEW_URL


def test_jeview_flag_accepts_another_address():
    assert parse_args(["--jeview", "http://127.0.0.1:4800"]).jeview == "http://127.0.0.1:4800"


def test_jeview_base_url_groups_calls_under_the_project_label():
    assert jeview_base_url("http://127.0.0.1:4777") == f"http://127.0.0.1:4777/{JEVIEW_LABEL}"
    assert jeview_base_url("http://127.0.0.1:4777/") == f"http://127.0.0.1:4777/{JEVIEW_LABEL}"
