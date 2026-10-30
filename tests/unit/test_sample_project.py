"""The sample project ("Aurelia Heights") validates against the contracts and fits the template."""
import json
from pathlib import Path

import pytest

from brochure.contracts.brand import BrandKit
from brochure.contracts.images import ImageTag
from brochure.contracts.manifest import ImageManifest
from brochure.contracts.project import Brief, ProjectFacts
from brochure.dpi import classify_dpi, effective_dpi
from brochure.slots import load_slots

ROOT = Path(__file__).parents[2]
SAMPLE = ROOT / "sample"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_brand_kit_validates_and_its_logo_exists():
    kit = BrandKit.model_validate(read_json(SAMPLE / "brand_kit.json"))
    assert kit.company_name == "Kestrel Urbanscapes"
    assert (SAMPLE / kit.logo_path).is_file()


def test_brief_validates_and_its_form_is_complete_enough_to_become_project_facts():
    brief = Brief.model_validate(read_json(SAMPLE / "brief.json"))
    facts = ProjectFacts.model_validate(brief.form.model_dump())
    assert facts.name == "Aurelia Heights"
    assert facts.rera_number
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


def dpi_by_file(manifest, template):
    result = {}
    for e in manifest.images:
        slot = template.get(e.intended_slot)
        result[e.filename] = effective_dpi(e.width_px, e.height_px, slot.bleed_width_mm, slot.bleed_height_mm)
    return result


def test_exactly_three_images_fail_the_dpi_rule_and_one_warns(manifest, template):
    status = {name: classify_dpi(dpi) for name, dpi in dpi_by_file(manifest, template).items()}
    assert sorted(n for n, s in status.items() if s == "fail") == [
        "amenity_gym.jpg", "developer_office.jpg", "floorplan_3bhk.jpg",
    ]
    assert [n for n, s in status.items() if s == "warn"] == ["amenity_clubhouse.jpg"]


@pytest.fixture(scope="module")
def image_tags():
    return [ImageTag.model_validate(t) for t in read_json(ROOT / "sample" / "image_tags.json")]


def test_image_tag_fixture_matches_the_manifest_size_kind_and_filename(manifest, image_tags):
    by_path = {t.path: t for t in image_tags}
    assert len(image_tags) == 12
    assert set(by_path) == {e.filename for e in manifest.images}
    for e in manifest.images:
        tag = by_path[e.filename]
        assert (tag.width_px, tag.height_px, tag.kind) == (e.width_px, e.height_px, e.kind), e.filename
