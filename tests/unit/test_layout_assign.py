"""Image assignment in code: eligibility, scoring, picking order, findings. Synthetic slots and tags, no files."""
from brochure.contracts.images import ImageTag
from brochure.dpi import DpiStatus
from brochure.layout import SlotRule, eligible, fit, score
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
