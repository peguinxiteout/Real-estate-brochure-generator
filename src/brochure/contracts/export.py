"""JSON Schema export of the contract models, for the frontend."""
import json
from pathlib import Path

from brochure.contracts.base import ContractModel
from brochure.contracts.brand import BrandKit
from brochure.contracts.images import ImageTag
from brochure.contracts.manifest import ImageManifest
from brochure.contracts.project import Brief, ProjectFacts
from brochure.contracts.qa import QAIssue
from brochure.contracts.slots import SlotsFile
from brochure.contracts.spec import BrochureSpec
from brochure.contracts.state import PipelineState

# Every model the frontend (or another service) may read or write as a whole document.
EXPORTED_MODELS: list[type[ContractModel]] = [
    BrandKit,
    Brief,
    BrochureSpec,
    ImageManifest,
    ImageTag,
    PipelineState,
    ProjectFacts,
    QAIssue,
    SlotsFile,
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


def out_of_date(directory: Path) -> tuple[list[str], list[str]]:
    """(files that differ or are missing, files that no longer belong), comparing parsed JSON, not bytes."""
    expected = {name: json.loads(text) for name, text in schema_files().items()}
    found = {path.name: path for path in directory.glob("*.json")} if directory.is_dir() else {}
    stale = sorted(name for name, schema in expected.items() if name not in found or json.loads(found[name].read_text(encoding="utf-8")) != schema)
    extra = sorted(set(found) - set(expected))
    return stale, extra
