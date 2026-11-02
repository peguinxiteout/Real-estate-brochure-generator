"""The layout's image assignment on the Aurelia Heights sample: the rules file, the 12 image tags, the real template."""
from pathlib import Path

import pytest

from brochure.dpi import DpiStatus
from brochure.layout import assign_images, load_layout_rules
from brochure.pipeline import load_sample_data

ROOT = Path(__file__).parents[2]
DATA = load_sample_data()
RULES = load_layout_rules(ROOT / "templates" / "classic-8pp" / "layout_rules.json")
LOW_RES = {"amenity_gym.jpg": "amenity_img_c", "floorplan_3bhk.jpg": "plan_img_b", "developer_office.jpg": "about_img"}


@pytest.fixture(scope="module")
def result():
    return assign_images(DATA.template, RULES, DATA.image_tags)


def placed(result):
    return {slot_id: p.image for slot_id, p in result.placements.items()}


def notes(result, check):
    return [f.note for f in result.findings if f.check == check]


def test_no_image_is_placed_where_it_fails_the_dpi_rule(result):
    assert all(p.band != DpiStatus.FAIL for p in result.placements.values())


def test_the_three_low_resolution_images_are_not_placed_and_their_intended_slots_are_unfilled(result):
    assert not set(LOW_RES) & set(placed(result).values())
    assert not set(LOW_RES.values()) & set(placed(result))


def test_each_unfilled_slot_has_a_warning_naming_its_low_resolution_image_and_its_dpi(result):
    unfilled = {n.split(":")[0]: n for n in notes(result, "layout.slot_unfilled")}
    assert set(unfilled) == set(LOW_RES.values())
    for image, slot_id in LOW_RES.items():
        assert f"{image} is " in unfilled[slot_id] and " DPI" in unfilled[slot_id]
    pages = {f.note.split(":")[0]: f.page for f in result.findings if f.check == "layout.slot_unfilled"}
    assert pages == {"amenity_img_c": 4, "plan_img_b": 5, "about_img": 7}


def test_the_clubhouse_is_placed_with_a_warn_band_warning(result):
    assert placed(result)["amenity_img_b"] == "amenity_clubhouse.jpg"
    assert result.placements["amenity_img_b"].band == DpiStatus.WARN
    assert notes(result, "layout.dpi_warn") == [
        "amenity_img_b: amenity_clubhouse.jpg is 288 DPI, below the 300 DPI target (it prints, softer)"
    ]


def test_every_placed_image_is_of_a_kind_its_slot_accepts(result):
    kinds = {t.path: t.kind for t in DATA.image_tags}
    accepts = {r.slot: r.kinds for r in RULES.rules}
    assert all(kinds[image] in accepts[slot_id] for slot_id, image in placed(result).items())
    assert len(placed(result)) == 9


def test_every_placed_image_is_in_the_slot_the_manifest_intended_for_it(result):
    intended = {e.filename: e.intended_slot for e in DATA.manifest.images}
    assert {image: slot_id for slot_id, image in placed(result).items()} == {
        image: slot_id for image, slot_id in intended.items() if image not in LOW_RES
    }


def test_the_three_low_resolution_images_are_reported_as_unused(result):
    unused = notes(result, "layout.image_unused")
    assert sorted(n.split()[0] for n in unused) == sorted(LOW_RES)
    assert all("too small for every slot" in n for n in unused)


def test_the_hero_gets_the_tower_render(result):
    assert placed(result)["hero"] == "hero_tower.jpg"
