"""JSON Schema export of the contract models, for the frontend."""
import json
from pathlib import Path

from brochure.contracts.base import ContractModel
from brochure.contracts.brand import BrandKit
from brochure.contracts.images import ImageTag
from brochure.contracts.project import Brief, ProjectFacts
from brochure.contracts.qa import QAIssue
from brochure.contracts.spec import BrochureSpec
from brochure.contracts.state import PipelineState

# Every model the frontend (or another service) may read or write as a whole document.
EXPORTED_MODELS: list[type[ContractModel]] = [
    BrandKit,
    Brief,
    BrochureSpec,
    ImageTag,
    PipelineState,
    ProjectFacts,
    QAIssue,
]


def schema_files() -> dict[str, str]:
    """File name -> exact text of the JSON Schema for that model."""
    return {
        f"{model.__name__}.json": json.dumps(model.model_json_schema(), indent=2) + "\n"
        for model in EXPORTED_MODELS
    }


def write_schemas(out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, text in schema_files().items():
        path = out_dir / name
        path.write_text(text, encoding="utf-8", newline="\n")
        written.append(path)
    return written
