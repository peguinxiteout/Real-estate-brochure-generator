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


def stub_agents(data: SampleData | None = None) -> Agents:
    data = data or load_sample_data()

    def vision(state: PipelineState, llm) -> list[ImageTag]:
        return list(data.image_tags)

    def copywriter(state: PipelineState, llm) -> dict[str, str]:
        facts, brand = state.project_facts, state.brand_kit
        contact = brand.contact
        lines = "\n".join
        derived = {
            "cover_rera_line": f"RERA No. {facts.rera_number}",
            "rera_number": facts.rera_number,
            "location_address": facts.location,
            "location_landmarks": lines(f"{m.name}, {m.distance_km:g} km" for m in facts.landmarks),
            "amenities_list": lines(facts.amenities),
            "config_table": lines(f"{c.label}: {c.carpet_area_sqft:g} sq ft carpet" for c in facts.configurations),
            "specs_list": lines(f"{x.category}: {x.detail}" for x in facts.specifications),
            "about_text": brand.about_text,
            "contact_block": lines(v for v in (contact.phone, contact.email, contact.website, contact.address) if v),
            "disclaimer": brand.disclaimer,
        }
        return {**data.copy, **derived}

    return Agents(brief=None, vision=vision, copywriter=copywriter, layout=None, renderer=None, qa=None, export=None)
