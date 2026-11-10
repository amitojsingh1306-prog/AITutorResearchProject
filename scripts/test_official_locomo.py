"""Protocol and scoring tests; does not contact any model server."""
import json
from pathlib import Path
import unittest

from run_official_locomo import (
    DATA_ROOT, conversation_messages, evidence_metrics, load_official_scorer,
    select_questions, summarize,
)


class OfficialLoCoMoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scorer = load_official_scorer(DATA_ROOT / "upstream_evaluation.py")
        cls.dataset = json.loads((DATA_ROOT / "locomo10.json").read_text())

    def test_upstream_normalization_and_stemming(self):
        self.assertEqual(self.scorer["f1_score"]("The running dogs", "running dog"), 1)
        self.assertEqual(self.scorer["f1_score"]("wrong", "correct"), 0)

    def test_category_rules(self):
        rows = [
            {"question": "q", "answer": "red, blue", "prediction": "red, blue", "category": 1},
            {"question": "q", "answer": "May; alternative", "prediction": "May", "category": 3},
            {"question": "q", "answer": "", "prediction": "No information available", "category": 5},
        ]
        self.assertEqual(list(self.scorer["eval_question_answering"](rows)[0]), [1, 1, 1])

    def test_balanced_subset_is_deterministic(self):
        selected = select_questions(self.dataset[0]["qa"], 1)
        self.assertEqual({q["category"] for _, q in selected}, {1, 2, 3, 4, 5})
        self.assertEqual(len(selected), 5)
        self.assertEqual(selected, select_questions(self.dataset[0]["qa"], 1))

    def test_only_conversation_records_are_ingested(self):
        sample = json.loads(json.dumps(self.dataset[0]))
        sample["qa"] = [{"question": "DO_NOT_INDEX_QUESTION", "answer": "DO_NOT_INDEX_GOLD"}]
        class Record:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
        messages = conversation_messages(sample, Record)
        self.assertGreater(len(messages), 100)
        self.assertFalse(any("DO_NOT_INDEX" in m.content for m in messages))
        self.assertTrue(all(m.role == "user" for m in messages))
        self.assertEqual(len({m.id for m in messages}), len(messages))

    def test_evidence_deduplicated_and_missing_annotations_excluded(self):
        self.assertEqual(evidence_metrics(["D1:1", "D1:1", "D1:2"], ["D1:1"]),
                         {"precision": .5, "recall": 1})
        self.assertEqual(evidence_metrics([], []), {"precision": None, "recall": None})

    def test_errors_not_silently_counted_as_valid_predictions(self):
        result = summarize([{"mode": "hybrid", "error": "server unavailable"}])
        self.assertEqual(result["hybrid"]["errors"], 1)
        self.assertIsNone(result["hybrid"]["mean_official_qa_score"])


if __name__ == "__main__":
    unittest.main()
