"""WeasyPrint and Ghostscript checks, with the import / lookup faked (no real tools needed)."""
from pathlib import Path
from types import SimpleNamespace

from brochure.doctor import GsLookup, check_ghostscript, check_weasyprint

NATIVE_LIBS_ERROR = (
    "\n-----\n\nWeasyPrint could not import some external libraries. Please carefully follow the installation steps.\n"
    "\n-----\n\ncannot load library 'libgobject-2.0-0': error 0x7e"
)


def raising(exc: Exception):
    def importer(name: str):
        raise exc

    return importer


def test_importable_weasyprint_passes_and_shows_the_version():
    check = check_weasyprint(lambda name: SimpleNamespace(__version__="70.0"))

    assert check.ok
    assert check.name == "WeasyPrint"
    assert "70.0" in check.detail
    assert check.fixes == ()


def test_weasyprint_not_installed_suggests_pip():
    check = check_weasyprint(raising(ModuleNotFoundError("No module named 'weasyprint'")))

    assert not check.ok
    assert "not installed" in check.detail
    assert any("pip install weasyprint" in fix for fix in check.fixes)


def test_weasyprint_missing_native_libraries_reports_the_real_error_and_the_msys2_fix(windows):
    check = check_weasyprint(raising(OSError(NATIVE_LIBS_ERROR)))

    assert not check.ok
    assert check.detail == "cannot load library 'libgobject-2.0-0': error 0x7e"
    assert "winget install MSYS2.MSYS2" in check.fixes
    assert any("pacman -S --noconfirm mingw-w64-x86_64-pango" in fix for fix in check.fixes)
    assert any(fix.startswith("setx WEASYPRINT_DLL_DIRECTORIES C:\\msys64\\mingw64\\bin") for fix in check.fixes)


def test_found_ghostscript_passes_and_shows_path_and_source():
    gs = Path(r"C:\Program Files\gs\gs10.04.0\bin\gswin64c.exe")

    check = check_ghostscript(GsLookup(gs, "Program Files"))

    assert check.ok
    assert check.name == "Ghostscript"
    assert str(gs) in check.detail
    assert "Program Files" in check.detail
    assert check.fixes == ()


def test_missing_ghostscript_fails_with_a_download_link(windows):
    check = check_ghostscript(GsLookup())

    assert not check.ok
    assert "not found" in check.detail
    assert any("https://ghostscript.com/releases/gsdnld.html" in fix for fix in check.fixes)


def test_missing_ghostscript_with_a_bad_gs_bin_explains_it_and_suggests_setx(windows):
    note = r"GS_BIN is set to C:\nope\gswin64c.exe but that file does not exist"

    check = check_ghostscript(GsLookup(note=note))

    assert not check.ok
    assert note in check.detail
    assert any(fix.startswith("setx GS_BIN") for fix in check.fixes)
