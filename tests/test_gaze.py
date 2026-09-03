import random
import time

import pytest
from PySide6.QtCore import QPoint

import cat as C


def test_gaze_default_on():
    assert C.DEFAULTS["gaze"] is True


def test_gaze_target_zero_on_anchor():
    assert C.gaze_target(0, 0, 1.6, "round") == (0.0, 0.0)


@pytest.mark.parametrize("style,mx,my", [("round", 2.9, 2.8), ("slim", 3.5, 1.4)])
def test_gaze_target_saturates_far_away(style, mx, my):
    assert C.gaze_target(5000, 0, 1.6, style) == pytest.approx((mx, 0.0))
    assert C.gaze_target(-5000, 0, 1.6, style) == pytest.approx((-mx, 0.0))
    assert C.gaze_target(0, 5000, 1.6, style) == pytest.approx((0.0, my))
    assert C.gaze_target(0, -5000, 1.6, style) == pytest.approx((0.0, -my))


def test_gaze_target_ramps_with_distance():
    half = C.GAZE_RANGE_PX * 1.6 / 2
    assert C.gaze_target(half, 0, 1.6, "round") == pytest.approx((1.45, 0.0))


def test_gaze_target_never_exceeds_max():
    rng = random.Random(1)
    for _ in range(500):
        dx, dy = rng.uniform(-3000, 3000), rng.uniform(-3000, 3000)
        for style, (mx, my) in C.GAZE_MAX.items():
            ox, oy = C.gaze_target(dx, dy, 2.2, style)
            assert abs(ox) <= mx + 1e-9 and abs(oy) <= my + 1e-9


def test_gaze_goal_tracks_an_explicit_cursor(cat_widget):
    ax, ay = cat_widget.gaze_anchor()
    on_anchor = QPoint(int(ax), int(ay))
    assert cat_widget.gaze_goal(on_anchor) == pytest.approx((0.0, 0.0), abs=0.05)
    far_right = QPoint(int(ax) + 5000, int(ay))
    ox, oy = cat_widget.gaze_goal(far_right)
    assert ox == pytest.approx(2.9) and oy == pytest.approx(0.0, abs=0.01)


def test_gaze_goal_zero_when_disabled(cat_widget):
    cat_widget.s["gaze"] = False
    ax, ay = cat_widget.gaze_anchor()
    assert cat_widget.gaze_goal(QPoint(int(ax) + 5000, int(ay))) == (0.0, 0.0)


def test_gaze_goal_zero_while_asleep(cat_widget):
    cat_widget.last_active = time.monotonic() - 1000
    assert cat_widget.state() == "sleep"
    ax, ay = cat_widget.gaze_anchor()
    assert cat_widget.gaze_goal(QPoint(int(ax) + 5000, int(ay))) == (0.0, 0.0)


def test_pupils_move_in_the_painted_cat(cat_widget):
    cat_widget.gaze = [0.0, 0.0]
    a = cat_widget.grab().toImage()
    a2 = cat_widget.grab().toImage()
    cat_widget.gaze = [2.9, 0.0]
    b = cat_widget.grab().toImage()
    assert a == a2          # nothing else is animating between grabs
    assert a != b           # ...so the only difference is the pupils

    # The catchlight is pinned to the eye: the pixel at its centre is white in
    # both frames even though the pupil underneath it moved.
    sc = float(cat_widget.s["scale"])
    gx = int(cat_widget.MARGIN_SIDE + (46 - 1.8) * sc)
    gy = int(cat_widget.MARGIN_TOP + 47.6 * sc)
    assert a.pixelColor(gx, gy) == b.pixelColor(gx, gy)
    assert a.pixelColor(gx, gy).lightness() > 240


def test_menu_has_follow_cursor_toggle(cat_widget):
    menu = cat_widget.build_menu()
    eyes = next(a.menu() for a in menu.actions() if a.text() == "Eyes")
    toggle = next(a for a in eyes.actions() if a.text() == "Follow the cursor")
    assert toggle.isCheckable() and toggle.isChecked()
    toggle.trigger()
    assert cat_widget.s["gaze"] is False
