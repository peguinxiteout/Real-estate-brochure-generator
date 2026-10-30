"""The sample project ("Aurelia Heights") validates against the contracts and fits the template."""
import json
from pathlib import Path

import pytest

from brochure.contracts.brand import BrandKit
from brochure.contracts.project import Brief

ROOT = Path(__file__).parents[2]
SAMPLE = ROOT / "sample"


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_brand_kit_validates_and_its_logo_exists():
    kit = BrandKit.model_validate(read_json(SAMPLE / "brand_kit.json"))
    assert kit.company_name == "Kestrel Urbanscapes"
    assert (SAMPLE / kit.logo_path).is_file()


def test_brief_validates_and_has_a_non_empty_rera_number():
    brief = Brief.model_validate(read_json(SAMPLE / "brief.json"))
    assert brief.project_facts.name == "Aurelia Heights"
    assert brief.project_facts.rera_number
    assert len(brief.prompt) < 600
