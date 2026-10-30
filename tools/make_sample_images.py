"""Generate the 12 sample images listed in sample/images.json.

Usage: python tools/make_sample_images.py [--out DIR]   (default: sample/images/)
"""
import argparse
import json
import zlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from brochure.contracts.manifest import ImageManifest, ImageManifestEntry

ROOT = Path(__file__).resolve().parents[1]
JPEG_QUALITY = 70


def _colour(seed: int, shift: int) -> tuple[int, int, int]:
    return tuple(60 + (seed >> (shift + 8 * i)) % 160 for i in range(3))


def _draw(entry: ImageManifestEntry) -> Image.Image:
    """A gradient plus a few shapes, derived only from the file name and size, so output is reproducible."""
    seed = zlib.crc32(entry.filename.encode())
    w, h = entry.width_px, entry.height_px
    gradient = Image.linear_gradient("L").resize((w, h))
    image = ImageOps.colorize(gradient, _colour(seed, 0), _colour(seed, 3))
    pen = ImageDraw.Draw(image)
    for i in range(3):
        x, y = (seed >> (4 * i)) % (w // 2), (seed >> (4 * i + 2)) % (h // 2)
        pen.rectangle([x, y, x + w // 3, y + h // 4], outline=_colour(seed, 5 + i), width=max(2, w // 200))
    pen.ellipse([w // 3, h // 3, 2 * w // 3, 2 * h // 3], outline=(255, 255, 255), width=max(2, w // 150))
    return image


def generate_images(manifest: ImageManifest, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for entry in manifest.images:
        path = out_dir / entry.filename
        _draw(entry).save(path, "JPEG", quality=JPEG_QUALITY)
        written.append(path)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "sample" / "images.json")
    parser.add_argument("--out", type=Path, default=ROOT / "sample" / "images")
    args = parser.parse_args()
    manifest = ImageManifest.model_validate(json.loads(args.manifest.read_text(encoding="utf-8")))
    for path in generate_images(manifest, args.out):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
