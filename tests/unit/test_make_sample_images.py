import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image

from brochure.contracts.manifest import ImageManifest

ROOT = Path(__file__).parents[2]


def load_tool(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def manifest():
    return ImageManifest.model_validate(json.loads((ROOT / "sample" / "images.json").read_text(encoding="utf-8")))


@pytest.fixture(scope="module")
def tool():
    return load_tool("make_sample_images")


def test_writes_one_file_per_manifest_entry(tool, manifest, tmp_path):
    written = tool.generate_images(manifest, tmp_path / "images")
    assert sorted(p.name for p in written) == sorted(e.filename for e in manifest.images)
    assert all(p.is_file() for p in written)
