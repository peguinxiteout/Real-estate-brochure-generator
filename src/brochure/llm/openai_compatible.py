"""LLMClient for any OpenAI-compatible chat completions endpoint (Groq by default)."""
import json
import os
import time
from collections.abc import Callable, Mapping
from pathlib import Path

import httpx
from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from brochure.llm.errors import LLMBadReply, LLMError, LLMRateLimited
from brochure.llm.tasks import TaskSpec

MAX_ATTEMPTS = 3
MAX_WAIT_SECONDS = 60.0


def _wait_seconds(retry_after: str | None, attempt: int) -> float:
    """How long to sleep before the next attempt: the server's Retry-After if it sent one, else 1s, 2s, 4s..."""
    try:
        wait = float(retry_after)
    except (TypeError, ValueError):
        wait = 2.0 ** (attempt - 1)
    return min(max(wait, 0.0), MAX_WAIT_SECONDS)


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
        self._scrub = lambda text: text.replace(api_key, "***") if api_key else text  # the key is kept out of repr()
        self._sdk = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, max_retries=0, http_client=http_client)

    def complete(self, task: str, payload: dict, images: list[Path] | None = None) -> dict:
        if images:
            raise NotImplementedError("OpenAICompatibleClient does not send images yet (no vision support)")
        if task not in self.tasks:
            raise LLMError(f"no prompt is registered for task {task!r} (known: {', '.join(sorted(self.tasks)) or 'none'})")
        spec = self.tasks[task]
        system, response_format = self._format(task, spec)
        response = self._create(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format=response_format,
        )
        return self._parse(response.choices[0].message.content)

    @staticmethod
    def _parse(content: str | None) -> dict:
        try:
            reply = json.loads(content or "")
        except json.JSONDecodeError:
            raise LLMBadReply(f"the model's reply is not valid JSON: {(content or '')[:200]!r}") from None
        if not isinstance(reply, dict):
            raise LLMBadReply(f"the model's reply is a JSON {type(reply).__name__}, not an object")
        return reply

    def _create(self, **request):
        """One chat completion. An HTTP 429 is retried after the wait the server asked for, up to MAX_ATTEMPTS in all.

        Every other failure is an LLMError whose text never includes the API key.
        """
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return self._sdk.chat.completions.create(model=self.model, temperature=0, **request)
            except RateLimitError as error:
                if attempt == MAX_ATTEMPTS:
                    raise LLMRateLimited(f"rate limit still hit after {MAX_ATTEMPTS} attempts") from None
                self._sleep(_wait_seconds(error.response.headers.get("retry-after"), attempt))
            except APITimeoutError:
                raise LLMError(f"the request timed out after {self.timeout:g}s") from None
            except APIConnectionError:
                raise LLMError(f"could not connect to {self.base_url}") from None
            except APIStatusError as error:
                # `from None`: the SDK error can carry the server's text, which might echo the key.
                raise LLMError(f"the provider answered HTTP {error.status_code}: {self._scrub(str(error.message))}") from None

    def _format(self, task: str, spec: TaskSpec) -> tuple[str, dict]:
        """The system message and response_format for a task: strict json_schema where the model supports it."""
        if spec.schema is not None and self.model in STRICT_SCHEMA_MODELS:
            name = task.replace(".", "_")
            return spec.system, {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": spec.schema}}
        parts = [spec.system, "Reply with a single JSON object."]
        if spec.schema is not None:
            parts.append(f"It must match this JSON Schema:\n{json.dumps(spec.schema)}")
        return "\n\n".join(parts), {"type": "json_object"}


DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"


def client_from_env(tasks: Mapping[str, TaskSpec], environ: Mapping[str, str] | None = None) -> OpenAICompatibleClient:
    """A client from LLM_BASE_URL, LLM_API_KEY and LLM_MODEL (os.environ unless `environ` is given).

    The base URL and the model have defaults (Groq); the key does not.
    """
    env = os.environ if environ is None else environ
    api_key = (env.get("LLM_API_KEY") or "").strip()
    if not api_key:
        raise LLMError("LLM_API_KEY is not set. Put your key in the environment (see .env.example); it is never read from a file by this program.")
    base_url = (env.get("LLM_BASE_URL") or "").strip() or DEFAULT_BASE_URL
    model = (env.get("LLM_MODEL") or "").strip() or DEFAULT_MODEL
    return OpenAICompatibleClient(base_url, api_key, model, tasks)
