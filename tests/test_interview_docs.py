import re
import unittest
from hashlib import sha256
from pathlib import Path

from evaluation.review_dataset import DEFAULT_INDEX, DEFAULT_INPUTS, DEFAULT_REVIEWS, load_cases
from evaluation.review_progress import render_markdown
from evaluation.review_workflow import read_review_records, review_progress

PROJECT_ROOT = Path(__file__).resolve().parents[1]
QUESTION_BANK = PROJECT_ROOT / "docs" / "interview" / "QUESTION_BANK.md"
ROADMAP = PROJECT_ROOT / "docs" / "interview" / "ROADMAP.md"
PROJECT_STORY = PROJECT_ROOT / "docs" / "interview" / "PROJECT_STORY.md"
ROOT_README = PROJECT_ROOT / "README.md"
HUMAN_REVIEW_PROGRESS = (
    PROJECT_ROOT / "docs" / "interview" / "evidence" /
    "HUMAN_REVIEW_PROGRESS_2026-09-15.md"
)
ROW_PATTERN = re.compile(
    r"^\| (?P<id>[A-Z][0-9]{2}) \| (?P<priority>P[0-3]) \| "
    r"(?P<knowledge>[1-5])/(?P<frequency>[1-5]) \| "
    r"(?P<question>[^|]+) \| (?P<anchor>[^|]+) \| "
    r"(?P<status>READY|PARTIAL|GAP) \|$"
)


def expected_priority(knowledge, frequency):
    score = 0.55 * knowledge + 0.45 * frequency
    if score >= 4.5:
        return "P0"
    if score >= 3.7:
        return "P1"
    if score >= 2.8:
        return "P2"
    return "P3"


class InterviewDocumentationTests(unittest.TestCase):
    def test_question_bank_rows_are_unique_complete_and_correctly_prioritized(self):
        lines = QUESTION_BANK.read_text(encoding="utf-8").splitlines()
        candidate_lines = [line for line in lines if re.match(r"^\| [A-Z][0-9]{2} \|", line)]
        parsed = [ROW_PATTERN.fullmatch(line) for line in candidate_lines]
        self.assertTrue(all(parsed), "Every question row must follow the documented schema")
        rows = [match.groupdict() for match in parsed]
        ids = [row["id"] for row in rows]
        self.assertGreaterEqual(len(rows), 100)
        self.assertEqual(len(ids), len(set(ids)), "Question IDs must be globally unique")
        for row in rows:
            with self.subTest(question_id=row["id"]):
                self.assertTrue(row["question"].strip())
                self.assertTrue(row["anchor"].strip())
                self.assertEqual(
                    row["priority"],
                    expected_priority(int(row["knowledge"]), int(row["frequency"])),
                )

    def test_current_test_count_and_capability_claims_match_repository(self):
        discovered = unittest.TestLoader().discover(
            str(PROJECT_ROOT), pattern="test*.py"
        ).countTestCases()
        count_patterns = (
            (ROADMAP, r"\[x\] (\d+) 个有效离线测试"),
            (QUESTION_BANK, r"D14 .*?当前 (\d+) 项测试"),
            (QUESTION_BANK, r"F09 .*?当前 (\d+) 项覆盖"),
            (PROJECT_STORY, r"Result：(\d+) 项离线测试通过"),
            (PROJECT_STORY, r"当前开发环境的 (\d+) 项测试"),
        )
        for path, pattern in count_patterns:
            with self.subTest(path=path.name, pattern=pattern):
                match = re.search(pattern, path.read_text(encoding="utf-8"))
                self.assertIsNotNone(match, f"Missing current-test-count claim in {path}")
                self.assertEqual(int(match.group(1)), discovered)

        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (QUESTION_BANK, PROJECT_STORY, ROOT_README)
        )
        for obsolete in (
            "本项目尚未用持久化",
            "下一阶段纳入 SDK HTTP 重试与 embedding",
            "下一步是节点级 checkpoint",
        ):
            with self.subTest(obsolete=obsolete):
                self.assertNotIn(obsolete, combined)

        cases, _ = load_cases(DEFAULT_INPUTS)
        review_records, review_errors = read_review_records(DEFAULT_REVIEWS)
        self.assertFalse(review_errors)
        progress = review_progress(
            cases,
            review_records,
            sha256(DEFAULT_INDEX.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            HUMAN_REVIEW_PROGRESS.read_text(encoding="utf-8"),
            render_markdown(progress),
            "The authoritative human-review progress artifact must match the review log",
        )


if __name__ == "__main__":
    unittest.main()
