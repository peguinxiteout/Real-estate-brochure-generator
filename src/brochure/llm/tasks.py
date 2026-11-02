"""What a task name stands for when it is sent to a real model: a system prompt and an optional JSON Schema."""
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskSpec:
    system: str
    schema: dict | None = None
