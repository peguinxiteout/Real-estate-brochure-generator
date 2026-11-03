"""Verbatim text longer than its char_budget is reported before rendering and never shortened."""
from brochure.llm import FakeLLM
from brochure.pipeline import stub_agents
from brochure.pipeline.real import real_layout_step
from brochure.pipeline.stubs import layout_spec, load_sample_data
from brochure.layout import load_layout_rules
from brochure.verbatim import VERBATIM_SLOTS, over_budget_issues, verbatim_copy
from tests.support import GOOD_COPY, ROOT, Run, sample_state

TEMPLATE = load_sample_data().template
STATE = sample_state()
THIRTY_AMENITIES = [f"Landscaped podium garden {n}" for n in range(30)]
LONG_DISCLAIMER = "All images are artist impressions and for illustration only. " * 12


def copy_for(facts=None, brand=None):
    return {**GOOD_COPY, **verbatim_copy(facts or STATE.project_facts, brand or STATE.brand_kit)}


def spec_for(facts=None, brand=None, images=None):
    state = STATE.model_copy(update={"slot_copy": copy_for(facts, brand), **({"project_facts": facts} if facts else {}),
                                     **({"brand_kit": brand} if brand else {})})
    return layout_spec(state, TEMPLATE, images or {})


def over_budget(spec):
    return [w for w in spec.qa_warnings if w.check == "verbatim.over_budget"]


def many_amenities():
    return STATE.project_facts.model_copy(update={"amenities": THIRTY_AMENITIES})


def fill_of(spec, slot_id):
    return next(page.slots[slot_id] for page in spec.pages if slot_id in page.slots)


def test_the_sample_has_no_verbatim_text_over_budget():
    assert over_budget(spec_for()) == []


def test_an_amenities_list_of_30_items_is_a_warning_with_the_slot_its_length_and_budget():
    [issue] = over_budget(spec_for(many_amenities()))
    text = "\n".join(THIRTY_AMENITIES)
    assert (issue.severity, issue.route_to, issue.page) == ("warning", "none", 4)
    assert "amenities_list" in issue.note and str(len(text)) in issue.note and "300" in issue.note


def test_an_amenities_list_over_budget_is_printed_in_full():
    assert fill_of(spec_for(many_amenities()), "amenities_list").text == "\n".join(THIRTY_AMENITIES)


def test_a_disclaimer_over_budget_is_a_warning_and_its_text_is_unchanged():
    brand = STATE.brand_kit.model_copy(update={"disclaimer": LONG_DISCLAIMER})
    spec = spec_for(brand=brand)
    [issue] = over_budget(spec)
    assert (issue.severity, issue.route_to, issue.page) == ("warning", "none", 8)
    assert "disclaimer" in issue.note and str(len(LONG_DISCLAIMER)) in issue.note and "500" in issue.note
    assert fill_of(spec, "disclaimer").text == LONG_DISCLAIMER


def test_text_exactly_at_the_budget_is_not_reported():
    budget = TEMPLATE.get("disclaimer").char_budget
    assert over_budget_issues({"disclaimer": "x" * budget}, TEMPLATE) == []
    assert len(over_budget_issues({"disclaimer": "x" * (budget + 1)}, TEMPLATE)) == 1


def test_every_verbatim_slot_is_checked_and_no_copywriter_slot_is():
    texts = {s.id: "x" * (s.char_budget + 1) for s in TEMPLATE.slots if s.type == "text"}
    reported = {i.note.split(":")[0] for i in over_budget_issues(texts, TEMPLATE)}
    assert reported == set(VERBATIM_SLOTS)


def test_the_real_layout_keeps_its_findings_and_adds_the_budget_warning_after_them():
    rules = load_layout_rules(ROOT / "templates" / "classic-8pp" / "layout_rules.json")
    data = load_sample_data()
    state = STATE.model_copy(update={"project_facts": many_amenities(), "image_tags": data.image_tags,
                                     "slot_copy": copy_for(many_amenities())})
    warnings = real_layout_step(state, FakeLLM({}), data.template, rules).qa_warnings
    assert [w.check for w in warnings][-1] == "verbatim.over_budget"
    assert any(w.check == "layout.slot_unfilled" for w in warnings)


def test_a_verbatim_text_over_budget_does_not_loop_and_reaches_the_reviewer():
    form = sample_state(briefed=False).brief.form.model_copy(update={"amenities": THIRTY_AMENITIES})
    state = sample_state(briefed=False)
    state = state.model_copy(update={"brief": state.brief.model_copy(update={"form": form})})
    run = Run(stub_agents())
    run.start(state)
    assert run.paused_at == ("human_review",) and run.state.qa_round == 1
    assert [w.check for w in run.state.spec.qa_warnings] == ["verbatim.over_budget"]
