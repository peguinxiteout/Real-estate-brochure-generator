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


def test_existing_fonts_folder_passes(tmp_path):
    check = check_fonts(tmp_path)

    assert check.ok
    assert check.name == "Bundled fonts"
    assert str(tmp_path) in check.detail


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
