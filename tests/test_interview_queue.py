import unittest

from evaluation.interview_questions import (
    InterviewQuestion,
    prioritized_questions,
    render_study_queue,
)


def question(identifier, priority, status, knowledge=5, frequency=5):
    return InterviewQuestion(
        id=identifier, priority=priority, knowledge=knowledge,
        frequency=frequency, question=f"Question {identifier}?", anchor="anchor",
        status=status, section="A. Test",
    )


class InterviewQueueTests(unittest.TestCase):
    def test_priority_precedes_readiness_then_score(self):
        items = [
            question("A01", "P1", "GAP"),
            question("A02", "P0", "READY"),
            question("A03", "P0", "GAP", 5, 4),
            question("A04", "P0", "GAP", 5, 5),
        ]
        self.assertEqual(
            [item.id for item in prioritized_questions(items)],
            ["A04", "A03", "A02", "A01"],
        )

    def test_rendered_queue_is_bounded_and_contains_source_hash(self):
        from pathlib import Path
        source = Path(__file__)
        rendered = render_study_queue(
            source,
            [question("A01", "P0", "GAP"), question("A02", "P1", "READY")],
            limit=1,
        )
        self.assertIn("Question bank SHA256", rendered)
        self.assertIn("| 1 | A01 |", rendered)
        self.assertNotIn("| 2 | A02 |", rendered)


if __name__ == "__main__":
    unittest.main()
