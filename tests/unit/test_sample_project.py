"""The sample project ("Aurelia Heights") validates against the contracts and fits the template."""
import json
from pathlib import Path

import pytest

from brochure.contracts.brand import BrandKit
from brochure.contracts.manifest import ImageManifest
from brochure.contracts.project import Brief
from brochure.slots import load_slots

ROOT = Path(__file__).parents[2]
SAMPLE = ROOT / "sample"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_brand_kit_validates_and_its_logo_exists():
    kit = BrandKit.model_validate(read_json(SAMPLE / "brand_kit.json"))
    assert kit.company_name == "Kestrel Urbanscapes"
    assert (SAMPLE / kit.logo_path).is_file()


def test_brief_validates_and_has_a_non_empty_rera_number():
    brief = Brief.model_validate(read_json(SAMPLE / "brief.json"))
    assert brief.project_facts.name == "Aurelia Heights"
    assert brief.project_facts.rera_number
    assert len(brief.prompt) < 600


@pytest.fixture(scope="module")
def manifest():
    return ImageManifest.model_validate(read_json(SAMPLE / "images.json"))


@pytest.fixture(scope="module")
def template():
    return load_slots(ROOT / "templates" / "classic-8pp" / "slots.json")


def test_manifest_has_12_images_each_aimed_at_a_different_image_slot_of_the_template(manifest, template):
    image_slots = {s.id for s in template.slots if s.type == "image"}
    targets = [e.intended_slot for e in manifest.images]
    assert len(manifest.images) == 12
    assert len(set(targets)) == 12
    assert set(targets) <= image_slots
    assert len({e.filename for e in manifest.images}) == 12
