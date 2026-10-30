"""Shared helpers for the pipeline tests: the sample project as a PipelineState."""
import json
from pathlib import Path

from brochure.contracts.brand import BrandKit
from brochure.contracts.project import Brief
from brochure.contracts.state import PipelineState

ROOT = Path(__file__).parents[1]


def sample_state(**form_changes) -> PipelineState:
    """The Aurelia Heights sample as a fresh PipelineState. form_changes override fields of the brief form."""
    brand = BrandKit.model_validate(json.loads((ROOT / "sample" / "brand_kit.json").read_text(encoding="utf-8")))
    brief = Brief.model_validate(json.loads((ROOT / "sample" / "brief.json").read_text(encoding="utf-8")))
    brief = brief.model_copy(update={"form": brief.form.model_copy(update=form_changes)})
    return PipelineState(template_id="classic-8pp", brand_kit=brand, brief=brief, image_dir="sample/images")
