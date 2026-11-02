"""The bundled fonts: the files the brand kit's families need, and their licences."""
import json
from pathlib import Path

import pytest

from brochure.contracts.brand import BrandKit
from brochure.fonts import BUNDLED_FACES, FONTS_DIR, faces_for, missing_font_files

ROOT = Path(__file__).parents[2]


def sample_kit() -> BrandKit:
    return BrandKit.model_validate(json.loads((ROOT / "sample" / "brand_kit.json").read_text(encoding="utf-8")))


def test_the_sample_brand_kit_uses_inter_for_headings_and_open_sans_for_body():
    fonts = sample_kit().fonts
    assert (fonts.heading, fonts.body) == ("Inter", "Open Sans")


def test_every_font_file_the_sample_brand_kits_families_need_exists():
    fonts = sample_kit().fonts
    faces = faces_for(fonts.heading) + faces_for(fonts.body)
    assert faces
    assert [str(f.path) for f in faces if not f.path.is_file()] == []


def test_the_weights_bundled_are_the_ones_the_template_uses():
    weights = {(f.family, f.weight, f.style) for f in BUNDLED_FACES}
    assert weights == {
        ("Inter", 400, "normal"), ("Inter", 600, "normal"), ("Inter", 700, "normal"),
        ("Open Sans", 400, "normal"), ("Open Sans", 400, "italic"), ("Open Sans", 600, "normal"), ("Open Sans", 700, "normal"),
    }


def test_each_family_folder_has_its_ofl_licence():
    folders = {f.path.parent for f in BUNDLED_FACES}
    assert folders == {FONTS_DIR / "Inter", FONTS_DIR / "OpenSans"}
    assert [str(d) for d in sorted(folders) if not (d / "OFL.txt").is_file()] == []


def test_only_static_ttfs_and_licences_are_bundled():
    files = {p.relative_to(FONTS_DIR).as_posix() for p in FONTS_DIR.rglob("*") if p.is_file()}
    expected = {f.path.relative_to(FONTS_DIR).as_posix() for f in BUNDLED_FACES} | {"Inter/OFL.txt", "OpenSans/OFL.txt"}
    assert files == expected


def test_a_family_that_is_not_bundled_is_refused_with_its_name():
    with pytest.raises(ValueError, match="Playfair Display"):
        faces_for("Playfair Display")


def test_missing_font_files_names_each_missing_file_and_licence(tmp_path):
    (tmp_path / "Inter").mkdir()
    (tmp_path / "Inter" / "OFL.txt").write_text("licence")
    missing = missing_font_files(tmp_path)
    assert "Inter/Inter_18pt-Regular.ttf" in missing
    assert "OpenSans/OFL.txt" in missing
    assert "Inter/OFL.txt" not in missing


def test_nothing_is_missing_from_the_repo_fonts_folder():
    assert missing_font_files(FONTS_DIR) == []
