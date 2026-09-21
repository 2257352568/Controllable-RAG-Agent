"""Exercise Qwen structured claim citations through the compiled answer subgraph."""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

from langchain_community.callbacks import get_openai_callback

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controllable_rag.budget import BudgetLedger, activate_budget  # noqa: E402
from controllable_rag.citations import build_evidence_records, render_evidence  # noqa: E402
from controllable_rag.config import get_settings  # noqa: E402
from controllable_rag.graph import get_answer_workflow  # noqa: E402
from controllable_rag.prompts import PROMPT_VERSION  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).with_name("results"))
    args = parser.parse_args()
    dataset_path = Path(__file__).with_name("claim_citation_cases.json")
    dataset_bytes = dataset_path.read_bytes()
    dataset = json.loads(dataset_bytes)
    records = build_evidence_records("chunks", [
        SimpleNamespace(page_content=source["content"], metadata={"page": source["page"]})
        for source in dataset["sources"]
    ])
    settings = get_settings()
    workflow = get_answer_workflow()
    ledger = BudgetLedger(max_requests=8, max_tokens=12000, max_elapsed_seconds=120)
    outcomes = []
    for case in dataset["cases"]:
        started = time.perf_counter()
        before_requests = ledger.requests_started
        outcome = {"case_id": case["id"], "error_type": None}
        with activate_budget(ledger), get_openai_callback() as usage:
            try:
                result = workflow.invoke({
                    "question": case["question"],
                    "context": render_evidence(records),
                    "answer": "", "grounded": False, "attempts": 0,
                    "max_attempts": 2, "supporting_ids": [],
                    "claim_citations": [], "candidate_claim_citations": [],
                    "claim_citation_validation_error": "",
                    "evidence_records": records, "grounding_explanation": "",
                })
                expected_ids = {records[index]["id"] for index in case["expected_source_indexes"]}
                supporting_ids = set(result.get("supporting_ids") or [])
                outcome.update(
                    answer=result.get("answer", ""), grounded=bool(result.get("grounded")),
                    attempts=result.get("attempts", 0),
                    supporting_ids=result.get("supporting_ids", []),
                    claim_citations=result.get("claim_citations", []),
                    candidate_claim_citations=result.get("candidate_claim_citations", []),
                    validation_error=result.get("claim_citation_validation_error", ""),
                    grounding_explanation=result.get("grounding_explanation", ""),
                    expected_phrases_present=all(
                        phrase.casefold() in str(result.get("answer", "")).casefold()
                        for phrase in case["expected_phrases"]
                    ),
                    expected_sources_present=expected_ids.issubset(supporting_ids),
                )
            except Exception as error:
                outcome["error_type"] = type(error).__name__
        outcome.update(
            latency_seconds=round(time.perf_counter() - started, 4),
            model_requests=ledger.requests_started - before_requests,
            successful_requests=usage.successful_requests,
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
            token_usage_available=usage.total_tokens > 0,
        )
        outcome["passed"] = bool(
            outcome.get("error_type") is None
            and outcome.get("grounded")
            and outcome.get("expected_phrases_present")
            and outcome.get("expected_sources_present")
            and not outcome.get("validation_error")
            and outcome.get("claim_citations")
        )
        outcomes.append(outcome)
    report = {
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dataset_sha256": sha256(dataset_bytes).hexdigest(),
            "prompt_version": PROMPT_VERSION, "model": settings.chat_model,
            "base_url_host": urlsplit(settings.base_url).hostname,
            "temperature": 0, "max_output_tokens": 2000,
            "sdk_max_retries": settings.max_retries,
            "request_timeout_seconds": settings.request_timeout_seconds,
            "max_attempts_per_case": 2, "logical_call_limit": 8,
            "token_limit": 12000, "deadline_seconds": 120,
            "scope": "2 synthetic cases through answer generation and grounding; no retrieval/full Agent",
            "source_sha256": {
                path: sha256((PROJECT_ROOT / path).read_bytes()).hexdigest()
                for path in (
                    "controllable_rag/citations.py", "controllable_rag/nodes.py",
                    "controllable_rag/prompts.py", "controllable_rag/schemas.py",
                    "evaluation/run_claim_citation_probe.py",
                )
            },
            "packages": {name: version(name) for name in (
                "langchain-core", "langchain-openai", "langgraph",
            )},
        },
        "summary": {
            "cases": len(outcomes),
            "passed": sum(outcome["passed"] for outcome in outcomes),
            "errors": sum(outcome["error_type"] is not None for outcome in outcomes),
        },
        "budget": ledger.snapshot(), "cases": outcomes,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"claim-citation-{uuid4().hex}.json"
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(report["summary"], indent=2))
    print(f"Report: {output}")
    if report["summary"]["passed"] != len(outcomes):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
