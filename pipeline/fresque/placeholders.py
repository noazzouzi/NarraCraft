"""Generate stand-in visuals so the montage can be built and watched before
a single euro is spent on image generation or a single archive is fetched.

Deliberately ugly-but-informative: each card states its shot id, beat, and
the visual intention, so a review pass is about rhythm and pacing rather than
about pictures.
"""
from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .shots import Shot


def _palette(seed: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    digest = hashlib.sha256(seed.encode()).digest()
    hue = digest[0] / 255.0
    base = tuple(int(30 + 55 * abs(((hue * 3 + shift) % 1.0) * 2 - 1)) for shift in (0.0, 0.33, 0.66))
    top = tuple(min(255, channel + 38) for channel in base)
    return base, top  # type: ignore[return-value]


def _font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def card(shot: Shot, destination: Path, size: tuple[int, int] = (1920, 1080)) -> None:
    width, height = size
    bottom, top = _palette(shot.id)

    image = Image.new("RGB", size, bottom)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / height
        draw.line(
            [(0, y), (width, y)],
            fill=tuple(int(t + (b - t) * ratio) for t, b in zip(top, bottom)),
        )

    draw.text((90, 80), shot.id, font=_font(96), fill=(255, 255, 255))
    draw.text(
        (90, 200),
        f"{shot.beat} · {shot.type} · {shot.mouvement}",
        font=_font(40), fill=(190, 200, 215),
    )

    intention = shot.intention or shot.requete or shot.prompt or "—"
    wrapped = textwrap.fill(intention, width=46)
    draw.multiline_text(
        (90, 330), wrapped, font=_font(54), fill=(238, 242, 248), spacing=16
    )

    draw.text(
        (90, height - 120),
        "PLACEHOLDER — aucun visuel réel n'a encore été sourcé",
        font=_font(34), fill=(150, 160, 175),
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, quality=88)
