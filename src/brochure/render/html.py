"""The brochure HTML from a BrochureSpec, with no WeasyPrint: templates/<id>/brochure.html.j2 and brochure.css, the
slot boxes from slots.json (sizes) and positions.json (places), the print geometry's page rule and crop marks.

Also the text overflow check, which reads the start and end marks of each text slot from the laid-out pages
(WeasyPrint's public Page.anchors) and so needs no WeasyPrint itself.
"""
import math
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from brochure.contracts.brand import BrandKit
from brochure.contracts.images import FocalPoint, ImageTag
from brochure.contracts.qa import QAIssue
from brochure.contracts.spec import BrochureSpec
from brochure.fonts import faces_for
from brochure.layout import LOGO_SLOTS
from brochure.print_config import PRINT, PrintConfig
from brochure.render.geometry import page_geometry_pt
from brochure.render.pdf import crop_marks_svg, media_svg_css, page_css
from brochure.render.positions import (
    PositionsFile, Rect, caption_rect, drawn_rect, load_positions, position_problems, static_rect,
)
from brochure.render.qr import qr_svg
from brochure.slots import ResolvedSlot, SlotTemplate, load_slots
from brochure.verbatim import VERBATIM_SLOTS

TEMPLATES_DIR = Path(__file__).resolve().parents[3] / "templates"
PX_PER_MM = 96 / 25.4  # CSS px, the unit of Page.anchors
CAPTION = "Artist's impression"
TEXT_PREFIX = {"rera_number": "RERA No. "}  # template words printed before a slot's text
LABELLED_LISTS = {"specs_list"}  # list items "label: detail" get the label in bold


@dataclass(frozen=True)
class Template:
    directory: Path
    slots: SlotTemplate
    positions: PositionsFile


def load_template(template_id: str, templates_dir: Path = TEMPLATES_DIR, config: PrintConfig = PRINT) -> Template:
    """The template's slots and positions. ValueError when the positions break a rule (see positions.py)."""
    directory = Path(templates_dir) / template_id
    slots = load_slots(directory / "slots.json", config)
    positions = load_positions(directory / "positions.json")
    problems = position_problems(positions, slots, config)
    if problems:
        raise ValueError(f"{directory / 'positions.json'}: " + "; ".join(problems))
    return Template(directory, slots, positions)


def object_position(focal: FocalPoint, width_px: int, height_px: int, box_w_mm: float, box_h_mm: float) -> tuple[float, float]:
    """CSS object-position (percent, x and y) for object-fit: cover that puts the focal point in the middle of the box,
    or as near as the image's edges allow. 50% on an axis the image does not overflow."""
    scale = max(box_w_mm / width_px, box_h_mm / height_px)

    def axis(f: float, image: float, box: float) -> float:
        travel = box - image  # <= 0: how far the image can move
        if travel > -1e-9:
            return 50.0
        offset = min(0.0, max(travel, box / 2 - f * image))  # where the image's near edge goes
        return offset / travel * 100

    return axis(focal.x, width_px * scale, box_w_mm), axis(focal.y, height_px * scale, box_h_mm)


def _mm(v: float) -> str:
    return f"{round(v, 4):g}mm"


def _box_style(r: Rect) -> str:
    return f"left: {_mm(r.left)}; top: {_mm(r.top)}; width: {_mm(r.w)}; height: {_mm(r.h)};"


def _caption_style(box: Rect, drawn: Rect) -> str:
    """The caption's box, relative to the slot's drawn box."""
    return _box_style(Rect(box.x - drawn.x, box.y - drawn.y, box.w, box.h))


def _colours(brand: BrandKit) -> dict[str, str]:
    by_name = {c.name.casefold(): c.hex for c in brand.colors}
    primary = by_name.get("primary", brand.colors[0].hex if brand.colors else "#000000")
    accent = by_name.get("accent", brand.colors[1].hex if len(brand.colors) > 1 else primary)
    return {"primary": primary, "accent": accent}


def _font_faces(brand: BrandKit) -> list[dict]:
    faces = {f.path: f for family in (brand.fonts.heading, brand.fonts.body) for f in faces_for(family)}
    return [{"family": f.family, "weight": f.weight, "style": f.style, "uri": f.path.as_uri()} for f in faces.values()]


def _text_view(slot_id: str, text: str, role: str) -> dict:
    lines = text.splitlines()
    view = {"role": role, "prefix": TEXT_PREFIX.get(slot_id, ""), "lines": lines, "items": []}
    if role == "list":
        for line in (ln.strip() for ln in lines):
            if not line:
                continue
            label, sep, rest = line.partition(": ")
            if slot_id in LABELLED_LISTS and sep:
                view["items"].append({"label": label + ":", "text": rest})
            else:
                view["items"].append({"label": "", "text": line})
    return view


def _slot_view(slot: ResolvedSlot, template: Template, page_fills: dict, tags: dict[str, ImageTag],
               image_dir: Path, brand: BrandKit, brand_dir: Path, config: PrintConfig) -> dict:
    pos = template.positions.of(slot.id)
    rect = drawn_rect(slot, pos, config)
    view = {"id": slot.id, "style": _box_style(rect)}
    fill = page_fills.get(slot.id)
    if slot.id in LOGO_SLOTS:
        logo = Path(brand.logo_path)
        logo = logo if logo.is_absolute() else brand_dir / logo
        return {**view, "kind": "logo", "company": brand.company_name, "src": logo.resolve().as_uri() if logo.is_file() else ""}
    if slot.type == "image":
        if fill is None or fill.image_path is None:
            return {**view, "kind": "placeholder"}
        tag = tags.get(fill.image_path)
        x, y = object_position(tag.focal_point, tag.width_px, tag.height_px, rect.w, rect.h) if tag else (50.0, 50.0)
        return {
            **view, "kind": "image", "src": (image_dir / fill.image_path).resolve().as_uri(),
            "object_position": f"{x:.2f}% {y:.2f}%",
            "caption": CAPTION if tag is not None and tag.kind == "render" else "",
            "caption_style": _caption_style(caption_rect(slot, pos, config), rect),
        }
    if slot.type == "qr":
        data = fill.qr_data if fill is not None else None
        return {**view, "kind": "qr", "svg": qr_svg(data, slot.width_mm) if data else ""}
    text = fill.text if fill is not None and fill.text is not None else ""
    return {**view, "kind": "text", **_text_view(slot.id, text, pos.role)}


def build_html(spec: BrochureSpec, brand_kit: BrandKit, image_tags: list[ImageTag], image_dir: Path, *,
               brand_dir: Path | None = None, config: PrintConfig = PRINT, templates_dir: Path = TEMPLATES_DIR) -> str:
    """The whole brochure as one HTML string. Images and fonts are file URIs; nothing is fetched from the network.

    ValueError when a brand font is not bundled, or the template's positions break a rule.
    """
    template = load_template(spec.template_id, templates_dir, config)
    faces = _font_faces(brand_kit)
    image_dir = Path(image_dir)
    brand_dir = Path.cwd() if brand_dir is None else Path(brand_dir)
    tags = {t.path: t for t in image_tags}
    g = page_geometry_pt(config)
    pages = []
    for number, page in enumerate(spec.pages, start=1):
        slots = [s for s in template.slots.slots if s.page == number]
        views = [_slot_view(s, template, page.slots, tags, image_dir, brand_kit, brand_dir, config) for s in slots]
        views += [{"id": f"static-{t.id}", "style": _box_style(static_rect(t)), "kind": "text",
                   **_text_view(t.id, t.text, t.role)} for t in template.positions.static_text if t.page == number]
        decorations = [{"id": d.id, "style": _box_style(Rect(d.x_mm, d.y_mm, d.width_mm, d.height_mm))}
                       for d in template.positions.decorations if number in d.pages]
        pages.append({"number": number, "slots": views, "decorations": decorations})
    title = next((f.text for p in spec.pages for sid, f in p.slots.items() if sid == "cover_title" and f.text), "")
    env = Environment(loader=FileSystemLoader(template.directory), autoescape=True, undefined=StrictUndefined,
                      trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)
    return env.get_template("brochure.html.j2").render(
        title=title or brand_kit.company_name,
        page_css=page_css(g),
        font_faces=faces,
        colours=_colours(brand_kit),
        fonts={"heading": brand_kit.fonts.heading, "body": brand_kit.fonts.body},
        trim={"w": _mm(config.page_width_mm), "h": _mm(config.page_height_mm)},
        crop_marks_css=media_svg_css(g, "crop-marks"),
        crop_marks=crop_marks_svg(g),
        stylesheet=(template.directory / "brochure.css").read_text(encoding="utf-8"),
        pages=pages,
    )


def text_heights(page_anchors: list[dict], spec: BrochureSpec, slots: SlotTemplate) -> dict[str, float]:
    """slot id -> height in mm of the text of each filled text slot, from its start and end marks on the laid-out page.
    page_anchors[i] is Page.anchors of page i + 1. Text that ran off the page loses its end mark, along with the end of
    the text itself: its height is math.inf. A missing start mark is a fault in the template: RuntimeError."""
    heights = {}
    for number, (page, anchors) in enumerate(zip(spec.pages, page_anchors), start=1):
        for slot in slots.slots:
            fill = page.slots.get(slot.id)
            if slot.page != number or slot.type != "text" or fill is None or not fill.text:
                continue
            start, end = anchors.get(f"start-{slot.id}"), anchors.get(f"end-{slot.id}")
            if start is None:
                raise RuntimeError(f"the laid-out page {number} has no start mark for text slot {slot.id!r}")
            heights[slot.id] = (end[1] - start[1]) / PX_PER_MM if end is not None else math.inf
    return heights


def text_overflow_issues(page_anchors: list[dict], spec: BrochureSpec, slots: SlotTemplate,
                         config: PrintConfig = PRINT) -> list[QAIssue]:
    """A render.text_overflow issue for each filled text slot whose text runs below the slot's height (by more than
    config.text_overflow_tolerance_mm). Routed to the copywriter when it wrote the text; a verbatim slot goes to nobody,
    because the Copywriter cannot change it. A warning, or an error when the text ran off the page, because then part of
    it is not printed. page_anchors[i] is Page.anchors of page i + 1."""
    issues = []
    for slot_id, height in text_heights(page_anchors, spec, slots).items():
        slot = slots.get(slot_id)
        if height <= slot.height_mm + config.text_overflow_tolerance_mm:
            continue
        verbatim = slot_id in VERBATIM_SLOTS
        fix = "it is verbatim, so a person must change its source" if verbatim else "shorten it"
        what = ("the text runs off the page, so part of it is not printed" if math.isinf(height)
                else f"the text is {height:.0f} mm tall")
        issues.append(QAIssue(
            check="render.text_overflow", page=slot.page, severity="error" if math.isinf(height) else "warning",
            route_to="none" if verbatim else "copywriter",
            note=f"{slot.id}: {what} but the slot is {slot.height_mm:g} mm; {fix}",
        ))
    return issues
