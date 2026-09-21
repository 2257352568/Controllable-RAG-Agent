"""LangGraph topology for retrieval subgraphs and the main Agent workflow."""

from functools import lru_cache

from langgraph.graph import END, StateGraph

from . import nodes
from .observability import observed_node
from .runtime import BoundedAgent
from .schemas import (
    PlanExecute,
    QualitativeAnswerGraphState,
    QualitativeRetrievalGraphState,
)

RETRIEVAL_NODES = {
    "chunks": nodes.retrieve_chunks_context,
    "summaries": nodes.retrieve_summaries_context,
    "quotes": nodes.retrieve_quotes_context,
}
AGENT_GRAPH_VERSION = "2026-09-17.1"


@lru_cache(maxsize=3)
def get_retrieval_workflow(source):
    """Build one bounded retrieve-filter-verify subgraph per source."""
    try:
        retrieve_node = RETRIEVAL_NODES[source]
    except KeyError as error:
        raise ValueError(f"Unsupported retrieval source: {source!r}") from error

    workflow = StateGraph(QualitativeRetrievalGraphState)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("filter", nodes.filter_relevant_content)
    workflow.add_node("verify", nodes.verify_distilled_content)
    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "filter")
    workflow.add_edge("filter", "verify")
    workflow.add_conditional_edges(
        "verify",
        nodes.route_distillation,
        {"grounded": END, "retry": "filter", "failed": END},
    )
    return workflow.compile()


@lru_cache(maxsize=1)
def get_answer_workflow():
    """Build a bounded answer-and-grounding subgraph."""
    workflow = StateGraph(QualitativeAnswerGraphState)
    workflow.add_node("generate_answer", nodes.answer_from_context)
    workflow.add_node("verify_answer", nodes.verify_answer)
    workflow.set_entry_point("generate_answer")
    workflow.add_edge("generate_answer", "verify_answer")
    workflow.add_conditional_edges(
        "verify_answer",
        nodes.route_answer_grounding,
        {"grounded": END, "retry": "generate_answer", "failed": END},
    )
    return workflow.compile()


def _add_observed_node(workflow, name, node):
    workflow.add_node(name, observed_node(name, node))


def create_agent(checkpointer=None, *, interrupt_before=None, interrupt_after=None):
    """Compile the main Agent; persistence is explicit and disabled by default."""
    workflow = StateGraph(PlanExecute)
    for name, node in (
        ("initialize", nodes.initialize_state),
        ("anonymize_question", nodes.anonymize_question),
        ("planner", nodes.plan_question),
        ("de_anonymize_plan", nodes.deanonymize_plan),
        ("break_down_plan", nodes.break_down_plan),
        ("task_handler", nodes.handle_task),
        ("retrieve_chunks", nodes.retrieve_chunks),
        ("retrieve_summaries", nodes.retrieve_summaries),
        ("retrieve_quotes", nodes.retrieve_quotes),
        ("retrieval_source_disabled", nodes.reject_disabled_source),
        ("answer", nodes.answer_intermediate),
        ("replan", nodes.replan),
        ("assess_answerability", nodes.assess_answerability),
        ("get_final_answer", nodes.finalize_answer),
        ("budget_exhausted", nodes.stop_for_budget),
        ("search_exhausted", nodes.stop_for_search_exhaustion),
    ):
        _add_observed_node(workflow, name, node)

    workflow.set_entry_point("initialize")
    workflow.add_edge("initialize", "anonymize_question")
    workflow.add_edge("anonymize_question", "planner")
    workflow.add_edge("planner", "de_anonymize_plan")
    workflow.add_edge("de_anonymize_plan", "break_down_plan")
    workflow.add_edge("break_down_plan", "task_handler")
    workflow.add_conditional_edges(
        "task_handler",
        nodes.route_tool,
        {
            "chunks": "retrieve_chunks",
            "summaries": "retrieve_summaries",
            "quotes": "retrieve_quotes",
            "answer": "answer",
            "disabled": "retrieval_source_disabled",
        },
    )
    for node_name in (
        "retrieve_chunks",
        "retrieve_summaries",
        "retrieve_quotes",
        "retrieval_source_disabled",
        "answer",
    ):
        workflow.add_edge(node_name, "assess_answerability")
    workflow.add_conditional_edges(
        "assess_answerability",
        nodes.route_after_assessment,
        {
            "answerable": "get_final_answer",
            "continue": "replan",
            "budget_exhausted": "budget_exhausted",
            "search_exhausted": "search_exhausted",
        },
    )
    workflow.add_edge("replan", "break_down_plan")
    workflow.add_edge("get_final_answer", END)
    workflow.add_edge("budget_exhausted", END)
    workflow.add_edge("search_exhausted", END)
    return BoundedAgent(
        workflow.compile(
            checkpointer=checkpointer,
            interrupt_before=interrupt_before,
            interrupt_after=interrupt_after,
        )
    )
