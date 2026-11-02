"""Image assignment in code: eligibility, scoring, picking order, findings. Synthetic slots and tags, no files."""
from brochure.contracts.images import ImageTag
from brochure.dpi import DpiStatus
from brochure.layout import LayoutRules, SlotRule, assign_images, eligible, fit, score
from brochure.slots import SlotTemplate
from brochure.slots import ResolvedSlot


def slot(slot_id="s", width_mm=88.0, height_mm=60.0, page=4) -> ResolvedSlot:
    """An image slot inside the trim (no bleed), so its print size is its size."""
    return ResolvedSlot(
        id=slot_id, type="image", page=page, width_mm=width_mm, height_mm=height_mm,
        bleed_width_mm=width_mm, bleed_height_mm=height_mm,
    )


def tag(path="a.jpg", kind="render", width_px=1100, height_px=750, quality="good", subject="", features=()) -> ImageTag:
    return ImageTag(path=path, kind=kind, subject=subject, width_px=width_px, height_px=height_px, quality=quality,
                    features=list(features), focal_point={"x": 0.5, "y": 0.5})


def rule(slot_id="s", kinds=("render", "photo"), keywords=(), priority=1) -> SlotRule:
    return SlotRule(slot=slot_id, kinds=list(kinds), keywords=list(keywords), priority=priority)


# 88 x 60 mm at 300 DPI is 1040 x 709 px; at 250 DPI, 867 x 591 px.
PASS_PX, WARN_PX, FAIL_PX = (1040, 709), (867, 591), (800, 545)


# --- eligibility -------------------------------------------------------------------------------------------------------

def test_the_fit_is_the_effective_dpi_for_the_slot_size_and_its_band():
    dpi, band = fit(tag(width_px=800, height_px=545), slot())
    assert round(dpi) == 231 and band == DpiStatus.FAIL
    assert fit(tag(width_px=1040, height_px=709), slot())[1] == DpiStatus.PASS


def test_the_fit_uses_the_slot_size_including_its_bleed():
    with_bleed = slot(width_mm=88.0).model_copy(update={"bleed_width_mm": 94.0})
    assert fit(tag(width_px=1040, height_px=2000), with_bleed)[0] < 300


def test_an_image_of_a_kind_the_slot_does_not_accept_is_not_eligible():
    assert not eligible(tag(kind="floor_plan", width_px=2000, height_px=1400), slot(), rule(kinds=["render", "photo"]))


def test_an_image_below_the_dpi_floor_for_the_slot_is_not_eligible():
    assert not eligible(tag(width_px=FAIL_PX[0], height_px=FAIL_PX[1]), slot(), rule())


def test_an_image_in_the_warn_band_is_eligible():
    assert eligible(tag(width_px=WARN_PX[0], height_px=WARN_PX[1]), slot(), rule())


def test_an_image_of_an_accepted_kind_that_passes_is_eligible():
    assert eligible(tag(kind="photo", width_px=PASS_PX[0], height_px=PASS_PX[1]), slot(), rule(kinds=["photo"]))


# --- scoring ----------------------------------------------------------------------------------------------------------

def test_an_image_whose_subject_or_features_match_a_preferred_keyword_scores_higher_than_one_that_does_not():
    r = rule(keywords=["Pool", "deck"])
    plain = tag(path="a.jpg", subject="Clubhouse lobby", features=["lounge"])
    by_subject = tag(path="b.jpg", subject="Infinity POOL at sunset")
    by_feature = tag(path="c.jpg", subject="Amenity view", features=["deck"])
    assert score(by_subject, slot(), r) > score(plain, slot(), r)
    assert score(by_feature, slot(), r) > score(plain, slot(), r)


def test_an_image_in_the_pass_band_scores_higher_than_one_in_the_warn_band():
    passing = tag(path="a.jpg", width_px=PASS_PX[0], height_px=PASS_PX[1])
    warning = tag(path="b.jpg", width_px=WARN_PX[0], height_px=WARN_PX[1])  # the same shape
    assert fit(passing, slot())[1] == DpiStatus.PASS and fit(warning, slot())[1] == DpiStatus.WARN
    assert score(passing, slot(), rule()) > score(warning, slot(), rule())


def test_an_image_closer_to_the_slots_shape_scores_higher_because_less_is_cropped():
    # the slot is 88 x 60 (1.47); both images pass at 300 DPI and have the same grade
    close = tag(path="a.jpg", width_px=1500, height_px=1000)   # 1.50
    wide = tag(path="b.jpg", width_px=2200, height_px=1000)    # 2.20
    tall = tag(path="c.jpg", width_px=1100, height_px=1500)    # 0.73
    assert score(close, slot(), rule()) > score(wide, slot(), rule())
    assert score(close, slot(), rule()) > score(tall, slot(), rule())


def test_a_better_quality_grade_scores_higher_good_then_fair_then_poor():
    good, fair, poor = (tag(path=f"{q}.jpg", quality=q) for q in ("good", "fair", "poor"))
    assert score(good, slot(), rule()) > score(fair, slot(), rule()) > score(poor, slot(), rule())


# --- picking ------------------------------------------------------------------------------------------------------------

def assign(slots_and_rules, tags):
    template = SlotTemplate(template_id="t", slots=[s for s, _ in slots_and_rules])
    rules = LayoutRules(template_id="t", rules=[r for _, r in slots_and_rules])
    return assign_images(template, rules, tags)


def placed(assignment) -> dict[str, str]:
    return {slot_id: p.image for slot_id, p in assignment.placements.items()}


def test_the_slot_with_the_first_priority_picks_first_and_gets_the_best_image():
    best = tag(path="best.jpg", subject="tower at dusk")
    other = tag(path="other.jpg", subject="garden")
    # "small" is listed first and also wants the tower, but "hero" has priority 1
    pairs = [(slot("small"), rule("small", keywords=["tower"], priority=2)),
             (slot("hero"), rule("hero", keywords=["tower"], priority=1))]
    assert placed(assign(pairs, [other, best])) == {"hero": "best.jpg", "small": "other.jpg"}
    assert list(assign(pairs, [other, best]).placements) == ["hero", "small"]  # in picking order


def test_each_image_is_used_at_most_once_and_a_slot_with_nothing_left_stays_unfilled():
    pairs = [(slot(f"s{n}"), rule(f"s{n}", priority=n)) for n in (1, 2, 3)]
    result = placed(assign(pairs, [tag(path="a.jpg"), tag(path="b.jpg")]))
    assert sorted(result.values()) == ["a.jpg", "b.jpg"]
    assert set(result) == {"s1", "s2"}


def test_a_slot_takes_only_an_eligible_image():
    pairs = [(slot("plan"), rule("plan", kinds=["floor_plan"], priority=1))]
    assert placed(assign(pairs, [tag(path="a.jpg", kind="render")])) == {}


def test_ties_go_to_the_path_that_sorts_first_whatever_the_input_order():
    twins = [tag(path="b.jpg"), tag(path="a.jpg"), tag(path="c.jpg")]
    pairs = [(slot("s1"), rule("s1", priority=1)), (slot("s2"), rule("s2", priority=2))]
    assert placed(assign(pairs, twins)) == {"s1": "a.jpg", "s2": "b.jpg"}


def test_the_same_input_gives_the_same_assignment_every_time_and_in_any_order():
    import random

    tags = [tag(path=f"{n}.jpg", width_px=1000 + 37 * n, height_px=700 + 11 * n, quality=q, subject=s)
            for n, (q, s) in enumerate([("good", "pool"), ("fair", "gym"), ("poor", "pool deck"), ("good", "lounge"),
                                        ("fair", "pool"), ("good", "garden")])]
    pairs = [(slot(f"s{n}", width_mm=60 + 10 * n), rule(f"s{n}", keywords=["pool", "gym"][: n % 3], priority=n))
             for n in (1, 2, 3, 4)]
    first = assign(pairs, tags)
    assert assign(pairs, tags) == first
    for seed in range(5):
        shuffled = tags[:]
        random.Random(seed).shuffle(shuffled)
        assert assign(pairs, shuffled) == first


# --- findings: every problem is a warning the reviewer sees ---------------------------------------------------------------

def findings(assignment, check):
    return [f for f in assignment.findings if f.check == check]


def one(assignment, check):
    found = findings(assignment, check)
    assert len(found) == 1, f"expected one {check} finding, got {[f.note for f in found]}"
    return found[0]


def test_an_unfilled_slot_is_an_error_on_its_page_naming_the_images_that_were_too_small_and_their_dpi():
    pairs = [(slot("plan_img_b", page=5), rule("plan_img_b", kinds=["floor_plan"], priority=1))]
    tags = [tag(path="plan.jpg", kind="floor_plan", width_px=720, height_px=491),   # 207 DPI in 88 x 60
            tag(path="tiny.jpg", kind="floor_plan", width_px=400, height_px=273),
            tag(path="pool.jpg", kind="render", width_px=2000, height_px=1364)]     # wrong kind: not mentioned
    issue = one(assign(pairs, tags), "layout.slot_unfilled")
    assert (issue.severity, issue.route_to, issue.page) == ("error", "none", 5)
    assert issue.note == ("plan_img_b: no image of kind floor_plan with enough resolution; "
                          "plan.jpg is 207 DPI, tiny.jpg is 115 DPI")


def test_an_unfilled_slot_with_no_image_of_its_kind_says_so():
    pairs = [(slot("location_map", page=3), rule("location_map", kinds=["map"], priority=1))]
    issue = one(assign(pairs, [tag(path="a.jpg")]), "layout.slot_unfilled")
    assert issue.note == "location_map: no image of kind map"


def test_an_unfilled_slot_whose_images_all_went_to_other_slots_says_so():
    pairs = [(slot("s1"), rule("s1", priority=1)), (slot("s2"), rule("s2", kinds=["photo", "render"], priority=2))]
    issue = one(assign(pairs, [tag(path="a.jpg")]), "layout.slot_unfilled")
    assert issue.note == "s2: every image of kind photo or render that fits is used in another slot"


def test_a_filled_slot_gives_no_unfilled_warning():
    pairs = [(slot("s1"), rule("s1", priority=1))]
    assert findings(assign(pairs, [tag(path="a.jpg")]), "layout.slot_unfilled") == []


def test_an_image_placed_in_the_warn_band_is_a_warning_with_its_effective_dpi():
    pairs = [(slot("amenity_img_b", page=4), rule("amenity_img_b", priority=1))]
    result = assign(pairs, [tag(path="club.jpg", width_px=1000, height_px=682)])  # 288.6 DPI in 88 x 60
    assert placed(result) == {"amenity_img_b": "club.jpg"}
    issue = one(result, "layout.dpi_warn")
    assert (issue.severity, issue.route_to, issue.page) == ("warning", "none", 4)
    assert issue.note == "amenity_img_b: club.jpg is 288 DPI, below the 300 DPI target (it prints, softer)"


def test_an_image_placed_in_the_pass_band_gives_no_dpi_warning():
    pairs = [(slot("s1"), rule("s1", priority=1))]
    assert findings(assign(pairs, [tag(path="a.jpg", width_px=PASS_PX[0], height_px=PASS_PX[1])]), "layout.dpi_warn") == []


def test_an_image_too_small_for_every_slot_that_accepts_its_kind_is_an_unused_warning_with_its_best_dpi():
    pairs = [(slot("big", width_mm=180, height_mm=90), rule("big", priority=1)),
             (slot("small", page=7), rule("small", priority=2))]
    tags = [tag(path="ok_big.jpg", width_px=2200, height_px=1100), tag(path="ok_small.jpg"),
            tag(path="gym.jpg", kind="photo", width_px=800, height_px=545)]   # 230.7 DPI in "small", less in "big"
    issue = one(assign(pairs, tags), "layout.image_unused")
    assert (issue.severity, issue.route_to, issue.page) == ("warning", "none", None)
    assert issue.note == "gym.jpg is not used: too small for every slot that accepts a photo (at most 230 DPI, in small; 250 needed)"


def test_an_image_no_slot_accepts_is_an_unused_warning_saying_so():
    pairs = [(slot("s1"), rule("s1", kinds=["render"], priority=1))]
    issue = one(assign(pairs, [tag(path="a.jpg"), tag(path="plan.jpg", kind="floor_plan")]), "layout.image_unused")
    assert issue.note == "plan.jpg is not used: no slot accepts a floor_plan"


def test_an_image_that_fits_but_lost_to_better_ones_is_an_unused_warning_saying_so():
    pairs = [(slot("s1"), rule("s1", keywords=["pool"], priority=1))]
    issue = one(assign(pairs, [tag(path="pool.jpg", subject="pool"), tag(path="spare.jpg")]), "layout.image_unused")
    assert issue.note == "spare.jpg is not used: every slot it fits took a better image"


def test_unused_warnings_come_after_the_slot_warnings_in_path_order():
    pairs = [(slot("s1"), rule("s1", kinds=["map"], priority=1))]
    result = assign(pairs, [tag(path="b.jpg"), tag(path="a.jpg")])
    assert [f.check for f in result.findings] == ["layout.slot_unfilled", "layout.image_unused", "layout.image_unused"]
    assert [f.note.split()[0] for f in result.findings[1:]] == ["a.jpg", "b.jpg"]
