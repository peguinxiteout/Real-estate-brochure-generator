"""LLMClient for any OpenAI-compatible chat completions endpoint (Groq by default)."""
import json
import time
from collections.abc import Callable, Mapping
from pathlib import Path

import httpx
from openai import OpenAI

from brochure.llm.tasks import TaskSpec

# Models Groq documents as supporting strict json_schema (constrained decoding). Anything else gets JSON-object mode.
STRICT_SCHEMA_MODELS = frozenset({
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "qwen/qwen3.8-27b",
    "meta-models/muse-spark-open",
})


class OpenAICompatibleClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        tasks: Mapping[str, TaskSpec],
        timeout: float = 60.0,
        *,
        http_client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.base_url, self.model, self.tasks, self.timeout = base_url, model, tasks, timeout
        self._sleep = sleep
        # max_retries=0: retrying is done here, where the 429 policy lives.
        self._sdk = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0, http_client=http_client)

    def complete(self, task: str, payload: dict, images: list[Path] | None = None) -> dict:
        spec = self.tasks[task]
        system, response_format = self._format(task, spec)
        response = self._sdk.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format=response_format,
        )
        return json.loads(response.choices[0].message.content)

    def _format(self, task: str, spec: TaskSpec) -> tuple[str, dict]:
        """The system message and response_format for a task: strict json_schema where the model supports it."""
        if spec.schema is not None and self.model in STRICT_SCHEMA_MODELS:
            name = task.replace(".", "_")
            return spec.system, {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": spec.schema}}
        parts = [spec.system, "Reply with a single JSON object."]
        if spec.schema is not None:
            parts.append(f"It must match this JSON Schema:\n{json.dumps(spec.schema)}")
        return "\n\n".join(parts), {"type": "json_object"}
