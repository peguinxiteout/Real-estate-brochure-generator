"""The Brief agent with a FakeLLM: what it fills, what it refuses to fill, and how it fails. No network."""
import json
from pathlib import Path

import pytest

from brochure.agents.brief import PROMPT_FILE, TASK_SPEC, brief_agent
from brochure.contracts.project import Brief, BriefForm
from brochure.llm import FakeLLM, LLMBadReply, LLMError, LLMRateLimited

SAMPLE = Path(__file__).parents[2] / "sample"


def sparse() -> Brief:
    return Brief.model_validate(json.loads((SAMPLE / "brief_sparse.json").read_text(encoding="utf-8")))


def reply(**fields) -> dict:
    """A model reply in the full shape: every key present, nothing extracted unless given."""
    empty = {
        "name": None, "rera_number": None, "rera_state": None, "location": None, "configurations": [],
        "amenities": [], "specifications": [], "landmarks": [], "possession": None, "tone_notes": None,
    }
    return {**empty, **fields}


# What the model should find in sample/brief_sparse.json's prompt.
STATED = reply(
    rera_number="P99999000000 (SAMPLE)",
    configurations=[{"label": "2 BHK", "carpet_area_sqft": 780}, {"label": "3 BHK", "carpet_area_sqft": 1090}],
    possession="December 2028",
    tone_notes="warm and aspirational, calm and confident",
)


def run(canned: dict, brief: Brief | None = None) -> tuple[BriefForm, FakeLLM]:
    llm = FakeLLM({"brief.extract": canned})
    return brief_agent(brief or sparse(), llm), llm


def test_empty_form_fields_are_filled_from_what_the_model_found_in_the_prompt():
    form, _ = run(STATED)
    assert form.rera_number == "P99999000000 (SAMPLE)"
    assert form.possession == "December 2028"
    assert [(c.label, c.carpet_area_sqft) for c in form.configurations] == [("2 BHK", 780), ("3 BHK", 1090)]
    assert form.tone_notes == "warm and aspirational, calm and confident"
    assert form.location is None  # the prompt does not say, so it stays empty


def test_a_filled_form_field_is_never_overwritten_by_the_model():
    brief = sparse()
    brief = brief.model_copy(update={"form": brief.form.model_copy(update={"possession": "Dec 2027", "tone_notes": "Plain."})})
    form, _ = run(STATED, brief)
    assert form.possession == "Dec 2027"
    assert form.tone_notes == "Plain."
    assert form.name == "Aurelia Heights"
    assert form.rera_number == "P99999000000 (SAMPLE)"  # still empty in the form, so still filled


def test_a_string_the_prompt_does_not_contain_is_dropped():
    form, _ = run({**STATED, "possession": "March 2031", "location": "Baner, Pune"})
    assert form.possession is None  # the prompt says December 2028, not March 2031
    assert form.location is None
    assert form.rera_number == "P99999000000 (SAMPLE)"  # grounded values in the same reply are kept


def test_a_number_the_prompt_does_not_contain_drops_that_configuration_only():
    found = [{"label": "2 BHK", "carpet_area_sqft": 780}, {"label": "3 BHK", "carpet_area_sqft": 1200}]
    form, _ = run({**STATED, "configurations": found})
    assert [(c.label, c.carpet_area_sqft) for c in form.configurations] == [("2 BHK", 780)]


def test_a_landmark_distance_the_prompt_does_not_contain_is_dropped():
    brief = sparse().model_copy(update={"prompt": "The metro station is 1.2 km away. RERA P1."})
    brief = brief.model_copy(update={"form": brief.form.model_copy(update={"landmarks": []})})
    found = [{"name": "metro station", "distance_km": 1.2}, {"name": "metro station", "distance_km": 9.9}]
    form, _ = run(reply(landmarks=found), brief)
    assert [m.distance_km for m in form.landmarks] == [1.2]


def test_an_invented_rera_number_is_dropped():
    form, _ = run({**STATED, "rera_number": "P52100012345"})
    assert form.rera_number is None


def test_a_rera_number_must_match_the_prompt_character_for_character():
    form, _ = run({**STATED, "rera_number": "p99999000000 (sample)"})  # right digits, wrong case: not verbatim
    assert form.rera_number is None


def test_strings_match_the_prompt_ignoring_case_and_whitespace():
    form, _ = run({**STATED, "possession": "december   2028", "tone_notes": "Warm and\naspirational"})
    assert form.possession == "december   2028"
    assert form.tone_notes == "Warm and\naspirational"


def test_a_number_written_with_a_thousands_comma_in_the_prompt_is_found():
    brief = sparse().model_copy(update={"prompt": "3 BHK with 1,090 sq ft carpet area."})
    form, _ = run(reply(configurations=[{"label": "3 BHK", "carpet_area_sqft": 1090}]), brief)
    assert [c.carpet_area_sqft for c in form.configurations] == [1090]


def test_every_dropped_value_is_logged_with_its_field(caplog):
    caplog.set_level("INFO", logger="brochure.agents.brief")
    run({**STATED, "possession": "March 2031", "rera_number": "P52100012345"})
    dropped = [r.getMessage() for r in caplog.records if "not in the prompt" in r.getMessage()]
    assert any("possession" in m and "March 2031" in m for m in dropped)
    assert any("rera_number" in m for m in dropped)
    assert not any("configurations" in m for m in dropped)


class Script:
    """An LLMClient that plays one scripted answer per call (a dict is returned, an exception is raised)."""

    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def complete(self, task, payload, images=None):
        self.calls.append((task, payload, images))
        answer = self.answers[len(self.calls) - 1]
        if isinstance(answer, Exception):
            raise answer
        return answer


INVALID = {**STATED, "possession": 2028}  # a number where a string belongs


def test_one_extract_call_whose_payload_is_the_form_and_the_prompt_and_no_images():
    brief = sparse()
    _, llm = run(STATED, brief)
    assert [(c.task, c.images) for c in llm.calls] == [("brief.extract", [])]
    assert llm.calls[0].payload == {"form": brief.form.model_dump(), "prompt": brief.prompt}
    assert llm.calls[0].payload["form"]["rera_number"] is None  # empty fields are sent too


def test_an_invalid_reply_is_retried_once_with_the_validation_error_and_the_second_reply_is_used():
    llm = Script(INVALID, STATED)
    form = brief_agent(sparse(), llm)
    assert len(llm.calls) == 2
    first, second = llm.calls[0][1], llm.calls[1][1]
    assert "previous_error" not in first
    assert "possession" in second["previous_error"]
    assert (second["form"], second["prompt"]) == (first["form"], first["prompt"])
    assert form.possession == "December 2028"


def test_a_reply_that_is_not_json_is_retried_like_an_invalid_one():
    llm = Script(LLMBadReply("not valid JSON"), STATED)
    assert brief_agent(sparse(), llm).possession == "December 2028"
    assert "not valid JSON" in llm.calls[1][1]["previous_error"]


def test_two_invalid_replies_return_the_form_unchanged_and_log_a_warning(caplog):
    llm = Script(INVALID, INVALID)
    brief = sparse()
    form = brief_agent(brief, llm)
    assert form == brief.form
    assert len(llm.calls) == 2  # one retry, not more
    assert [r.levelname for r in caplog.records if "form only" in r.getMessage()] == ["WARNING"]


@pytest.mark.parametrize("error", [LLMRateLimited("rate limit still hit"), LLMError("HTTP 500"), LLMError("timed out")])
def test_a_client_error_returns_the_form_unchanged_without_raising_and_logs_a_warning(error, caplog):
    llm = Script(error)
    brief = sparse()
    assert brief_agent(brief, llm) == brief.form
    assert len(llm.calls) == 1  # no retry: the client has already done its own
    warning = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warning) == 1 and str(error) in warning[0].getMessage()


def test_an_error_on_the_retry_also_falls_back_to_the_form():
    llm = Script(INVALID, LLMError("HTTP 503"))
    brief = sparse()
    assert brief_agent(brief, llm) == brief.form


def objects_in(schema):
    """Every JSON Schema object node in a schema, including those under $defs."""
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            yield schema
        for value in schema.values():
            yield from objects_in(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from objects_in(value)


def keys_in(schema):
    if isinstance(schema, dict):
        yield from schema
        for value in schema.values():
            yield from keys_in(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from keys_in(value)


def test_the_task_spec_pairs_the_prompt_file_with_a_schema_over_the_form_fields():
    spec = TASK_SPEC
    assert spec.system == PROMPT_FILE.read_text(encoding="utf-8").strip()
    assert set(spec.schema["properties"]) == set(BriefForm.model_fields)


def test_the_schema_meets_the_strict_structured_output_rules():
    schema = TASK_SPEC.schema
    assert len(list(objects_in(schema))) == 4  # the reply, and its configuration, specification and landmark items
    for node in objects_in(schema):
        assert node["additionalProperties"] is False
        assert sorted(node["required"]) == sorted(node["properties"])  # every property is required (null for none)
    assert "default" not in set(keys_in(schema))  # pydantic's defaults are not part of a strict schema


def test_the_prompt_file_states_the_extraction_rules():
    text = PROMPT_FILE.read_text(encoding="utf-8").lower()
    for rule in ["explicitly", "null", "never guess", "rera", "character for character", "user's own wording", "tone_notes", "form always wins"]:
        assert rule in text


def test_the_real_client_wired_to_the_agent_sends_the_prompt_file_and_schema_and_fills_the_form():
    import httpx

    from brochure.agents import TASKS
    from brochure.llm import OpenAICompatibleClient

    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        content = json.dumps(STATED)
        return httpx.Response(200, json={"id": "x", "object": "chat.completion", "created": 0, "model": "m", "choices": [
            {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}]})

    client = OpenAICompatibleClient(
        "https://llm.example.test/v1", "k", "openai/gpt-oss-120b", TASKS,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    brief = sparse()
    form = brief_agent(brief, client)

    assert form.possession == "December 2028"
    body = seen[0]
    assert body["messages"][0]["content"] == TASK_SPEC.system
    assert body["response_format"]["json_schema"]["schema"] == TASK_SPEC.schema
    assert json.loads(body["messages"][1]["content"]) == {"form": brief.form.model_dump(), "prompt": brief.prompt}


def test_llm_from_env_builds_a_client_that_knows_the_agents_tasks():
    from brochure.agents import llm_from_env

    client = llm_from_env({"LLM_API_KEY": "k"})
    assert set(client.tasks) == {"brief.extract"}


def test_the_fallback_warning_carries_the_providers_error_details_and_never_the_key(caplog):
    import httpx

    from brochure.agents import TASKS
    from brochure.llm import OpenAICompatibleClient

    key = "gsk_live_SECRET_abc123"
    body = {"error": {"message": f"schema rejected for key {key}", "type": "invalid_request_error", "code": "invalid_json_schema"}}
    client = OpenAICompatibleClient(
        "https://llm.example.test/v1", key, "openai/gpt-oss-120b", TASKS,
        http_client=httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(400, json=body))),
    )
    caplog.set_level("DEBUG")
    brief = sparse()
    assert brief_agent(brief, client) == brief.form

    warning = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert len(warning) == 1
    for detail in ["400", "invalid_request_error", "invalid_json_schema", "schema rejected"]:
        assert detail in warning[0]
    assert key not in caplog.text
