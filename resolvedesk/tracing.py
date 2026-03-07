"""Small LangSmith helpers that keep tracing optional.

The app should run normally without LangSmith credentials. When
LANGSMITH_TRACING=true and a LangSmith API key is present, LangGraph and these
decorated helper functions emit richer traces for the interview/debugging flow.
"""

import os
from functools import wraps


def tracing_enabled():
    return os.getenv("LANGSMITH_TRACING", "").lower() in {"1", "true", "yes", "on"}


try:
    from langsmith import traceable as _traceable
except Exception:  # pragma: no cover - defensive optional dependency fallback
    _traceable = None


def traceable(name=None, run_type="chain", metadata=None, tags=None):
    """Return a LangSmith trace decorator, or a no-op when unavailable."""

    def decorator(func):
        if not _traceable:
            return func
        wrapped = _traceable(name=name or func.__name__, run_type=run_type, metadata=metadata, tags=tags)(func)

        @wraps(func)
        def inner(*args, **kwargs):
            return wrapped(*args, **kwargs)

        return inner

    return decorator


def wrap_openai_client(client):
    """Wrap OpenAI clients so LangSmith captures model call details."""
    if not tracing_enabled():
        return client
    try:
        from langsmith.wrappers import wrap_openai
    except Exception:  # pragma: no cover - optional SDK surface
        return client
    return wrap_openai(client)


def runnable_config(run_id, **metadata):
    """Attach tags/metadata to LangGraph invocations without changing logic."""
    clean_metadata = {k: v for k, v in metadata.items() if v is not None}
    return {
        "configurable": {"thread_id": run_id},
        "recursion_limit": 20,
        "metadata": {"run_id": run_id, **clean_metadata},
        "tags": ["resolvedesk", clean_metadata.get("mode", "unknown")],
    }
