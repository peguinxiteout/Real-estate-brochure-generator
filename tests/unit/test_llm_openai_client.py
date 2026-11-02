"""OpenAICompatibleClient against a fake HTTP transport: no network."""
import json

import httpx
import pytest

from brochure.llm.errors import LLMBadReply, LLMError, LLMRateLimited
from brochure.llm.openai_compatible import DEFAULT_MODEL, STRICT_SCHEMA_MODELS, OpenAICompatibleClient, client_from_env
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


def rate_limited(retry_after: str | None = None) -> httpx.Response:
    headers = {"retry-after": retry_after} if retry_after else {}
    return httpx.Response(429, headers=headers, json={"error": {"message": "Rate limit reached", "type": "tokens"}})


def test_a_429_is_retried_after_the_wait_the_server_asked_for():
    transport, sleeps = Transport(rate_limited("7"), completion('{"name": "A"}')), []
    assert make_client(transport, sleeps=sleeps).complete("brief.extract", {}) == {"name": "A"}
    assert len(transport.requests) == 2
    assert sleeps == [7]


def test_three_429s_raise_llm_rate_limited_after_exactly_three_attempts_with_growing_waits():
    transport, sleeps = Transport(rate_limited()), []
    with pytest.raises(LLMRateLimited, match="rate limit"):
        make_client(transport, sleeps=sleeps).complete("brief.extract", {})
    assert len(transport.requests) == 3
    assert sleeps == [1, 2]  # no sleep after the last attempt


def test_a_timeout_is_an_llm_error_and_is_not_retried():
    transport = Transport(httpx.ReadTimeout("timed out"))
    with pytest.raises(LLMError, match="timed out") as raised:
        make_client(transport).complete("brief.extract", {})
    assert not isinstance(raised.value, LLMRateLimited)
    assert len(transport.requests) == 1


def test_an_http_error_is_an_llm_error_with_the_status_and_is_not_retried():
    transport = Transport(httpx.Response(500, json={"error": {"message": "upstream broke"}}))
    with pytest.raises(LLMError, match="500.*upstream broke"):
        make_client(transport).complete("brief.extract", {})
    assert len(transport.requests) == 1


def test_a_connection_failure_is_an_llm_error():
    transport = Transport(httpx.ConnectError("name resolution failed"))
    with pytest.raises(LLMError, match="connect"):
        make_client(transport).complete("brief.extract", {})


def test_the_api_key_never_appears_in_an_error_even_when_the_server_echoes_it():
    echo = httpx.Response(401, json={"error": {"message": f"Invalid API Key: {API_KEY}"}})
    with pytest.raises(LLMError) as raised:
        make_client(Transport(echo)).complete("brief.extract", {})
    assert API_KEY not in str(raised.value)
    assert "401" in str(raised.value)
    assert raised.value.__cause__ is None or API_KEY not in str(raised.value.__cause__)


@pytest.mark.parametrize("content", ["not json at all", '["a", "list"]', ""])
def test_a_reply_that_is_not_a_json_object_is_an_llm_bad_reply(content):
    with pytest.raises(LLMBadReply):
        make_client(Transport(completion(content))).complete("brief.extract", {})


def test_the_api_key_is_never_logged_or_shown_in_the_client_repr(caplog):
    caplog.set_level("DEBUG")
    client = make_client(Transport(rate_limited("1"), completion("{}")))
    client.complete("brief.extract", {})
    with pytest.raises(LLMError):
        make_client(Transport(httpx.Response(500, json={}))).complete("brief.extract", {})
    assert API_KEY not in caplog.text
    assert API_KEY not in repr(client) and API_KEY not in str(vars(client))


def test_the_factory_reads_the_three_env_vars():
    env = {"LLM_BASE_URL": "https://other.example/v1", "LLM_API_KEY": API_KEY, "LLM_MODEL": "some/model"}
    client = client_from_env(TASKS, env)
    assert (client.base_url, client.model) == ("https://other.example/v1", "some/model")


def test_the_factory_defaults_to_groq_and_a_production_model_with_strict_schemas():
    client = client_from_env(TASKS, {"LLM_API_KEY": API_KEY})
    assert client.base_url == "https://api.groq.com/openai/v1"
    assert client.model == DEFAULT_MODEL == "openai/gpt-oss-120b"
    assert client.model in STRICT_SCHEMA_MODELS


@pytest.mark.parametrize("env", [{}, {"LLM_API_KEY": ""}, {"LLM_API_KEY": "   "}])
def test_the_factory_without_an_api_key_says_which_variable_to_set(env):
    with pytest.raises(LLMError, match="LLM_API_KEY"):
        client_from_env(TASKS, env)


def api_error(status: int, message="bad", type_="invalid_request_error", code="bad_request") -> httpx.Response:
    return httpx.Response(status, json={"error": {"message": message, "type": type_, "code": code}})


def error_of(response: httpx.Response) -> str:
    with pytest.raises(LLMError) as raised:
        make_client(Transport(response)).complete("brief.extract", {})
    return str(raised.value)


def test_a_400_error_carries_the_status_type_code_and_message_from_the_body():
    text = error_of(api_error(400, "The JSON schema is invalid: 'default' is not allowed", "invalid_request_error", "invalid_json_schema"))
    assert "400" in text
    assert "invalid_request_error" in text
    assert "invalid_json_schema" in text
    assert "The JSON schema is invalid: 'default' is not allowed" in text


def test_a_body_without_type_or_code_still_gives_the_status_and_message():
    text = error_of(httpx.Response(400, json={"error": {"message": "model not found"}}))
    assert "400" in text and "model not found" in text
    assert "None" not in text


def test_a_401_says_the_key_was_rejected_and_keeps_the_providers_message():
    text = error_of(api_error(401, "Invalid API Key", "invalid_request_error", "invalid_api_key"))
    assert "API key was rejected" in text
    assert "401" in text and "invalid_api_key" in text and "Invalid API Key" in text


def test_the_key_is_redacted_wherever_the_provider_echoes_it():
    echoes = [
        api_error(400, f"bad key {API_KEY} given"),
        api_error(400, "bad", type_=API_KEY, code=API_KEY),
        api_error(401, f"Invalid API Key: {API_KEY}"),
        httpx.Response(502, text=f"<html>upstream saw {API_KEY}</html>"),
    ]
    for response in echoes:
        text = error_of(response)
        assert API_KEY not in text
        assert str(response.status_code) in text


def test_a_body_that_is_not_json_gives_the_status_and_a_short_raw_snippet():
    text = error_of(httpx.Response(502, text="<html>\n<body>Bad   Gateway</body>\n</html>"))
    assert "502" in text
    assert "<html> <body>Bad Gateway</body> </html>" in text  # whitespace collapsed


def test_the_providers_message_is_truncated_to_300_characters():
    text = error_of(api_error(400, "x" * 5000))
    assert "x" * 300 in text and "x" * 301 not in text
    assert text.endswith("...") and len(text) < 500
    raw = error_of(httpx.Response(502, text="y" * 5000))
    assert "y" * 300 in raw and "y" * 301 not in raw


def test_an_error_with_an_empty_body_is_just_the_status():
    assert error_of(httpx.Response(500, json={})).endswith("HTTP 500")
    assert error_of(httpx.Response(503, text="")).endswith("HTTP 503")


# --- reasoning effort: a reasoning model spends its output budget thinking unless told to think less -------------------

THINKING_TASKS = {"copy.write": TaskSpec(system="Write.", schema=SCHEMA, reasoning_effort="low"), "plain.task": TASKS["plain.task"]}


def reasoning_body(model, task="copy.write"):
    transport = Transport(completion('{"name": "x"}'))
    client = OpenAICompatibleClient(
        BASE_URL, API_KEY, model, THINKING_TASKS, http_client=httpx.Client(transport=httpx.MockTransport(transport))
    )
    client.complete(task, {})
    return transport.body()


def test_a_task_that_asks_for_low_reasoning_sends_reasoning_effort_to_a_gpt_oss_model():
    assert reasoning_body("openai/gpt-oss-120b")["reasoning_effort"] == "low"
    assert reasoning_body("openai/gpt-oss-20b")["reasoning_effort"] == "low"


def test_a_task_that_does_not_ask_sends_no_reasoning_effort():
    assert "reasoning_effort" not in reasoning_body("openai/gpt-oss-120b", task="plain.task")


def test_reasoning_effort_is_not_sent_to_a_model_that_may_reject_it():
    assert "reasoning_effort" not in reasoning_body("llama-3.3-70b-versatile")
