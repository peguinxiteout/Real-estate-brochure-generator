"""QA findings."""
from typing import Literal

from pydantic import Field

from brochure.contracts.base import ContractModel


class QAIssue(ContractModel):
    check: str
    page: int | None = Field(default=None, ge=1)
    severity: Literal["error", "warning"]
    note: str
    route_to: Literal["copywriter", "layout", "none"] = "none"
