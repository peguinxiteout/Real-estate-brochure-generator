"""Typing for agents. Implementations come later."""
from typing import Protocol, runtime_checkable

from brochure.llm.base import LLMClient


@runtime_checkable
class Agent[I, O](Protocol):
    """An agent step: takes its inputs and an LLM client, returns a schema object (a contract model)."""

    def __call__(self, inputs: I, llm: LLMClient) -> O: ...
