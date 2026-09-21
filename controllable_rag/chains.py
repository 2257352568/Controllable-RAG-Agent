"""Lazy construction of all prompt/model chains used by the graph."""

from dataclasses import dataclass
from functools import lru_cache

from langchain_core.prompts import PromptTemplate

from . import prompts
from .models import create_chat_model
from .schemas import (
    AnonymizeQuestion,
    AnswerabilityDecision,
    GroundingDecision,
    KeepRelevantContent,
    Plan,
    QuestionAnswerFromContext,
    TaskHandlerOutput,
)


def _structured_chain(llm, template, schema):
    prompt = PromptTemplate.from_template(template)
    return prompt | llm.with_structured_output(schema)


@dataclass(frozen=True)
class AgentChains:
    keep_relevant_content: object
    answer_from_context: object
    ground_answer: object
    ground_distillation: object
    planner: object
    break_down_plan: object
    replanner: object
    task_handler: object
    anonymize_question: object
    can_answer: object


def build_agent_chains(chat_model=None):
    """Build all chains around one shared, injectable chat model."""
    llm = chat_model or create_chat_model()
    return AgentChains(
        keep_relevant_content=_structured_chain(
            llm, prompts.KEEP_RELEVANT_CONTENT, KeepRelevantContent
        ),
        answer_from_context=_structured_chain(
            llm, prompts.ANSWER_FROM_CONTEXT, QuestionAnswerFromContext
        ),
        ground_answer=_structured_chain(llm, prompts.GROUND_ANSWER, GroundingDecision),
        ground_distillation=_structured_chain(
            llm, prompts.GROUND_DISTILLATION, GroundingDecision
        ),
        planner=_structured_chain(llm, prompts.PLAN, Plan),
        break_down_plan=_structured_chain(llm, prompts.BREAK_DOWN_PLAN, Plan),
        replanner=_structured_chain(llm, prompts.REPLAN, Plan),
        task_handler=_structured_chain(llm, prompts.ROUTE_TASK, TaskHandlerOutput),
        anonymize_question=_structured_chain(
            llm, prompts.ANONYMIZE, AnonymizeQuestion
        ),
        can_answer=_structured_chain(llm, prompts.CAN_ANSWER, AnswerabilityDecision),
    )


@lru_cache(maxsize=1)
def get_agent_chains():
    """Create chains only when the first Agent node needs them."""
    return build_agent_chains()
