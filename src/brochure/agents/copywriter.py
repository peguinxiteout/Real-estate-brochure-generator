"""The Copywriter agent: writes the free-text slots from the project facts. Facts are strict, wording is free."""
import logging
from dataclasses import dataclass, field
from pathlib import Path

from brochure.contracts.images import ImageTag
from brochure.contracts.project import ProjectFacts
from brochure.contracts.qa import QAIssue
from brochure.llm import LLMClient, TaskSpec
from brochure.slots import ResolvedSlot, SlotTemplate, load_slots
from brochure.verbatim import VERBATIM_SLOTS

logger = logging.getLogger(__name__)

TASK = "copy.write"
PROMPT_FILE = Path(__file__).parent / "prompts" / "copy_write.md"
TEMPLATE_FILE = Path(__file__).resolve().parents[3] / "templates" / "classic-8pp" / "slots.json"


@dataclass(frozen=True)
class CopyInputs:
    """Everything the Copywriter sees. `slots` are the slots to write, never the verbatim ones."""

    facts: ProjectFacts
    company_name: str
    image_tags: list[ImageTag]
    slots: list[ResolvedSlot]
    qa_issues: list[QAIssue] = field(default_factory=list)  # only the issues routed to the copywriter


def owned_slots(template: SlotTemplate) -> list[ResolvedSlot]:
    """The text slots the Copywriter writes: every text slot that code does not fill verbatim."""
    return [s for s in template.slots if s.type == "text" and s.id not in VERBATIM_SLOTS]


def copy_task_spec(slots: list[ResolvedSlot]) -> TaskSpec:
    """The system prompt and a strict JSON Schema with one required string property per slot."""
    schema = {
        "type": "object",
        "properties": {slot.id: {"type": "string"} for slot in slots},
        "required": [slot.id for slot in slots],
        "additionalProperties": False,
    }
    return TaskSpec(system=PROMPT_FILE.read_text(encoding="utf-8").strip(), schema=schema)


TASK_SPEC = copy_task_spec(owned_slots(load_slots(TEMPLATE_FILE)))


def _payload(inputs: CopyInputs, slots: list[ResolvedSlot]) -> dict:
    """What the model is sent: the facts, what the images show, the tone and the slots to write. No paths, no geometry."""
    payload = {
        "project": inputs.facts.model_dump(exclude={"tone_notes"}),
        "company_name": inputs.company_name,
        "images": [{"subject": tag.subject, "features": tag.features} for tag in inputs.image_tags],
        "tone_notes": inputs.facts.tone_notes,
        "slots": [{"id": s.id, "page": s.page, "char_budget": s.char_budget, "comment": s.comment} for s in slots],
    }
    return payload


def copywriter_agent(inputs: CopyInputs, llm: LLMClient) -> dict[str, str]:
    """slot id -> text for the slots whose copy passed every check; a slot that could not be written is left out."""
    reply = llm.complete(TASK, _payload(inputs, inputs.slots))
    return {slot.id: reply[slot.id].strip() for slot in inputs.slots}
