import types

# Import internal helpers directly from the handler module
from lambdas.charger_gpt import handler as h


def test_normalize_building_basic():
    assert h._normalize_building("Library") == "library"
    assert h._normalize_building("the Library") == "library"
    assert h._normalize_building("Engineering Building") == "engineering"
    assert h._normalize_building("the Engineering Hall") == "engineering"


def test_is_building_match_substrings():
    assert h._is_building_match("M. Louis Salmon Library", "the library") is True
    assert h._is_building_match("Engineering Building", "engineering hall") is True
    assert h._is_building_match("Engineering Building", "eng building") is False  # not a synonym list; substring based


def test_normalize_course_code():
    assert h._normalize_course_code("cs101") == "CS101"
    assert h._normalize_course_code("CS 101") == "CS101"
    assert h._normalize_course_code("CS-101") == "CS101"


def test_resolve_building_reference_with_pronoun():
    sess = {"last_building_name": "Library"}
    assert h._resolve_building_reference("it", "what time does it open?", sess) == "Library"


def test_resolve_building_reference_from_transcript():
    sess = {"last_building_name": "Engineering Building"}
    # no slot value, but transcript contains pronoun -> use memory
    assert h._resolve_building_reference(None, "when does it close?", sess) == "Engineering Building"


def test_resolve_course_reference_with_pronoun():
    sess = {"last_course_code": "CS101"}
    assert h._resolve_course_reference("it", "when is it?", sess) == "CS101"


def test_resolve_course_reference_normalization():
    sess = {}
    assert h._resolve_course_reference("cs-101", "", sess) == "CS101"
