"""Render the sample brochure through the pipeline graph, with no LLM: stub brief, vision and copy, the real layout and
the real renderer. Stops at human review and prints the PDF, the page PNGs and the warnings.

Usage: python tools/render_sample.py [--out DIR] [--images DIR]
  default: writes out/sample/brochure.pdf and out/sample/page-<n>.png; reads sample/images/ (generated if missing)
Needs WeasyPrint with Pango and Ghostscript (run it in WSL).
"""
import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # run as a script, only tools/ is on the path
    sys.path.insert(0, str(ROOT))

from brochure.contracts.brand import BrandKit  # noqa: E402
from brochure.contracts.manifest import ImageManifest  # noqa: E402
from brochure.contracts.project import Brief  # noqa: E402
from brochure.contracts.state import PipelineState  # noqa: E402
from brochure.llm import FakeLLM  # noqa: E402
from brochure.pipeline import build_graph, memory_checkpointer, real_agents, stub_agents  # noqa: E402
from brochure.pipeline.agents import Agents  # noqa: E402
from brochure.pipeline.real import RealRenderer  # noqa: E402
from brochure.render.pdf import ISSUES_FILE  # noqa: E402
from tools.make_sample_images import generate_images  # noqa: E402

SAMPLE = ROOT / "sample"
DEFAULT_OUT_ROOT = ROOT / "out"
DEFAULT_IMAGES = SAMPLE / "images"
THREAD_ID = "sample"  # the renderer writes into <out root>/<thread id>/


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sample_agents(out_root: Path, render=None) -> Agents:
    """Stub brief, vision and copy (no LLM), the real layout, the real renderer writing under out_root."""
    renderer = RealRenderer(out_root, SAMPLE, render=render)
    return replace(stub_agents(), layout=real_agents(renderer=renderer).layout, renderer=renderer)


def ensure_images(image_dir: Path) -> None:
    manifest = ImageManifest.model_validate(_read(SAMPLE / "images.json"))
    if any(not (image_dir / e.filename).is_file() for e in manifest.images):
        generate_images(manifest, image_dir)


def run_sample(out_root: Path = DEFAULT_OUT_ROOT, image_dir: Path = DEFAULT_IMAGES, render=None) -> PipelineState:
    """Run the graph on the sample until it pauses for review; returns the state there."""
    image_dir = Path(image_dir)
    ensure_images(image_dir)
    state = PipelineState(
        template_id="classic-8pp",
        brand_kit=BrandKit.model_validate(_read(SAMPLE / "brand_kit.json")),
        brief=Brief.model_validate(_read(SAMPLE / "brief.json")),
        image_dir=str(image_dir),
    )
    graph = build_graph(sample_agents(Path(out_root), render), memory_checkpointer(), FakeLLM({}))
    config = {"configurable": {"thread_id": THREAD_ID}}
    graph.invoke(state, config)
    return PipelineState.model_validate(graph.get_state(config).values)


def main(argv: list[str] | None = None, render=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_ROOT,
                        help=f"output root; files go in <out>/{THREAD_ID}/ (default: {DEFAULT_OUT_ROOT})")
    parser.add_argument("--images", type=Path, default=DEFAULT_IMAGES, help=f"sample images (default: {DEFAULT_IMAGES})")
    args = parser.parse_args(argv)
    state = run_sample(args.out, args.images, render)
    print(f"PDF: {state.pdf_path}")
    print("Pages:")
    for png in state.page_images:
        print(f"  {png}")
    warnings = list(state.spec.qa_warnings)
    issues_file = Path(state.pdf_path).parent / ISSUES_FILE
    if issues_file.is_file():
        from brochure.contracts.qa import QAIssue

        warnings += [QAIssue.model_validate(i) for i in _read(issues_file)]
    print(f"Warnings ({len(warnings)}):" if warnings else "Warnings: none")
    for w in warnings:
        page = f"page {w.page}" if w.page else "no page"
        print(f"  [{w.severity}] {w.check} ({page}): {w.note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
