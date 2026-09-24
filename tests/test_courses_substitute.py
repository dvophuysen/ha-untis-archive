"""Ein ausgeblendeter Kurs bleibt ausgeblendet, auch wenn jemand vertritt."""
import json

from backend.courses import course_key, lesson_is_hidden
from backend.queries import _teacher_orig_from_payload


def test_a_hidden_course_stays_hidden_under_a_substitute_teacher():
    hidden = {course_key(7, 41)}
    regular = {"subject_untis_id": 7, "teacher_untis_id": 41}
    covered = {"subject_untis_id": 7, "teacher_untis_id": 99, "teacher_orig_untis_id": 41}
    other = {"subject_untis_id": 7, "teacher_untis_id": 42}
    assert lesson_is_hidden(regular, hidden) and lesson_is_hidden(covered, hidden)
    assert not lesson_is_hidden(other, hidden)
    by_name = {"subject_name": "Religion", "teacher_name": "Vertretung", "teacher_orig_name": "Muster"}
    assert lesson_is_hidden(by_name, {course_key(None, None, "Religion", "Muster")})


def test_the_original_teacher_comes_from_the_raw_lesson():
    assert _teacher_orig_from_payload(json.dumps({"te": [{"id": 99, "orgid": 41}]})) == 41
    assert _teacher_orig_from_payload(json.dumps({"te": [{"id": 99}]})) is None
    assert _teacher_orig_from_payload(None) is None and _teacher_orig_from_payload("kaputt") is None
