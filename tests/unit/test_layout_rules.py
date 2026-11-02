"""templates/classic-8pp/layout_rules.json: one rule per non-logo image slot, and every rule names a real slot."""
from pathlib import Path

import pytest
from pydantic import ValidationError

from brochure.layout import LOGO_SLOTS, LayoutRules, load_layout_rules, rule_problems
from brochure.pipeline import load_sample_data

ROOT = Path(__file__).parents[2]
RULES_FILE = ROOT / "templates" / "classic-8pp" / "layout_rules.json"
TEMPLATE = load_sample_data().template


def rules() -> LayoutRules:
    return load_layout_rules(RULES_FILE)


def without(slot_id: str) -> LayoutRules:
    r = rules()
    return r.model_copy(update={"rules": [x for x in r.rules if x.slot != slot_id]})


def plus(**rule) -> LayoutRules:
    r = rules()
    return LayoutRules.model_validate({**r.model_dump(), "rules": [*r.model_dump()["rules"], rule]})


def test_the_rules_file_fits_the_template():
    assert rule_problems(rules(), TEMPLATE) == []


def test_every_non_logo_image_slot_has_a_rule_and_the_logos_have_none():
    image_slots = {s.id for s in TEMPLATE.slots if s.type == "image"}
    assert {r.slot for r in rules().rules} == image_slots - set(LOGO_SLOTS)


def test_a_non_logo_image_slot_without_a_rule_is_a_problem_that_names_it():
    problems = rule_problems(without("spec_img"), TEMPLATE)
    assert len(problems) == 1 and "spec_img" in problems[0]


def test_a_rule_for_a_slot_that_is_not_in_the_template_is_a_problem():
    problems = rule_problems(plus(slot="pool_terrace", kinds=["render"], priority=13), TEMPLATE)
    assert len(problems) == 1 and "pool_terrace" in problems[0]


@pytest.mark.parametrize("slot_id", ["cover_title", "rera_qr", "cover_logo"])
def test_a_rule_for_a_text_qr_or_logo_slot_is_a_problem(slot_id):
    problems = rule_problems(plus(slot=slot_id, kinds=["render"], priority=13), TEMPLATE)
    assert len(problems) == 1 and slot_id in problems[0]


def test_two_rules_for_one_slot_is_a_problem():
    problems = rule_problems(plus(slot="hero", kinds=["photo"], priority=13), TEMPLATE)
    assert len(problems) == 1 and "hero" in problems[0]


def test_two_rules_with_the_same_priority_is_a_problem_so_the_picking_order_is_never_ambiguous():
    r = rules()
    clash = r.model_copy(update={"rules": [x.model_copy(update={"priority": 1}) if x.slot == "about_img" else x for x in r.rules]})
    problems = rule_problems(clash, TEMPLATE)
    assert len(problems) == 1 and "priority 1" in problems[0]


def test_rules_for_another_template_are_a_problem():
    problems = rule_problems(rules().model_copy(update={"template_id": "modern-12pp"}), TEMPLATE)
    assert len(problems) == 1 and "modern-12pp" in problems[0]


@pytest.mark.parametrize("bad", [
    {"slot": "hero", "kinds": [], "priority": 1},                      # accepts nothing
    {"slot": "hero", "kinds": ["drawing"], "priority": 1},             # not an image kind
    {"slot": "hero", "kinds": ["render"], "priority": 0},              # priorities start at 1
    {"slot": "hero", "kinds": ["render"], "priority": 1, "weight": 2},  # a typo'd field
])
def test_a_malformed_rule_is_rejected_by_the_model(bad):
    with pytest.raises(ValidationError):
        LayoutRules.model_validate({"template_id": "classic-8pp", "rules": [bad]})


def test_the_cover_hero_picks_first():
    assert min(rules().rules, key=lambda r: r.priority).slot == "hero"
