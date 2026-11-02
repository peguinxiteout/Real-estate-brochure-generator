"""The real agents. TASKS maps every task name an agent sends to its prompt and schema, for the real LLM client."""
from collections.abc import Mapping

from brochure.agents import brief, copywriter
from brochure.agents.brief import brief_agent
from brochure.agents.copywriter import copywriter_agent
from brochure.llm import OpenAICompatibleClient, TaskSpec, client_from_env

TASKS: dict[str, TaskSpec] = {brief.TASK: brief.TASK_SPEC, copywriter.TASK: copywriter.TASK_SPEC}


def llm_from_env(environ: Mapping[str, str] | None = None) -> OpenAICompatibleClient:
    """The real client for the agents above, configured from LLM_BASE_URL, LLM_API_KEY and LLM_MODEL."""
    return client_from_env(TASKS, environ)


__all__ = ["TASKS", "brief_agent", "copywriter_agent", "llm_from_env"]
