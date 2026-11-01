"""The steps of the pipeline, as plain callables. The graph only knows this shape, never a concrete agent."""
from dataclasses import dataclass

from brochure.contracts.images import ImageTag
from brochure.contracts.project import ProjectFacts
from brochure.contracts.qa import QAIssue
from brochure.contracts.spec import BrochureSpec
from brochure.contracts.state import PipelineState
from brochure.llm import Agent


@dataclass(frozen=True)
class BriefOutcome:
    """What the brief step found: the facts, or the fields it still needs from the user."""

    project_facts: ProjectFacts | None
    missing_fields: list[str]


@dataclass(frozen=True)
class RenderResult:
    pdf_path: str
    page_images: list[str]  # one PNG path per page, in page order


@dataclass(frozen=True)
class Agents:
    """One callable per step. Each is an Agent: (state, llm) -> that step's output."""

    brief: Agent[PipelineState, BriefOutcome]
    vision: Agent[PipelineState, list[ImageTag]]
    copywriter: Agent[PipelineState, dict[str, str]]  # slot id -> text
    layout: Agent[PipelineState, BrochureSpec]
    renderer: Agent[PipelineState, RenderResult]
    qa: Agent[PipelineState, list[QAIssue]]
    export: Agent[PipelineState, None]
