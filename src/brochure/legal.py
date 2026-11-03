"""Legal content that must be in the print file. A template lists its legal slots in legal_slots.json; blocking_issues
says what about them stops a brochure from being approved."""
import json
from pathlib import Path

from brochure.contracts.qa import QAIssue
from brochure.contracts.spec import BrochureSpec, SlotFill
from brochure.slots import SlotTemplate, load_slots

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"
OVERFLOW_CHECK = "render.text_overflow"
EMPTY_CHECK = "legal.slot_empty"


def copy_needed(slot_id: str) -> str:
    """The visible text the layout puts in a text slot that has no copy."""
    return f"[copy needed: {slot_id}]"


def is_lost_text(issue: QAIssue) -> bool:
    """The render's report that a slot's text ran off the page, so that part of it is not printed."""
    return issue.check == OVERFLOW_CHECK and issue.severity == "error"


def load_legal_slots(template_id: str, templates_dir: Path = TEMPLATES_DIR) -> list[str]:
    """The template's legal slot ids. FileNotFoundError without a list: a template must say what is legal, or nothing
    would ever block. ValueError when the list names a slot the template does not have."""
    folder = Path(templates_dir) / template_id
    legal = json.loads((folder / "legal_slots.json").read_text(encoding="utf-8"))["legal_slots"]
    known = {s.id for s in load_slots(folder / "slots.json").slots}
    unknown = [slot_id for slot_id in legal if slot_id not in known]
    if unknown:
        raise ValueError(f"{folder / 'legal_slots.json'} names slots the template does not have: {', '.join(unknown)}")
    return legal


def _is_empty(slot_id: str, slot_type: str, fill: SlotFill | None) -> bool:
    if fill is None:
        return True
    value = fill.qr_data if slot_type == "qr" else fill.text
    return value is None or not value.strip() or value == copy_needed(slot_id)


def blocking_issues(spec: BrochureSpec, template: SlotTemplate, legal_slots: list[str]) -> list[QAIssue]:
    """What stops this brochure from being approved, in the order of legal_slots: legal text that ran off the page
    (found in spec.qa_warnings) and legal slots left empty. Each means legal content is missing from the print file.
    A legal text that is merely taller than its slot or over its budget is still printed, so it does not block."""
    fills = {slot_id: fill for page in spec.pages for slot_id, fill in page.slots.items()}
    blocking = []
    for slot_id in legal_slots:
        slot = template.get(slot_id)
        if _is_empty(slot_id, slot.type, fills.get(slot_id)):
            what = "no QR data" if slot.type == "qr" else "no text"
            blocking.append(QAIssue(check=EMPTY_CHECK, page=slot.page, severity="error", route_to="none",
                                    note=f"{slot_id}: {what}, so it is missing from the print file"))
        # The issue has no slot field: its note starts with the slot id (a test holds this against text_overflow_issues).
        blocking += [i for i in spec.qa_warnings if is_lost_text(i) and i.note.startswith(f"{slot_id}: ")]
    return blocking


def blocking_for(spec: BrochureSpec, templates_dir: Path = TEMPLATES_DIR) -> list[QAIssue]:
    """blocking_issues for a spec, with its template's slots and legal list."""
    legal = load_legal_slots(spec.template_id, templates_dir)
    return blocking_issues(spec, load_slots(Path(templates_dir) / spec.template_id / "slots.json"), legal)
