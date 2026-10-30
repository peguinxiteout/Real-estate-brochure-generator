"""Platform-specific fix text and Ghostscript lookup. sys.platform is monkeypatched; nothing real is probed."""
from brochure.doctor import GsLookup, check_ghostscript, check_weasyprint

NATIVE_LIBS_ERROR = "cannot load library 'libgobject-2.0-0': error 0x7e"


def raising(exc: Exception):
    def importer(name: str):
        raise exc

    return importer


def test_on_windows_the_weasyprint_fixes_are_unchanged(windows):
    check = check_weasyprint(raising(OSError(NATIVE_LIBS_ERROR)))

    assert check.fixes == (
        "winget install MSYS2.MSYS2",
        'C:\\msys64\\usr\\bin\\bash.exe -lc "pacman -S --noconfirm mingw-w64-x86_64-pango"',
        "setx WEASYPRINT_DLL_DIRECTORIES C:\\msys64\\mingw64\\bin    (then open a new terminal)",
    )


def test_on_windows_a_missing_ghostscript_is_reported_as_before(windows):
    check = check_ghostscript(GsLookup())

    assert check.detail == "not found (looked at GS_BIN, PATH, C:\\Program Files\\gs)"
    assert check.fixes == ("download the 64-bit installer from https://ghostscript.com/releases/gsdnld.html",)
