"""Shared graph state and structured-output schemas."""

from typing import List, Literal

from typing_extensions import TypedDict

try:
    # LangChain <=0.1 exposes its Pydantic-v1 compatibility namespace.
    from langchain_core.pydantic_v1 import BaseModel, Field
except ImportError:  # LangChain 1.x uses native Pydantic v2 models.
    from pydantic import BaseModel, Field


class PlanExecute(TypedDict, total=False):
    curr_state: str
    question: str
    anonymized_question: str
    query_to_retrieve_or_answer: str
    plan: List[str]
    past_steps: List[str]
    mapping: dict
    curr_context: str
    aggregated_context: str
    tool: str
    response: str
    max_steps: int
    step_count: int
    retrieval_count: int
    attempted_retrieval_sources: List[str]
    answer_attempts: int
    termination_reason: str
    route_decision: str
    trace_events: List[dict]
    evidence_records: List[dict]
    citations: List[dict]
    claim_citations: List[dict]
    max_model_requests: int
    max_total_tokens: int
    max_elapsed_seconds: float
    elapsed_seconds: float
    max_embedding_requests: int
    max_embedding_inputs: int
    embedding_requests: int
    embedding_inputs: int
    model_requests: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    token_accounting_available: bool
    last_generated_answer: str
    candidate_supporting_ids: List[str]
    candidate_claim_citations: List[dict]
    claim_citation_validation_error: str
    grounding_explanation: str
    enabled_retrieval_sources: List[str]
    min_evidence_records: int
    evidence_gate_reason: str
    policy_feedback: str
    source_policy_events: List[dict]
    budget_mode: str
    budget_diagnostics: dict
    trace_id: str
    trace_enabled: bool
    trace_persisted: bool
    trace_path: str
    trace_persistence_error: str


class Plan(BaseModel):
    """Plan to follow in future."""

    steps: List[str] = Field(
        description="different steps to follow, should be in sorted order"
    )


class KeepRelevantContent(BaseModel):
    relevant_content: str = Field(description="Relevant content copied from the documents")
    supporting_ids: List[str] = Field(
        default_factory=list,
        description="Exact evidence IDs that support the retained content",
    )


class ClaimCitation(BaseModel):
    claim: str = Field(description="One complete factual sentence copied verbatim from the answer")
    supporting_ids: List[str] = Field(
        default_factory=list,
        description="Exact evidence IDs that jointly support this claim",
    )


class QuestionAnswerFromContext(BaseModel):
    answer_based_on_content: str = Field(description="Answer grounded in the supplied context")
    claim_citations: List[ClaimCitation] = Field(
        default_factory=list,
        description="Complete mapping from every answer sentence to its supporting evidence IDs",
    )


class GroundingDecision(BaseModel):
    grounded: bool
    explanation: str


class AnswerabilityDecision(BaseModel):
    can_be_answered: bool
    explanation: str


class TaskHandlerOutput(BaseModel):
    query: str
    curr_context: str = ""
    tool: Literal[
        "retrieve_chunks",
        "retrieve_summaries",
        "retrieve_quotes",
        "answer_from_context",
    ]


class AnonymizeQuestion(BaseModel):
    anonymized_question: str
    mapping: dict


class QualitativeRetrievalGraphState(TypedDict):
    enabled_retrieval_sources: List[str]
    question: str
    context: str
    relevant_context: str
    grounded: bool
    attempts: int
    max_attempts: int
    retrieved_evidence: List[dict]
    relevant_evidence: List[dict]
    grounding_explanation: str


class QualitativeAnswerGraphState(TypedDict):
    question: str
    context: str
    answer: str
    grounded: bool
    attempts: int
    max_attempts: int
    supporting_ids: List[str]
    claim_citations: List[dict]
    candidate_claim_citations: List[dict]
    claim_citation_validation_error: str
    evidence_records: List[dict]
    grounding_explanation: str
