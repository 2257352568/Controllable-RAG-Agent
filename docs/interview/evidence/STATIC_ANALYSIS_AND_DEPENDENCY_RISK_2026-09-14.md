# Static analysis and dependency-risk evidence — 2026-09-14

## Ruff gate

The project separates runtime dependencies from `requirements-dev.txt`, which pins `ruff==0.16.7`. CI runs this exact command without an API key:

```powershell
python -m ruff check controllable_rag evaluation tests simulate_agent.py functions_for_pipeline.py helper_functions.py rebuild_vector_stores.py
```

The deliberately bounded rule set is `E4`, `E7`, `E9`, `F`, and `I`: import/runtime syntax errors, Pyflakes correctness checks, and deterministic import ordering. It is not presented as type checking, security scanning, or model-quality evaluation.

The first run reported 81 findings. Ruff safely fixed 68; the remaining 13 were either replaced with named functions or covered by narrow per-file exceptions for intentional script bootstrap imports and the upstream-compatible Streamlit wildcard facade. The final run returned `All checks passed!`.

## Sunset dependency decision

Loading the current FAISS pickle emits a deprecation warning because `langchain-community` was sunset and archived in May 2026. The [LangChain sunset notice](https://github.com/langchain-ai/langchain-community/issues/674) recommends standalone integration packages, but no official standalone FAISS package was identified; current LangChain guidance still lists FAISS via `langchain-community`.

An import-only rename would not remove the deeper coupling: existing `index.pkl` files serialize community docstore classes and pickle remains an executable deserialization format. The current decision is therefore to pin the tested version, restrict pickle loading to explicit trusted-local workflows, keep integrity/readiness checks, and treat migration to an application-owned safe document format plus direct FAISS adapter as open work. This is a recorded risk decision, not a claim that the dependency problem is solved.
