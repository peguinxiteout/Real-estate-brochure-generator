import json
import subprocess
import sys
from pathlib import Path

from brochure.contracts.export import schema_files, write_schemas

EXPECTED = {
    "BrandKit.json",
    "Brief.json",
    "BrochureSpec.json",
    "ImageTag.json",
    "PipelineState.json",
    "ProjectFacts.json",
    "QAIssue.json",
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
