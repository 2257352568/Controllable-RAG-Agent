"""Parse and prioritize the Markdown interview question bank."""

import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

ROW_PATTERN = re.compile(
    r"^\| (?P<id>[A-Z][0-9]{2}) \| (?P<priority>P[0-3]) \| "
    r"(?P<knowledge>[1-5])/(?P<frequency>[1-5]) \| "
    r"(?P<question>[^|]+) \| (?P<anchor>[^|]+) \| "
    r"(?P<status>READY|PARTIAL|GAP) \|$"
)
SECTION_PATTERN = re.compile(r"^## (?P<section>[A-Z])\. (?P<title>.+)$")
STATUS_ORDER = {"GAP": 0, "PARTIAL": 1, "READY": 2}


@dataclass(frozen=True)
class InterviewQuestion:
    id: str
    priority: str
    knowledge: int
    frequency: int
    question: str
    anchor: str
    status: str
    section: str

    @property
    def score(self):
        return round(0.55 * self.knowledge + 0.45 * self.frequency, 2)


def parse_question_bank(text):
    questions = []
    section = "Unknown"
    for line in text.splitlines():
        section_match = SECTION_PATTERN.fullmatch(line)
        if section_match:
            section = f"{section_match['section']}. {section_match['title']}"
            continue
        match = ROW_PATTERN.fullmatch(line)
        if not match:
            continue
        values = match.groupdict()
        questions.append(InterviewQuestion(
            id=values["id"], priority=values["priority"],
            knowledge=int(values["knowledge"]), frequency=int(values["frequency"]),
            question=values["question"].strip(), anchor=values["anchor"].strip(),
            status=values["status"], section=section,
        ))
    return questions


def prioritized_questions(questions):
    return sorted(
        questions,
        key=lambda item: (
            int(item.priority[1:]), STATUS_ORDER[item.status],
            -item.score, item.id,
        ),
    )


def render_study_queue(source_path, questions, limit=50):
    source_bytes = Path(source_path).read_bytes()
    selected = prioritized_questions(questions)[:limit]
    counts = {
        status: sum(item.status == status for item in questions)
        for status in STATUS_ORDER
    }
    lines = [
        "# 面试冲刺队列",
        "",
        "> 此文件由 `evaluation/build_interview_queue.py` 生成，请勿手工编辑。",
        "",
        f"- Question bank SHA256: `{sha256(source_bytes).hexdigest()}`",
        f"- 总题数：{len(questions)}",
        f"- 状态：GAP {counts['GAP']} / PARTIAL {counts['PARTIAL']} / READY {counts['READY']}",
        f"- 当前展示：前 {len(selected)} 题",
        "- 排序：P0→P3；同级 GAP→PARTIAL→READY；再按综合分降序、ID 升序。",
        "",
        "| 排名 | ID | 优先级 | K/F | 分数 | 状态 | 问题 |",
        "|---:|---|---|---:|---:|---|---|",
    ]
    for rank, item in enumerate(selected, 1):
        lines.append(
            f"| {rank} | {item.id} | {item.priority} | "
            f"{item.knowledge}/{item.frequency} | {item.score:.2f} | "
            f"{item.status} | {item.question} |"
        )
    lines.extend([
        "",
        "使用建议：GAP 先补项目能力或原理，PARTIAL 补证据和取舍，READY 用“结论—原理—项目实现—取舍—证据—改进”结构做脱稿复述。",
        "",
    ])
    return "\n".join(lines)
