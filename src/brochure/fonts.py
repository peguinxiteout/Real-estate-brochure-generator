"""The bundled brand fonts: static TTFs under assets/fonts/<folder>/, each folder with its OFL.txt.

Only these faces are ever used in a PDF; the renderer never falls back to a system font.
Inter is the 18pt optical size from the Google Fonts download (the text cut).
"""
from dataclasses import dataclass
from pathlib import Path

# <repo>/src/brochure/fonts.py -> <repo>/assets/fonts (valid for the editable install used in development)
FONTS_DIR = Path(__file__).resolve().parents[2] / "assets" / "fonts"
LICENCE = "OFL.txt"


@dataclass(frozen=True)
class FontFace:
    family: str
    weight: int
    style: str  # "normal" or "italic"
    path: Path


def _faces(family: str, folder: str, files: dict[tuple[int, str], str]) -> list[FontFace]:
    return [FontFace(family, weight, style, FONTS_DIR / folder / name) for (weight, style), name in files.items()]


BUNDLED_FACES: tuple[FontFace, ...] = (
    *_faces("Inter", "Inter", {
        (400, "normal"): "Inter_18pt-Regular.ttf",
        (600, "normal"): "Inter_18pt-SemiBold.ttf",
        (700, "normal"): "Inter_18pt-Bold.ttf",
    }),
    *_faces("Open Sans", "OpenSans", {
        (400, "normal"): "OpenSans-Regular.ttf",
        (400, "italic"): "OpenSans-Italic.ttf",
        (600, "normal"): "OpenSans-SemiBold.ttf",
        (700, "normal"): "OpenSans-Bold.ttf",
    }),
)
BUNDLED_FAMILIES: tuple[str, ...] = tuple(dict.fromkeys(f.family for f in BUNDLED_FACES))


def faces_for(family: str) -> list[FontFace]:
    """The bundled faces of a family. ValueError for a family that is not bundled."""
    faces = [f for f in BUNDLED_FACES if f.family == family]
    if not faces:
        raise ValueError(f"font family {family!r} is not bundled; bundled: {', '.join(BUNDLED_FAMILIES)}")
    return faces


def missing_font_files(fonts_dir: Path) -> list[str]:
    """Every bundled font file and licence absent from fonts_dir, as paths relative to it ('Inter/OFL.txt')."""
    wanted = []
    for face in BUNDLED_FACES:
        rel = face.path.relative_to(FONTS_DIR)
        wanted += [rel.as_posix(), (rel.parent / LICENCE).as_posix()]
    return [rel for rel in dict.fromkeys(wanted) if not (Path(fonts_dir) / rel).is_file()]
