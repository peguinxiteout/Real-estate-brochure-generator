"""The Copywriter agent: writes the free-text slots from the project facts. Facts are strict, wording is free."""
import logging
from dataclasses import dataclass, field
from pathlib import Path

from brochure.agents.copy_checks import Known, known_from, problems
from brochure.contracts.images import ImageTag
from brochure.contracts.project import ProjectFacts
from brochure.contracts.qa import QAIssue
from brochure.llm import LLMClient, LLMError, TaskSpec
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
    if inputs.qa_issues:  # only when the QA loop sent the run back
        payload["qa_issues"] = [{"page": i.page, "check": i.check, "note": i.note} for i in inputs.qa_issues]
    return payload


def _judge(reply: dict, slots: list[ResolvedSlot], known: Known) -> tuple[dict[str, str], dict[str, list[str]]]:
    """Split a reply into the slots whose text passed every check (id -> text) and those that did not (id -> reasons)."""
    passed, failed = {}, {}
    for slot in slots:
        value = reply.get(slot.id)
        if not isinstance(value, str):
            failed[slot.id] = ["the reply has no text for this slot"]
            continue
        text = value.strip()
        if reasons := problems(text, slot.char_budget, known):
            failed[slot.id] = reasons
        else:
            passed[slot.id] = text
    return passed, failed


def copywriter_agent(inputs: CopyInputs, llm: LLMClient) -> dict[str, str]:
    """slot id -> text for the slots whose copy passed every check; a slot that could not be written is left out.

    A failing slot is asked for again once, alone, with the reasons; the slots that passed keep their first text.
    """
    known = known_from(inputs.facts, inputs.company_name)
    written: dict[str, str] = {}
    pending, failed, error = list(inputs.slots), {}, None
    for attempt in (1, 2):
        payload = _payload(inputs, pending)
        if failed:
            payload["problems"] = {slot_id: "; ".join(reasons) for slot_id, reasons in failed.items()}
        try:
            reply = llm.complete(TASK, payload)
        except LLMError as exc:  # the client has already retried what it can: do not ask again
            error = exc
            break
        passed, failed = _judge(reply, pending, known)
        written.update(passed)
        pending = [slot for slot in pending if slot.id in failed]
        if not pending:
            break
        logger.info("asking again for %s: %s", ", ".join(failed), failed)
    if pending:
        details = "; ".join(f"{slot.id} ({'; '.join(failed.get(slot.id, ['no reply']))})" for slot in pending)
        cause = f"; the model could not be used: {error}" if error else ""
        logger.warning("the Copywriter left %d slot(s) without copy: %s%s", len(pending), details, cause)
    return {slot.id: written[slot.id] for slot in inputs.slots if slot.id in written}
