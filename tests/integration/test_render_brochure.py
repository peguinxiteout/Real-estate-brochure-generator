"""The sample brochure rendered for real (WeasyPrint, Ghostscript) and read back: pages, boxes, fonts, text, pixels."""
import importlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image
from pypdf import PdfReader

from brochure.agents.copywriter import owned_slots
from brochure.contracts.manifest import ImageManifest
from brochure.doctor import find_ghostscript
from brochure.layout import load_layout_rules
from brochure.llm import FakeLLM
from brochure.pipeline.real import real_layout_step
from brochure.pipeline.stubs import load_sample_data, stub_agents
from brochure.render.geometry import page_geometry_pt
from brochure.render.html import PX_PER_MM, build_html, load_template, text_heights
from brochure.render.pdf import ISSUES_FILE, render_brochure, render_with_issues
from brochure.render.positions import block_gaps, caption_rect, gap_problems
from tests.integration.test_blank_pdf import PX_PER_PT, Raster, as_box, assert_box, white
from tests.support import sample_state
from tools.make_sample_images import generate_images

pytestmark = pytest.mark.integration

ROOT = Path(__file__).parents[2]
RENDER_PAGES = [1, 2, 4]  # hero_tower, overview_aerial, amenity_pool and amenity_clubhouse are renders


@pytest.fixture(scope="module")
def tools_present():
    try:
        importlib.import_module("weasyprint")
    except Exception as exc:  # ModuleNotFoundError, or OSError when the Pango libraries are missing
        pytest.skip(f"WeasyPrint is not importable ({type(exc).__name__}). Run `brochure doctor` for the fix.")
    if find_ghostscript().path is None:
        pytest.skip("Ghostscript not found (looked at GS_BIN, PATH, C:\\Program Files\\gs). Run `brochure doctor` for the fix.")


@pytest.fixture(scope="module")
def images(tmp_path_factory):
    folder = tmp_path_factory.mktemp("images")
    manifest = ImageManifest.model_validate(json.loads((ROOT / "sample" / "images.json").read_text(encoding="utf-8")))
    generate_images(manifest, folder)
    return folder


@pytest.fixture(scope="module")
def sample(tools_present, images, tmp_path_factory):
    """The sample spec (stub copy, real layout) rendered once: (state, spec, out_dir, pdf_path, pngs)."""
    data = load_sample_data()
    state = sample_state().model_copy(update={"image_tags": data.image_tags, "image_dir": str(images)})
    state = state.model_copy(update={"slot_copy": stub_agents(data).copywriter(state, FakeLLM({}))})
    rules = load_layout_rules(ROOT / "templates" / "classic-8pp" / "layout_rules.json")
    spec = real_layout_step(state, FakeLLM({}), data.template, rules)
    out = tmp_path_factory.mktemp("render")
    pdf, pngs = render_brochure(spec, state.brand_kit, data.image_tags, images, out, brand_dir=ROOT / "sample")
    return state, spec, out, pdf, pngs


def squash(s: str) -> str:
    return " ".join(s.split())


@pytest.fixture(scope="module")
def page_text(sample):
    return [squash(p.extract_text()) for p in PdfReader(sample[3]).pages]


def test_the_pdf_has_8_pages(sample):
    assert len(PdfReader(sample[3]).pages) == 8


def test_every_page_has_the_boxes_of_the_print_geometry(sample):
    g = page_geometry_pt()
    for n, page in enumerate(PdfReader(sample[3]).pages, start=1):
        assert_box(as_box(page.mediabox), g.media, "MediaBox", n)
        assert_box(as_box(page.bleedbox), g.bleed, "BleedBox", n)
        assert_box(as_box(page.trimbox), g.trim, "TrimBox", n)


def embedded_fonts(pdf_path) -> set[str]:
    found = set()

    def walk(resources):
        for font in (resources.get("/Font") or {}).values():
            found.add(str(font.get_object()["/BaseFont"]))
        for xobject in (resources.get("/XObject") or {}).values():
            xobject = xobject.get_object()
            if "/Resources" in xobject:
                walk(xobject["/Resources"])

    for page in PdfReader(pdf_path).pages:
        walk(page["/Resources"])
    return found


def test_only_inter_and_open_sans_are_embedded(sample):
    fonts = embedded_fonts(sample[3])
    families = {re.sub(r"^/[A-Z]{6}\+", "", f).split("-")[0] for f in fonts}
    assert families == {"Inter", "Open"}, fonts  # Open-Sans
    assert not [f for f in fonts if "DejaVu" in f]


def test_the_rera_number_is_on_the_cover_and_the_back(page_text, sample):
    rera = sample[0].project_facts.rera_number
    assert rera in page_text[0] and rera in page_text[7]


def test_the_project_name_is_on_the_cover_and_the_disclaimer_on_the_back(page_text, sample):
    assert sample[0].project_facts.name in page_text[0]
    assert squash(sample[0].brand_kit.disclaimer) in page_text[7]


def test_artists_impression_is_on_every_page_with_a_render_and_no_other(page_text):
    assert [n for n, text in enumerate(page_text, start=1) if "Artist's impression" in text] == RENDER_PAGES


def test_unfilled_slots_show_image_needed(page_text):
    assert [n for n, text in enumerate(page_text, start=1) if "Image needed" in text] == [4, 5, 7]


def test_the_sample_text_fits_its_slots(sample):
    assert json.loads((sample[2] / ISSUES_FILE).read_text(encoding="utf-8")) == []


def crop_mark_black(rgb) -> bool:
    return max(rgb) < 40  # the brand navy (31, 58, 95) is dark but not this dark


def test_eight_page_pngs_of_the_trim_box_are_written_in_order(sample):
    pngs = sample[4]
    trim = page_geometry_pt().trim
    expected = (trim.width * PX_PER_PT, trim.height * PX_PER_PT)  # 826.8 x 1169.3 at 100 DPI
    assert [p.name for p in pngs] == [f"page-{n}.png" for n in range(1, 9)]
    for png in pngs:
        size = Image.open(png).size
        assert abs(size[0] - expected[0]) <= 1 and abs(size[1] - expected[1]) <= 1, (png.name, size)


def test_the_page_pngs_have_no_crop_marks_in_their_corners(sample):
    for png in sample[4]:
        image = Image.open(png).convert("RGB")
        w, h = image.size
        for c, r in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1), (2, 2), (w - 3, h - 3)):
            assert not crop_mark_black(image.getpixel((c, r))), (png.name, (c, r), image.getpixel((c, r)))


@pytest.fixture(scope="module")
def cover_media_png(sample, tmp_path_factory):
    """Page 1 over the whole MediaBox (the page PNGs stop at the trim), rendered here with Ghostscript."""
    png = tmp_path_factory.mktemp("cover") / "cover.png"
    result = subprocess.run(
        [str(find_ghostscript().path), "-dSAFER", "-dBATCH", "-dNOPAUSE", "-dQUIET", "-sDEVICE=png16m", "-r100",
         "-dFirstPage=1", "-dLastPage=1", f"-sOutputFile={png}", str(sample[3])],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return png


def test_the_hero_reaches_the_bleed_edge_on_the_cover(cover_media_png, images):
    raster = Raster(Image.open(cover_media_png).convert("RGB"), page_geometry_pt().media)
    b = page_geometry_pt().bleed
    hero = Image.open(images / "hero_tower.jpg").convert("RGB")
    inside, outside = 1.5 / PX_PER_PT, 3 / PX_PER_PT
    # The hero is the same shape as the bleed box, so its pixels map almost one to one: compare the top edge and the
    # upper left and right edges (the bottom is under the cover band) with the image there.
    for name, (x, y), (fx, fy) in [
        ("top", (b.left + b.width / 2, b.top - inside), (0.5, 0.0)),
        ("left", (b.left + inside, b.top - b.height * 0.3), (0.0, 0.3)),
        ("right", (b.right - inside, b.top - b.height * 0.3), (1.0, 0.3)),
    ]:
        expected = hero.getpixel((min(int(fx * hero.width), hero.width - 1), min(int(fy * hero.height), hero.height - 1)))
        got = raster.at(x, y)
        assert all(abs(a - e) <= 30 for a, e in zip(got, expected)), (name, got, expected)
        assert not white(got), name
    assert white(raster.at(b.left + b.width / 2, b.top + outside))  # and stops there: white beyond the bleed
    assert white(raster.at(b.left - outside, b.top - b.height * 0.3))


def test_render_sample_script_writes_the_pdf_and_pngs_and_prints_them_with_the_warnings(tools_present, images, tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "render_sample.py"), "--out", str(tmp_path),
                             "--images", str(images)], capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    out = tmp_path / "sample"
    assert (out / "brochure.pdf").is_file() and len(PdfReader(out / "brochure.pdf").pages) == 8
    assert str(out / "brochure.pdf") in result.stdout
    for n in range(1, 9):
        assert (out / f"page-{n}.png").is_file() and str(out / f"page-{n}.png") in result.stdout
    assert "layout.slot_unfilled" in result.stdout


def test_render_with_issues_returns_the_issues_it_writes_to_the_issues_file(sample, images, tmp_path):
    state, spec = sample[0], sample[1]
    pdf, pngs, issues = render_with_issues(spec, state.brand_kit, state.image_tags, images, tmp_path, brand_dir=ROOT / "sample")
    assert pdf == tmp_path / "brochure.pdf" and len(pngs) == 8
    assert [i.model_dump() for i in issues] == json.loads((tmp_path / ISSUES_FILE).read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("page, title", [(3, "Location"), (4, "Amenities"), (5, "Floor plans"), (6, "Specifications")])
def test_each_section_page_has_its_title(page_text, page, title):
    assert title in page_text[page - 1]


def test_the_qr_label_is_on_the_back_cover(page_text):
    assert "Scan for RERA registration details" in page_text[7]


@pytest.fixture(scope="module")
def laid_out(sample, images):
    """The sample laid out by WeasyPrint: (template, anchors of each page, measured text height of each text slot)."""
    from weasyprint import HTML

    state, spec = sample[0], sample[1]
    template = load_template(spec.template_id)
    html = build_html(spec, state.brand_kit, state.image_tags, images, brand_dir=ROOT / "sample")
    anchors = [p.anchors for p in HTML(string=html, base_url=str(template.directory)).render().pages]
    return template, anchors, text_heights(anchors, spec, template.slots)


def test_no_copywriter_slot_of_the_sample_is_under_60_percent_full(laid_out):
    # Verbatim slots are not checked: their heights fit their full budgets (test_full_budget_fit.py), not the sample.
    template, _, heights = laid_out
    owned = {s.id for s in owned_slots(template.slots)}
    assert owned <= set(heights)
    fill = {sid: heights[sid] / template.slots.get(sid).height_mm for sid in owned}
    assert {sid: round(f, 2) for sid, f in fill.items() if f < 0.6} == {}


def test_no_measured_gap_on_the_sample_is_over_the_limit_but_the_one_above_the_disclaimer(laid_out):
    template, _, heights = laid_out
    assert gap_problems(template.positions, template.slots, text_heights=heights) == []
    assert any(g.below == "disclaimer" and g.gap_mm > 15 for g in block_gaps(template.positions, template.slots, heights))


def test_the_static_text_fits_its_boxes(laid_out):
    template, anchors, _ = laid_out
    assert template.positions.static_text
    for item in template.positions.static_text:
        page = anchors[item.page - 1]
        height = (page[f"end-static-{item.id}"][1] - page[f"start-static-{item.id}"][1]) / PX_PER_MM
        assert 0 < height <= item.height_mm, (item.id, height)


def test_the_cover_caption_is_visible_above_the_band(sample):
    template = load_template("classic-8pp")
    box = caption_rect(template.slots.get("hero"), template.positions.of("hero"))
    assert box.w > 0
    image = Image.open(sample[4][0]).convert("RGB")
    px = 100 / 25.4
    # just inside the top-left corner of the caption's box: its light background, not the image under it or the band
    r, g, b = image.getpixel((round((box.left + 0.6) * px), round((box.top + 0.4) * px)))
    assert min(r, g, b) > 190, (r, g, b)
