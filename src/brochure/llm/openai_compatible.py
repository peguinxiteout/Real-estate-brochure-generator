"""LLMClient for any OpenAI-compatible chat completions endpoint (Groq by default)."""
import json
import time
from collections.abc import Callable, Mapping
from pathlib import Path

import httpx
from openai import OpenAI

from brochure.llm.tasks import TaskSpec


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
        response = self._sdk.chat.completions.create(
            model=self.model,
            temperature=0,
            messages=[
                {"role": "system", "content": spec.system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": task.replace(".", "_"), "strict": True, "schema": spec.schema},
            },
        )
        return json.loads(response.choices[0].message.content)
