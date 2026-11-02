"""The real renderer step: what real_agents() and stub_agents() use, and where the output goes. The rendering itself
is faked here (CI has no Pango); tests/integration/test_render_brochure.py renders for real."""
from pathlib import Path

from brochure.llm import FakeLLM
from brochure.pipeline import real_agents, stub_agents
from brochure.pipeline.real import RealRenderer
from brochure.pipeline.stubs import REPO_ROOT
from tests.support import GOOD_COPY, Run, sample_state
from tests.unit.test_agent_copywriter import Script
from tests.unit.test_pipeline_real_agents import NOTHING_FOUND


class FakeRender:
    def __init__(self):
        self.calls = []

    def __call__(self, spec, brand_kit, image_tags, image_dir, out_dir, *, brand_dir=None):
        self.calls.append({"spec": spec, "brand_kit": brand_kit, "image_tags": image_tags, "image_dir": Path(image_dir),
                           "out_dir": Path(out_dir), "brand_dir": brand_dir})
        return Path(out_dir) / "brochure.pdf", [Path(out_dir) / f"page-{n}.png" for n in range(1, len(spec.pages) + 1)]


def test_real_agents_render_for_real_into_out_by_default_and_the_stub_agents_do_not():
    renderer = real_agents().renderer
    assert isinstance(renderer, RealRenderer)
    assert renderer.out_root == REPO_ROOT / "out"
    assert renderer.brand_dir == REPO_ROOT / "sample"
    assert not isinstance(stub_agents().renderer, RealRenderer)


def test_the_output_folder_is_configurable():
    assert real_agents(out_root=Path("/tmp/elsewhere")).renderer.out_root == Path("/tmp/elsewhere")


def test_in_a_run_the_renderer_writes_into_a_folder_named_after_the_thread(tmp_path):
    render = FakeRender()
    agents = real_agents(renderer=RealRenderer(tmp_path, REPO_ROOT / "sample", render=render))
    run = Run(agents, llm=Script(NOTHING_FOUND, GOOD_COPY), thread_id="aurelia-7")
    run.start(sample_state(briefed=False))
    assert run.paused_at == ("human_review",)
    [call] = render.calls
    state = run.state
    assert call["out_dir"] == tmp_path / "aurelia-7"
    assert call["spec"] == state.spec and call["brand_kit"] == state.brand_kit and call["image_tags"] == state.image_tags
    assert call["image_dir"] == Path(state.image_dir) and call["brand_dir"] == REPO_ROOT / "sample"
    assert state.pdf_path == str(tmp_path / "aurelia-7" / "brochure.pdf")
    assert state.page_images == [str(tmp_path / "aurelia-7" / f"page-{n}.png") for n in range(1, 9)]
    assert run.interrupt_value["pdf_path"] == state.pdf_path


def test_outside_a_run_the_folder_is_named_after_a_new_run_id(tmp_path):
    render = FakeRender()
    state = sample_state()
    spec = stub_agents().layout(state.model_copy(update={"slot_copy": GOOD_COPY}), FakeLLM({}))
    RealRenderer(tmp_path, REPO_ROOT / "sample", render=render)(state.model_copy(update={"spec": spec}), FakeLLM({}))
    out_dir = render.calls[0]["out_dir"]
    assert out_dir.parent == tmp_path and out_dir.name.startswith("run-")
