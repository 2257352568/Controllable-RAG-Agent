"""Provenance regressions using a deterministic synthetic-fact verifier."""

import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

from controllable_rag.citations import build_evidence_records, render_evidence
from controllable_rag.config import Settings
from controllable_rag.graph import get_answer_workflow, get_retrieval_workflow
from controllable_rag.nodes import (
    answer_from_context,
    finalize_answer,
    retrieve_chunks,
    verify_answer,
    verify_distilled_content,
)


class CitationGroundingTests(unittest.TestCase):
    def test_answer_retry_receives_only_bounded_validation_code(self):
        answer = self.fact
        generator = SimpleNamespace(invoke=Mock(side_effect=[
            SimpleNamespace(
                answer_based_on_content=answer,
                claim_citations=[{
                    "claim": "A paraphrase of the answer.",
                    "supporting_ids": [self.records[0]["id"]],
                }],
            ),
            SimpleNamespace(
                answer_based_on_content=answer,
                claim_citations=[{
                    "claim": answer,
                    "supporting_ids": [self.records[0]["id"]],
                }],
            ),
        ]))
        state = {
            "question": "What is the cabinet code?",
            "context": render_evidence(self.records),
            "evidence_records": self.records,
            "attempts": 0,
        }
        with patch("controllable_rag.nodes.get_agent_chains",
                   return_value=SimpleNamespace(answer_from_context=generator)):
            first = answer_from_context(state)
            second = answer_from_context(first)
        self.assertEqual(first["claim_citation_validation_error"],
                         "claim_not_found_as_answer_sentence")
        self.assertEqual(generator.invoke.call_args_list[0].args[0]["retry_feedback"],
                         "none")
        self.assertEqual(generator.invoke.call_args_list[1].args[0]["retry_feedback"],
                         "claim_not_found_as_answer_sentence")
        self.assertEqual(second["supporting_ids"], [self.records[0]["id"]])

    def setUp(self):
        self.fact = "The Neral-731 cabinet code is VASK-204."
        self.other_fact = "The Miven-982 cabinet code is TOLP-618."
        self.documents = [
            SimpleNamespace(page_content=content, metadata={"page": page})
            for page, content in enumerate((self.fact, self.other_fact), start=1)
        ]
        self.records = build_evidence_records("chunks", self.documents)

    def verifier(self, stage):
        context_key, claim_key = (
            ("context", "answer") if stage == "answer"
            else ("original_context", "distilled_content")
        )

        def decide(inputs):
            # A deliberately simple oracle for these exact synthetic claims.
            # Its purpose is to expose wrong context wiring, not test LLM quality.
            supported = all(
                claim in inputs[context_key] for claim in inputs[claim_key].split(" + ")
            )
            return SimpleNamespace(grounded=supported, explanation="synthetic fact check")

        return SimpleNamespace(invoke=Mock(side_effect=decide))

    def state_for(self, stage, selected, claim=None):
        context = render_evidence(self.records)
        if stage == "answer":
            supporting_ids = [record["id"] for record in selected]
            return {
                "context": context, "answer": claim or self.fact,
                "evidence_records": self.records,
                "supporting_ids": supporting_ids,
                "claim_citations": [{
                    "claim": claim or self.fact, "supporting_ids": supporting_ids,
                }],
                "claim_citation_validation_error": "",
            }
        return {
            "context": context, "relevant_context": claim or self.fact,
            "retrieved_evidence": self.records, "relevant_evidence": selected,
        }

    def verify(self, stage, state, verifier):
        chains = SimpleNamespace(**{f"ground_{stage}": verifier})
        node = verify_answer if stage == "answer" else verify_distilled_content
        with patch("controllable_rag.nodes.get_agent_chains", return_value=chains):
            return node(state)

    def test_existing_but_unrelated_citation_cannot_borrow_uncited_support(self):
        for stage in ("answer", "distillation"):
            with self.subTest(stage=stage):
                verifier = self.verifier(stage)
                state = self.state_for(stage, [self.records[1]])
                result = self.verify(stage, state, verifier)
                self.assertFalse(result["grounded"])
                inputs = verifier.invoke.call_args.args[0]
                context_key = "context" if stage == "answer" else "original_context"
                self.assertNotIn(self.fact, inputs[context_key])
                self.assertIn(self.other_fact, inputs[context_key])

    def test_each_multi_hop_premise_must_be_in_selected_sources(self):
        claim = self.fact + " + " + self.other_fact
        for stage in ("answer", "distillation"):
            for selected, expected in ((self.records[:1], False), (self.records, True)):
                with self.subTest(stage=stage, selected_count=len(selected)):
                    result = self.verify(
                        stage, self.state_for(stage, selected, claim), self.verifier(stage)
                    )
                    self.assertEqual(result["grounded"], expected)

    def test_original_sources_override_derived_context_and_modified_copies(self):
        for stage in ("answer", "distillation"):
            with self.subTest(stage=stage):
                state = self.state_for(stage, self.records[:1])
                state["context"] = self.other_fact
                result = self.verify(stage, state, self.verifier(stage))
                self.assertTrue(result["grounded"])

        copied = {**self.records[1], "content": self.fact}
        state = self.state_for("distillation", [copied])
        result = self.verify("distillation", state, self.verifier("distillation"))
        self.assertFalse(result["grounded"])
        self.assertEqual(result["relevant_evidence"], [self.records[1]])
        self.assertEqual(state["relevant_evidence"], [copied])

    def test_missing_evidence_or_blank_content_skips_paid_verifier(self):
        for stage in ("answer", "distillation"):
            for problem in ("missing_selection", "unknown_id", "empty_sources", "blank"):
                with self.subTest(stage=stage, problem=problem):
                    state = self.state_for(stage, self.records[:1])
                    if problem == "missing_selection":
                        state.update(
                            supporting_ids=[], claim_citations=[], relevant_evidence=[]
                        )
                    elif problem == "unknown_id":
                        state.update(
                            supporting_ids=["unknown"],
                            claim_citations=[{
                                "claim": self.fact, "supporting_ids": ["unknown"],
                            }],
                            relevant_evidence=[{"id": "unknown"}],
                        )
                    elif problem == "empty_sources":
                        state.update(evidence_records=[], retrieved_evidence=[])
                    else:
                        state.update(answer=" \n", relevant_context=" \n")
                    original = deepcopy(state)
                    verifier = self.verifier(stage)
                    result = self.verify(stage, state, verifier)
                    self.assertFalse(result["grounded"])
                    verifier.invoke.assert_not_called()
                    self.assertEqual(state, original)

    def generator(self, stage, selected_ids):
        content_field = "answer_based_on_content" if stage == "answer" else "relevant_content"
        return SimpleNamespace(invoke=Mock(side_effect=[
            SimpleNamespace(**(
                {
                    content_field: self.fact,
                    "claim_citations": [{
                        "claim": self.fact, "supporting_ids": [identifier],
                    }],
                }
                if stage == "answer"
                else {content_field: self.fact, "supporting_ids": [identifier]}
            ))
            for identifier in selected_ids
        ]))

    def test_compiled_subgraphs_retry_wrong_citations_then_recover(self):
        for stage in ("answer", "distillation"):
            with self.subTest(stage=stage):
                generator = self.generator(stage, [self.records[1]["id"], self.records[0]["id"]])
                verifier = self.verifier(stage)
                generator_name = "answer_from_context" if stage == "answer" else "keep_relevant_content"
                chains = SimpleNamespace(**{
                    generator_name: generator, f"ground_{stage}": verifier,
                })
                state = {
                    **self.state_for(stage, []), "question": "What is the Neral-731 code?",
                    "attempts": 0, "max_attempts": 2, "grounded": False,
                }
                retriever = SimpleNamespace(invoke=Mock(return_value=self.documents))
                workflow = get_answer_workflow() if stage == "answer" else get_retrieval_workflow("chunks")
                with (
                    patch("controllable_rag.nodes.get_agent_chains", return_value=chains),
                    patch("controllable_rag.nodes.get_retriever", return_value=retriever),
                ):
                    result = workflow.invoke(state)
                self.assertTrue(result["grounded"])
                self.assertEqual(result["attempts"], 2)
                self.assertEqual(generator.invoke.call_count, 2)
                self.assertEqual(verifier.invoke.call_count, 2)
                selected_ids = result.get("supporting_ids") if stage == "answer" else [
                    record["id"] for record in result["relevant_evidence"]
                ]
                self.assertEqual(selected_ids, [self.records[0]["id"]])

    def test_finalize_refuses_after_bounded_wrong_citations(self):
        generator = self.generator("answer", [self.records[1]["id"]] * 2)
        verifier = self.verifier("answer")
        chains = SimpleNamespace(answer_from_context=generator, ground_answer=verifier)
        with (
            patch("controllable_rag.nodes.get_agent_chains", return_value=chains),
            patch("controllable_rag.nodes.get_settings", return_value=Settings(grounding_max_attempts=2)),
        ):
            result = finalize_answer({
                "question": "What is the Neral-731 code?", "evidence_records": self.records,
                "aggregated_context": render_evidence(self.records),
            })
        self.assertEqual(result["termination_reason"], "grounding_failed")
        self.assertEqual(result["citations"], [])
        self.assertEqual(result["answer_attempts"], 2)
        self.assertNotIn(self.fact, result["response"])
        self.assertEqual(result["last_generated_answer"], self.fact)
        self.assertEqual(verifier.invoke.call_count, 2)

    def test_failed_distillation_never_enters_accumulated_evidence(self):
        generator = self.generator("distillation", [self.records[1]["id"]] * 2)
        verifier = self.verifier("distillation")
        chains = SimpleNamespace(keep_relevant_content=generator, ground_distillation=verifier)
        retriever = SimpleNamespace(invoke=Mock(return_value=self.documents))
        with (
            patch("controllable_rag.nodes.get_agent_chains", return_value=chains),
            patch("controllable_rag.nodes.get_retriever", return_value=retriever),
            patch("controllable_rag.nodes.get_settings", return_value=Settings(grounding_max_attempts=2)),
        ):
            result = retrieve_chunks({"query_to_retrieve_or_answer": "What is the Neral-731 code?"})
        self.assertEqual(result["aggregated_context"], "")
        self.assertEqual(result["evidence_records"], [])
        self.assertEqual(verifier.invoke.call_count, 2)
        retriever.invoke.assert_called_once()


if __name__ == "__main__":
    unittest.main()
