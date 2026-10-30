"""Platform-specific fix text and Ghostscript lookup. sys.platform is monkeypatched; nothing real is probed."""
from brochure.doctor import GsLookup, check_ghostscript, check_weasyprint, find_ghostscript

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


def test_on_linux_missing_pango_suggests_apt_not_the_windows_tools(linux):
    check = check_weasyprint(raising(OSError(NATIVE_LIBS_ERROR)))

    assert check.fixes == ("sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0",)


def test_on_linux_a_missing_ghostscript_suggests_apt(linux):
    check = check_ghostscript(GsLookup())

    assert check.fixes == ("sudo apt install ghostscript",)


def make_exe(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("")
    return path


def test_on_linux_the_lookup_skips_program_files(linux, tmp_path, monkeypatch):
    monkeypatch.delenv("GS_BIN", raising=False)
    root = tmp_path / "gs"
    make_exe(root / "gs10.04.0" / "bin" / "gswin64c.exe")

    result = find_ghostscript(which=lambda name: None, gs_root=root)

    assert result.path is None
    assert result.source is None


def test_on_linux_gs_bin_wins_over_path(linux, tmp_path, monkeypatch):
    from_env = make_exe(tmp_path / "custom" / "gs")
    from_path = make_exe(tmp_path / "onpath" / "gs")
    monkeypatch.setenv("GS_BIN", str(from_env))

    result = find_ghostscript(which=lambda name: str(from_path))

    assert (result.path, result.source) == (from_env, "GS_BIN")


def test_on_linux_path_is_searched_for_gs_only(linux, monkeypatch):
    monkeypatch.delenv("GS_BIN", raising=False)
    asked = []

    def which(name):
        asked.append(name)
        return None

    find_ghostscript(which=which)

    assert asked == ["gs"]


def test_on_linux_the_not_found_message_does_not_mention_program_files(linux):
    check = check_ghostscript(GsLookup())

    assert check.detail == "not found (looked at GS_BIN, PATH)"


def test_on_linux_a_bad_gs_bin_suggests_export_not_setx(linux):
    note = "GS_BIN is set to /nope/gs but that file does not exist"

    check = check_ghostscript(GsLookup(note=note))

    assert check.fixes == ("sudo apt install ghostscript", 'export GS_BIN="<full path to gs>"    (add it to ~/.bashrc)')
