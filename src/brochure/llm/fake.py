"""A scripted LLMClient for tests: canned answers, and a record of every call."""
import copy
from pathlib import Path


class FakeLLM:
    def __init__(self, responses: dict[str, dict]):
        self.responses = responses

    def complete(self, task: str, payload: dict, images: list[Path] | None = None) -> dict:
        return copy.deepcopy(self.responses[task])
