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

from brochure.contracts.manifest import ImageManifest
from brochure.doctor import find_ghostscript
from brochure.layout import load_layout_rules
from brochure.llm import FakeLLM
from brochure.pipeline.real import real_layout_step
from brochure.pipeline.stubs import load_sample_data, stub_agents
from brochure.render.geometry import page_geometry_pt
from brochure.render.pdf import ISSUES_FILE, render_brochure
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


def test_eight_page_pngs_of_the_whole_media_box_are_written_in_order(sample):
    pngs = sample[4]
    media = page_geometry_pt().media
    assert [p.name for p in pngs] == [f"page-{n}.png" for n in range(1, 9)]
    for png in pngs:
        assert Image.open(png).size == (round(media.width * PX_PER_PT), round(media.height * PX_PER_PT))


def test_the_hero_reaches_the_bleed_edge_on_the_cover(sample, images):
    raster = Raster(Image.open(sample[4][0]).convert("RGB"), page_geometry_pt().media)
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
