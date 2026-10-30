"""A scripted LLMClient for tests: canned answers, and a record of every call."""
import copy
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LLMCall:
    task: str
    payload: dict
    images: list[Path]


class FakeLLM:
    def __init__(self, responses: dict[str, dict]):
        self.responses = responses
        self.calls: list[LLMCall] = []

    def complete(self, task: str, payload: dict, images: list[Path] | None = None) -> dict:
        self.calls.append(LLMCall(task, copy.deepcopy(payload), [Path(i) for i in images or []]))
        if task not in self.responses:
            known = ", ".join(sorted(self.responses)) or "none"
            raise MissingCannedResponse(f"FakeLLM has no canned response for task {task!r} (it has: {known})")
        return copy.deepcopy(self.responses[task])


class MissingCannedResponse(LookupError):
    pass
