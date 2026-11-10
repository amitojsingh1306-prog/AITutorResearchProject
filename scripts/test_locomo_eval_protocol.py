from datetime import datetime
import pytest
from locomo_eval_protocol import (calendar_reference, extract_answer, isolated_storage,
    extract_json_answer, annotate_relative_dates)


@pytest.fixture
def isolated_test_env():
    with isolated_storage() as path:
        yield path


def test_multiline_answer_boundary():
    assert extract_answer("Explanation\n<ANSWER>\nmental health\n</ANSWER>")[0] == "mental health"


@pytest.mark.parametrize("raw", ["No tags", "<answer></answer>",
    "<answer>a</answer><answer>b</answer>", "<answer>a", "<answer><answer>a</answer></answer>"])
def test_invalid_boundaries_keep_raw(raw):
    answer, status = extract_answer(raw)
    assert answer == raw
    assert status != "valid_boundary"


def test_no_question_specific_extraction():
    raw = "The charity race raised awareness for mental health."
    assert extract_answer(raw)[0] == raw


def test_relative_date_uses_source_date():
    assert "yesterday=2023-05-07" in calendar_reference("I went yesterday.", "2023-05-08T13:56:00+00:00")


def test_year_boundary():
    assert "yesterday=2023-12-31" in calendar_reference("yesterday", "2024-01-01T00:00:00Z")


def test_absent_relative_words_add_no_claim():
    assert calendar_reference("an event on 9 May", "2023-05-08T00:00:00Z") == ""


def test_isolated_env_is_local_and_empty(isolated_test_env):
    assert str(isolated_test_env).startswith("/private/tmp/")
    assert list(isolated_test_env.iterdir()) == []


def test_cleanup_after_success_and_failure():
    with isolated_storage() as first:
        (first / "test.json").write_text("{}")
    assert not first.exists()
    with pytest.raises(RuntimeError):
        with isolated_storage() as second:
            assert second != first
            raise RuntimeError("test failure")
    assert not second.exists()


def test_structured_answer_ignores_explanation():
    assert extract_json_answer('{"answer":"mental health","explanation":"a longer sentence"}') == ("mental health", "valid_json_answer")


@pytest.mark.parametrize("raw", ["not json", '{"answer":"x"}',
    '{"answer":7,"explanation":"x"}', '{"answer":"","explanation":"x"}'])
def test_bad_json_keeps_raw(raw):
    assert extract_json_answer(raw)[0] == raw


def test_inline_annotation_preserves_original_words():
    assert annotate_relative_dates("I went yesterday.", "2023-05-08T13:56:00Z") == "I went yesterday [calendar date: 7 May 2023]."
