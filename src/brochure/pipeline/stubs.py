"""Stub agents: no LLM, no rendering. They return fixed data from sample/ so the whole flow can run end to end."""
import json
from dataclasses import dataclass
from pathlib import Path

from brochure.contracts.images import ImageTag
from brochure.contracts.manifest import ImageManifest
from brochure.contracts.state import PipelineState
from brochure.pipeline.agents import Agents
from brochure.slots import SlotTemplate, load_slots

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_ID = "classic-8pp"


@dataclass(frozen=True)
class SampleData:
    template: SlotTemplate
    manifest: ImageManifest
    image_tags: list[ImageTag]


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_sample_data(root: Path = REPO_ROOT) -> SampleData:
    """The one place the stubs get their data: the template's slots.json and the files in sample/."""
    return SampleData(
        template=load_slots(root / "templates" / TEMPLATE_ID / "slots.json"),
        manifest=ImageManifest.model_validate(_read_json(root / "sample" / "images.json")),
        image_tags=[ImageTag.model_validate(t) for t in _read_json(root / "sample" / "image_tags.json")],
    )


def stub_agents(data: SampleData | None = None) -> Agents:
    data = data or load_sample_data()

    def vision(state: PipelineState, llm) -> list[ImageTag]:
        return list(data.image_tags)

    return Agents(brief=None, vision=vision, copywriter=None, layout=None, renderer=None, qa=None, export=None)
