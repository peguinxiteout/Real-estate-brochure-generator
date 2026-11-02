"""The text slots filled by code, not by the Copywriter: legal, contact and list slots taken from the facts and the brand kit."""
from brochure.pipeline import load_sample_data
from brochure.verbatim import VERBATIM_SLOTS, verbatim_copy
from tests.support import sample_state


def text_ids():
    return {s.id for s in load_sample_data().template.slots if s.type == "text"}


def copy():
    state = sample_state()
    return verbatim_copy(state.project_facts, state.brand_kit)


def test_verbatim_copy_has_exactly_the_verbatim_slots_and_all_of_them_are_text_slots_of_the_template():
    assert set(copy()) == set(VERBATIM_SLOTS)
    assert len(VERBATIM_SLOTS) == len(set(VERBATIM_SLOTS)) == 11
    assert set(VERBATIM_SLOTS) <= text_ids()


def test_legal_and_contact_text_is_copied_from_the_brand_kit_and_the_facts_unchanged():
    state, text = sample_state(), copy()
    assert text["disclaimer"] == state.brand_kit.disclaimer
    assert text["about_text"] == state.brand_kit.about_text
    assert text["rera_number"] == state.project_facts.rera_number
    assert text["cover_rera_line"] == f"RERA No. {state.project_facts.rera_number}"
    contact = state.brand_kit.contact
    assert text["contact_block"] == "\n".join([contact.phone, contact.email, contact.website, contact.address])


def test_lists_are_one_line_per_item_straight_from_the_facts():
    text = copy()
    assert text["amenities_list"].splitlines()[:2] == ["Infinity pool", "Clubhouse"]
    assert text["config_table"].splitlines() == ["2 BHK: 780 sq ft carpet", "3 BHK: 1090 sq ft carpet"]
    assert text["location_landmarks"].splitlines()[0] == "Meridian Metro Station, 1.2 km"
    assert text["specs_list"].splitlines()[0] == "Flooring: Vitrified tiles in living and bedrooms"
    assert text["location_address"] == "Meridian Park Road, Pune"


def test_the_cover_title_is_the_exact_project_name_from_the_facts():
    state = sample_state()
    assert verbatim_copy(state.project_facts, state.brand_kit)["cover_title"] == "Aurelia Heights" == state.project_facts.name
    assert "cover_title" in VERBATIM_SLOTS
