"""PipelineState: what a LangGraph pipeline carries between agents."""
from typing import Literal

from pydantic import Field

from brochure.contracts.base import ContractModel
from brochure.contracts.brand import BrandKit
from brochure.contracts.images import ImageTag
from brochure.contracts.project import ProjectFacts
from brochure.contracts.qa import QAIssue
from brochure.contracts.spec import BrochureSpec


class PipelineState(ContractModel):
    # inputs, set once
    template_id: str
    brand_kit: BrandKit
    project_facts: ProjectFacts
    brief_prompt: str = ""
    image_dir: str
    # produced by agents
    image_tags: list[ImageTag] = []
    slot_copy: dict[str, str] = {}
    spec: BrochureSpec | None = None
    # review loop
    qa_issues: list[QAIssue] = []
    qa_round: int = Field(default=0, ge=0)
    approval_status: Literal["pending", "approved", "changes_requested"] = "pending"
