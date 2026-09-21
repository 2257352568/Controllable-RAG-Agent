"""Run nonce facts through real Qwen embeddings, FAISS retrieval, and Qwen generation.

Two isolated in-memory indexes contain paired original and counterfactual facts.
The experiment is a contamination-resistant naive-RAG diagnostic, not a full
LangGraph-agent benchmark.
"""

import argparse
import json
import statistics
import sys
import time
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controllable_rag.config import get_settings  # noqa: E402
from controllable_rag.models import (  # noqa: E402
    create_chat_model,
    create_embedding_model,
)
from evaluation.run_context_reliance_evaluation import (  # noqa: E402
    DEFAULT_DATASET,
    build_prompt,
    score_case_outputs,
    usage_from_message,
    validate_cases,
)

DEFAULT_OUTPUT_DIR = Path(__file__).with_name("results")


def documents_for(cases, context_field):
    return [
        Document(
            page_content=case[context_field],
            metadata={"case_id": case["id"], "variant": context_field},
        )
        for case in cases
    ]


def retrieval_record(ranked, expected_case_id):
    documents = [document for document, _ in ranked]
    return {
        "top1_correct": bool(documents and documents[0].metadata.get("case_id") == expected_case_id),
        "ranked": [
            {
                "rank": rank,
                "case_id": document.metadata.get("case_id"),
                "variant": document.metadata.get("variant"),
                "distance": round(float(distance), 6),
                "content_sha256": sha256(document.page_content.encode("utf-8")).hexdigest(),
            }
            for rank, (document, distance) in enumerate(ranked, 1)
        ],
    }


def mean(values):
    return round(statistics.fmean(values), 4) if values else None


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--retrieval-k", type=int, default=1)
    parser.add_argument("--limit", type=int)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.retrieval_k <= 0:
        raise SystemExit("--retrieval-k must be greater than zero")
    cases = [json.loads(line) for line in args.dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    errors = validate_cases(cases)
    if errors:
        raise SystemExit("Private RAG dataset invalid:\n- " + "\n- ".join(errors))
    if args.limit is not None:
        if args.limit <= 0:
            raise SystemExit("--limit must be greater than zero")
        cases = cases[: args.limit]
    if args.retrieval_k > len(cases):
        raise SystemExit("--retrieval-k cannot exceed selected case count")

    settings = get_settings()
    embedding = create_embedding_model(settings)
    index_start = time.perf_counter()
    stores = {
        field: FAISS.from_documents(documents_for(cases, field), embedding)
        for field in ("correct_context", "counterfactual_context")
    }
    index_latency_ms = round((time.perf_counter() - index_start) * 1000, 4)
    model = create_chat_model(max_tokens=80, settings=settings)
    records = []
    total_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    usage_complete = True
    generation_latencies = []
    retrieval_latencies = []

    for case in cases:
        outputs = {}
        calls = {}
        print(f"[{case['id']}] no_context", flush=True)
        start = time.perf_counter()
        direct_message = model.invoke(build_prompt(case, None))
        direct_ms = round((time.perf_counter() - start) * 1000, 4)
        direct_usage = usage_from_message(direct_message)
        outputs["no_context"] = str(direct_message.content)
        calls["no_context"] = {"answer": outputs["no_context"], "latency_ms": direct_ms, "usage": direct_usage}
        generation_latencies.append(direct_ms)

        retrievals = {}
        for field in ("correct_context", "counterfactual_context"):
            print(f"[{case['id']}] retrieve {field}", flush=True)
            retrieval_start = time.perf_counter()
            ranked = stores[field].similarity_search_with_score(case["question"], k=args.retrieval_k)
            retrieval_ms = round((time.perf_counter() - retrieval_start) * 1000, 4)
            retrieval_latencies.append(retrieval_ms)
            retrievals[field] = {**retrieval_record(ranked, case["id"]), "latency_ms": retrieval_ms}
            retrieved_context = "\n\n".join(document.page_content for document, _ in ranked)
            generation_start = time.perf_counter()
            message = model.invoke(build_prompt(case, retrieved_context))
            generation_ms = round((time.perf_counter() - generation_start) * 1000, 4)
            generation_latencies.append(generation_ms)
            usage = usage_from_message(message)
            outputs[field] = str(message.content)
            calls[field] = {"answer": outputs[field], "latency_ms": generation_ms, "usage": usage}

        for call in calls.values():
            usage = call["usage"]
            if any(value is None for value in usage.values()):
                usage_complete = False
            else:
                for key, value in usage.items():
                    total_usage[key] += int(value)
        records.append({
            "case_id": case["id"],
            "category": case["category"],
            "scores": score_case_outputs(case, outputs),
            "retrievals": retrievals,
            "calls": calls,
        })

    score_names = tuple(records[0]["scores"])
    summary = {name: mean([float(record["scores"][name]) for record in records]) for name in score_names}
    for field in ("correct_context", "counterfactual_context"):
        summary[f"{field}_retrieval_top1_accuracy"] = mean([
            float(record["retrievals"][field]["top1_correct"]) for record in records
        ])
    summary["end_to_end_pair_success"] = mean([
        float(
            record["scores"]["context_switch_success"]
            and record["retrievals"]["correct_context"]["top1_correct"]
            and record["retrievals"]["counterfactual_context"]["top1_correct"]
        )
        for record in records
    ])
    report = {
        "_metadata": {
            "created_at": datetime.now().astimezone().isoformat(),
            "dataset": str(args.dataset.resolve()),
            "dataset_sha256": sha256(args.dataset.read_bytes()).hexdigest(),
            "chat_model": settings.chat_model,
            "embedding_model": settings.embedding_model,
            "embedding_dimensions": settings.embedding_dimensions,
            "index_type": type(stores["correct_context"].index).__name__,
            "documents_per_index": len(cases),
            "retrieval_k": args.retrieval_k,
            "logical_chat_calls": len(cases) * 3,
            "embedding_inputs": len(cases) * 4,
            "embedding_input_breakdown": {
                "document_inputs": len(cases) * 2,
                "query_inputs": len(cases) * 2,
            },
            "http_attempts": "not observable through current SDK wrappers",
            "chat_usage_complete": usage_complete,
            "chat_token_usage": total_usage if usage_complete else None,
            "embedding_token_usage": "not returned by current SDK response",
            "index_build_latency_ms": index_latency_ms,
            "mean_retrieval_latency_ms": mean(retrieval_latencies),
            "mean_generation_latency_ms": mean(generation_latencies),
            "scope": "Qwen embedding + in-memory FAISS Top-K + Qwen generation; not the LangGraph agent",
        },
        "summary": summary,
        "cases": records,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"private-rag-reliance-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"metadata": report["_metadata"], "summary": summary}, ensure_ascii=False, indent=2))
    print(f"Report: {output_path}")


if __name__ == "__main__":
    main()
