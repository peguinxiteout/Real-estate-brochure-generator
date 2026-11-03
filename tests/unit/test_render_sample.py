"""tools/render_sample.py: the graph on the sample with no LLM (stub brief, vision and copy), the real layout and the
real renderer. Rendering is faked here; tests/integration/test_render_brochure.py runs the script for real."""
import importlib.util
import subprocess
from pathlib import Path

import pytest

from brochure.pipeline.real import RealRenderer

ROOT = Path(__file__).parents[2]


def load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeRender:
    def __init__(self):
        self.calls = []

    def __call__(self, spec, brand_kit, image_tags, image_dir, out_dir, *, brand_dir=None):
        self.calls.append((Path(image_dir), Path(out_dir)))
        return Path(out_dir) / "brochure.pdf", [Path(out_dir) / f"page-{n}.png" for n in range(1, 9)], []


@pytest.fixture
def tool():
    return load_tool("render_sample")


@pytest.fixture
def made(monkeypatch, tool):
    """Stands in for the image generator: records the folders it was asked to fill and writes empty files."""
    calls = []

    def fake_generate(manifest, out_dir):
        calls.append(Path(out_dir))
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        for entry in manifest.images:
            (Path(out_dir) / entry.filename).write_bytes(b"")

    monkeypatch.setattr(tool, "generate_images", fake_generate)
    return calls


def test_default_output_is_out_sample_and_out_is_git_ignored(tool):
    assert tool.DEFAULT_OUT_ROOT == ROOT / "out" and tool.THREAD_ID == "sample"
    assert subprocess.run(["git", "check-ignore", "-q", "out/sample/brochure.pdf"], cwd=ROOT).returncode == 0


def test_the_agents_are_stubs_for_brief_vision_and_copy_with_the_real_layout_and_renderer(tool, tmp_path):
    from brochure.pipeline import real_agents, stub_agents

    agents = tool.sample_agents(tmp_path)
    stub, real = stub_agents(), real_agents(renderer=lambda s, l: None)
    assert agents.brief is stub.brief
    assert isinstance(agents.renderer, RealRenderer) and agents.renderer.out_root == tmp_path
    assert agents.layout.__qualname__ == real.layout.__qualname__ and agents.layout.__module__ == real.layout.__module__
    assert agents.vision.__qualname__ == stub.vision.__qualname__ and agents.copywriter.__qualname__ == stub.copywriter.__qualname__


def test_a_run_renders_into_out_root_sample_and_stops_at_review_with_the_layout_warnings(tool, made, tmp_path):
    render = FakeRender()
    state = tool.run_sample(tmp_path / "out", tmp_path / "images", render=render)
    assert render.calls == [(tmp_path / "images", tmp_path / "out" / "sample")]
    assert state.pdf_path == str(tmp_path / "out" / "sample" / "brochure.pdf")
    unfilled = sorted(w.note.split(":")[0] for w in state.spec.qa_warnings if w.check == "layout.slot_unfilled")
    assert unfilled == ["about_img", "amenity_img_c", "plan_img_b"]


def test_missing_sample_images_are_generated_and_present_ones_are_not(tool, made, tmp_path):
    tool.run_sample(tmp_path / "out", tmp_path / "images", render=FakeRender())
    assert made == [tmp_path / "images"]
    tool.run_sample(tmp_path / "out", tmp_path / "images", render=FakeRender())
    assert made == [tmp_path / "images"]  # all 12 were there the second time


def test_main_prints_the_pdf_the_pages_and_the_warnings(tool, made, tmp_path, capsys):
    assert tool.main(["--out", str(tmp_path / "out"), "--images", str(tmp_path / "images")], render=FakeRender()) == 0
    out = capsys.readouterr().out
    assert str(tmp_path / "out" / "sample" / "brochure.pdf") in out
    for n in range(1, 9):
        assert str(tmp_path / "out" / "sample" / f"page-{n}.png") in out
    assert "layout.slot_unfilled" in out and "plan_img_b" in out
    assert "layout.dpi_warn" in out
