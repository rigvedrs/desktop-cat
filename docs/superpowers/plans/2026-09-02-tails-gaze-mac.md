# Black Tails, Cursor Gaze and macOS Support — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Nyx and Nora black tails, rename the cats, make the pupils follow the mouse cursor, and make Desktop Cat a proper macOS app (real typing detection, single instance, visible on every Space) shipped as a DMG from GitHub Actions next to the Windows exe.

**Architecture:** Everything lives in the single-file PySide6 app `cat.py`, which composes pre-rasterised SVG layers per frame. The eye layer is split into iris / pupil / gloss so only the pupil bitmap is translated by a gaze offset computed once per frame from `QCursor.pos()`. macOS-specific behaviour uses `ctypes` against system frameworks (ApplicationServices, libobjc) so no new runtime dependency is added. A new `tools/make_icons.py` regenerates the icon and splash assets from the live artwork.

**Tech Stack:** Python 3.11 (local, conda env `yolo`) / 3.12 (CI), PySide6 6.11, pytest 9, Pillow (tool only), PyInstaller on `macos-latest`, `iconutil` / `plutil` / `codesign` / `hdiutil` (macOS built-ins).

Spec: `docs/superpowers/specs/2026-09-02-tails-gaze-mac-design.md`

## Global Constraints

- Work in the conda env `yolo` — never `base`. Every Python command in this plan is run as
  `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && <command>`.
  PySide6 6.11.2, pytest 9.0.3 and Pillow 10.2.0 are already installed there.
- Tests run headless: `tests/conftest.py` sets `QT_QPA_PLATFORM=offscreen` before Qt loads.
- Commit messages carry **no** `Co-Authored-By` or AI attribution (user's global CLAUDE.md).
- Artwork canvas is 120 × 132. Sizes: Small 1.2, Medium 1.6, Large 2.2.
- The tail outline stroke is drawn **under** the fur stroke (fixed bug; do not reorder).
- `silhouette_path()` must be kept in sync with `BODY`/`EAR_L`/`EAR_R`/head — this plan does not change those paths.
- Do not go back to per-frame SVG rendering; all new layers go through `CatArt.rasterize()`.
- The Windows workflow `.github/workflows/build-windows.yml` is changed by exactly one line (`append_body: true`, Task 7).
- Cat ids/names: `nyx`/Nyx, `nora`/Nora, `nemo`/Nemo, `noir`/Noir. Legacy ids `mochi`, `patches`, `marmalade` migrate.
- Colours: Nyx tail `#2E2A33`, Nora tail `#332F38`, both `tail_line` `#6E6880`. Splash/icon tile background `#F8F6F2`.
- Gaze: `GAZE_MAX = {"round": (2.9, 2.8), "slim": (3.5, 1.4)}`, `GAZE_RANGE_PX = 220.0` (× scale), ease factor `min(1.0, dt * 9.0)`. Mouse movement never updates `last_active`.
- macOS: settings at `~/Library/Application Support/DesktopCat/settings.json`; other non-Windows at `~/.config/DesktopCat/settings.json`; one-time copy from legacy `~/DesktopCat/settings.json`, never deleting it.
- macOS build: arm64 only, unsigned (ad-hoc), `--windowed`, **no `--splash`**, `LSUIElement` true, bundle id `com.rigvedrs.desktopcat`, output `DesktopCat-macos.dmg`.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `cat.py` (modify) | The app. Sections in order: artwork constants/layers → `CatArt` cache → settings → platform helpers (Windows + new macOS) → `Cat` widget. New: `tail_line`, `LEGACY_CAT_IDS`, eye layer split, `gaze_target()`, `GAZE_*`, `IS_MAC`, `settings_dir()`, `LEGACY_SETTINGS`, `mac_seconds_since_keydown()`, `apply_mac_window_behaviour()`, `Cat.gaze_anchor()`, `Cat.gaze_goal()`, `Cat.set_gaze()`. |
| `tests/conftest.py` (new) | Offscreen Qt setup; `app` and `cat_widget` fixtures. |
| `tests/test_settings.py` (new) | Cat ids/names, legacy id migration, defaults. |
| `tests/test_art.py` (new) | Every layer rasterises; tail colours; eye layer split. |
| `tests/test_gaze.py` (new) | `gaze_target()` maths; `Cat.gaze_goal()`; menu toggle; pupils move in the painted output. |
| `tests/test_platform.py` (new) | `settings_dir()`, legacy copy, flock guard, mac key probe, mac window-behaviour guard, menu gating. |
| `tools/make_icons.py` (new) | Regenerates `cat.ico`, `cat.icns`, `splash.png` from Nyx. |
| `cat.ico`, `splash.png` (regenerate), `cat.icns` (new) | Shipped assets. |
| `.github/workflows/build-macos.yml` (new) | macOS build → DMG → artifact / release asset. |
| `.github/workflows/build-windows.yml` (modify, 1 line) | `append_body: true` so the two workflows don't overwrite each other's release notes. |
| `SEND-THIS-WITH-THE-MAC-FILE.txt` (new) | Recipient instructions for the Mac DMG. |
| `README.txt`, `BUILD-FROM-MAC.txt` (modify) | Names, macOS notes, local dev section. |

---

### Task 1: Test harness, cat renames and legacy-id migration

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_settings.py`
- Modify: `cat.py:45-96` (`CATS`, `CAT_BY_ID`), `cat.py:303-312` (`DEFAULTS`), `cat.py:322-333` (`load_settings`)
- Modify: `README.txt:46`

**Interfaces:**
- Produces: `CATS[i]["id"] in ("nyx","nora","nemo","noir")`, `LEGACY_CAT_IDS: dict[str,str]`, `DEFAULTS["cat"] == "nyx"`; `tests/conftest.py` fixture `app` (session-scoped `QApplication`).

- [ ] **Step 1: Create the test harness**

`tests/conftest.py`:

```python
import os
import sys

# Must happen before anything imports Qt: run without a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from PySide6.QtWidgets import QApplication

import cat as C


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def cat_widget(app, monkeypatch, tmp_path):
    """A live Cat window that reads/writes a throwaway settings file."""
    monkeypatch.setattr(C, "settings_path", lambda: str(tmp_path / "settings.json"))
    w = C.Cat()
    yield w
    for t in (w.timer, w.key_timer, w.top_timer):
        t.stop()
    w.close()
```

- [ ] **Step 2: Write the failing tests**

`tests/test_settings.py`:

```python
import json

import pytest

import cat as C


def use_tmp_settings(monkeypatch, tmp_path, data):
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(C, "settings_path", lambda: str(path))


def test_cat_ids_and_names():
    assert [c["id"] for c in C.CATS] == ["nyx", "nora", "nemo", "noir"]
    assert [c["name"] for c in C.CATS] == ["Nyx", "Nora", "Nemo", "Noir"]
    assert C.DEFAULTS["cat"] == "nyx"


@pytest.mark.parametrize("old,new", [
    ("mochi", "nyx"), ("patches", "nora"), ("marmalade", "nemo"), ("noir", "noir"),
])
def test_legacy_cat_ids_migrate(monkeypatch, tmp_path, old, new):
    use_tmp_settings(monkeypatch, tmp_path, {"cat": old})
    assert C.load_settings()["cat"] == new


def test_unknown_cat_id_falls_back_to_default(monkeypatch, tmp_path):
    use_tmp_settings(monkeypatch, tmp_path, {"cat": "garfield"})
    assert C.load_settings()["cat"] == "nyx"
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python -m pytest tests/test_settings.py -q`
Expected: FAIL — `test_cat_ids_and_names` asserts `['mochi', ...] == ['nyx', ...]`; the migration tests get `"nyx"` (default) instead of the mapped id.

- [ ] **Step 4: Rename the cats and add the legacy map**

In `cat.py`, change the four `CATS` entries' first two keys (leave every other key as it is for now — tails are Task 2):

```python
    {
        "id": "nyx",
        "name": "Nyx",
```
```python
    {
        "id": "nora",
        "name": "Nora",
```
```python
    {
        "id": "nemo",
        "name": "Nemo",
```
(`noir` / `Noir` is unchanged.)

Directly after `CAT_BY_ID = {c["id"]: c for c in CATS}` add:

```python
# Ids the cats had before they were renamed; old settings files still use them.
LEGACY_CAT_IDS = {"mochi": "nyx", "patches": "nora", "marmalade": "nemo"}
```

In `DEFAULTS` change `"cat": "mochi",` to `"cat": "nyx",`.

In `load_settings()` replace

```python
    if s.get("cat") not in CAT_BY_ID:
        s["cat"] = DEFAULTS["cat"]
```
with
```python
    s["cat"] = LEGACY_CAT_IDS.get(s.get("cat"), s.get("cat"))
    if s.get("cat") not in CAT_BY_ID:
        s["cat"] = DEFAULTS["cat"]
```

- [ ] **Step 5: Update the README**

`README.txt` line 46 becomes:

```
The menu has four cats (Nyx, Nora, Nemo, Noir), two eye styles
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python -m pytest tests/test_settings.py -q`
Expected: `6 passed`

- [ ] **Step 7: Commit**

```bash
git add tests/conftest.py tests/test_settings.py cat.py README.txt
git commit -m "Rename cats to Nyx, Nora, Nemo, Noir and migrate old ids"
```

---

### Task 2: Black tails for Nyx and Nora

**Files:**
- Create: `tests/test_art.py`
- Modify: `cat.py:45-73` (`CATS` nyx/nora entries), `cat.py:106-112` (`layer_tail`)

**Interfaces:**
- Consumes: `C.CAT_BY_ID`, `C.CatArt(cat, eye_style).rasterize(w, h, dpr)` → `.px[name]: QPixmap`.
- Produces: optional cat key `tail_line`; test helpers `rgba_bytes`, `has_ink`, `solid_colours` in `tests/test_art.py`.

- [ ] **Step 1: Write the failing tests**

`tests/test_art.py`:

```python
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python -m pytest tests/test_art.py -q`
Expected: `test_nyx_and_nora_have_black_tails` FAILS on `c["tail"] == "#2E2A33"` (`#F6F3EC` currently). The other two pass.

- [ ] **Step 3: Change the tail colours and the tail layer**

In `cat.py`, the `nyx` entry's colour line becomes:

```python
        "fur": "#F6F3EC", "belly": "#FFFFFF", "tail": "#2E2A33", "tail_line": "#6E6880",
```

The `nora` entry's colour line becomes:

```python
        "fur": "#F7F4EE", "belly": "#FFFFFF", "tail": "#332F38", "tail_line": "#6E6880",
```

Replace `layer_tail` with:

```python
def layer_tail(c):
    # A dark tail gets a lighter rim (tail_line) so it still reads as a shape.
    rim = c.get("tail_line", c["line"])
    return _svg(
        f'<path d="{TAIL}" fill="none" stroke="{rim}" stroke-width="13.6" '
        f'stroke-linecap="round"/>'
        f'<path d="{TAIL}" fill="none" stroke="{c["tail"]}" stroke-width="11" '
        f'stroke-linecap="round"/>'
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python -m pytest tests -q`
Expected: `9 passed`

- [ ] **Step 5: Look at it**

Run:
```bash
source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python - <<'EOF'
import os, sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, ".")
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QColor
from PySide6.QtCore import QPointF
app = QApplication([])
import cat as C
C.load_settings = lambda: dict(C.DEFAULTS)
imgs = []
for cid in ("nyx", "nora"):
    w = C.Cat(); w.s["cat"] = cid; w.rebuild_art(); w.t = 1.0
    imgs.append(w.grab().toImage()); w.hide()
out = QImage(sum(i.width() for i in imgs), max(i.height() for i in imgs), QImage.Format_ARGB32)
out.fill(QColor("#DEDEDE")); p = QPainter(out); x = 0
for i in imgs:
    p.drawImage(QPointF(x, 0), i); x += i.width()
p.end(); out.save("/private/tmp/claude-501/-Users-rigvedrs-AI-PersonalProj-Cat/fd48426c-3803-4c71-8dc0-0e08a3fc6dab/scratchpad/tails-live.png"); print("ok")
EOF
```
Then Read the PNG. Expected: both cats with a solid black tail and a visible lighter rim — matching variant C of the approved mock.

- [ ] **Step 6: Commit**

```bash
git add tests/test_art.py cat.py
git commit -m "Give Nyx and Nora black tails with a lighter rim"
```

---

### Task 3: Split the open-eye layer into iris, pupil and gloss

**Files:**
- Modify: `cat.py:151-171` (`_eye_round`, `_eye_slim`, `layer_eyes_open`), `cat.py:197-215` (`CatArt.NAMES`, `__init__`), `cat.py:618-636` (`make_icon`), `cat.py:878-880` (eye painting in `paintEvent`)
- Test: `tests/test_art.py`

**Interfaces:**
- Produces: `layer_eyes_iris(c, style)`, `layer_eyes_pupil(c, style)`, `layer_eyes_gloss(c, style)`; `CatArt.eyes_iris/eyes_pupil/eyes_gloss` renderers and `px["eyes_iris"]`, `px["eyes_pupil"]`, `px["eyes_gloss"]` pixmaps. `eyes_open` no longer exists anywhere.
- Pupil neutral positions are unchanged from today's `_eye_round` / `_eye_slim`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_art.py`:

```python
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python -m pytest tests/test_art.py::test_open_eye_is_three_layers -q`
Expected: FAIL — `assert not hasattr(art, "eyes_open")`.

- [ ] **Step 3: Replace the eye functions**

In `cat.py`, replace everything from `def _eye_round(x, c, d):` through the end of `def layer_eyes_open(c, style):` with:

```python
# Each eye is three layers so the pupil can slide on its own: iris (static),
# pupil (moves with the cursor), gloss (catchlights, pinned to the eye).
# All six take (x, c, d): eye centre x, the cat, and d = +1 left / -1 right.

def _iris_round(x, c, d):
    return (
        f'<ellipse cx="{x}" cy="50" rx="6.6" ry="7.2" fill="{c["eye"]}" '
        f'stroke="{c["line"]}" stroke-width="1.2"/>'
    )


def _pupil_round(x, c, d):
    return f'<ellipse cx="{x + 0.5 * d}" cy="50.6" rx="3.7" ry="4.4" fill="#241F2C"/>'


def _gloss_round(x, c, d):
    return (
        f'<circle cx="{x - 1.8}" cy="47.6" r="2.1" fill="#ffffff"/>'
        f'<circle cx="{x + 2.4}" cy="52.8" r="0.9" fill="#ffffff" opacity="0.75"/>'
    )


def _iris_slim(x, c, d):
    return f'<ellipse cx="{x}" cy="49" rx="6.2" ry="7.8" fill="{c["eye"]}"/>'


def _pupil_slim(x, c, d):
    return f'<ellipse cx="{x}" cy="49" rx="2.7" ry="6.4" fill="#221F2A"/>'


def _gloss_slim(x, c, d):
    return f'<circle cx="{x + 2.4}" cy="45.6" r="1.9" fill="#ffffff"/>'


EYE_PARTS = {
    "round": (_iris_round, _pupil_round, _gloss_round),
    "slim": (_iris_slim, _pupil_slim, _gloss_slim),
}


def _eye_layer(c, style, part):
    fn = EYE_PARTS["slim" if style == "slim" else "round"][part]
    return _svg(fn(46, c, 1) + fn(74, c, -1))


def layer_eyes_iris(c, style):
    return _eye_layer(c, style, 0)


def layer_eyes_pupil(c, style):
    return _eye_layer(c, style, 1)


def layer_eyes_gloss(c, style):
    return _eye_layer(c, style, 2)
```

- [ ] **Step 4: Update `CatArt`**

```python
    NAMES = ("tail", "base", "marks", "face", "blush",
             "eyes_iris", "eyes_pupil", "eyes_gloss", "eyes_shut", "paw_l", "paw_r")
```

and in `__init__` replace `self.eyes_open = make_renderer(layer_eyes_open(cat, eye_style))` with:

```python
        self.eyes_iris = make_renderer(layer_eyes_iris(cat, eye_style))
        self.eyes_pupil = make_renderer(layer_eyes_pupil(cat, eye_style))
        self.eyes_gloss = make_renderer(layer_eyes_gloss(cat, eye_style))
```

- [ ] **Step 5: Update `make_icon` and `paintEvent`**

In `make_icon`, the last render loop becomes:

```python
        for lay in (self.art.face, self.art.eyes_iris, self.art.eyes_pupil,
                    self.art.eyes_gloss, self.art.paw_l, self.art.paw_r):
            if lay:
                lay.render(p, r)
```

In `paintEvent`, replace

```python
        # eyes
        shut = (st in ("pet", "sleep")) or (self.t < self.blink_until)
        p.drawPixmap(top, px["eyes_shut" if shut else "eyes_open"])
```
with
```python
        # eyes
        shut = (st in ("pet", "sleep")) or (self.t < self.blink_until)
        if shut:
            p.drawPixmap(top, px["eyes_shut"])
        else:
            p.drawPixmap(top, px["eyes_iris"])
            p.drawPixmap(top, px["eyes_pupil"])
            p.drawPixmap(top, px["eyes_gloss"])
```

- [ ] **Step 6: Run all tests**

Run: `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python -m pytest tests -q`
Expected: `10 passed`

- [ ] **Step 7: Check nothing else references the old name**

Run: `grep -n "eyes_open\|_eye_round\|_eye_slim" cat.py README.txt`
Expected: only `README.txt:125` (`_eye_round and _eye_slim`) — fix that line to read:

```
functions in EYE_PARTS (iris, pupil and catchlights for each style).
```

- [ ] **Step 8: Commit**

```bash
git add tests/test_art.py cat.py README.txt
git commit -m "Split the open eye into iris, pupil and gloss layers"
```

---

### Task 4: Pupils follow the cursor

**Files:**
- Create: `tests/test_gaze.py`
- Modify: `cat.py:17` (import `QCursor`), `cat.py:301-312` (`GAZE_*`, `DEFAULTS["gaze"]`), `Cat.__init__`, `Cat.build_menu` (Eyes submenu), new `Cat.set_gaze`, `Cat.gaze_anchor`, `Cat.gaze_goal`, `Cat.tick`, `Cat.paintEvent`

**Interfaces:**
- Consumes: `px["eyes_iris"|"eyes_pupil"|"eyes_gloss"]` from Task 3; `Cat.state()`, `Cat.cat_rect()`.
- Produces: module-level `GAZE_MAX`, `GAZE_RANGE_PX`, `gaze_target(dx, dy, scale, eye_style) -> tuple[float, float]`; `Cat.gaze: list[float]` (current eased offset, canvas units); `Cat.gaze_anchor() -> tuple[float, float]` (global px); `Cat.gaze_goal(cursor: QPoint | None = None) -> tuple[float, float]`; `Cat.set_gaze(on: bool)`; setting key `"gaze"`.

- [ ] **Step 1: Write the failing tests**

`tests/test_gaze.py`:

```python
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


def test_menu_has_follow_cursor_toggle(cat_widget):
    menu = cat_widget.build_menu()
    eyes = next(a.menu() for a in menu.actions() if a.text() == "Eyes")
    toggle = next(a for a in eyes.actions() if a.text() == "Follow the cursor")
    assert toggle.isCheckable() and toggle.isChecked()
    toggle.trigger()
    assert cat_widget.s["gaze"] is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python -m pytest tests/test_gaze.py -q`
Expected: FAIL — `KeyError: 'gaze'`, `AttributeError: module 'cat' has no attribute 'gaze_target'`, etc.

- [ ] **Step 3: Add the import and the constants**

`cat.py` line 18-21, add `QCursor` to the QtGui import:

```python
from PySide6.QtGui import (
    QPainter, QColor, QPainterPath, QAction, QActionGroup, QIcon, QPixmap,
    QImage, QFont, QTransform, QCursor,
)
```

Directly above `SIZES = [...]` add:

```python
# How far the pupil may slide (canvas units) while staying inside the iris,
# per eye style, and how far away (px, times the cat's scale) the cursor has
# to be for the eyes to swing all the way over.
GAZE_MAX = {"round": (2.9, 2.8), "slim": (3.5, 1.4)}
GAZE_RANGE_PX = 220.0


def gaze_target(dx, dy, scale, eye_style):
    """Pupil offset for a cursor dx, dy pixels from the point between the eyes."""
    dist = math.hypot(dx, dy)
    if dist < 1.0:
        return 0.0, 0.0
    ramp = min(1.0, dist / (GAZE_RANGE_PX * scale))
    mx, my = GAZE_MAX["slim" if eye_style == "slim" else "round"]
    return dx / dist * ramp * mx, dy / dist * ramp * my
```

In `DEFAULTS` add, after `"eyes": "round",`:

```python
    "gaze": True,
```

- [ ] **Step 4: Add the widget state, helpers and setting action**

In `Cat.__init__`, after `self.drag_dist = 0.0`:

```python
        self.gaze = [0.0, 0.0]   # eased pupil offset, canvas units
```

In `build_menu`, after the `for key, label in EYE_STYLES:` loop (still inside the Eyes submenu, before `size_menu = ...`):

```python
        eye_menu.addSeparator()
        a_gaze = QAction("Follow the cursor", eye_menu, checkable=True)
        a_gaze.setChecked(bool(self.s.get("gaze", True)))
        a_gaze.triggered.connect(self.set_gaze)
        eye_menu.addAction(a_gaze)
```

After `set_eyes`:

```python
    def set_gaze(self, on):
        self.s["gaze"] = bool(on)
        save_settings(self.s)
        self.refresh_tray()
```

In the `# ---- input ----` section, after `over_cat`:

```python
    def gaze_anchor(self):
        """Global pixel position of the point between the eyes."""
        sc = float(self.s["scale"])
        rect = self.cat_rect()
        origin = self.mapToGlobal(QPoint(0, 0))
        return origin.x() + rect.x() + 60.0 * sc, origin.y() + rect.y() + 50.0 * sc

    def gaze_goal(self, cursor=None):
        """Where the pupils want to be. Zero while the eyes are shut for a while
        (petting, sleeping) so they re-centre and then look at the cursor on
        waking. Blinks deliberately don't reset it."""
        if not self.s.get("gaze", True) or self.state() in ("pet", "sleep"):
            return 0.0, 0.0
        if cursor is None:
            cursor = QCursor.pos()
        ax, ay = self.gaze_anchor()
        return gaze_target(cursor.x() - ax, cursor.y() - ay,
                           float(self.s["scale"]), self.s["eyes"])
```

- [ ] **Step 5: Ease in `tick`, translate in `paintEvent`**

In `tick`, directly after `dt = self._interval / 1000.0`:

```python
        # Pupils drift toward the cursor rather than snapping (~110 ms).
        tx, ty = self.gaze_goal()
        k = min(1.0, dt * 9.0)
        self.gaze[0] += (tx - self.gaze[0]) * k
        self.gaze[1] += (ty - self.gaze[1]) * k
```

In `paintEvent`, the open-eye branch from Task 3 becomes:

```python
        else:
            p.drawPixmap(top, px["eyes_iris"])
            p.save()
            p.translate(self.gaze[0] * sc, self.gaze[1] * sc)
            p.drawPixmap(top, px["eyes_pupil"])
            p.restore()
            p.drawPixmap(top, px["eyes_gloss"])
```

- [ ] **Step 6: Run all tests**

Run: `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python -m pytest tests -q`
Expected: `21 passed`

- [ ] **Step 7: See it move**

Run: `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python cat.py`
Move the mouse around the screen: pupils follow, ease rather than snap, a cursor sitting on the cat gives only a small glance. Hover to pet: eyes shut; move off: eyes reopen centred and then swing to the cursor. Right-click → Eyes → untick "Follow the cursor": pupils return to centre. Re-tick it. Quit via the menu.

- [ ] **Step 8: Commit**

```bash
git add tests/test_gaze.py cat.py
git commit -m "Make the pupils follow the cursor, with a menu toggle"
```

---

### Task 5: macOS runtime — typing detection, single instance, settings path, Spaces

**Files:**
- Create: `tests/test_platform.py`
- Modify: `cat.py:8-30` (imports, `IS_MAC`, framework handles), `cat.py:315-319` (`settings_path` → `settings_dir` + migration), `cat.py:395-417` (`single_instance_guard`, `any_key_pressed`), `Cat.__init__`, `Cat.set_on_top`, `Cat.build_menu` (preview item gating); new `mac_seconds_since_keydown`, `apply_mac_window_behaviour`

**Interfaces:**
- Produces: `IS_MAC: bool`; `settings_dir() -> str` (no side effects); `LEGACY_SETTINGS: str`; `settings_path() -> str` (creates the dir, copies legacy once); `mac_seconds_since_keydown() -> float`; `single_instance_guard() -> bool` (macOS: flock on `<settings_dir>/instance.lock`, handle kept in `_mutex_handle`); `apply_mac_window_behaviour(widget) -> None`.

- [ ] **Step 1: Write the failing tests**

`tests/test_platform.py`:

```python
import os

import pytest

import cat as C


def test_settings_dir_windows(monkeypatch):
    monkeypatch.setattr(C, "IS_WIN", True)
    monkeypatch.setattr(C, "IS_MAC", False)
    monkeypatch.setenv("APPDATA", "/fake/appdata")
    assert C.settings_dir() == os.path.join("/fake/appdata", "DesktopCat")


def test_settings_dir_mac(monkeypatch):
    monkeypatch.setattr(C, "IS_WIN", False)
    monkeypatch.setattr(C, "IS_MAC", True)
    assert C.settings_dir() == os.path.expanduser("~/Library/Application Support/DesktopCat")


def test_settings_dir_other(monkeypatch):
    monkeypatch.setattr(C, "IS_WIN", False)
    monkeypatch.setattr(C, "IS_MAC", False)
    assert C.settings_dir() == os.path.expanduser("~/.config/DesktopCat")


def test_legacy_settings_are_copied_once_and_left_in_place(monkeypatch, tmp_path):
    new_dir = tmp_path / "new"
    legacy = tmp_path / "old" / "settings.json"
    legacy.parent.mkdir()
    legacy.write_text('{"cat": "noir"}', encoding="utf-8")
    monkeypatch.setattr(C, "IS_WIN", False)
    monkeypatch.setattr(C, "settings_dir", lambda: str(new_dir))
    monkeypatch.setattr(C, "LEGACY_SETTINGS", str(legacy))

    path = C.settings_path()
    assert path == str(new_dir / "settings.json")
    assert open(path, encoding="utf-8").read() == '{"cat": "noir"}'
    assert legacy.exists()

    # Once the app has saved its own file, the legacy one is never copied again.
    with open(path, "w", encoding="utf-8") as f:
        f.write('{"cat": "nemo"}')
    C.settings_path()
    assert open(path, encoding="utf-8").read() == '{"cat": "nemo"}'


def test_settings_path_has_no_legacy_copy_on_windows(monkeypatch, tmp_path):
    legacy = tmp_path / "old" / "settings.json"
    legacy.parent.mkdir()
    legacy.write_text('{"cat": "noir"}', encoding="utf-8")
    monkeypatch.setattr(C, "IS_WIN", True)
    monkeypatch.setattr(C, "settings_dir", lambda: str(tmp_path / "new"))
    monkeypatch.setattr(C, "LEGACY_SETTINGS", str(legacy))
    assert not os.path.exists(C.settings_path())


@pytest.mark.skipif(not C.IS_MAC, reason="flock guard is macOS only")
def test_single_instance_lock(monkeypatch, tmp_path):
    monkeypatch.setattr(C, "settings_dir", lambda: str(tmp_path))
    monkeypatch.setattr(C, "_mutex_handle", None)
    assert C.single_instance_guard() is True
    assert C.single_instance_guard() is False      # a second cat is refused
    C._mutex_handle.close()
    C._mutex_handle = None
    assert C.single_instance_guard() is True       # ...until the first quits
    C._mutex_handle.close()
    C._mutex_handle = None


@pytest.mark.skipif(not C.IS_MAC, reason="macOS API")
def test_mac_keydown_probe():
    assert C.mac_seconds_since_keydown() >= 0.0
    assert C.any_key_pressed() in (True, False)


def test_mac_window_behaviour_is_safe_offscreen(cat_widget):
    # Under the offscreen platform winId() is not an NSView; the helper must
    # notice it is not on cocoa and do nothing rather than crash.
    assert C.apply_mac_window_behaviour(cat_widget) is None


def test_preview_typing_item_only_off_windows_and_mac(cat_widget, monkeypatch):
    def texts():
        return [a.text() for a in cat_widget.build_menu().actions()]
    monkeypatch.setattr(C, "IS_WIN", False)
    monkeypatch.setattr(C, "IS_MAC", True)
    assert "Preview typing animation" not in texts()
    monkeypatch.setattr(C, "IS_MAC", False)
    assert "Preview typing animation" in texts()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python -m pytest tests/test_platform.py -q`
Expected: FAIL — `AttributeError: module 'cat' has no attribute 'IS_MAC'` / `settings_dir` etc.

- [ ] **Step 3: Platform flags and framework handles**

Replace `cat.py` lines 8-30 (from `import sys` through `_user32 = None`) with:

```python
import sys
import os
import json
import math
import random
import shutil
import time

IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QByteArray, QPoint
from PySide6.QtGui import (
    QPainter, QColor, QPainterPath, QAction, QActionGroup, QIcon, QPixmap,
    QImage, QFont, QTransform, QCursor,
)
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon
from PySide6.QtSvg import QSvgRenderer

_user32 = None   # Windows: user32.dll
_cg = None       # macOS: ApplicationServices (CoreGraphics event timing)
_objc = None     # macOS: the Objective-C runtime, for one NSWindow tweak

if IS_WIN:
    import ctypes
    import winreg
    _user32 = ctypes.windll.user32

if IS_MAC:
    import ctypes
    import ctypes.util
    import fcntl
    try:
        _cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ApplicationServices"))
        _cg.CGEventSourceSecondsSinceLastEventType.restype = ctypes.c_double
        _cg.CGEventSourceSecondsSinceLastEventType.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
    except Exception:
        _cg = None
    try:
        _objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        _objc.sel_registerName.restype = ctypes.c_void_p
        _objc.sel_registerName.argtypes = [ctypes.c_char_p]
    except Exception:
        _objc = None
```

- [ ] **Step 4: Settings directory and legacy copy**

Replace `settings_path()`:

```python
def settings_dir():
    if IS_WIN:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "DesktopCat")
    if IS_MAC:
        return os.path.expanduser("~/Library/Application Support/DesktopCat")
    return os.path.expanduser("~/.config/DesktopCat")


# Where non-Windows builds kept their settings before 2026-09.
LEGACY_SETTINGS = os.path.join(os.path.expanduser("~"), "DesktopCat", "settings.json")


def settings_path():
    folder = settings_dir()
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "settings.json")
    if not IS_WIN and not os.path.exists(path) and os.path.exists(LEGACY_SETTINGS):
        try:
            shutil.copyfile(LEGACY_SETTINGS, path)   # copy, never move
        except Exception:
            pass
    return path
```

- [ ] **Step 5: Typing detection and single instance**

Replace `single_instance_guard()` and `any_key_pressed()`:

```python
def single_instance_guard():
    """Stop a second cat appearing when an impatient user double-clicks twice."""
    global _mutex_handle
    if IS_WIN:
        try:
            k32 = ctypes.windll.kernel32
            _mutex_handle = k32.CreateMutexW(None, False, "DesktopCat_SingleInstance")
            return k32.GetLastError() != 183  # ERROR_ALREADY_EXISTS
        except Exception:
            return True
    if IS_MAC:
        try:
            folder = settings_dir()
            os.makedirs(folder, exist_ok=True)
            f = open(os.path.join(folder, "instance.lock"), "w")
        except Exception:
            return True   # can't lock; better a possible second cat than none
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            f.close()
            return False
        _mutex_handle = f   # held until the process exits
        return True
    return True


def mac_seconds_since_keydown():
    """Seconds since any key went down, system-wide. Like the Windows check
    this only learns *that* a key was pressed, never which one, and needs no
    Accessibility or Input Monitoring permission."""
    if _cg is None:
        return 1e9
    try:
        # kCGEventSourceStateHIDSystemState = 1, kCGEventKeyDown = 10
        return float(_cg.CGEventSourceSecondsSinceLastEventType(1, 10))
    except Exception:
        return 1e9


def any_key_pressed():
    if IS_WIN:
        for vk in VK_CODES:
            if _user32.GetAsyncKeyState(vk) & 0x0001:
                return True
        return False
    if IS_MAC:
        return mac_seconds_since_keydown() < 0.20   # polled every 60 ms
    return False
```

- [ ] **Step 6: Show the cat on every Space**

Directly after `any_key_pressed()` add the block below. It is wrapped in
`if IS_MAC:` because `ctypes` is only imported on Windows/macOS and
`_objc_msg`'s default argument is evaluated at definition time.

```python
if IS_MAC:
    def _objc_msg(receiver, selector, *args, restype=ctypes.c_void_p, argtypes=()):
        proto = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p, *argtypes)
        send = ctypes.cast(_objc.objc_msgSend, proto)
        return send(receiver, _objc.sel_registerName(selector.encode()), *args)

    def apply_mac_window_behaviour(widget):
        """Keep the cat on every desktop (Space) and out of Mission Control's way.

        Qt gives a tool window 'move to active space'; a pet should simply be
        on all of them. Best effort: any failure leaves the default behaviour.
        """
        if _objc is None or QApplication.platformName() != "cocoa":
            return None
        try:
            view = int(widget.winId())            # an NSView* on cocoa
            win = _objc_msg(view, "window")
            if not win:
                return None
            # NSWindowCollectionBehaviorCanJoinAllSpaces | Stationary | FullScreenAuxiliary
            flags = (1 << 0) | (1 << 4) | (1 << 8)
            _objc_msg(win, "setCollectionBehavior:", flags,
                      restype=None, argtypes=(ctypes.c_ulong,))
        except Exception:
            pass
        return None
else:
    def apply_mac_window_behaviour(widget):
        return None
```

In `Cat.__init__`, after `self.show()` add:

```python
        apply_mac_window_behaviour(self)
```

In `set_on_top`, after `self.show()` add the same line (`setWindowFlags`
recreates the native window, so the behaviour has to be set again).

- [ ] **Step 7: Gate the preview item**

In `build_menu`, change `if not IS_WIN:` (the "Preview typing animation" block) to:

```python
        if not IS_WIN and not IS_MAC:
```

- [ ] **Step 8: Run all tests**

Run: `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python -m pytest tests -q`
Expected: `30 passed` (on the Mac; the two `skipif` tests run here).

- [ ] **Step 9: Try it for real**

Run: `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python cat.py`
- Type in any other app: the paws tap. No permission dialog appears.
- Open a second terminal and run the same command: it exits immediately, one cat remains.
- Switch to another desktop (ctrl-→): the cat is there too.
- Right-click: no "Preview typing animation" item.
- `ls ~/Library/Application\ Support/DesktopCat/` shows `settings.json` and `instance.lock`.
- Quit via the menu.

- [ ] **Step 10: Commit**

```bash
git add tests/test_platform.py cat.py
git commit -m "macOS: real typing detection, single instance, settings dir, all Spaces"
```

---

### Task 6: Asset regeneration tool (icon, icns, splash)

**Files:**
- Create: `tools/make_icons.py`
- Regenerate: `cat.ico`, `splash.png`; create: `cat.icns`

**Interfaces:**
- Consumes: `C.CatArt`, `C.get_silhouette()`, `C.CAT_BY_ID["nyx"]`.
- Produces: the three asset files at the repo root. `python tools/make_icons.py` is the only way they are ever regenerated.

- [ ] **Step 1: Write the tool**

`tools/make_icons.py`:

```python
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
```

- [ ] **Step 2: Run it**

Run: `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python tools/make_icons.py`
Expected: three lines with non-zero sizes; `cat.icns` is new; `git status` shows `cat.ico` and `splash.png` modified.

- [ ] **Step 3: Look at the output**

Run:
```bash
cd /private/tmp/claude-501/-Users-rigvedrs-AI-PersonalProj-Cat/fd48426c-3803-4c71-8dc0-0e08a3fc6dab/scratchpad && sips -s format png /Users/rigvedrs/AI/PersonalProj/Cat/cat.icns --out icns.png >/dev/null && sips -s format png /Users/rigvedrs/AI/PersonalProj/Cat/cat.ico --out ico.png >/dev/null && ls -la icns.png ico.png
```
Read `icns.png`, `ico.png` and `/Users/rigvedrs/AI/PersonalProj/Cat/splash.png`. Expected: Nyx with a **black tail** in all three; the icns on a cream rounded square with padding, the ico a bare cat, the splash laid out like the previous one (cat left, "Desktop Cat" / "Waking up..." right).

- [ ] **Step 4: Confirm the app still loads the icon**

Run: `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python -m pytest tests -q`
Expected: `30 passed` (the tool does not touch `cat.py`; this is a regression check).

- [ ] **Step 5: Commit**

```bash
git add tools/make_icons.py cat.ico cat.icns splash.png
git commit -m "Regenerate icon, icns and splash from the artwork (Nyx, black tail)"
```

---

### Task 7: macOS build workflow and the documents

**Files:**
- Create: `.github/workflows/build-macos.yml`
- Modify: `.github/workflows/build-windows.yml` (add `append_body: true`)
- Create: `SEND-THIS-WITH-THE-MAC-FILE.txt`
- Modify: `README.txt`, `BUILD-FROM-MAC.txt`

**Interfaces:**
- Consumes: `cat.icns` from Task 6.
- Produces: artifact `DesktopCat-macos` and release asset `DesktopCat-macos.dmg`.

- [ ] **Step 1: Write the workflow**

`.github/workflows/build-macos.yml`:

```yaml
name: Build macOS app

# Same triggers as the Windows build, so one tag push publishes both files
# on the same release.
on:
  workflow_dispatch:
  push:
    tags: ["v*"]

permissions:
  contents: write

jobs:
  macos:
    runs-on: macos-latest   # Apple Silicon; the .app is arm64-only

    steps:
      - name: Get the code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install PySide6 and PyInstaller
        run: |
          python -m pip install --upgrade pip
          python -m pip install PySide6 pyinstaller

      # No --splash here: PyInstaller's splash screen is Windows/Linux only
      # and the build fails on macOS if you ask for it.
      - name: Build Desktop Cat.app
        run: >
          python -m PyInstaller --noconfirm --windowed
          --name "Desktop Cat" --icon cat.icns
          --osx-bundle-identifier com.rigvedrs.desktopcat
          --exclude-module PySide6.QtQml
          --exclude-module PySide6.QtQuick
          --exclude-module PySide6.QtWebEngineCore
          --exclude-module PySide6.QtMultimedia
          --exclude-module PySide6.Qt3DCore
          --exclude-module PySide6.QtCharts
          --exclude-module PySide6.QtDataVisualization
          cat.py

      # A pet has no Dock icon or menu bar; it lives in the menu-bar tray.
      # Editing Info.plist breaks PyInstaller's ad-hoc signature, so re-sign.
      - name: Hide from the Dock and re-sign
        run: |
          plutil -replace LSUIElement -bool true "dist/Desktop Cat.app/Contents/Info.plist"
          codesign --force --deep --sign - "dist/Desktop Cat.app"

      - name: Make the dmg
        run: |
          mkdir staging
          cp -R "dist/Desktop Cat.app" staging/
          ln -s /Applications staging/Applications
          hdiutil create -volname "Desktop Cat" -srcfolder staging -ov -format UDZO DesktopCat-macos.dmg
          ls -lh DesktopCat-macos.dmg

      - name: Upload the dmg
        uses: actions/upload-artifact@v4
        with:
          name: DesktopCat-macos
          path: DesktopCat-macos.dmg
          if-no-files-found: error

      - name: Publish a download link (only when a tag is pushed)
        if: startsWith(github.ref, 'refs/tags/')
        uses: softprops/action-gh-release@v2
        with:
          files: DesktopCat-macos.dmg
          append_body: true
          body: |
            Mac (Apple Silicon): download DesktopCat-macos.dmg, open it, drag
            Desktop Cat into Applications.

            The first time, macOS will say it can't verify the app. Open
            System Settings > Privacy & Security, scroll down, and click
            "Open Anyway". Once only. Full steps are in
            SEND-THIS-WITH-THE-MAC-FILE.txt.
```

In `.github/workflows/build-windows.yml`, in the final `softprops/action-gh-release@v2` step, add one line under `with:` directly after `files: dist/DesktopCat.exe`:

```yaml
          append_body: true
```

(Without it, whichever workflow finishes second replaces the other's release notes.)

- [ ] **Step 2: Validate the YAML**

Run: `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python -c "import yaml; [yaml.safe_load(open(f)) for f in ('.github/workflows/build-macos.yml', '.github/workflows/build-windows.yml')]; print('yaml ok')"`
Expected: `yaml ok`

- [ ] **Step 3: Write the Mac recipient sheet**

`SEND-THIS-WITH-THE-MAC-FILE.txt`:

```
YOUR DESKTOP CAT (MAC)
======================

Open DesktopCat-macos.dmg and drag "Desktop Cat" onto the Applications
folder next to it. Then open Desktop Cat from Applications (or Launchpad).

A cat appears near the bottom-right of your screen and stays on top of
whatever you're doing. It's on every desktop, so it follows you around.

There is nothing else to install. It needs a Mac with an Apple chip
(M1 or newer, 2020 onwards).


THE FIRST TIME YOU OPEN IT
--------------------------

macOS will say something like "Desktop Cat" Not Opened -- Apple could not
verify it is free of malware. That's what macOS says about any app that
isn't from the App Store. Click Done, then:

   System Settings  >  Privacy & Security
   scroll down to the Security section
   next to "Desktop Cat was blocked", click  Open Anyway
   confirm with your password or Touch ID

You only ever do this once.

If instead macOS says the app is "damaged and can't be opened", open the
Terminal app (Cmd+Space, type Terminal), paste this line and press Return:

   xattr -dr com.apple.quarantine "/Applications/Desktop Cat.app"

Then open Desktop Cat again.


PLAYING WITH IT
---------------

  Type anything            the cat taps its paws along with you
  Move your mouse around   its eyes follow the cursor
  Move your mouse over it  it closes its eyes and hearts float up
  Click it                 a quick pet
  Drag it                  move it anywhere you like
  Leave it alone a while   it falls asleep

Right-click the cat for the menu. You can pick a different cat (there are
four), switch the eyes between round and slim, change the size, and turn
the cursor-following off if it's staring at you.

If the cat is ever in your way, turn on "Click through" in that menu. It
stays visible but your mouse goes straight past it.

To close it: right-click the cat, then Quit.
If you can't find the cat, click the small cat icon at the top-right of
the screen, near the clock.
```

- [ ] **Step 4: Update README.txt**

After line 55 (`with two cats.`) insert:

```

ON A MAC it's the same cat from DesktopCat-macos.dmg: drag it into
Applications, get past the one-time "Open Anyway" step (the steps are in
SEND-THIS-WITH-THE-MAC-FILE.txt), and it lives in the menu bar instead of
the tray. It shows on every desktop/Space. Settings are in:
    ~/Library/Application Support/DesktopCat/settings.json
Apple Silicon only; the app is unsigned, which is why the first-launch
dance exists. Forward SEND-THIS-WITH-THE-MAC-FILE.txt with the dmg.
```

Replace the typing-detection paragraph (lines 109-112) with:

```
Sixteen times a second the app asks the operating system one question:
"has any typing key been pressed since I last asked?" (on Windows) or
"how long since the last key went down?" (on the Mac). It gets back a yes
or no, or a number of seconds. It never learns which key, never stores
anything, and never sends anything anywhere. The only thing it does with
the answer is lift a paw. On the Mac this needs no Accessibility or Input
Monitoring permission.
```

Replace the last paragraph (lines 127-128, "Windows only. ...") with:

```
Windows and macOS. Always-on-top, the typing check, the tray icon and the
single-instance guard each have a small platform-specific branch in cat.py;
everything else is shared. After changing the art, run
    python tools/make_icons.py
to regenerate cat.ico, cat.icns and splash.png.
```

- [ ] **Step 5: Update BUILD-FROM-MAC.txt**

Replace Part 1 (lines 12-30) with:

```
-----------------------------------------------------------------------
PART 1 -- RUN THE CAT ON YOUR MAC (2 minutes)
-----------------------------------------------------------------------

    cd path/to/DesktopCat
    conda activate yolo          # or any env that isn't base
    pip install PySide6
    python cat.py

The cat appears bottom-right. Drag it, hover to pet it, right-click for
the menu. Typing in any app makes the paws tap -- no permission prompt,
because it only asks macOS how long ago the last key went down. Its eyes
follow your cursor. It's on every desktop.

Tests:            python -m pytest tests -q
After art changes: python tools/make_icons.py   (rewrites cat.ico,
                   cat.icns and splash.png -- commit them)

Quit via right-click > Quit. Settings live in
~/Library/Application Support/DesktopCat/.
```

Update the title and intro (lines 1-8) to:

```
BUILDING THE WINDOWS EXE AND THE MAC APP FROM YOUR MAC
======================================================

PyInstaller can't cross-compile: a Windows .exe has to be produced on
Windows, and a Mac .app on a Mac. You don't need a Windows machine though.
GitHub will lend you one for a few minutes, for free, and hand you back
the finished file -- and it builds the Mac app at the same time.

Ignore build.bat entirely -- that was for a Windows laptop. This replaces it.
```

In Part 2 step 2, the file list becomes:

```
       cat.py
       cat.ico
       cat.icns
       splash.png
       .github/workflows/build-windows.yml
       .github/workflows/build-macos.yml
```

Step 3 becomes:

```
3. On GitHub, open the Actions tab.
   Click "Build Windows exe" on the left, then "Run workflow" on the right.
   Do the same for "Build macOS app".
```

Step 5 becomes:

```
5. Scroll to the bottom of each finished run. Under "Artifacts" there's
   DesktopCat-windows (a zip containing DesktopCat.exe) and, on the other
   run, DesktopCat-macos (a zip containing DesktopCat-macos.dmg).
```

In the OPTIONAL section, the sentence starting "The same build runs" becomes:

```
Both builds run, and a few minutes later github.com/YOU/desktop-cat/releases
has direct DesktopCat.exe and DesktopCat-macos.dmg links. Send the link plus
SEND-THIS-WITH-THE-FILE.txt (Windows) or SEND-THIS-WITH-THE-MAC-FILE.txt
(Mac) and you're done.
```

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/build-macos.yml .github/workflows/build-windows.yml SEND-THIS-WITH-THE-MAC-FILE.txt README.txt BUILD-FROM-MAC.txt
git commit -m "Build a macOS dmg in Actions; docs for Mac recipients and local dev"
```

---

### Task 8: Verify on the Mac, ship

**Files:** none new.

- [ ] **Step 1: Full test run**

Run: `source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python -m pytest tests -q`
Expected: `30 passed`

- [ ] **Step 2: Fresh-settings run of the app**

Run: `mv ~/Library/Application\ Support/DesktopCat/settings.json /private/tmp/claude-501/-Users-rigvedrs-AI-PersonalProj-Cat/fd48426c-3803-4c71-8dc0-0e08a3fc6dab/scratchpad/settings.bak 2>/dev/null; source /opt/miniconda3/etc/profile.d/conda.sh && conda activate yolo && python cat.py`

Checklist (all four cats, both eye styles, via the menu):
- Nyx and Nora: black tail with a lighter rim, swaying.
- Eyes follow the cursor across the whole screen; ease, don't snap; small glance when the cursor is on the cat.
- Blink does not twitch the pupils. Pet → eyes shut, hearts. After petting, eyes reopen near centre then swing to the cursor.
- Eyes → "Follow the cursor" off → pupils centre; on → follow again.
- Typing in another app taps the paws. No permission prompt.
- Switch desktops: cat is there. Mission Control: cat stays put.
- Second `python cat.py`: exits, one cat.
- Tray icon in the menu bar shows Nyx with a black tail; its menu works.
- Quit; `settings.json` contains `"cat": "nyx"` and `"gaze": true`.

Restore: `mv /private/tmp/claude-501/-Users-rigvedrs-AI-PersonalProj-Cat/fd48426c-3803-4c71-8dc0-0e08a3fc6dab/scratchpad/settings.bak ~/Library/Application\ Support/DesktopCat/settings.json 2>/dev/null; true`

- [ ] **Step 3: Push and run both workflows by hand**

**Ask the user before pushing** — this is outward-facing.

```bash
git push origin main
gh workflow run "Build macOS app" && gh workflow run "Build Windows exe"
gh run watch
```
Expected: both green. Download the `DesktopCat-macos` artifact, open the dmg, drag to Applications, go through "Open Anyway", launch: cat appears, no Dock icon, menu-bar icon present, typing taps, eyes follow.

- [ ] **Step 4: Tag a release**

**Ask the user first.** There are no tags yet (`git ls-remote --tags origin` is empty), so:

```bash
git tag v1.0 && git push origin v1.0
gh run watch
```
Expected: the release at `github.com/rigvedrs/desktop-cat/releases/tag/v1.0` carries both `DesktopCat.exe` and `DesktopCat-macos.dmg`, with both bodies appended. If one workflow's release step fails with a 422 because both tried to create the release at the same instant, re-run just that job — the second attempt finds the release and uploads.
