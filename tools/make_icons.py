"""Regenerate cat.ico, cat.icns and splash.png from the artwork in cat.py.

Run on the Mac (needs the built-in iconutil):

    python tools/make_icons.py

Needs Pillow for the .ico; the app itself does not.
"""

import os
import subprocess
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from PySide6.QtWidgets import QApplication            # noqa: E402
from PySide6.QtGui import (                            # noqa: E402
    QImage, QPainter, QPainterPath, QTransform, QColor, QFont,
)
from PySide6.QtCore import QRectF, QPointF, Qt         # noqa: E402

app = QApplication([])

import cat as C                                        # noqa: E402

ICON_CAT = "nyx"          # the white cat is the logo
TILE = "#F8F6F2"          # cream, same as the splash background


def paint_cat(p, art, rect):
    """Draw every static layer of one cat into rect (QRectF, painter coords)."""
    for lay in (art.tail, art.base):
        lay.render(p, rect)
    if art.marks:
        p.save()
        tf = QTransform().translate(rect.x(), rect.y()).scale(
            rect.width() / 120.0, rect.height() / 132.0)
        p.setClipPath(tf.map(QPainterPath(C.get_silhouette())))
        art.marks.render(p, rect)
        p.restore()
    for lay in (art.face, art.eyes_iris, art.eyes_pupil, art.eyes_gloss,
                art.paw_l, art.paw_r):
        lay.render(p, rect)


def cat_image(size, art, tile):
    """A size x size image of the cat. tile=True puts it on a macOS-style
    rounded square; tile=False is the bare cat on transparency (Windows)."""
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    if tile:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(TILE))
        radius = size * 0.22
        p.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)
        pad = size * 0.10
    else:
        pad = size * 0.02
    inner = size - 2 * pad
    h = inner
    w = h * 120.0 / 132.0
    paint_cat(p, art, QRectF(pad + (inner - w) / 2, pad, w, h))
    p.end()
    return img


def to_pil(img):
    from PIL import Image
    img = img.convertToFormat(QImage.Format_RGBA8888)
    return Image.frombytes("RGBA", (img.width(), img.height()), bytes(img.constBits()))


def write_ico(path, art):
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [to_pil(cat_image(s, art, tile=False)) for s in sizes]
    frames[-1].save(path, format="ICO", sizes=[(s, s) for s in sizes],
                    append_images=frames[:-1])


def write_icns(path, art):
    with tempfile.TemporaryDirectory() as tmp:
        iconset = os.path.join(tmp, "cat.iconset")
        os.makedirs(iconset)
        for base in (16, 32, 128, 256, 512):
            cat_image(base, art, tile=True).save(
                os.path.join(iconset, f"icon_{base}x{base}.png"))
            cat_image(base * 2, art, tile=True).save(
                os.path.join(iconset, f"icon_{base}x{base}@2x.png"))
        subprocess.run(["iconutil", "-c", "icns", iconset, "-o", path], check=True)


def write_splash(path, art):
    w, h = 340, 190
    img = QImage(w, h, QImage.Format_ARGB32)
    img.fill(QColor(TILE))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    paint_cat(p, art, QRectF(28, 22, 130, 143))
    f = QFont()
    f.setPointSize(22)
    f.setWeight(QFont.Medium)
    p.setFont(f)
    p.setPen(QColor("#2E2A33"))
    p.drawText(QPointF(178, 88), "Desktop Cat")
    f.setPointSize(14)
    f.setWeight(QFont.Normal)
    p.setFont(f)
    p.setPen(QColor("#8C8798"))
    p.drawText(QPointF(178, 116), "Waking up...")
    p.end()
    img.save(path)


def main():
    art = C.CatArt(C.CAT_BY_ID[ICON_CAT], "round")
    for name, fn in (("cat.ico", write_ico), ("cat.icns", write_icns),
                     ("splash.png", write_splash)):
        path = os.path.join(ROOT, name)
        fn(path, art)
        print(f"{name:12s} {os.path.getsize(path) / 1024:7.1f} KB")


if __name__ == "__main__":
    main()
