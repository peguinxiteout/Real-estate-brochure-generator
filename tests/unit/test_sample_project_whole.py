"""Load the whole sample project the way a fresh clone would: generate the images into tmp_path, then validate."""
import json
from pathlib import Path

from PIL import Image

from brochure.contracts.brand import BrandKit
from brochure.contracts.images import ImageTag
from brochure.contracts.manifest import ImageManifest
from brochure.contracts.project import Brief
from brochure.contracts.state import PipelineState
from brochure.slots import load_slots
from tests.unit.test_make_sample_images import load_tool

ROOT = Path(__file__).parents[2]


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_whole_sample_project_validates_and_a_pipeline_state_can_be_built_from_it(tmp_path):
    kit = BrandKit.model_validate(read_json(ROOT / "sample" / "brand_kit.json"))
    brief = Brief.model_validate(read_json(ROOT / "sample" / "brief.json"))
    manifest = ImageManifest.model_validate(read_json(ROOT / "sample" / "images.json"))
    tags = [ImageTag.model_validate(t) for t in read_json(ROOT / "tests" / "fixtures" / "image_tags.json")]
    template = load_slots(ROOT / "templates" / "classic-8pp" / "slots.json")

    images = tmp_path / "images"
    load_tool("make_sample_images").generate_images(manifest, images)

    for tag in tags:
        with Image.open(images / tag.path) as img:
            assert img.size == (tag.width_px, tag.height_px)
    assert {e.intended_slot for e in manifest.images} <= {s.id for s in template.slots}

    state = PipelineState(
        template_id=template.template_id,
        brand_kit=kit,
        brief=brief,
        image_dir=str(images),
        image_tags=tags,
    )
    assert len(state.image_tags) == 12
