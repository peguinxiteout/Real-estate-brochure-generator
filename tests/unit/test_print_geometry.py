import pytest

from brochure.print_config import PRINT
from brochure.render.geometry import Box, mm_to_pt, page_geometry_mm, page_geometry_pt

TOL_PT = 0.01


def test_mm_to_pt_uses_72_points_per_25_4_mm():
    assert mm_to_pt(25.4) == pytest.approx(72, abs=TOL_PT)
    assert mm_to_pt(1) == pytest.approx(2.8346, abs=TOL_PT)
    assert mm_to_pt(210) == pytest.approx(595.2756, abs=TOL_PT)


def test_trim_box_is_the_a4_page_with_its_origin_at_the_lower_left():
    assert page_geometry_mm().trim == Box(0, 0, PRINT.page_width_mm, PRINT.page_height_mm)
    assert (PRINT.page_width_mm, PRINT.page_height_mm) == (210, 297)


def test_bleed_box_is_exactly_3_mm_outside_the_trim_on_every_edge():
    g = page_geometry_mm()
    assert PRINT.bleed_mm == 3
    assert g.trim.left - g.bleed.left == 3
    assert g.trim.bottom - g.bleed.bottom == 3
    assert g.bleed.right - g.trim.right == 3
    assert g.bleed.top - g.trim.top == 3


def test_media_box_is_trim_plus_bleed_plus_slug_on_every_edge_236_by_323_mm():
    media = page_geometry_mm().media
    assert (media.width, media.height) == (236, 323)


def test_trim_is_centred_in_the_media_box():
    g = page_geometry_mm()
    margins = {g.trim.left - g.media.left, g.trim.bottom - g.media.bottom,
               g.media.right - g.trim.right, g.media.top - g.trim.top}
    assert margins == {PRINT.bleed_mm + PRINT.slug_beyond_bleed_mm}


def test_boxes_are_nested_trim_inside_bleed_inside_media():
    g = page_geometry_mm()
    assert g.media.contains(g.bleed)
    assert g.bleed.contains(g.trim)
    assert not g.trim.contains(g.bleed)
    assert not g.bleed.contains(g.media)


def boxes_approx(actual: Box, expected: tuple[float, float, float, float]) -> bool:
    return all(abs(a - e) <= TOL_PT for a, e in zip((actual.left, actual.bottom, actual.right, actual.top), expected))


def test_boxes_in_points():
    g = page_geometry_pt()
    assert boxes_approx(g.trim, (0, 0, 595.2756, 841.8898))
    assert boxes_approx(g.bleed, (-8.5039, -8.5039, 603.7795, 850.3937))
    assert boxes_approx(g.media, (-36.8504, -36.8504, 632.1260, 878.7402))


def horizontal(m) -> bool:
    return m.y0 == m.y1 and m.x0 != m.x1


def vertical(m) -> bool:
    return m.x0 == m.x1 and m.y0 != m.y1


def test_two_crop_marks_per_corner_one_horizontal_one_vertical_on_the_trim_lines():
    g = page_geometry_mm()
    t = g.trim
    assert len(g.crop_marks) == 8
    for cx, cy in [(t.left, t.bottom), (t.right, t.bottom), (t.left, t.top), (t.right, t.top)]:
        h = [m for m in g.crop_marks if horizontal(m) and m.y0 == cy and (m.x0 - cx) * (m.x1 - cx) >= 0 and abs(m.x0 - cx) < t.width / 2]
        v = [m for m in g.crop_marks if vertical(m) and m.x0 == cx and (m.y0 - cy) * (m.y1 - cy) >= 0 and abs(m.y0 - cy) < t.height / 2]
        assert len(h) == 1 and len(v) == 1, (cx, cy)
        # each mark points away from the page: its far end is further from the trim than its near end
        assert abs(h[0].x1 - cx) > abs(h[0].x0 - cx)
        assert abs(v[0].y1 - cy) > abs(v[0].y0 - cy)


def distance_outside_trim(trim: Box, x: float, y: float) -> float:
    """How far a point on a trim line extension lies outside the trim edge it extends."""
    return max(trim.left - x, x - trim.right, trim.bottom - y, y - trim.top)


def test_each_crop_mark_starts_5_mm_from_the_trim_edge_and_is_5_mm_long():
    g = page_geometry_mm()
    for m in g.crop_marks:
        assert distance_outside_trim(g.trim, m.x0, m.y0) == pytest.approx(5), m
        assert distance_outside_trim(g.trim, m.x1, m.y1) == pytest.approx(10), m
        assert m.length == pytest.approx(5), m
