"""Stub agents: no LLM, no rendering. They return fixed data from sample/ so the whole flow can run end to end."""
import json
from dataclasses import dataclass
from pathlib import Path

from brochure.contracts.images import ImageTag
from brochure.contracts.manifest import ImageManifest
from brochure.contracts.qa import QAIssue
from brochure.contracts.spec import BrochureSpec, PageSpec, SlotFill
from brochure.contracts.state import PipelineState
from brochure.pipeline.brief import brief_step
from brochure.pipeline.agents import Agents, RenderResult
from brochure.slots import SlotTemplate, load_slots
from brochure.verbatim import verbatim_copy

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_ID = "classic-8pp"
LOGO_SLOTS = ("cover_logo", "back_logo")
SAMPLE_RERA_URL = "https://example.com/rera/sample"  # a fake address; the real one is not decided


@dataclass(frozen=True)
class SampleData:
    template: SlotTemplate
    manifest: ImageManifest
    image_tags: list[ImageTag]
    copy: dict[str, str]  # text that cannot be derived from the facts or the brand kit


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_sample_data(root: Path = REPO_ROOT) -> SampleData:
    """The one place the stubs get their data: the template's slots.json and the files in sample/."""
    return SampleData(
        template=load_slots(root / "templates" / TEMPLATE_ID / "slots.json"),
        manifest=ImageManifest.model_validate(_read_json(root / "sample" / "images.json")),
        image_tags=[ImageTag.model_validate(t) for t in _read_json(root / "sample" / "image_tags.json")],
        copy=_read_json(root / "sample" / "stub_copy.json"),
    )


class ScriptedQA:
    """QA stub. issues_per_round[n] is what the critic reports on its (n+1)th pass; later passes report nothing."""

    def __init__(self, issues_per_round: list[list[QAIssue]] | None = None):
        self.issues_per_round = issues_per_round or []

    def __call__(self, state: PipelineState, llm) -> list[QAIssue]:
        if state.qa_round < len(self.issues_per_round):
            return list(self.issues_per_round[state.qa_round])
        return []


def stub_agents(data: SampleData | None = None, qa=None) -> Agents:
    data = data or load_sample_data()

    def vision(state: PipelineState, llm) -> list[ImageTag]:
        return list(data.image_tags)

    def copywriter(state: PipelineState, llm) -> dict[str, str]:
        return {**data.copy, **verbatim_copy(state.project_facts, state.brand_kit)}

    def layout(state: PipelineState, llm) -> BrochureSpec:
        image_for_slot = {e.intended_slot: e.filename for e in data.manifest.images}
        fills: dict[int, dict[str, SlotFill]] = {n: {} for n in range(1, 9)}
        for slot in data.template.slots:
            empty = {"text": SlotFill(text=""), "image": SlotFill(image_path=""), "qr": SlotFill(qr_data="")}
            fills[slot.page][slot.id] = empty[slot.type]
            if slot.id in image_for_slot:
                fills[slot.page][slot.id] = SlotFill(image_path=image_for_slot[slot.id])
            if slot.type == "text":
                fills[slot.page][slot.id] = SlotFill(text=state.slot_copy.get(slot.id, f"[copy needed: {slot.id}]"))  # visible, so a reviewer sees the gap
            if slot.id == "rera_number":  # a legal fact: it comes from the facts, not from the copy
                fills[slot.page][slot.id] = SlotFill(text=state.project_facts.rera_number)
            if slot.type == "qr":
                fills[slot.page][slot.id] = SlotFill(qr_data=SAMPLE_RERA_URL)
            if slot.id in LOGO_SLOTS:
                fills[slot.page][slot.id] = SlotFill(image_path=state.brand_kit.logo_path)
        pages = [PageSpec(layout_id=f"{state.template_id}-p{n}", slots=fills[n]) for n in sorted(fills)]
        return BrochureSpec(template_id=state.template_id, pages=pages)

    def renderer(state: PipelineState, llm) -> RenderResult:
        """Renders nothing. Returns fake paths (FAKE-NOT-RENDERED/...), one PNG per page of the spec; no file exists."""
        pages = len(state.spec.pages)
        return RenderResult(
            pdf_path="FAKE-NOT-RENDERED/brochure.pdf",
            page_images=[f"FAKE-NOT-RENDERED/page-{n}.png" for n in range(1, pages + 1)],
        )

    def export(state: PipelineState, llm) -> None:
        """Exports nothing; it only marks the end of an approved run."""
        return None

    return Agents(brief=brief_step, vision=vision, copywriter=copywriter, layout=layout, renderer=renderer, qa=qa or ScriptedQA(), export=export)
