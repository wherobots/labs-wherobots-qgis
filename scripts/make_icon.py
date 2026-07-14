"""Generate wherobots_qgis/icon.png — the plugin's toolbar / manager icon.

The icon is drawn at 4x and downscaled with LANCZOS for smooth edges. Re-run
after changing the design:

    python3 scripts/make_icon.py
"""

import os

from PIL import Image, ImageDraw

SIZE = 128          # final icon size (px)
SS = 4              # supersample factor
INDIGO = (79, 70, 229, 255)   # #4F46E5 background
WHITE = (255, 255, 255, 255)

OUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "wherobots_qgis",
    "icon.png",
)


def draw(scale):
    """Draw the icon on a `scale`-times-larger canvas."""
    s = SIZE * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Rounded-square background.
    radius = int(0.22 * s)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=radius, fill=INDIGO)

    # White map pin (teardrop): a circular head fused with a downward triangle.
    cx = s / 2
    head_cy = s * 0.40
    head_r = s * 0.20
    tip_y = s * 0.80

    d.ellipse(
        [cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r],
        fill=WHITE,
    )
    d.polygon(
        [(cx - head_r * 0.86, head_cy + head_r * 0.30),
         (cx + head_r * 0.86, head_cy + head_r * 0.30),
         (cx, tip_y)],
        fill=WHITE,
    )

    # Indigo hole punched through the head.
    hole_r = s * 0.085
    d.ellipse(
        [cx - hole_r, head_cy - hole_r, cx + hole_r, head_cy + hole_r],
        fill=INDIGO,
    )
    return img


def main():
    big = draw(SS)
    icon = big.resize((SIZE, SIZE), Image.LANCZOS)
    icon.save(OUT)
    print(f"wrote {OUT} ({icon.size[0]}x{icon.size[1]})")


if __name__ == "__main__":
    main()
