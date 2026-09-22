"""Generate wherobots_qgis/icon.png — the plugin's toolbar / manager icon.

The icon is the Wherobots company logo with its square corners rounded to
match the shape QGIS uses elsewhere. The mask is built at 4x and downscaled
with LANCZOS so the corner arc is antialiased rather than stair-stepped.
Re-run after replacing the source logo:

    python3 scripts/make_icon.py
"""

import os

from PIL import Image, ImageDraw

SIZE = 128          # final icon size (px)
SS = 4              # supersample factor
RADIUS_RATIO = 0.22  # corner radius as a fraction of the icon's edge

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

SRC = os.path.join(SCRIPT_DIR, "wherobots_logo.png")
OUT = os.path.join(REPO_ROOT, "wherobots_qgis", "icon.png")


def rounded_mask(size, radius):
    """An L-mode mask: opaque inside a rounded square, transparent outside."""
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=radius, fill=255
    )
    return mask


def main():
    big = SIZE * SS
    logo = Image.open(SRC).convert("RGBA").resize((big, big), Image.LANCZOS)

    # Punch the rounded corners out of the alpha channel, then downscale so
    # the resampling antialiases the arc.
    logo.putalpha(rounded_mask(big, int(RADIUS_RATIO * big)))
    icon = logo.resize((SIZE, SIZE), Image.LANCZOS)

    icon.save(OUT)
    print(f"wrote {OUT} ({icon.size[0]}x{icon.size[1]})")


if __name__ == "__main__":
    main()
