"""Compare full-context and selected-source grounding using live Qwen verifiers.

Both variants use today's prompt and real model. The baseline isolates the old
context wiring; it is not a replay of a previous model/prompt or a quality claim.
"""

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
from controllable_rag.chains import get_agent_chains  # noqa: E402
from controllable_rag.citations import build_evidence_records, render_evidence  # noqa: E402
from controllable_rag.config import get_settings  # noqa: E402
from controllable_rag.nodes import verify_answer, verify_distilled_content  # noqa: E402
from controllable_rag.prompts import PROMPT_VERSION  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).with_name("results"))
    args = parser.parse_args()
    dataset_path = Path(__file__).with_name("citation_grounding_cases.json")
    dataset_bytes = dataset_path.read_bytes()
    dataset = json.loads(dataset_bytes)
    records = build_evidence_records("chunks", [
        SimpleNamespace(page_content=source["content"], metadata={"page": source["page"]})
        for source in dataset["sources"]
    ])
    full_context = render_evidence(records)
    settings = get_settings()
    chains = get_agent_chains()
    ledger = BudgetLedger(max_requests=16, max_tokens=20000, max_elapsed_seconds=180)
    run_records = []
    for case_index, case in enumerate(dataset["cases"]):
        selected = [records[index] for index in case["selected"]]
        for stage in ("answer", "distillation"):
            # Alternate order to avoid always favouring the second variant.
            variants = ("all_evidence_context", "selected_source_context")
            if case_index % 2:
                variants = tuple(reversed(variants))
            for variant in variants:
                print(f"{case['id']} / {stage} / {variant}", flush=True)
                start = time.perf_counter()
                before_requests = ledger.requests_started
                record = {
                    "case_id": case["id"], "stage": stage, "variant": variant,
                    "expected_grounded": case["expected_grounded"],
                    "selected_source_ids": [source["id"] for source in selected],
                    "grounded": None, "error_type": None,
                }
                with activate_budget(ledger), get_openai_callback() as usage:
                    try:
                        if variant == "all_evidence_context":
                            chain = chains.ground_answer if stage == "answer" else chains.ground_distillation
                            inputs = (
                                {"context": full_context, "answer": case["claim"]}
                                if stage == "answer" else
                                {"original_context": full_context, "distilled_content": case["claim"]}
                            )
                            record["grounded"] = bool(chain.invoke(inputs).grounded)
                        elif stage == "answer":
                            record["grounded"] = verify_answer({
                                "context": full_context, "answer": case["claim"],
                                "evidence_records": records,
                                "supporting_ids": record["selected_source_ids"],
                            })["grounded"]
                        else:
                            record["grounded"] = verify_distilled_content({
                                "context": full_context, "relevant_context": case["claim"],
                                "retrieved_evidence": records, "relevant_evidence": selected,
                            })["grounded"]
                    except Exception as error:
                        # Keep failed attempts in evidence without provider bodies/secrets.
                        record["error_type"] = type(error).__name__
                record.update(
                    latency_seconds=round(time.perf_counter() - start, 4),
                    model_requests=ledger.requests_started - before_requests,
                    successful_requests=usage.successful_requests,
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                    token_usage_available=usage.total_tokens > 0,
                )
                run_records.append(record)
    summaries = {}
    for variant in ("all_evidence_context", "selected_source_context"):
        group = [record for record in run_records if record["variant"] == variant]
        negatives = [record for record in group if not record["expected_grounded"]]
        summaries[variant] = {
            "decisions": len(group),
            "matches_expected": sum(
                record["error_type"] is None and record["grounded"] == record["expected_grounded"]
                for record in group
            ),
            "unsupported_accepted": sum(record["grounded"] is True for record in negatives),
            "errors": sum(record["error_type"] is not None for record in group),
        }
    report = {
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "dataset_sha256": sha256(dataset_bytes).hexdigest(),
            "prompt_version": PROMPT_VERSION, "model": settings.chat_model,
            "base_url_host": urlsplit(settings.base_url).hostname,
            "temperature": 0, "max_output_tokens": 2000,
            "sdk_max_retries": settings.max_retries,
            "request_timeout_seconds": settings.request_timeout_seconds,
            "logical_call_limit": 16, "token_limit": 20000, "deadline_seconds": 180,
            "baseline": "all evidence context with the SAME current prompt/model",
            "scope": "4 synthetic cases x 2 verifier stages x 2 context variants; no retrieval/generation benchmark",
            "source_sha256": {
                path: sha256((PROJECT_ROOT / path).read_bytes()).hexdigest()
                for path in (
                    "controllable_rag/nodes.py", "controllable_rag/prompts.py",
                    "controllable_rag/citations.py", "evaluation/run_citation_grounding_probe.py",
                )
            },
            "packages": {name: version(name) for name in ("langchain-core", "langchain-openai", "langgraph")},
        },
        "summary": summaries, "budget": ledger.snapshot(), "records": run_records,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / f"citation-grounding-{uuid4().hex}.json"
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(json.dumps(summaries, indent=2))
    print(f"Report: {output}")
    if summaries["selected_source_context"]["matches_expected"] != 8:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
