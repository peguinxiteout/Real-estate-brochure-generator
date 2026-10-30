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


def test_each_image_has_exactly_the_manifest_pixel_size(tool, manifest, tmp_path):
    tool.generate_images(manifest, tmp_path)
    for e in manifest.images:
        with Image.open(tmp_path / e.filename) as img:
            assert img.size == (e.width_px, e.height_px), e.filename


def test_files_are_jpeg_and_small(tool, manifest, tmp_path):
    written = tool.generate_images(manifest, tmp_path)
    for path in written:
        with Image.open(path) as img:
            assert img.format == "JPEG"
    assert sum(p.stat().st_size for p in written) < 3_000_000


def test_output_is_deterministic(tool, manifest, tmp_path):
    first = tool.generate_images(manifest, tmp_path / "a")
    second = tool.generate_images(manifest, tmp_path / "b")
    assert [p.read_bytes() for p in first] == [p.read_bytes() for p in second]
