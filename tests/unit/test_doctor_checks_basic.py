"""Python-version and bundled-fonts checks."""
from brochure.doctor import check_fonts, check_python


def test_supported_python_passes_and_shows_the_version():
    check = check_python((3, 12, 10))

    assert check.ok
    assert check.name == "Python"
    assert "3.12.10" in check.detail
    assert check.fixes == ()


def test_old_python_fails_with_an_install_command():
    check = check_python((3, 11, 9))

    assert not check.ok
    assert "3.11.9" in check.detail
    assert "3.12" in check.detail
    assert "winget install Python.Python.3.12" in check.fixes


def bundle_fonts(folder):
    """Every bundled font file and licence, as empty files under folder."""
    from brochure.fonts import BUNDLED_FACES, FONTS_DIR

    for face in BUNDLED_FACES:
        for rel in (face.path.relative_to(FONTS_DIR), face.path.parent.relative_to(FONTS_DIR) / "OFL.txt"):
            (folder / rel).parent.mkdir(parents=True, exist_ok=True)
            (folder / rel).write_text("")


def test_fonts_folder_with_every_bundled_file_passes_and_names_the_families(tmp_path):
    bundle_fonts(tmp_path)

    check = check_fonts(tmp_path)

    assert check.ok
    assert check.name == "Bundled fonts"
    assert str(tmp_path) in check.detail
    assert "Inter" in check.detail and "Open Sans" in check.detail


def test_the_repo_fonts_folder_passes():
    assert check_fonts().ok


def test_an_empty_fonts_folder_fails_and_names_what_is_missing(tmp_path):
    check = check_fonts(tmp_path)

    assert not check.ok
    assert "Inter/Inter_18pt-Bold.ttf" in check.detail
    assert "OpenSans/OFL.txt" in check.detail


def test_a_folder_missing_one_file_fails_and_names_only_that_file(tmp_path):
    bundle_fonts(tmp_path)
    (tmp_path / "OpenSans" / "OpenSans-Italic.ttf").unlink()

    check = check_fonts(tmp_path)

    assert not check.ok
    assert "OpenSans/OpenSans-Italic.ttf" in check.detail
    assert "Inter/" not in check.detail


def test_the_fonts_fix_names_the_bundled_families_and_their_folders(tmp_path):
    fixes = " ".join(check_fonts(tmp_path).fixes)

    assert "git restore assets/fonts" in fixes
    assert "Inter" in fixes and "Open Sans" in fixes
    assert "assets/fonts/Inter" in fixes and "assets/fonts/OpenSans" in fixes
    assert "OFL.txt" in fixes
    assert "Playfair" not in fixes


def test_missing_fonts_folder_fails_and_names_the_path_and_a_fix(tmp_path):
    missing = tmp_path / "assets" / "fonts"

    check = check_fonts(missing)

    assert not check.ok
    assert str(missing) in check.detail
    assert any("git restore assets/fonts" in fix for fix in check.fixes)


def test_a_file_in_place_of_the_fonts_folder_fails(tmp_path):
    not_a_folder = tmp_path / "fonts"
    not_a_folder.write_text("")

    assert not check_fonts(not_a_folder).ok
