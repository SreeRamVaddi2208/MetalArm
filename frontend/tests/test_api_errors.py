"""What a person reads when the API refuses their input.

The backend's validation rules are only as good as the sentence they produce on
screen. FastAPI hands back two different shapes - a plain `detail` string from
HTTPException, and a LIST of per-field objects from a 422 - and Pydantic adds a
"Value error, " prefix meant for a traceback. These pin the translation from
all of that into something worth showing a person.
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from metalarm.api import _extract_detail, _field_label  # noqa: E402


def _response(payload: object, status: int = 422) -> httpx.Response:
    return httpx.Response(status, json=payload)


def test_plain_detail_string_is_shown_verbatim():
    """HTTPException details are already written for a person."""
    got = _extract_detail(_response({"detail": "Quest already completed"}, 409))
    assert got == "Quest already completed"


def test_field_error_names_the_field_in_words():
    """"display_name" is a column; "Display name" is what the label says."""
    got = _extract_detail(
        _response({"detail": [{"loc": ["body", "display_name"], "msg": "Value error, cannot be blank"}]})
    )
    assert got == "Display name: cannot be blank"


def test_whole_model_error_names_no_field():
    """A validator comparing password against email has loc ("body",).

    There is no "body" field on screen, so labelling it would send the person
    looking for something that does not exist.
    """
    got = _extract_detail(
        _response(
            {
                "detail": [
                    {
                        "loc": ["body"],
                        "msg": "Value error, password cannot be your email address or your name",
                    }
                ]
            }
        )
    )
    assert got == "password cannot be your email address or your name"


def test_value_error_prefix_is_stripped():
    """Pydantic's prefix is for developers reading a stack trace."""
    got = _extract_detail(_response({"detail": [{"loc": ["body", "password"], "msg": "Value error, too short"}]}))
    assert "Value error" not in got


def test_several_problems_are_all_reported():
    """Fixing one field at a time, one round trip each, is a bad form."""
    got = _extract_detail(
        _response(
            {
                "detail": [
                    {"loc": ["body", "email"], "msg": "value is not a valid email address"},
                    {"loc": ["body", "display_name"], "msg": "Value error, cannot be blank"},
                ]
            }
        )
    )
    assert got == "Email: value is not a valid email address; Display name: cannot be blank"


def test_pydantic_builtin_messages_pass_through_unprefixed():
    """min_length and friends have no "Value error, " prefix to strip."""
    got = _extract_detail(
        _response({"detail": [{"loc": ["body", "password"], "msg": "String should have at least 8 characters"}]})
    )
    assert got == "Password: String should have at least 8 characters"


def test_non_json_body_falls_back_to_the_status():
    """A proxy's HTML error page must not render as a traceback."""
    got = _extract_detail(httpx.Response(502, text="<html>Bad Gateway</html>"))
    assert got == "<html>Bad Gateway</html>"


def test_empty_non_json_body_names_the_status():
    got = _extract_detail(httpx.Response(503, text=""))
    assert got == "HTTP 503"


def test_unrecognised_shape_names_the_status():
    """Never show a person a bare "None" or a dict repr."""
    assert _extract_detail(_response({"error": "nope"}, 400)) == "HTTP 400"
    assert _extract_detail(_response({"detail": []}, 400)) == "HTTP 400"
    assert _extract_detail(_response(["unexpected"], 400)) == "HTTP 400"


def test_malformed_items_are_skipped_not_crashed_on():
    got = _extract_detail(
        _response({"detail": ["just a string", {"loc": ["body", "email"], "msg": "required"}]})
    )
    assert got == "Email: required"


def test_field_label_humanises_snake_case():
    assert _field_label(["body", "display_name"]) == "Display name"
    assert _field_label(["query", "routine_id"]) == "Routine id"
    assert _field_label(["body"]) == ""
    assert _field_label([]) == ""
