from PySide6.QtGui import QImage

import cat as C

W, H = 192.0, 211.2   # Medium: 120 x 1.6, 132 x 1.6


def rgba_bytes(pixmap):
    img = pixmap.toImage().convertToFormat(QImage.Format_RGBA8888)
    return bytes(img.constBits())


def has_ink(pixmap):
    return any(rgba_bytes(pixmap)[3::4])


def solid_colours(pixmap):
    """Hex colours of every fully opaque pixel, e.g. {'#2E2A33', ...}."""
    b = rgba_bytes(pixmap)
    seen = set()
    for i in range(0, len(b), 4):
        if b[i + 3] == 255:
            seen.add("#%02X%02X%02X" % (b[i], b[i + 1], b[i + 2]))
    return seen


def test_every_layer_rasterises_for_every_cat_and_eye_style(app):
    for c in C.CATS:
        for style in ("round", "slim"):
            art = C.CatArt(c, style)
            art.rasterize(W, H, 1.0)
            for name in C.CatArt.NAMES:
                if name == "marks" and not c["marks"]:
                    continue
                assert name in art.px, f"{c['id']}/{style}: no layer {name}"
                assert has_ink(art.px[name]), f"{c['id']}/{style}: empty layer {name}"


def test_nyx_and_nora_have_black_tails(app):
    for cid, fill in (("nyx", "#2E2A33"), ("nora", "#332F38")):
        c = C.CAT_BY_ID[cid]
        assert c["tail"] == fill
        assert c["tail_line"] == "#6E6880"
        art = C.CatArt(c, "round")
        art.rasterize(360.0, 396.0, 1.0)          # 3x so the rim has whole pixels
        cols = solid_colours(art.px["tail"])
        assert fill in cols, f"{cid}: tail fill missing"
        assert "#6E6880" in cols, f"{cid}: light rim missing"
        assert c["fur"].upper() not in cols, f"{cid}: tail still fur-coloured"


def test_other_cats_keep_their_tail_colour(app):
    for cid in ("nemo", "noir"):
        c = C.CAT_BY_ID[cid]
        assert c["tail"] == c["fur"]
        assert "tail_line" not in c


def test_open_eye_is_three_layers(app):
    for style in ("round", "slim"):
        art = C.CatArt(C.CAT_BY_ID["nyx"], style)
        art.rasterize(W, H, 1.0)
        assert not hasattr(art, "eyes_open")
        assert "eyes_open" not in C.CatArt.NAMES
        for name in ("eyes_iris", "eyes_pupil", "eyes_gloss"):
            assert has_ink(art.px[name]), f"{style}: empty {name}"
        # the pupil layer is only the dark pupil, nothing else
        pupil_colour = "#241F2C" if style == "round" else "#221F2A"
        assert solid_colours(art.px["eyes_pupil"]) == {pupil_colour}
        # the gloss layer is only white catchlights
        assert solid_colours(art.px["eyes_gloss"]) <= {"#FFFFFF"}
