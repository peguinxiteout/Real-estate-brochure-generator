"""The one interface agents use to talk to a model."""
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    def complete(self, task: str, payload: dict, images: list[Path] | None = None) -> dict:
        """Run the named agent step (e.g. "brief.extract") and return its JSON-able result."""
        ...
