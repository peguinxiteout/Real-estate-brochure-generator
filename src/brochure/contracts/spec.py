"""BrochureSpec: the filled-in brochure that the renderer consumes."""
from pydantic import field_validator

from brochure.contracts.base import ContractModel
from brochure.contracts.qa import QAIssue


class SlotFill(ContractModel):
    """The content for one slot: text, an image path, or QR payload."""

    text: str | None = None
    image_path: str | None = None
    qr_data: str | None = None


class PageSpec(ContractModel):
    layout_id: str
    slots: dict[str, SlotFill]


class BrochureSpec(ContractModel):
    template_id: str
    pages: list[PageSpec]
    qa_warnings: list[QAIssue] = []
    version: int = 1

    @field_validator("pages")
    @classmethod
    def _page_count_is_a_positive_multiple_of_four(cls, pages: list[PageSpec]) -> list[PageSpec]:
        if not pages or len(pages) % 4 != 0:
            raise ValueError(f"page count must be a positive multiple of 4, got {len(pages)}")
        return pages
