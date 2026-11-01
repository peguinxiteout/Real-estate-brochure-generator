"""The real agents. TASKS maps every task name an agent sends to its prompt and schema, for the real LLM client."""
from collections.abc import Mapping

from brochure.agents.brief import TASK, TASK_SPEC, brief_agent
from brochure.llm import OpenAICompatibleClient, TaskSpec, client_from_env

TASKS: dict[str, TaskSpec] = {TASK: TASK_SPEC}


def llm_from_env(environ: Mapping[str, str] | None = None) -> OpenAICompatibleClient:
    """The real client for the agents above, configured from LLM_BASE_URL, LLM_API_KEY and LLM_MODEL."""
    return client_from_env(TASKS, environ)


__all__ = ["TASKS", "brief_agent", "llm_from_env"]
