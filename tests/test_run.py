from jevcommon.jeview import JEVIEW_URL, base_url, display_headers
from jevdoom.run import JEVIEW_LABEL, parse_args


def test_jeview_is_off_by_default():
    assert parse_args([]).jeview is None
    assert base_url(None, JEVIEW_LABEL) is None


def test_bare_jeview_flag_uses_the_default_address():
    assert parse_args(["--jeview"]).jeview == JEVIEW_URL


def test_jeview_flag_accepts_another_address():
    assert parse_args(["--jeview", "http://127.0.0.1:4800"]).jeview == "http://127.0.0.1:4800"


def test_base_url_groups_calls_under_a_label():
    assert base_url("http://127.0.0.1:4777", "jevdoom") == "http://127.0.0.1:4777/jevdoom"
    assert base_url("http://127.0.0.1:4777/", "jevdoom") == "http://127.0.0.1:4777/jevdoom"


def test_display_header_names_a_field_per_question():
    assert display_headers({"placement": "where"}) == {"Jeview-Display": "placement=where"}
    assert display_headers({"a": "x", "b": "y.z"}) == {"Jeview-Display": "a=x, b=y.z"}
