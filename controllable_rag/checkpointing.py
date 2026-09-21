"""Explicit lifecycle helpers for local SQLite Agent checkpoints."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from .graph import create_agent


@contextmanager
def open_sqlite_agent(path, *, interrupt_before=None, interrupt_after=None):
    """Open an opt-in persistent Agent and close its database deterministically.

    Checkpoints contain the complete graph State, including user questions and
    retrieved context. Callers must protect the file and delete threads according
    to their retention policy.
    """
    checkpoint_path = Path(path).expanduser().resolve()
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(checkpoint_path, check_same_thread=False)
    try:
        yield create_agent(
            checkpointer=SqliteSaver(connection),
            interrupt_before=interrupt_before,
            interrupt_after=interrupt_after,
        )
    finally:
        connection.close()
