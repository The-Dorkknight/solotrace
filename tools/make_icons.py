# Required Notice: Copyright Matthew Armstrong (https://github.com/The-Dorkknight)
# Licensed under the PolyForm Noncommercial License 1.0.0. No warranty.
"""Draw the SoloTrace icon set (needs Pillow, development only).  python3 tools/make_icons.py"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def draw(size):
    s = size * 4
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=s // 5, fill=(22, 48, 28, 255))
    cu = (215, 154, 78, 255)
    w = int(s * 0.07)
    u = s / 100.0
    # a chamfered trace joining two pads, plus a jumper
    pts = [(24 * u, 74 * u), (24 * u, 48 * u), (38 * u, 34 * u), (62 * u, 34 * u), (76 * u, 48 * u), (76 * u, 74 * u)]
    d.line(pts, fill=cu, width=w, joint="curve")
    for x, y in (pts[0], pts[-1]):
        r = 9 * u
        d.ellipse([x - r, y - r, x + r, y + r], fill=cu)
        r2 = 3.6 * u
        d.ellipse([x - r2, y - r2, x + r2, y + r2], fill=(22, 48, 28, 255))
    # laser spark
    d.polygon([(50 * u, 6 * u), (56 * u, 22 * u), (44 * u, 22 * u)], fill=(255, 154, 31, 255))
    return im.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    os.makedirs(os.path.join(ROOT, "icons"), exist_ok=True)
    for n in (16, 32, 48, 64, 128, 256, 512):
        draw(n).save(os.path.join(ROOT, "icons", "solotrace-%d.png" % n))
    draw(256).save(os.path.join(ROOT, "icons", "solotrace.ico"), sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    draw(512).save(os.path.join(ROOT, "docs", "images", "icon-512.png"))
    draw(180).save(os.path.join(ROOT, "docs", "images", "apple-touch-icon.png"))
    draw(64).save(os.path.join(ROOT, "docs", "images", "favicon-64.png"))
    print("icons written")
