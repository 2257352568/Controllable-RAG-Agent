"""Backward-compatible imports for the original notebook and Streamlit entrypoint.

New code should import from ``controllable_rag`` modules directly.
"""

from controllable_rag.config import PROJECT_ROOT, get_settings
from controllable_rag.graph import (
    create_agent,
)
from controllable_rag.graph import (
    get_answer_workflow as create_qualitative_answer_workflow_app,
)
from controllable_rag.models import create_chat_model, create_embedding_model
from controllable_rag.nodes import (
    anonymize_question as anonymize_queries,
)
from controllable_rag.nodes import (
    answer_from_context as answer_question_from_context,
)
from controllable_rag.nodes import (
    answer_intermediate as run_qualtative_answer_workflow,
)
from controllable_rag.nodes import (
    assess_answerability,
)
from controllable_rag.nodes import (
    break_down_plan as break_down_plan_step,
)
from controllable_rag.nodes import (
    deanonymize_plan as deanonymize_queries,
)
from controllable_rag.nodes import (
    filter_relevant_content as keep_only_relevant_content,
)
from controllable_rag.nodes import (
    finalize_answer as run_qualtative_answer_workflow_for_final_answer,
)
from controllable_rag.nodes import (
    handle_task as run_task_handler_chain,
)
from controllable_rag.nodes import (
    plan_question as plan_step,
)
from controllable_rag.nodes import (
    replan as replan_step,
)
from controllable_rag.nodes import (
    retrieve_chunks as run_qualitative_chunks_retrieval_workflow,
)
from controllable_rag.nodes import (
    retrieve_chunks_context as retrieve_chunks_context_per_question,
)
from controllable_rag.nodes import (
    retrieve_quotes as run_qualitative_book_quotes_retrieval_workflow,
)
from controllable_rag.nodes import (
    retrieve_quotes_context as retrieve_book_quotes_context_per_question,
)
from controllable_rag.nodes import (
    retrieve_summaries as run_qualitative_summaries_retrieval_workflow,
)
from controllable_rag.nodes import (
    retrieve_summaries_context as retrieve_summaries_context_per_question,
)
from controllable_rag.nodes import (
    route_after_replan as can_be_answered,
)
from controllable_rag.nodes import (
    route_tool as retrieve_or_answer,
)
from controllable_rag.nodes import (
    verify_answer as is_answer_grounded_on_context,
)
from controllable_rag.nodes import (
    verify_distilled_content as is_distilled_content_grounded_on_content,
)
from controllable_rag.retrieval import create_retrievers, get_retrievers

SETTINGS = get_settings()
QWEN_BASE_URL = SETTINGS.base_url
QWEN_MODEL = SETTINGS.chat_model
QWEN_EMBEDDING_MODEL = SETTINGS.embedding_model
QWEN_EMBEDDING_DIMENSIONS = SETTINGS.embedding_dimensions
QWEN_MAX_RETRIES = SETTINGS.max_retries


__all__ = [
    "PROJECT_ROOT",
    "QWEN_BASE_URL",
    "QWEN_EMBEDDING_DIMENSIONS",
    "QWEN_EMBEDDING_MODEL",
    "QWEN_MAX_RETRIES",
    "QWEN_MODEL",
    "SETTINGS",
    "anonymize_queries",
    "answer_question_from_context",
    "assess_answerability",
    "break_down_plan_step",
    "can_be_answered",
    "create_agent",
    "create_chat_model",
    "create_embedding_model",
    "create_qualitative_answer_workflow_app",
    "create_retrievers",
    "deanonymize_queries",
    "get_retrievers",
    "is_answer_grounded_on_context",
    "is_distilled_content_grounded_on_content",
    "keep_only_relevant_content",
    "plan_step",
    "replan_step",
    "retrieve_book_quotes_context_per_question",
    "retrieve_chunks_context_per_question",
    "retrieve_or_answer",
    "retrieve_summaries_context_per_question",
    "run_qualitative_book_quotes_retrieval_workflow",
    "run_qualitative_chunks_retrieval_workflow",
    "run_qualitative_summaries_retrieval_workflow",
    "run_qualtative_answer_workflow",
    "run_qualtative_answer_workflow_for_final_answer",
    "run_task_handler_chain",
]
