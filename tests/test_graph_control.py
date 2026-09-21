import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from controllable_rag.graph import (
    create_agent,
    get_answer_workflow,
    get_retrieval_workflow,
)
from controllable_rag.nodes import (
    assess_answerability,
    filter_relevant_content,
    finalize_answer,
    initialize_state,
    plan_question,
    reject_disabled_source,
    replan,
    retrieve_chunks,
    route_after_replan,
    route_answer_grounding,
    route_distillation,
    route_tool,
    stop_for_budget,
    stop_for_search_exhaustion,
    verify_answer,
)
from controllable_rag.observability import ObservedNodeError, observed_node


class GraphControlTests(unittest.TestCase):
    def test_last_step_skips_replanner_but_preserves_answerability_path(self):
        state = {"question": "q", "plan": ["unused"], "step_count": 3,
                 "max_steps": 3, "route_decision": "insufficient"}
        with patch("controllable_rag.nodes.get_agent_chains") as chains:
            result = replan(state)
        chains.assert_not_called()
        self.assertEqual(result["plan"], ["unused"])
        self.assertEqual(result["curr_state"], "replan")
        self.assertEqual(route_after_replan({**result, "route_decision": "answerable"}),
                         "answerable")
        self.assertEqual(route_after_replan(result), "budget_exhausted")

    def test_eight_step_loop_reaches_business_budget_before_recursion_limit(self):
        def pass_through(name):
            return lambda state: {**state, "curr_state": name}

        def handle(state):
            return {
                **state, "curr_state": "task_handler",
                "tool": "retrieve_chunks",
                "step_count": state.get("step_count", 0) + 1,
            }

        def assess(state):
            return {**state, "route_decision": "insufficient"}

        with ExitStack() as patches:
            for name in (
                "anonymize_question", "plan_question", "deanonymize_plan",
                "break_down_plan", "retrieve_chunks", "replan",
            ):
                patches.enter_context(patch(
                    f"controllable_rag.nodes.{name}", pass_through(name)
                ))
            patches.enter_context(patch("controllable_rag.nodes.handle_task", handle))
            patches.enter_context(patch(
                "controllable_rag.nodes.assess_answerability", assess
            ))
            agent = create_agent()
        result = agent.invoke(
            {"question": "offline fixture", "max_steps": 8},
            config={"recursion_limit": 60},
        )
        self.assertEqual(result["termination_reason"], "step_budget_exhausted")
        self.assertEqual(result["step_count"], 8)

    def test_initialize_state_preserves_explicit_budget(self):
        state = initialize_state(
            {
                "question": "q",
                "max_steps": 3,
                "max_model_requests": 7,
                "max_total_tokens": 900,
                "enabled_retrieval_sources": ["chunks", "quotes"],
                "min_evidence_records": 2,
            }
        )
        self.assertEqual(state["max_steps"], 3)
        self.assertEqual(state["max_model_requests"], 7)
        self.assertEqual(state["max_total_tokens"], 900)
        self.assertEqual(state["model_requests"], 0)
        self.assertEqual(state["total_tokens"], 0)
        self.assertEqual(state["enabled_retrieval_sources"], ["chunks", "quotes"])
        self.assertEqual(state["min_evidence_records"], 2)
        self.assertEqual(state["step_count"], 0)
        self.assertEqual(state["attempted_retrieval_sources"], [])
        self.assertEqual(state["termination_reason"], "")
        self.assertEqual(state["trace_events"], [])
        self.assertEqual(state["evidence_records"], [])
        self.assertEqual(state["citations"], [])

    def test_initialize_state_rejects_non_positive_budget(self):
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            initialize_state({"question": "q", "max_steps": 0})
        with self.assertRaisesRegex(ValueError, "max_model_requests"):
            initialize_state({"question": "q", "max_model_requests": 0})
        with self.assertRaisesRegex(ValueError, "max_total_tokens"):
            initialize_state({"question": "q", "max_total_tokens": 0})
        with self.assertRaisesRegex(ValueError, "min_evidence_records"):
            initialize_state({"question": "q", "min_evidence_records": 0})
        with self.assertRaisesRegex(ValueError, "at least one"):
            initialize_state({"question": "q", "enabled_retrieval_sources": []})
        with self.assertRaisesRegex(ValueError, "unsupported"):
            initialize_state(
                {"question": "q", "enabled_retrieval_sources": ["web"]}
            )

    def test_budget_route_only_stops_when_answer_is_insufficient(self):
        self.assertEqual(
            route_after_replan(
                {"route_decision": "answerable", "step_count": 3, "max_steps": 3}
            ),
            "answerable",
        )
        self.assertEqual(
            route_after_replan(
                {"route_decision": "insufficient", "step_count": 3, "max_steps": 3}
            ),
            "budget_exhausted",
        )
        self.assertEqual(
            route_after_replan(
                {"route_decision": "insufficient", "step_count": 2, "max_steps": 3}
            ),
            "continue",
        )

    def test_source_sweep_stops_only_after_all_enabled_sources_are_tried(self):
        base = {
            "route_decision": "insufficient",
            "step_count": 3,
            "max_steps": 8,
            "retrieval_count": 3,
            "enabled_retrieval_sources": ["chunks", "summaries", "quotes"],
        }
        self.assertEqual(route_after_replan({
            **base, "attempted_retrieval_sources": ["chunks", "summaries"],
        }), "continue")
        swept = {**base, "attempted_retrieval_sources": [
            "chunks", "summaries", "quotes",
        ]}
        self.assertEqual(route_after_replan(swept), "search_exhausted")
        self.assertEqual(route_after_replan({**swept, "route_decision": "answerable"}),
                         "answerable")
        self.assertEqual(route_after_replan({
            **base, "enabled_retrieval_sources": ["chunks"],
            "attempted_retrieval_sources": ["chunks"], "retrieval_count": 1,
        }), "continue")
        stopped = stop_for_search_exhaustion(swept)
        self.assertEqual(stopped["termination_reason"], "search_exhausted")
        self.assertEqual(stopped["citations"], [])

    def test_grounding_retries_are_bounded(self):
        self.assertEqual(
            route_distillation({"grounded": False, "attempts": 1, "max_attempts": 2}),
            "retry",
        )
        self.assertEqual(
            route_distillation({"grounded": False, "attempts": 2, "max_attempts": 2}),
            "failed",
        )
        self.assertEqual(
            route_answer_grounding({"grounded": True, "attempts": 1, "max_attempts": 2}),
            "grounded",
        )

    def test_budget_stop_has_machine_readable_reason(self):
        result = stop_for_budget({"question": "q", "step_count": 2, "max_steps": 2})
        self.assertEqual(result["termination_reason"], "step_budget_exhausted")
        self.assertIn("step budget", result["response"])

    def test_observed_node_appends_serializable_event(self):
        wrapped = observed_node("sample", lambda state: {**state, "tool": "retrieve_chunks"})
        result = wrapped({"step_count": 1, "trace_events": []})
        event = result["trace_events"][0]
        self.assertEqual(event["sequence"], 1)
        self.assertEqual(event["node"], "sample")
        self.assertEqual(event["status"], "ok")
        self.assertGreaterEqual(event["duration_ms"], 0)

    def test_observed_node_propagates_exception_without_committing_false_success(self):
        def failing_node(_):
            raise RuntimeError("planned failure")

        wrapped = observed_node("failing", failing_node)
        state = {"trace_events": []}
        with self.assertRaisesRegex(
            ObservedNodeError, r"Node 'failing' failed \(RuntimeError\)"
        ) as raised:
            wrapped(state)
        self.assertEqual(state["trace_events"], [])
        self.assertEqual(raised.exception.diagnostics["node"], "failing")
        self.assertEqual(raised.exception.diagnostics["error_type"], "RuntimeError")
        self.assertGreaterEqual(raised.exception.diagnostics["duration_ms"], 0)

    def test_planner_preserves_state_and_uses_structured_steps(self):
        planner = SimpleNamespace(
            invoke=lambda payload: SimpleNamespace(
                steps=[f"retrieve evidence for {payload['question']}"]
            )
        )
        with patch(
            "controllable_rag.nodes.get_agent_chains",
            return_value=SimpleNamespace(planner=planner),
        ):
            result = plan_question(
                {"question": "original", "anonymized_question": "X question"}
            )
        self.assertEqual(result["curr_state"], "planner")
        self.assertEqual(result["plan"], ["retrieve evidence for X question"])
        self.assertEqual(result["question"], "original")

    def test_tool_routing_accepts_schema_values_and_rejects_unknown_values(self):
        self.assertEqual(route_tool({"tool": "retrieve_chunks"}), "chunks")
        self.assertEqual(route_tool({"tool": "answer"}), "answer")
        with self.assertRaisesRegex(ValueError, "Unsupported tool"):
            route_tool({"tool": "browse_web"})

    def test_tool_routing_blocks_a_disabled_retrieval_source(self):
        state = {
            "tool": "retrieve_quotes",
            "enabled_retrieval_sources": ["chunks"],
        }
        self.assertEqual(route_tool(state), "disabled")
        rejected = reject_disabled_source(state)
        self.assertEqual(rejected["curr_state"], "retrieval_source_disabled")
        self.assertIn("quotes", rejected["policy_feedback"])
        self.assertEqual(rejected["source_policy_events"][0]["action"], "blocked")

    def test_answerability_requires_deterministic_minimum_evidence(self):
        chain = SimpleNamespace(
            invoke=lambda _: SimpleNamespace(can_be_answered=True, explanation="yes")
        )
        with patch(
            "controllable_rag.nodes.get_agent_chains",
            return_value=SimpleNamespace(can_answer=chain),
        ):
            result = assess_answerability(
                {
                    "question": "q",
                    "aggregated_context": "context",
                    "evidence_records": [{"id": "one"}],
                    "min_evidence_records": 2,
                }
            )
        self.assertEqual(result["route_decision"], "insufficient")
        self.assertIn("below required minimum 2", result["evidence_gate_reason"])

    def test_finalize_fails_closed_below_minimum_evidence_without_model_call(self):
        with patch("controllable_rag.graph.get_answer_workflow") as workflow:
            result = finalize_answer(
                {
                    "question": "q",
                    "aggregated_context": "context",
                    "evidence_records": [{"id": "one"}],
                    "min_evidence_records": 2,
                }
            )
        workflow.assert_not_called()
        self.assertEqual(result["termination_reason"], "evidence_threshold_not_met")
        self.assertEqual(result["citations"], [])

    def test_retrieval_node_merges_validated_evidence_and_updates_count(self):
        old_record = {
            "id": "chunks-p1-old",
            "source": "chunks",
            "rank": 1,
            "content": "old",
            "metadata": {"page": 1},
        }
        new_record = {
            "id": "chunks-p2-new",
            "source": "chunks",
            "rank": 1,
            "content": "new evidence",
            "metadata": {"page": 2},
        }
        workflow = SimpleNamespace(
            invoke=lambda _: {
                "grounded": True,
                "relevant_context": "new evidence",
                "relevant_evidence": [new_record],
                "grounding_explanation": "supported",
            }
        )
        with patch(
            "controllable_rag.graph.get_retrieval_workflow", return_value=workflow
        ):
            result = retrieve_chunks(
                {
                    "query_to_retrieve_or_answer": "query",
                    "aggregated_context": "[chunks-p1-old]\nold",
                    "evidence_records": [old_record],
                    "retrieval_count": 1,
                }
            )
        self.assertEqual(result["retrieval_count"], 2)
        self.assertEqual(result["evidence_records"], [old_record, new_record])
        self.assertIn("[chunks-p2-new]", result["aggregated_context"])
        self.assertEqual(result["grounding_explanation"], "supported")

    def test_filter_rejects_model_invented_evidence_ids(self):
        record = {
            "id": "chunks-p1-deadbeef00",
            "source": "chunks",
            "rank": 1,
            "content": "evidence",
            "metadata": {"page": 1},
        }
        chain = SimpleNamespace(
            invoke=lambda _: SimpleNamespace(
                relevant_content="evidence",
                supporting_ids=[record["id"], "invented-id"],
            )
        )
        with patch(
            "controllable_rag.nodes.get_agent_chains",
            return_value=SimpleNamespace(keep_relevant_content=chain),
        ):
            result = filter_relevant_content(
                {
                    "question": "q",
                    "context": "evidence",
                    "retrieved_evidence": [record],
                    "attempts": 0,
                }
            )
        self.assertEqual(result["relevant_evidence"], [record])

    def test_grounded_answer_requires_a_valid_citation_when_evidence_exists(self):
        chain = SimpleNamespace(
            invoke=lambda _: SimpleNamespace(grounded=True, explanation="supported")
        )
        with patch(
            "controllable_rag.nodes.get_agent_chains",
            return_value=SimpleNamespace(ground_answer=chain),
        ):
            result = verify_answer(
                {
                    "context": "[known] evidence",
                    "answer": "answer",
                    "evidence_records": [{"id": "known"}],
                    "supporting_ids": [],
                }
            )
        self.assertFalse(result["grounded"])

    def test_finalize_renders_only_validated_citations(self):
        record = {
            "id": "chunks-p92-deadbeef00",
            "source": "chunks",
            "rank": 1,
            "content": "Caput Draconis",
            "metadata": {"page": 92},
        }
        workflow = SimpleNamespace(
            invoke=lambda _: {
                "grounded": True,
                "answer": "Caput Draconis.",
                "supporting_ids": [record["id"]],
                "claim_citations": [{
                    "claim": "Caput Draconis.",
                    "supporting_ids": [record["id"]],
                }],
                "attempts": 1,
            }
        )
        with patch("controllable_rag.graph.get_answer_workflow", return_value=workflow):
            result = finalize_answer(
                {
                    "question": "q",
                    "aggregated_context": "context",
                    "evidence_records": [record],
                    "answer_attempts": 0,
                }
            )
        self.assertEqual(result["termination_reason"], "answered")
        self.assertEqual(result["citations"], [record])
        self.assertEqual(result["last_generated_answer"], "Caput Draconis.")
        self.assertEqual(result["candidate_supporting_ids"], [record["id"]])
        self.assertEqual(result["claim_citations"][0]["claim"], "Caput Draconis.")
        self.assertIn(f"[{record['id']}]", result["response"])
        self.assertIn("chunks, page 92", result["response"])

    def test_finalize_preserves_grounding_failure_diagnostics(self):
        workflow = SimpleNamespace(
            invoke=lambda _: {
                "grounded": False,
                "answer": "candidate answer",
                "supporting_ids": ["known"],
                "grounding_explanation": "one claim was not supported",
                "attempts": 2,
            }
        )
        with patch("controllable_rag.graph.get_answer_workflow", return_value=workflow):
            result = finalize_answer(
                {
                    "question": "q",
                    "aggregated_context": "[known] context",
                    "evidence_records": [{"id": "known"}],
                    "answer_attempts": 0,
                }
            )
        self.assertEqual(result["termination_reason"], "grounding_failed")
        self.assertEqual(result["last_generated_answer"], "candidate answer")
        self.assertEqual(result["candidate_supporting_ids"], ["known"])
        self.assertEqual(
            result["grounding_explanation"], "one claim was not supported"
        )

    def test_finalize_rejects_unknown_citation(self):
        workflow = SimpleNamespace(
            invoke=lambda _: {
                "grounded": True,
                "answer": "unsupported",
                "supporting_ids": ["invented-id"],
                "attempts": 1,
            }
        )
        with patch("controllable_rag.graph.get_answer_workflow", return_value=workflow):
            result = finalize_answer(
                {
                    "question": "q",
                    "aggregated_context": "context",
                    "evidence_records": [{"id": "known"}],
                    "answer_attempts": 0,
                }
            )
        self.assertEqual(result["termination_reason"], "citation_validation_failed")
        self.assertEqual(result["citations"], [])

    def test_compiled_graph_contains_control_and_observation_nodes(self):
        graph = create_agent().get_graph()
        for node_name in ("initialize", "assess_answerability", "budget_exhausted"):
            self.assertIn(node_name, graph.nodes)
        edges = {(edge.source, edge.target) for edge in graph.edges}
        self.assertIn(("retrieve_chunks", "assess_answerability"), edges)
        self.assertIn(("assess_answerability", "replan"), edges)
        self.assertIn(("replan", "break_down_plan"), edges)

    def test_all_lazy_subgraphs_compile(self):
        self.assertIn("generate_answer", get_answer_workflow().get_graph().nodes)
        for source in ("chunks", "summaries", "quotes"):
            self.assertIn("retrieve", get_retrieval_workflow(source).get_graph().nodes)


if __name__ == "__main__":
    unittest.main()
