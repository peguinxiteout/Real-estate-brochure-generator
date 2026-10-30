from brochure.contracts.images import ImageTag
from brochure.llm import Agent, FakeLLM, LLMClient


def tag_image(inputs: dict, llm: LLMClient) -> ImageTag:
    """A toy agent written against the Agent protocol: (inputs, llm) -> schema object."""
    return ImageTag.model_validate(llm.complete("vision.tag", inputs))


def test_fake_llm_satisfies_the_client_protocol():
    assert isinstance(FakeLLM({}), LLMClient)


def test_an_agent_is_a_function_of_inputs_and_llm_returning_a_schema_object():
    canned = {
        "path": "a.jpg", "kind": "photo", "subject": "pool", "width_px": 10, "height_px": 10,
        "quality": "good", "features": [], "focal_point": {"x": 0.5, "y": 0.5},
    }
    llm = FakeLLM({"vision.tag": canned})
    assert isinstance(tag_image, Agent)
    agent: Agent[dict, ImageTag] = tag_image
    tag = agent({"path": "a.jpg"}, llm)
    assert isinstance(tag, ImageTag)
    assert [c.task for c in llm.calls] == ["vision.tag"]
