"""OpenAICompatibleClient against a fake HTTP transport: no network."""
import json

import httpx
import pytest

from brochure.llm.errors import LLMBadReply, LLMError, LLMRateLimited
from brochure.llm.openai_compatible import OpenAICompatibleClient
from brochure.llm.tasks import TaskSpec

BASE_URL = "https://llm.example.test/v1"
API_KEY = "gsk_test_SECRET_key_123"
SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": ["string", "null"]}},
    "required": ["name"],
    "additionalProperties": False,
}
TASKS = {"brief.extract": TaskSpec(system="Extract the facts.", schema=SCHEMA), "plain.task": TaskSpec(system="Just talk.")}
STRICT_MODEL = "openai/gpt-oss-120b"


def completion(content: str) -> httpx.Response:
    body = {
        "id": "x", "object": "chat.completion", "created": 0, "model": "m",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
    }
    return httpx.Response(200, json=body)


class Transport:
    """Plays the answers in order (the last one repeats) and records every request."""

    def __init__(self, *answers):
        self.answers, self.requests = list(answers), []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        answer = self.answers[min(len(self.requests), len(self.answers)) - 1]
        if isinstance(answer, Exception):
            raise answer
        return answer

    def body(self, n: int = 0) -> dict:
        return json.loads(self.requests[n].content)


def make_client(transport, model=STRICT_MODEL, sleeps=None, **kwargs):
    return OpenAICompatibleClient(
        BASE_URL, API_KEY, model, TASKS,
        http_client=httpx.Client(transport=httpx.MockTransport(transport)),
        sleep=(sleeps if sleeps is not None else []).append,
        **kwargs,
    )


def test_sends_model_messages_temperature_and_a_strict_json_schema_to_chat_completions():
    transport = Transport(completion('{"name": "Aurelia"}'))
    make_client(transport).complete("brief.extract", {"prompt": "Aurelia Heights, Pune"})

    request = transport.requests[0]
    assert str(request.url) == f"{BASE_URL}/chat/completions"
    body = transport.body()
    assert body["model"] == STRICT_MODEL
    assert body["temperature"] == 0
    assert body["messages"][0] == {"role": "system", "content": "Extract the facts."}
    assert body["messages"][1]["role"] == "user"
    assert json.loads(body["messages"][1]["content"]) == {"prompt": "Aurelia Heights, Pune"}
    assert body["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "brief_extract", "strict": True, "schema": SCHEMA},
    }


def test_parses_the_reply_as_a_dict():
    transport = Transport(completion('{"name": "Aurelia Heights"}'))
    assert make_client(transport).complete("brief.extract", {}) == {"name": "Aurelia Heights"}


def test_a_model_without_strict_schemas_gets_json_object_mode_with_the_schema_in_the_system_message():
    transport = Transport(completion("{}"))
    make_client(transport, model="llama-3.3-70b-versatile").complete("brief.extract", {"prompt": "p"})

    body = transport.body()
    assert body["response_format"] == {"type": "json_object"}
    system = body["messages"][0]["content"]
    assert system.startswith("Extract the facts.")
    assert "JSON" in system
    assert json.dumps(SCHEMA) in system


def test_a_task_without_a_schema_uses_json_object_mode_even_on_a_strict_model():
    transport = Transport(completion("{}"))
    make_client(transport).complete("plain.task", {})

    body = transport.body()
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0]["content"].startswith("Just talk.")
    assert "JSON" in body["messages"][0]["content"]


def test_images_are_not_supported_yet_and_nothing_is_sent(tmp_path):
    transport = Transport(completion("{}"))
    with pytest.raises(NotImplementedError, match="images"):
        make_client(transport).complete("brief.extract", {}, images=[tmp_path / "a.jpg"])
    assert transport.requests == []


def test_an_unknown_task_is_an_llm_error_that_names_the_task():
    transport = Transport(completion("{}"))
    with pytest.raises(LLMError, match=r"layout\.arrange.*brief\.extract"):
        make_client(transport).complete("layout.arrange", {})
    assert transport.requests == []
