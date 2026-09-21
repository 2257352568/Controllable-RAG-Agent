"""Pure and side-effecting node functions used by the LangGraph workflows."""


from .chains import get_agent_chains
from .citations import (
    build_evidence_records,
    cited_records,
    claim_citation_ids,
    merge_evidence,
    render_claim_cited_answer,
    render_distilled_context,
    render_evidence,
    validate_citation_ids,
    validate_claim_citations,
)
from .config import get_settings
from .policy import unique_evidence_count, validate_evidence_minimum, validate_sources
from .retrieval import get_retriever
from .schemas import PlanExecute
from .text import apply_entity_mapping
from .tracing import new_trace_id, validate_trace_id


def _escaped(text):
    # Vector-store text may include quotes, but PromptTemplate accepts normal text;
    # preserving content avoids the lossy legacy quote replacement helper.
    return str(text)


def _enabled_sources(state):
    sources = state.get("enabled_retrieval_sources")
    return validate_sources(
        get_settings().enabled_retrieval_sources if sources is None else sources
    )


def _evidence_gate(state):
    minimum = validate_evidence_minimum(state.get(
        "min_evidence_records", get_settings().min_evidence_records
    ))
    count = unique_evidence_count(state.get("evidence_records"))
    return "" if count >= minimum else (
        f"validated evidence {count} is below required minimum {minimum}"
    )


def initialize_state(state: PlanExecute):
    # This pinned LangGraph version materializes absent TypedDict channels as None.
    # Strip those placeholders so minimal UI/Python inputs receive real defaults.
    state = {key: value for key, value in state.items() if value is not None}
    settings = get_settings()
    max_steps = int(state.get("max_steps", settings.agent_max_steps))
    max_model_requests = int(
        state.get("max_model_requests", settings.agent_max_model_requests)
    )
    max_total_tokens = int(
        state.get("max_total_tokens", settings.agent_max_total_tokens)
    )
    max_elapsed_seconds = float(
        state.get("max_elapsed_seconds", settings.agent_max_elapsed_seconds)
    )
    max_embedding_requests = int(
        state.get(
            "max_embedding_requests", settings.agent_max_embedding_requests
        )
    )
    max_embedding_inputs = int(
        state.get("max_embedding_inputs", settings.agent_max_embedding_inputs)
    )
    enabled_sources = list(_enabled_sources(state))
    min_evidence_records = validate_evidence_minimum(
        state.get("min_evidence_records", settings.min_evidence_records)
    )
    trace_id = validate_trace_id(state.get("trace_id") or new_trace_id())
    trace_enabled = state.get("trace_enabled", settings.trace_enabled)
    if type(trace_enabled) is not bool:
        raise ValueError("trace_enabled must be a boolean")
    for name, value in (
        ("max_steps", max_steps),
        ("max_model_requests", max_model_requests),
        ("max_total_tokens", max_total_tokens),
        ("max_elapsed_seconds", max_elapsed_seconds),
        ("max_embedding_requests", max_embedding_requests),
        ("max_embedding_inputs", max_embedding_inputs),
        ("min_evidence_records", min_evidence_records),
    ):
        if value <= 0:
            raise ValueError(f"{name} must be greater than zero, got {value}")
    return {
        **state,
        "curr_state": "initialize",
        "anonymized_question": state.get("anonymized_question", ""),
        "query_to_retrieve_or_answer": state.get("query_to_retrieve_or_answer", ""),
        "plan": list(state.get("plan") or []),
        "past_steps": list(state.get("past_steps") or []),
        "mapping": dict(state.get("mapping") or {}),
        "curr_context": state.get("curr_context", ""),
        "aggregated_context": state.get("aggregated_context", ""),
        "tool": state.get("tool", ""),
        "response": state.get("response", ""),
        "max_steps": max_steps,
        "max_model_requests": max_model_requests,
        "max_total_tokens": max_total_tokens,
        "max_elapsed_seconds": max_elapsed_seconds,
        "elapsed_seconds": float(state.get("elapsed_seconds") or 0.0),
        "max_embedding_requests": max_embedding_requests,
        "max_embedding_inputs": max_embedding_inputs,
        "embedding_requests": int(state.get("embedding_requests") or 0),
        "embedding_inputs": int(state.get("embedding_inputs") or 0),
        "enabled_retrieval_sources": enabled_sources,
        "min_evidence_records": min_evidence_records,
        "evidence_gate_reason": state.get("evidence_gate_reason", ""),
        "policy_feedback": state.get("policy_feedback", ""),
        "source_policy_events": list(state.get("source_policy_events") or []),
        "trace_id": trace_id,
        "trace_enabled": trace_enabled,
        "trace_persisted": False,
        "trace_path": "",
        "model_requests": int(state.get("model_requests") or 0),
        "input_tokens": int(state.get("input_tokens") or 0),
        "output_tokens": int(state.get("output_tokens") or 0),
        "total_tokens": int(state.get("total_tokens") or 0),
        "token_accounting_available": bool(
            state.get("token_accounting_available", False)
        ),
        "step_count": int(state.get("step_count") or 0),
        "retrieval_count": int(state.get("retrieval_count") or 0),
        "attempted_retrieval_sources": list(
            state.get("attempted_retrieval_sources") or []
        ),
        "answer_attempts": int(state.get("answer_attempts") or 0),
        "termination_reason": state.get("termination_reason", ""),
        "route_decision": state.get("route_decision", ""),
        "trace_events": list(state.get("trace_events") or []),
        "evidence_records": list(state.get("evidence_records") or []),
        "citations": list(state.get("citations") or []),
        "claim_citations": list(state.get("claim_citations") or []),
        "last_generated_answer": state.get("last_generated_answer", ""),
        "candidate_supporting_ids": list(
            state.get("candidate_supporting_ids") or []
        ),
        "candidate_claim_citations": list(
            state.get("candidate_claim_citations") or []
        ),
        "claim_citation_validation_error": state.get(
            "claim_citation_validation_error", ""
        ),
        "grounding_explanation": state.get("grounding_explanation", ""),
    }


def _retrieve_context(state, source):
    if source not in _enabled_sources(state):
        # Also guard direct subgraph invocations, before loading any index/model.
        raise ValueError(f"Retrieval source {source!r} is disabled")
    documents = get_retriever(source).invoke(state["question"])
    evidence = build_evidence_records(source, documents)
    return {
        **state,
        "context": _escaped(render_evidence(evidence)),
        "retrieved_evidence": evidence,
        "relevant_evidence": [],
    }


def retrieve_chunks_context(state):
    return _retrieve_context(state, "chunks")


def retrieve_summaries_context(state):
    return _retrieve_context(state, "summaries")


def retrieve_quotes_context(state):
    return _retrieve_context(state, "quotes")


def filter_relevant_content(state):
    output = get_agent_chains().keep_relevant_content.invoke(
        {"query": state["question"], "retrieved_documents": state["context"]}
    )
    supporting_ids = validate_citation_ids(
        output.supporting_ids, state.get("retrieved_evidence", [])
    )
    return {
        **state,
        "relevant_context": _escaped(output.relevant_content),
        "relevant_evidence": cited_records(
            supporting_ids, state.get("retrieved_evidence", [])
        ),
        "attempts": int(state.get("attempts", 0)) + 1,
    }


def verify_distilled_content(state):
    # Resolve IDs back to the retrieved originals. The full retrieval context may
    # support the claim even when the selected citations refer to other facts.
    selected = cited_records(
        [record["id"] for record in state.get("relevant_evidence", [])],
        state.get("retrieved_evidence", []),
    )
    if not selected or not state.get("relevant_context", "").strip():
        return {
            **state,
            "relevant_evidence": selected,
            "grounded": False,
            "grounding_explanation": "Non-empty content and selected source evidence are required.",
        }
    decision = get_agent_chains().ground_distillation.invoke(
        {
            "distilled_content": state["relevant_context"],
            "original_context": render_evidence(selected),
        }
    )
    return {
        **state,
        "relevant_evidence": selected,
        "grounded": bool(decision.grounded),
        "grounding_explanation": decision.explanation,
    }


def route_distillation(state):
    if state.get("grounded"):
        return "grounded"
    if state.get("attempts", 0) < state.get("max_attempts", 1):
        return "retry"
    return "failed"


def answer_from_context(state):
    retry_feedback = "none"
    if state.get("attempts", 0):
        candidate_feedback = state.get("claim_citation_validation_error")
        retry_feedback = (
            candidate_feedback
            if candidate_feedback in {
                "answer_has_no_claims", "duplicate_answer_sentence",
                "claim_supporting_ids_invalid", "claim_contains_unknown_evidence_id",
                "claim_not_found_as_answer_sentence", "duplicate_claim_mapping",
                "claim_has_no_evidence", "not_every_answer_sentence_is_mapped",
                "claim_order_mismatch",
            }
            else "grounding_failed"
        )
    output = get_agent_chains().answer_from_context.invoke(
        {
            "question": state["question"],
            "context": state["context"],
            "retry_feedback": retry_feedback,
        }
    )
    raw_claim_citations = [
        item.model_dump() if hasattr(item, "model_dump") else dict(item)
        for item in (output.claim_citations or [])
    ]
    claim_citations, validation_error = validate_claim_citations(
        output.answer_based_on_content,
        raw_claim_citations,
        state.get("evidence_records", []),
    )
    supporting_ids = claim_citation_ids(claim_citations)
    return {
        **state,
        "answer": output.answer_based_on_content,
        "supporting_ids": supporting_ids,
        "claim_citations": claim_citations,
        "candidate_claim_citations": raw_claim_citations,
        "claim_citation_validation_error": validation_error,
        "attempts": int(state.get("attempts", 0)) + 1,
    }


def verify_answer(state):
    selected = cited_records(
        state.get("supporting_ids", []), state.get("evidence_records", [])
    )
    if not selected or not state.get("answer", "").strip():
        return {
            **state,
            "grounded": False,
            "grounding_explanation": "Non-empty answer and selected source evidence are required.",
        }
    if state.get("claim_citation_validation_error") or not state.get("claim_citations"):
        return {
            **state,
            "grounded": False,
            "grounding_explanation": (
                "A complete sentence-to-evidence mapping is required: "
                f"{state.get('claim_citation_validation_error') or 'mapping_missing'}"
            ),
        }
    decision = get_agent_chains().ground_answer.invoke(
        {"context": render_evidence(selected), "answer": state["answer"]}
    )
    return {
        **state,
        "grounded": bool(decision.grounded),
        "grounding_explanation": decision.explanation,
    }


def route_answer_grounding(state):
    if state.get("grounded"):
        return "grounded"
    if state.get("attempts", 0) < state.get("max_attempts", 1):
        return "retry"
    return "failed"


def anonymize_question(state: PlanExecute):
    output = get_agent_chains().anonymize_question.invoke({"question": state["question"]})
    return {
        **state,
        "curr_state": "anonymize_question",
        "anonymized_question": output.anonymized_question,
        "mapping": output.mapping,
    }


def plan_question(state: PlanExecute):
    output = get_agent_chains().planner.invoke({
        "question": state["anonymized_question"],
        "enabled_sources": ", ".join(_enabled_sources(state)),
    })
    return {**state, "curr_state": "planner", "plan": output.steps}


def deanonymize_plan(state: PlanExecute):
    return {
        **state,
        "curr_state": "de_anonymize_plan",
        "plan": apply_entity_mapping(state["plan"], state["mapping"]),
    }


def break_down_plan(state: PlanExecute):
    output = get_agent_chains().break_down_plan.invoke({
        "plan": state["plan"],
        "enabled_sources": ", ".join(_enabled_sources(state)),
    })
    return {**state, "curr_state": "break_down_plan", "plan": output.steps}


def handle_task(state: PlanExecute):
    if not state.get("plan"):
        raise ValueError("The task handler received an empty plan")
    current_task = state["plan"][0]
    output = get_agent_chains().task_handler.invoke(
        {
            "curr_task": current_task,
            "aggregated_context": state.get("aggregated_context", ""),
            "last_tool": state.get("tool", ""),
            "past_steps": state.get("past_steps", []),
            "question": state["question"],
            "enabled_sources": ", ".join(_enabled_sources(state)),
            "policy_feedback": state.get("policy_feedback", ""),
        }
    )
    tool = "answer" if output.tool == "answer_from_context" else output.tool
    return {
        **state,
        "curr_state": "task_handler",
        "past_steps": [*state.get("past_steps", []), current_task],
        "plan": state["plan"][1:],
        "query_to_retrieve_or_answer": output.query,
        "curr_context": (
            state.get("aggregated_context", "")
            if tool == "answer"
            else state.get("curr_context", "")
        ),
        "tool": tool,
        "step_count": int(state.get("step_count", 0)) + 1,
        "policy_feedback": "",
    }


def route_tool(state: PlanExecute):
    routes = {
        "retrieve_chunks": "chunks",
        "retrieve_summaries": "summaries",
        "retrieve_quotes": "quotes",
        "answer": "answer",
    }
    try:
        route = routes[state["tool"]]
    except KeyError as error:
        raise ValueError(f"Unsupported tool: {state.get('tool')!r}") from error
    if route != "answer" and route not in _enabled_sources(state):
        return "disabled"
    return route


def reject_disabled_source(state: PlanExecute):
    source = str(state.get("tool", "")).removeprefix("retrieve_")
    enabled = list(_enabled_sources(state))
    feedback = (
        f"source '{source}' is disabled; enabled sources: {', '.join(enabled)}. "
        "This attempted task did not retrieve any evidence; replan using an enabled source."
    )
    return {
        **state,
        "curr_state": "retrieval_source_disabled",
        "route_decision": "insufficient",
        "policy_feedback": feedback,
        "source_policy_events": [*state.get("source_policy_events", []), {
            "source": source, "action": "blocked",
            "enabled_sources": enabled, "step_count": state.get("step_count", 0),
        }],
    }


def _run_retrieval(state: PlanExecute, source):
    from .graph import get_retrieval_workflow

    if source not in _enabled_sources(state):
        return reject_disabled_source({**state, "tool": f"retrieve_{source}"})
    result = get_retrieval_workflow(source).invoke(
        {
            "enabled_retrieval_sources": list(_enabled_sources(state)),
            "question": state["query_to_retrieve_or_answer"],
            "context": "",
            "relevant_context": "",
            "grounded": False,
            "attempts": 0,
            "max_attempts": get_settings().grounding_max_attempts,
            "retrieved_evidence": [],
            "relevant_evidence": [],
            "grounding_explanation": "",
        }
    )
    relevant_evidence = result.get("relevant_evidence", []) if result.get("grounded") else []
    supporting_ids = [record["id"] for record in relevant_evidence]
    context = (
        render_distilled_context(result.get("relevant_context", ""), supporting_ids)
        if relevant_evidence
        else ""
    )
    return {
        **state,
        "curr_state": f"retrieve_{source}",
        "aggregated_context": "\n\n".join(
            part for part in (state.get("aggregated_context", ""), context) if part
        ),
        "evidence_records": merge_evidence(
            state.get("evidence_records", []), relevant_evidence
        ),
        "retrieval_count": int(state.get("retrieval_count", 0)) + 1,
        "attempted_retrieval_sources": list(dict.fromkeys([
            *state.get("attempted_retrieval_sources", []), source,
        ])),
        "grounding_explanation": result.get("grounding_explanation", ""),
    }


def retrieve_chunks(state: PlanExecute):
    return _run_retrieval(state, "chunks")


def retrieve_summaries(state: PlanExecute):
    return _run_retrieval(state, "summaries")


def retrieve_quotes(state: PlanExecute):
    return _run_retrieval(state, "quotes")


def answer_intermediate(state: PlanExecute):
    from .graph import get_answer_workflow

    result = get_answer_workflow().invoke(
        {
            "question": state["query_to_retrieve_or_answer"],
            "context": state.get("curr_context", ""),
            "answer": "",
            "grounded": False,
            "attempts": 0,
            "max_attempts": get_settings().grounding_max_attempts,
            "supporting_ids": [],
            "claim_citations": [],
            "candidate_claim_citations": [],
            "claim_citation_validation_error": "",
            "evidence_records": state.get("evidence_records", []),
            "grounding_explanation": "",
        }
    )
    answer = result.get("answer", "") if result.get("grounded") else ""
    answer_context = (
        render_distilled_context(answer, result.get("supporting_ids", []))
        if answer
        else ""
    )
    return {
        **state,
        "curr_state": "answer",
        "aggregated_context": "\n\n".join(
            part
            for part in (state.get("aggregated_context", ""), answer_context)
            if part
        ),
        "answer_attempts": int(state.get("answer_attempts", 0)) + result.get("attempts", 0),
        "last_generated_answer": result.get("answer", ""),
        "candidate_supporting_ids": list(result.get("supporting_ids") or []),
        "candidate_claim_citations": list(
            result.get("candidate_claim_citations") or []
        ),
        "claim_citation_validation_error": result.get(
            "claim_citation_validation_error", ""
        ),
        "grounding_explanation": result.get("grounding_explanation", ""),
    }


def replan(state: PlanExecute):
    # No additional task can run after the last permitted step. Keep the
    # answerability check: evidence gathered on that step may still suffice.
    if state.get("step_count", 0) >= state.get("max_steps", 1):
        return {**state, "curr_state": "replan"}
    output = get_agent_chains().replanner.invoke(
        {
            "question": state["question"],
            "plan": state.get("plan", []),
            "past_steps": state.get("past_steps", []),
            "aggregated_context": state.get("aggregated_context", ""),
            "enabled_sources": ", ".join(_enabled_sources(state)),
            "policy_feedback": state.get("policy_feedback", ""),
            "evidence_gate_reason": _evidence_gate(state),
        }
    )
    return {**state, "curr_state": "replan", "plan": output.steps}


def assess_answerability(state: PlanExecute):
    gate_reason = _evidence_gate(state)
    if gate_reason:
        return {
            **state, "curr_state": "assess_answerability",
            "route_decision": "insufficient", "evidence_gate_reason": gate_reason,
        }
    decision = get_agent_chains().can_answer.invoke(
        {"question": state["question"], "context": state.get("aggregated_context", "")}
    )
    return {
        **state,
        "curr_state": "assess_answerability",
        "route_decision": (
            "answerable" if decision.can_be_answered else "insufficient"
        ),
        "evidence_gate_reason": "",
    }


def route_after_assessment(state: PlanExecute):
    if state.get("route_decision") == "answerable":
        return "answerable"
    attempted = set(state.get("attempted_retrieval_sources") or [])
    if (
        state.get("retrieval_count", 0) >= 2
        and set(_enabled_sources(state)).issubset(attempted)
    ):
        return "search_exhausted"
    if state.get("step_count", 0) >= state.get("max_steps", 1):
        return "budget_exhausted"
    return "continue"


# Keep the legacy export used by functions_for_pipeline.py.
route_after_replan = route_after_assessment


def finalize_answer(state: PlanExecute):
    from .graph import get_answer_workflow

    gate_reason = _evidence_gate(state)
    if gate_reason:
        return {
            **state,
            "curr_state": "get_final_answer",
            "response": "The available evidence did not meet the configured minimum threshold.",
            "termination_reason": "evidence_threshold_not_met",
            "citations": [],
            "claim_citations": [],
            "evidence_gate_reason": gate_reason,
        }

    result = get_answer_workflow().invoke(
        {
            "question": state["question"],
            "context": state.get("aggregated_context", ""),
            "answer": "",
            "grounded": False,
            "attempts": 0,
            "max_attempts": get_settings().grounding_max_attempts,
            "supporting_ids": [],
            "claim_citations": [],
            "candidate_claim_citations": [],
            "claim_citation_validation_error": "",
            "evidence_records": state.get("evidence_records", []),
            "grounding_explanation": "",
        }
    )
    if result.get("grounded"):
        citations = cited_records(
            result.get("supporting_ids", []), state.get("evidence_records", [])
        )
        if citations:
            response = render_claim_cited_answer(
                result.get("claim_citations", []), citations
            )
            reason = "answered"
        else:
            response = "The answer could not be linked to a validated source."
            reason = "citation_validation_failed"
    else:
        citations = []
        response = "The available evidence was insufficient to produce a grounded answer."
        reason = "grounding_failed"
    return {
        **state,
        "curr_state": "get_final_answer",
        "response": response,
        "termination_reason": reason,
        "citations": citations,
        "claim_citations": (
            list(result.get("claim_citations") or []) if reason == "answered" else []
        ),
        "answer_attempts": int(state.get("answer_attempts", 0)) + result.get("attempts", 0),
        "last_generated_answer": result.get("answer", ""),
        "candidate_supporting_ids": list(result.get("supporting_ids") or []),
        "candidate_claim_citations": list(
            result.get("candidate_claim_citations") or []
        ),
        "claim_citation_validation_error": result.get(
            "claim_citation_validation_error", ""
        ),
        "grounding_explanation": result.get("grounding_explanation", ""),
    }


def stop_for_budget(state: PlanExecute):
    return {
        **state,
        "curr_state": "budget_exhausted",
        "response": "Unable to answer with sufficient evidence within the configured step budget.",
        "termination_reason": "step_budget_exhausted",
    }


def stop_for_search_exhaustion(state: PlanExecute):
    return {
        **state,
        "curr_state": "search_exhausted",
        "response": "I could not find sufficient evidence in the enabled sources to answer.",
        "termination_reason": "search_exhausted",
        "citations": [],
        "claim_citations": [],
    }
