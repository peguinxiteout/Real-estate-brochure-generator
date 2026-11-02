"""The brochure HTML, built from the sample spec with no WeasyPrint: which content lands in which slot element."""
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

from brochure.contracts.images import FocalPoint
from brochure.contracts.spec import SlotFill
from brochure.fonts import BUNDLED_FACES, FONTS_DIR
from brochure.layout import load_layout_rules
from brochure.llm import FakeLLM
from brochure.pipeline.real import real_layout_step
from brochure.pipeline.stubs import SAMPLE_RERA_URL, load_sample_data, stub_agents
from brochure.render.html import build_html, object_position
from brochure.render.positions import drawn_rect, load_positions
from brochure.render.qr import qr_svg
from tests.support import ROOT, sample_state

TEMPLATE_DIR = ROOT / "templates" / "classic-8pp"
IMAGE_DIR = ROOT / "sample" / "images"
BRAND_DIR = ROOT / "sample"
UNFILLED = {"plan_img_b", "amenity_img_c", "about_img"}  # the sample images for these fail the DPI rule

VOID = {"img", "br", "meta", "link", "hr", "input"}


class Node:
    def __init__(self, tag, attrs, parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []

    def text(self) -> str:
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)

    def iter(self):
        for c in self.children:
            if isinstance(c, Node):
                yield c
                yield from c.iter()

    def find_all(self, tag=None, cls=None):
        return [n for n in self.iter() if (tag is None or n.tag == tag)
                and (cls is None or cls in n.attrs.get("class", "").split())]


class Tree(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = self.current = Node("#root", {})
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.current.children.append(Node(tag, attrs, self.current))

    def handle_endtag(self, tag):
        node = self.current
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.current = node.parent

    def handle_data(self, data):
        self.current.children.append(data)

    def by_id(self, id_):
        found = [n for n in self.root.iter() if n.attrs.get("id") == id_]
        assert len(found) == 1, (id_, len(found))
        return found[0]


def squash(s: str) -> str:
    return " ".join(s.split())


@pytest.fixture(scope="module")
def data():
    return load_sample_data()


@pytest.fixture(scope="module")
def spec(data):
    state = sample_state().model_copy(update={"image_tags": data.image_tags})
    state = state.model_copy(update={"slot_copy": stub_agents(data).copywriter(state, FakeLLM({}))})
    rules = load_layout_rules(TEMPLATE_DIR / "layout_rules.json")
    return real_layout_step(state, FakeLLM({}), data.template, rules)


@pytest.fixture(scope="module")
def brand():
    return sample_state().brand_kit


@pytest.fixture(scope="module")
def html(spec, brand, data):
    return build_html(spec, brand, data.image_tags, IMAGE_DIR, brand_dir=BRAND_DIR)


@pytest.fixture(scope="module")
def tree(html):
    return Tree(html)


def fills(spec):
    return {sid: (n, fill) for n, page in enumerate(spec.pages, start=1) for sid, fill in page.slots.items()}


def path_of(uri: str) -> Path:
    parsed = urlparse(uri)
    assert parsed.scheme == "file", uri
    path = unquote(parsed.path)
    if re.match(r"^/[A-Za-z]:", path):  # file:///Y:/... on Windows
        path = path[1:]
    return Path(path)


def test_there_is_one_sheet_per_page_in_order(tree, spec):
    sheets = tree.root.find_all("section", cls="sheet")
    assert [s.attrs["id"] for s in sheets] == [f"page-{n}" for n in range(1, len(spec.pages) + 1)]


def test_each_slot_is_on_its_page_at_its_drawn_box_in_mm(tree, data):
    positions = load_positions(TEMPLATE_DIR / "positions.json")
    for slot in data.template.slots:
        node = tree.by_id(f"slot-{slot.id}")
        assert node.parent.attrs["id"] == f"page-{slot.page}", slot.id
        r = drawn_rect(slot, positions.of(slot.id))
        style = squash(node.attrs["style"])
        for prop, value in (("left", r.left), ("top", r.top), ("width", r.w), ("height", r.h)):
            assert f"{prop}: {value:g}mm" in style, (slot.id, prop, style)


def test_each_text_fill_is_in_its_slot_element(tree, spec, data):
    for sid, (_, fill) in fills(spec).items():
        if fill.text is None:
            continue
        got = squash(tree.by_id(f"slot-{sid}").text())
        for line in fill.text.splitlines():
            assert squash(line) in got, (sid, line)


def test_newlines_in_text_become_line_breaks(tree, spec):
    contact = fills(spec)["contact_block"][1].text
    node = tree.by_id("slot-contact_block")
    assert len(node.find_all("br")) == len(contact.splitlines()) - 1


def test_list_slots_render_one_list_item_per_line(tree, spec):
    for sid in ("overview_highlights", "amenities_list", "location_landmarks", "specs_list", "config_table"):
        lines = [line for line in fills(spec)[sid][1].text.splitlines() if line.strip()]
        items = tree.by_id(f"slot-{sid}").find_all("li")
        assert [squash(li.text()) for li in items] == [squash(line) for line in lines], sid


def test_text_is_escaped(spec, brand, data):
    pages = [p.model_copy(deep=True) for p in spec.pages]
    pages[1].slots["overview_intro"] = SlotFill(text="Tom & Jerry <b>bold</b>")
    html = build_html(spec.model_copy(update={"pages": pages}), brand, data.image_tags, IMAGE_DIR, brand_dir=BRAND_DIR)
    assert "Tom &amp; Jerry &lt;b&gt;bold&lt;/b&gt;" in html


def test_images_render_from_the_files_in_image_dir(tree, spec):
    for sid, (_, fill) in fills(spec).items():
        if fill.image_path is None or sid in ("cover_logo", "back_logo"):
            continue
        imgs = tree.by_id(f"slot-{sid}").find_all("img")
        assert len(imgs) == 1, sid
        assert path_of(imgs[0].attrs["src"]) == (IMAGE_DIR / fill.image_path).resolve(), sid


def test_object_position_puts_the_focal_point_in_the_middle_of_the_crop(tree, spec, data):
    tags = {t.path: t for t in data.image_tags}
    positions = load_positions(TEMPLATE_DIR / "positions.json")
    for sid, (_, fill) in fills(spec).items():
        if fill.image_path is None or sid in ("cover_logo", "back_logo"):
            continue
        tag, slot = tags[fill.image_path], data.template.get(sid)
        r = drawn_rect(slot, positions.of(sid))
        x, y = object_position(tag.focal_point, tag.width_px, tag.height_px, r.w, r.h)
        img = tree.by_id(f"slot-{sid}").find_all("img")[0]
        assert f"object-position: {x:.2f}% {y:.2f}%" in squash(img.attrs["style"]), sid
        assert "object-fit: cover" in squash(img.attrs["style"]), sid


def test_object_position_centres_the_crop_on_the_focal_point_and_stops_at_the_image_edge():
    centre = FocalPoint(x=0.5, y=0.5)
    assert object_position(centre, 2000, 1000, 100, 100) == (50.0, 50.0)
    # A 2:1 image in a square box shows half its width. With the focal point at x = 0.375 the crop runs from 0.125 to
    # 0.625 of the width, centred on it: the image moves 25 of the 100 units it can travel, so 25%.
    assert object_position(FocalPoint(x=0.375, y=0.5), 2000, 1000, 100, 100) == (pytest.approx(25.0), 50.0)
    assert object_position(FocalPoint(x=0.0, y=0.5), 2000, 1000, 100, 100)[0] == 0.0  # clamped at the left edge
    assert object_position(FocalPoint(x=1.0, y=0.5), 2000, 1000, 100, 100)[0] == 100.0  # and at the right edge
    assert object_position(FocalPoint(x=0.1, y=0.9), 1000, 1000, 50, 50) == (50.0, 50.0)  # nothing is cut off


def test_render_images_carry_an_artists_impression_caption_and_photos_plans_and_maps_do_not(tree, spec, data):
    kinds = {t.path: t.kind for t in data.image_tags}
    seen = set()
    for sid, (_, fill) in fills(spec).items():
        if fill.image_path is None or sid in ("cover_logo", "back_logo"):
            continue
        captions = tree.by_id(f"slot-{sid}").find_all(cls="caption")
        kind = kinds[fill.image_path]
        seen.add(kind)
        if kind == "render":
            assert [squash(c.text()) for c in captions] == ["Artist's impression"], sid
        else:
            assert captions == [], sid
    assert seen == {"render", "photo", "floor_plan", "map"}


def test_unfilled_image_slots_show_image_needed_and_no_image(tree, spec, data):
    image_slots = {s.id for s in data.template.slots if s.type == "image"} - {"cover_logo", "back_logo"}
    unfilled = image_slots - set(fills(spec))
    assert unfilled == UNFILLED
    for sid in unfilled:
        node = tree.by_id(f"slot-{sid}")
        assert "placeholder" in node.attrs["class"].split()
        assert "Image needed" in node.text()
        assert node.find_all("img") == []


def test_the_logo_slots_show_the_brand_kit_logo_file(tree):
    for sid in ("cover_logo", "back_logo"):
        imgs = tree.by_id(f"slot-{sid}").find_all("img")
        assert [path_of(i.attrs["src"]) for i in imgs] == [(BRAND_DIR / "logo.svg").resolve()]


def test_without_the_logo_file_the_logo_slots_show_the_company_name_in_the_heading_font(spec, brand, data, tmp_path):
    tree = Tree(build_html(spec, brand, data.image_tags, IMAGE_DIR, brand_dir=tmp_path))
    for sid in ("cover_logo", "back_logo"):
        node = tree.by_id(f"slot-{sid}")
        assert node.find_all("img") == []
        assert squash(node.text()) == "Kestrel Urbanscapes"
        assert node.find_all(cls="logo-text")


def test_the_qr_slot_holds_the_vector_qr_of_its_data_at_the_slot_size(tree, html, data):
    node = tree.by_id("slot-rera_qr")
    assert node.find_all("svg") and node.find_all("path")
    assert qr_svg(SAMPLE_RERA_URL, data.template.get("rera_qr").width_mm) in html


def test_font_faces_are_the_bundled_files_only(html):
    faces = re.findall(r"@font-face\s*{([^}]*)}", html)
    assert faces
    srcs = [path_of(u) for f in faces for u in re.findall(r'url\("([^"]+)"\)', f)]
    assert sorted(srcs) == sorted(f.path for f in BUNDLED_FACES)
    assert all(FONTS_DIR in s.parents for s in srcs)
    families = {re.search(r'font-family:\s*"([^"]+)"', f).group(1) for f in faces}
    assert families == {"Inter", "Open Sans"}
    assert "local(" not in html and "fonts.googleapis" not in html


def test_the_brand_kit_fonts_and_colours_are_used(html):
    style = squash(html)
    assert '--heading-font: "Inter"' in style and '--body-font: "Open Sans"' in style
    assert "--primary: #1F3A5F" in style and "--accent: #C8A24A" in style


def test_a_brand_font_that_is_not_bundled_is_refused(spec, brand, data):
    other = brand.model_copy(update={"fonts": brand.fonts.model_copy(update={"heading": "Playfair Display"})})
    with pytest.raises(ValueError, match="Playfair Display"):
        build_html(spec, other, data.image_tags, IMAGE_DIR, brand_dir=BRAND_DIR)


def test_the_page_rule_and_crop_marks_come_from_the_print_geometry(html, tree):
    from brochure.render.geometry import page_geometry_pt
    from brochure.render.pdf import crop_marks_svg, page_css

    g = page_geometry_pt()
    assert page_css(g) in html
    for sheet in tree.root.find_all("section", cls="sheet"):
        assert len(sheet.find_all("line")) == len(g.crop_marks)
    assert crop_marks_svg(g) in html


def test_the_stylesheet_never_clips(html):
    css = (TEMPLATE_DIR / "brochure.css").read_text(encoding="utf-8")
    assert "overflow" not in css and "overflow" not in html
    assert css.strip() and squash(css) in squash(html)  # the template's stylesheet is in the page


def test_every_text_slot_carries_start_and_end_marks_for_measuring(tree, data):
    for slot in data.template.slots:
        if slot.type == "text":
            node = tree.by_id(f"slot-{slot.id}")
            ids = [n.attrs.get("id") for n in node.iter() if n.attrs.get("id")]
            assert ids[0] == f"start-{slot.id}" and ids[-1] == f"end-{slot.id}", slot.id
