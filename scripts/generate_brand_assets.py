#!/usr/bin/env python3
"""Generate the 数識電収 favicon, touch icons, and social preview."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
NAVY = "#17324d"
OFF_WHITE = "#fffefb"
VERMILION = "#e24b2c"
CORAL = "#f2c3b7"


def brand_mark(size: int) -> Image.Image:
    scale = 4
    canvas_size = size * scale
    image = Image.new("RGB", (canvas_size, canvas_size), NAVY)
    draw = ImageDraw.Draw(image)
    center = canvas_size / 2

    for radius in (0.36, 0.275, 0.19):
        r = canvas_size * radius
        width = max(scale, round(canvas_size * 0.046))
        draw.ellipse(
            (center - r, center - r, center + r, center + r),
            outline=OFF_WHITE,
            width=width,
        )

    points = [
        (0.63, 0.07),
        (0.43, 0.45),
        (0.57, 0.45),
        (0.31, 0.94),
        (0.42, 0.57),
        (0.29, 0.57),
    ]
    draw.polygon(
        [(round(x * canvas_size), round(y * canvas_size)) for x, y in points],
        fill=VERMILION,
    )
    return image.resize((size, size), Image.Resampling.LANCZOS)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("/System/Library/Fonts/ヒラギノ明朝 ProN.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size, index=1 if bold else 0)
    return ImageFont.load_default(size=size)


def social_preview() -> Image.Image:
    image = Image.new("RGB", (1200, 630), NAVY)
    draw = ImageDraw.Draw(image)
    mark = brand_mark(420)
    image.paste(mark, (55, 105))

    draw.text((515, 135), "数識電収", fill=OFF_WHITE, font=font(92, bold=True))
    draw.text(
        (520, 270),
        "数学識電脳界溢出部位封神蔵収",
        fill=CORAL,
        font=font(32),
    )
    draw.text((520, 330), "私と放電", fill=CORAL, font=font(28))
    draw.rectangle((515, 405, 1090, 411), fill=VERMILION)
    draw.text(
        (520, 445),
        "数学原稿・PDF・TeXソースのアーカイブ",
        fill=OFF_WHITE,
        font=font(29),
    )
    return image


def main() -> None:
    favicon_16 = brand_mark(16)
    favicon_32 = brand_mark(32)
    favicon_16.save(ROOT / "favicon-16.png")
    favicon_32.save(ROOT / "favicon-32.png")
    favicon_32.save(
        ROOT / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32)],
        append_images=[favicon_16],
    )
    brand_mark(180).save(ROOT / "apple-touch-icon.png")
    brand_mark(192).save(ROOT / "icon-192.png")
    brand_mark(512).save(ROOT / "icon-512.png")
    social_preview().save(ROOT / "og-image.png", optimize=True)


if __name__ == "__main__":
    main()
