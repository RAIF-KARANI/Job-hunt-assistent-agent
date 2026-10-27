"""
Draw the JobLens app icon: a magnifying glass (the "lens") with a check mark
(a good fit), in the app's blue. Writes assets/joblens.png and joblens.ico.

Run:  python scripts/make_icon.py

Drawn at 4x size, then shrunk: that gives smooth (anti-aliased) edges.
A .ico holds several sizes; Windows picks the right one for the taskbar,
title bar, Explorer, etc.
"""

from pathlib import Path

from PIL import Image, ImageDraw

BLUE = (42, 120, 214, 255)       # #2a78d6, the app's accent
DARK_BLUE = (24, 79, 149, 255)   # #184f95, handle
WHITE = (255, 255, 255, 255)
S = 1024                          # work size (4 x 256)

img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Handle: a thick rounded line from the lens towards the bottom-right corner.
d.line([(610, 610), (900, 900)], fill=DARK_BLUE, width=150)
d.ellipse([900 - 75, 900 - 75, 900 + 75, 900 + 75], fill=DARK_BLUE)  # round end

# Lens: filled blue disc with a white ring inside (glass rim).
cx, cy, r = 430, 430, 330
d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BLUE)
d.ellipse([cx - r + 46, cy - r + 46, cx + r - 46, cy + r - 46], outline=WHITE, width=30)

# Check mark inside the lens.
d.line([(290, 440), (395, 545), (580, 330)], fill=WHITE, width=78, joint="curve")
for x, y in [(290, 440), (580, 330)]:  # rounded line caps
    d.ellipse([x - 39, y - 39, x + 39, y + 39], fill=WHITE)

out = Path(__file__).resolve().parent.parent / "assets"
out.mkdir(exist_ok=True)
icon = img.resize((256, 256), Image.Resampling.LANCZOS)
icon.save(out / "joblens.png")
icon.save(out / "joblens.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                                      (128, 128), (256, 256)])
print("wrote", out / "joblens.png", "and", out / "joblens.ico")
