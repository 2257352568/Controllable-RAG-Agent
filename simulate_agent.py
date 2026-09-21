import tempfile

import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network

from controllable_rag.config import get_settings
from functions_for_pipeline import *


def create_network_graph(current_state):
    """
    Create a network graph visualization of the agent's current state.

    Args:
        current_state (str): The current state of the agent.

    Returns:
        Network: The network graph visualization.
    """
    net = Network(directed=True, notebook=True, height="250px", width="100%")
    net.toggle_physics(False)  # Disable physics simulation
    
    nodes = [
        {"id": "initialize", "label": "initialize", "x": -175, "y": 0},
        {"id": "anonymize_question", "label": "anonymize_question", "x": 0, "y": 0},
        {"id": "planner", "label": "planner", "x": 175*1.75, "y": -100},
        {"id": "de_anonymize_plan", "label": "de_anonymize_plan", "x": 350*1.75, "y": -100},
        {"id": "break_down_plan", "label": "break_down_plan", "x": 525*1.75, "y": -100},
        {"id": "task_handler", "label": "task_handler", "x": 700*1.75, "y": 0},
        {"id": "retrieve_chunks", "label": "retrieve_chunks", "x": 875*1.75, "y": +200},
        {"id": "retrieve_summaries", "label": "retrieve_summaries", "x": 875*1.75, "y": +100},
        {"id": "retrieve_quotes", "label": "retrieve_quotes", "x": 875*1.75, "y": 0},
        {"id": "retrieval_source_disabled", "label": "source_disabled", "x": 875*1.75, "y": +300},
        {"id": "answer", "label": "answer", "x": 875*1.75, "y": -100},
        {"id": "replan", "label": "replan", "x": 1050*1.75, "y": 0},
        {"id": "assess_answerability", "label": "assess_answerability", "x": 1225*1.75, "y": 0},
        {"id": "get_final_answer", "label": "get_final_answer", "x": 1400*1.75, "y": 0},
        {"id": "budget_exhausted", "label": "budget_exhausted", "x": 1400*1.75, "y": 140},
    ]

    
    edges = [
        ("initialize", "anonymize_question"),
        ("anonymize_question", "planner"),
        ("planner", "de_anonymize_plan"),
        ("de_anonymize_plan", "break_down_plan"),
        ("break_down_plan", "task_handler"),
        ("task_handler", "retrieve_chunks"),
        ("task_handler", "retrieve_summaries"),
        ("task_handler", "retrieve_quotes"),
        ("task_handler", "retrieval_source_disabled"),
        ("task_handler", "answer"),
        ("retrieve_chunks", "replan"),
        ("retrieve_summaries", "replan"),
        ("retrieve_quotes", "replan"),
        ("retrieval_source_disabled", "replan"),
        ("answer", "replan"),
        ("replan", "assess_answerability"),
        ("replan", "break_down_plan"),
        ("assess_answerability", "get_final_answer"),
        ("assess_answerability", "budget_exhausted")
    ]
    
    # Add nodes with conditional coloring
    for node in nodes:
        color = "#00FF00" if node["id"] == current_state else "#FF69B4"  # Green if current, else pink
        net.add_node(node["id"], label=node["label"], x=node["x"], y=node["y"], color=color, physics=False, font={'size': 22})
    
    # Add edges with a default color
    for edge in edges:
        net.add_edge(edge[0], edge[1], color="#808080")  # Set edge color to gray
    
    # Customize other visual aspects
    net.options.edges.smooth.type = "straight"  # Make edges straight lines
    net.options.edges.width = 1.5  # Set edge width
    
    return net


def compute_initial_positions(net):
    """
    Compute the initial positions of the nodes in the network graph.

    Args:
        net (Network): The network graph.

    Returns:
        dict: The initial positions of the nodes.
    """
    net.barnes_hut()
    return {node['id']: (node['x'], node['y']) for node in net.nodes}


def save_and_display_graph(net):
    """
    Save the network graph to an HTML file and display it in Streamlit.

    Args:
        net (Network): The network graph.

    Returns:
        str: The HTML content of the network graph.
    """
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".html") as tmp_file:
        net.write_html(tmp_file.name, notebook=True)
        tmp_file.flush()
        with open(tmp_file.name, "r", encoding="utf-8") as f:
            return f.read()


def update_placeholders_and_graph(agent_state_value, placeholders, graph_placeholder, previous_values, previous_state):
    """
    Update the placeholders and graph in the Streamlit app based on the current state.

    Args:
        agent_state_value (dict): The current state value of the agent.
        placeholders (dict): The placeholders to display the steps.
        graph_placeholder (Streamlit.placeholder): The placeholder to display the network graph.
        previous_values (dict): The previous values of the placeholders.
        previous_state: The previous state of the agent.

    Returns:
        tuple: Updated previous_values and previous_state.
    """
    current_state = agent_state_value.get("curr_state")

    # Update graph
    if current_state:
        net = create_network_graph(current_state)
        graph_html = save_and_display_graph(net)
        graph_placeholder.empty()
        with graph_placeholder.container():
            components.html(graph_html, height=400, scrolling=True)

    # Update placeholders only if the state has changed (i.e., we've finished visiting the previous node)
    if current_state != previous_state and previous_state is not None:
        for key, placeholder in placeholders.items():
            if key in previous_values and previous_values[key] is not None:
                if isinstance(previous_values[key], list):
                    formatted_value = "\n".join([f"{i+1}. {item}" for i, item in enumerate(previous_values[key])])
                else:
                    formatted_value = previous_values[key]
                placeholder.markdown(f"{formatted_value}")

    # Store current values for the next iteration
    for key in placeholders:
        if key in agent_state_value:
            previous_values[key] = agent_state_value[key]

    return previous_values, current_state


def execute_plan_and_print_steps(inputs, plan_and_execute_app, placeholders, graph_placeholder, recursion_limit=25):
    """
    Execute the plan and print the steps in the Streamlit app.

    Args:
        inputs (dict): The inputs to the plan.
        plan_and_execute_app (StateGraph): The compiled plan and execute app.
        placeholders (dict): The placeholders to display the steps.
        graph_placeholder (Streamlit.placeholder): The placeholder to display the network graph.
        recursion_limit (int): The recursion limit for the plan execution.

    Returns:
        str: The final response from the agent.
    """
    config = {"recursion_limit": recursion_limit}
    agent_state_value = None
    progress_bar = st.progress(0)
    step = 0
    previous_state = None
    previous_values = {key: None for key in placeholders}

    try:
        for plan_output in plan_and_execute_app.stream(inputs, config=config):
            step += 1
            for _, agent_state_value in plan_output.items():
                previous_values, previous_state = update_placeholders_and_graph(
                    agent_state_value, placeholders, graph_placeholder, previous_values, previous_state
                )

                progress_bar.progress(step / recursion_limit)
                if step >= recursion_limit:
                    break

        # After the loop, update placeholders with the final state
        for key, placeholder in placeholders.items():
            if key in previous_values and previous_values[key] is not None:
                if isinstance(previous_values[key], list):
                    formatted_value = "\n".join([f"{i+1}. {item}" for i, item in enumerate(previous_values[key])])
                else:
                    formatted_value = previous_values[key]
                placeholder.markdown(f"{formatted_value}")

        response = agent_state_value.get('response', "No response found.") if agent_state_value else "No response found."
    except Exception as e:
        response = f"An error occurred: {str(e)}"
        st.error(f"Error: {e}")

    return response, agent_state_value or {}


def main():
    """
    Main function to run the Streamlit app.
    """
    st.set_page_config(layout="wide")  # Use wide layout
    settings = get_settings()
    
    st.title("Real-Time Agent Execution Visualization")
    
    # Load your existing agent creation function
    plan_and_execute_app = create_agent()

    # Get the user's question
    question = st.text_input("Enter your question:", "what is the class that the proffessor who helped the villain is teaching?")
    max_steps = st.number_input(
        "Maximum Agent steps:", min_value=1, max_value=20, value=8, step=1
    )
    max_model_requests = st.number_input(
        "Chat-model logical invocation budget:",
        min_value=1,
        max_value=200,
        value=40,
        step=1,
        help="Factory-created chat calls are rejected before dispatch once spent; SDK HTTP retries are not counted separately.",
    )
    max_total_tokens = st.number_input(
        "Conservative chat-token admission budget:",
        min_value=100,
        max_value=200000,
        value=20000,
        step=100,
        help="Each chat call reserves a conservative upper bound before dispatch; embedding operations have separate limits below.",
    )
    max_embedding_requests = st.number_input(
        "Embedding request budget:", min_value=1, max_value=100,
        value=settings.agent_max_embedding_requests, step=1,
    )
    max_embedding_inputs = st.number_input(
        "Embedding input-text budget:", min_value=1, max_value=500,
        value=settings.agent_max_embedding_inputs, step=1,
        help="A document batch is one request but consumes one input unit per text.",
    )
    max_elapsed_seconds = st.number_input(
        "Cumulative execution deadline (seconds):", min_value=1.0,
        max_value=3600.0, value=float(settings.agent_max_elapsed_seconds), step=1.0,
        help="Checked before model calls and at node boundaries; it does not kill an in-flight synchronous request.",
    )
    enabled_sources = st.multiselect(
        "Enabled retrieval sources:",
        options=["chunks", "summaries", "quotes"],
        default=list(settings.enabled_retrieval_sources),
        help="The router is prevented from executing disabled sources.",
    )
    min_evidence_records = st.number_input(
        "Minimum validated evidence records:",
        min_value=1,
        max_value=20,
        value=settings.min_evidence_records,
        step=1,
        help="The Agent cannot finalize an answer below this deterministic gate.",
    )
    persist_trace = st.checkbox(
        "Persist privacy-minimized execution trace",
        value=settings.trace_enabled,
        help="Stores node/control/usage metadata only; prompts, context and answers are excluded.",
    )

    if st.button("Run Agent"):
        if not enabled_sources:
            st.error("Enable at least one retrieval source before running the Agent.")
            return
        inputs = {
            "question": question,
            "max_steps": int(max_steps),
            "max_model_requests": int(max_model_requests),
            "max_total_tokens": int(max_total_tokens),
            "max_embedding_requests": int(max_embedding_requests),
            "max_embedding_inputs": int(max_embedding_inputs),
            "max_elapsed_seconds": float(max_elapsed_seconds),
            "enabled_retrieval_sources": list(enabled_sources),
            "min_evidence_records": int(min_evidence_records),
            "trace_enabled": bool(persist_trace),
        }
        
        # Create a row for the graph
        st.markdown("**Graph**")
        graph_placeholder = st.empty()

        # Create three columns for the other variables
        col1, col2, col3 = st.columns([1, 1, 4])
        
        with col1:
            st.markdown("**Plan**")
        with col2:
            st.markdown("**Past Steps**")
        with col3:
            st.markdown("**Aggregated Context**")

        # Initialize placeholders for each column
        placeholders = {
            "plan": col1.empty(),
            "past_steps": col2.empty(),
            "aggregated_context": col3.empty(),
        }

        response, final_state = execute_plan_and_print_steps(inputs, plan_and_execute_app, placeholders, graph_placeholder, recursion_limit=45)
        st.write("Final Answer:")
        st.write(response)

        st.write("Execution Summary:")
        st.json({
            "termination_reason": final_state.get("termination_reason", "unknown"),
            "step_count": final_state.get("step_count", 0),
            "max_steps": final_state.get("max_steps"),
            "model_requests": final_state.get("model_requests", 0),
            "max_model_requests": final_state.get("max_model_requests"),
            "total_tokens": final_state.get("total_tokens", 0),
            "max_total_tokens": final_state.get("max_total_tokens"),
            "embedding_requests": final_state.get("embedding_requests", 0),
            "max_embedding_requests": final_state.get("max_embedding_requests"),
            "embedding_inputs": final_state.get("embedding_inputs", 0),
            "max_embedding_inputs": final_state.get("max_embedding_inputs"),
            "elapsed_seconds": final_state.get("elapsed_seconds", 0.0),
            "max_elapsed_seconds": final_state.get("max_elapsed_seconds"),
            "token_accounting_available": final_state.get(
                "token_accounting_available", False
            ),
            "budget_mode": final_state.get("budget_mode", "unknown"),
            "budget_diagnostics": final_state.get("budget_diagnostics", {}),
            "retrieval_count": final_state.get("retrieval_count", 0),
            "enabled_retrieval_sources": final_state.get(
                "enabled_retrieval_sources", []
            ),
            "min_evidence_records": final_state.get("min_evidence_records"),
            "evidence_gate_reason": final_state.get("evidence_gate_reason", ""),
            "source_policy_events": final_state.get("source_policy_events", []),
            "trace_id": final_state.get("trace_id"),
            "trace_persisted": final_state.get("trace_persisted", False),
            "trace_path": final_state.get("trace_path", ""),
            "trace_persistence_error": final_state.get(
                "trace_persistence_error", ""
            ),
            "answer_attempts": final_state.get("answer_attempts", 0),
            "candidate_supporting_ids": final_state.get(
                "candidate_supporting_ids", []
            ),
            "grounding_explanation": final_state.get(
                "grounding_explanation", ""
            ),
        })
        trace_events = final_state.get("trace_events", [])
        if trace_events:
            with st.expander("Node Trace", expanded=True):
                st.dataframe(trace_events, use_container_width=True)
        citations = final_state.get("citations", [])
        if citations:
            citation_rows = []
            for citation in citations:
                metadata = citation.get("metadata", {})
                citation_rows.append(
                    {
                        "id": citation.get("id"),
                        "source": citation.get("source"),
                        "rank": citation.get("rank"),
                        "page": metadata.get("page"),
                        "chapter": metadata.get("chapter"),
                        "page_candidates": metadata.get("location_candidates"),
                    }
                )
            with st.expander("Validated Sources", expanded=True):
                st.dataframe(citation_rows, use_container_width=True)


if __name__ == "__main__":
    main()
