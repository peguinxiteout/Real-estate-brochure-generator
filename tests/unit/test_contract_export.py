import json

import pytest
import subprocess
import sys
from pathlib import Path

from brochure.contracts.export import EXPORTED_MODELS, out_of_date, schema_files, write_schemas

EXPECTED = {
    "BrandKit.json",
    "Brief.json",
    "BrochureSpec.json",
    "ImageManifest.json",
    "ImageTag.json",
    "PipelineState.json",
    "ProjectFacts.json",
    "QAIssue.json",
    "SlotsFile.json",
}


def test_one_schema_file_per_contract_model():
    assert set(schema_files()) == EXPECTED


def test_each_schema_is_valid_json_that_describes_the_model():
    for name, text in schema_files().items():
        schema = json.loads(text)
        assert schema["title"] == name.removesuffix(".json")
        assert schema["additionalProperties"] is False


def test_write_schemas_writes_every_file_into_the_folder(tmp_path):
    out = tmp_path / "nested" / "json"
    written = write_schemas(out)
    assert sorted(p.name for p in written) == sorted(EXPECTED)
    for name, text in schema_files().items():
        assert (out / name).read_text(encoding="utf-8") == text


def test_export_script_writes_schemas_to_the_given_folder(tmp_path):
    script = Path(__file__).parents[2] / "tools" / "export_schemas.py"
    result = subprocess.run(
        [sys.executable, str(script), "--out", str(tmp_path)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in tmp_path.glob("*.json")) == sorted(EXPECTED)


REGENERATE = "python tools/export_schemas.py"
COMMITTED = Path(__file__).parents[2] / "contracts" / "json"


def test_a_checkout_with_crlf_line_endings_is_not_out_of_date(tmp_path):
    for name, text in schema_files().items():
        (tmp_path / name).write_bytes(text.replace(chr(10), chr(13) + chr(10)).encode("utf-8"))
    assert out_of_date(tmp_path) == ([], [])


def test_a_changed_or_missing_or_extra_file_is_reported(tmp_path):
    write_schemas(tmp_path)
    (tmp_path / "QAIssue.json").write_text('{"title": "QAIssue"}', encoding="utf-8")
    (tmp_path / "BrandKit.json").unlink()
    (tmp_path / "Old.json").write_text("{}", encoding="utf-8")
    assert out_of_date(tmp_path) == (["BrandKit.json", "QAIssue.json"], ["Old.json"])


def test_committed_schemas_match_the_models():
    stale, extra = out_of_date(COMMITTED)
    assert not stale and not extra, (
        f"contracts/json/ is out of date (differs or missing: {stale}; no longer a model: {extra}). "
        f"Regenerate and commit with: {REGENERATE}"
    )


@pytest.mark.parametrize("model", EXPORTED_MODELS, ids=lambda m: m.__name__)
def test_every_exported_model_rejects_unknown_fields(model):
    assert model.model_config.get("extra") == "forbid"
