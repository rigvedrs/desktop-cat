# Desktop Cat: black tails, cursor-following eyes, macOS support

Date: 2026-09-02

## Goals

1. Nyx (white) and Nora (calico) get black tails. Cats are renamed
   Nyx / Nora / Nemo / Noir.
2. The cat's pupils follow the mouse cursor.
3. `python cat.py` on macOS is a first-class experience (real typing
   detection, single instance, sensible settings path, stays visible across
   Spaces).
4. A macOS build (`DesktopCat-macos.dmg`) is produced by GitHub Actions
   alongside the Windows exe and shared directly with friends on
   Apple Silicon Macs. Unsigned; a plain-language instruction file covers
   the Gatekeeper dialog.
5. The app icon (Windows `.ico`, macOS `.icns`) and the splash are
   regenerated from the live artwork so they show Nyx with her new tail.

## Non-goals

- Code signing / notarization. Not an official release; friends only.
- Intel Mac support. Build is arm64-only.
- "Start at login" on macOS. Stays Windows-only.
- Any change to the bitmap-cache rendering architecture, the four-cat
  roster, the two eye styles, or the sleep/pet/type state machine.

---

## 1. Artwork and naming

### 1.1 Tails

Add an optional `tail_line` key to each entry in `CATS`. `layer_tail()`
uses `c.get("tail_line", c["line"])` for the outline stroke. The outline
stroke is still drawn *under* the fur stroke (existing fixed bug — do not
reorder).

| cat  | `tail`    | `tail_line` |
|------|-----------|-------------|
| Nyx  | `#2E2A33` | `#6E6880`   |
| Nora | `#332F38` | `#6E6880`   |
| Nemo | unchanged | (absent → `line`) |
| Noir | unchanged | (absent → `line`) |

`#2E2A33` / `#332F38` are the cats' own existing dark mark colours.
`#6E6880` is the lighter rim Noir already uses so a black tail reads as a
shape against both the pale body and a dark wallpaper (variant C, approved).

### 1.2 Names and ids

| old id      | new id | name |
|-------------|--------|------|
| `mochi`     | `nyx`  | Nyx  |
| `patches`   | `nora` | Nora |
| `marmalade` | `nemo` | Nemo |
| `noir`      | `noir` | Noir |

`DEFAULTS["cat"]` becomes `"nyx"`.

`LEGACY_CAT_IDS = {"mochi": "nyx", "patches": "nora", "marmalade": "nemo"}`
is applied in `load_settings()` before the "unknown id → default" check, so
an existing `settings.json` keeps the same cat.

`README.txt` line 46 is updated to the new names.

### 1.3 Asset regeneration tool

New file `tools/make_icons.py`. Run on the Mac from the `yolo` conda env.
It imports `cat.py`, renders **Nyx, round eyes** (the white cat, per the
user) and writes:

- `cat.ico` — sizes 16, 24, 32, 48, 64, 128, 256; cat on transparent
  background, no tile (Windows convention). Written with Pillow (dev-only
  dependency of the tool, not of the app).
- `cat.icns` — sizes 16…1024 (`iconset` naming incl. `@2x`), built with
  `iconutil -c icns`. The cat sits centred on a cream `#F8F6F2` rounded
  square (corner radius 22% of the side) so it looks native in the Dock and
  Finder, with ~10% padding.
- `splash.png` — 340×190, background `#F8F6F2`, Nyx at left, "Desktop Cat"
  (dark, ~22pt) and "Waking up…" (grey, ~14pt) at right, matching the
  current splash layout.

The three generated files are committed. The script is the source of truth
whenever the art changes again.

---

## 2. Cursor-following eyes

### 2.1 Layers

`layer_eyes_open` is replaced by three full-canvas layers so only the
pupils move while the cache architecture stays intact:

| layer        | contents (per eye)                                   |
|--------------|------------------------------------------------------|
| `eyes_iris`  | iris ellipse (+ its stroke for the round style)      |
| `eyes_pupil` | dark pupil at its neutral position                   |
| `eyes_gloss` | white catchlight(s)                                  |

Neutral pupil positions are exactly the current ones (round style keeps its
`0.5 * d` inward convergence). Paint order: iris → pupil (translated by the
gaze offset) → gloss. Catchlights stay pinned to the eye.

`CatArt.NAMES` becomes
`("tail", "base", "marks", "face", "blush", "eyes_iris", "eyes_pupil",
"eyes_gloss", "eyes_shut", "paw_l", "paw_r")`. `make_icon()` draws the
three eye layers at neutral.

### 2.2 Gaze computation

Runs in `tick()` every frame, only when the eyes will be open
(`state()` not in `("pet", "sleep")` and not mid-blink) and the `gaze`
setting is on; otherwise the target is `(0, 0)`.

```
GAZE_MAX = {"round": (2.9, 2.8), "slim": (3.5, 1.4)}   # canvas units
GAZE_RANGE_PX = 220                                    # × scale

anchor  = window top-left + cat rect origin + (60, 50) * scale   # global px,
                                                                # midpoint between the eyes
d       = QCursor.pos() - anchor
dist    = hypot(d)
if dist < 1:  target = (0, 0)
else:
    ramp   = min(1.0, dist / (GAZE_RANGE_PX * scale))
    mx, my = GAZE_MAX[eye_style]
    target = (d.x / dist * ramp * mx,  d.y / dist * ramp * my)

gaze += (target - gaze) * min(1.0, dt * 9.0)          # ~110 ms ease
```

Both pupils receive the same offset. `GAZE_MAX` values are the largest
offsets at which the pupil ellipse still lies fully inside the iris ellipse
(approved: "stays inside iris").

The cursor is read with `QCursor.pos()` — cross-platform, no extra API, no
permission.

### 2.3 Painting

In `paintEvent`, after `eyes_iris`, the `eyes_pupil` pixmap is drawn inside
a `save()/translate(gaze.x * sc, gaze.y * sc)/restore()`; then `eyes_gloss`.
When `shut` is true, `eyes_shut` is drawn instead of all three, as today.

### 2.4 Behaviour rules

- Mouse movement does **not** count as activity. `last_active` is still
  updated only by typing and petting, so the cat naps after 90 s as before.
- Tracking has no effect while eyes are shut (pet, sleep, blink); no extra
  state.
- New setting `"gaze": True` in `DEFAULTS`, persisted like the others. New
  checkable action **"Follow the cursor"** at the bottom of the Eyes
  submenu. When off, the pupil offset eases back to neutral.

---

## 3. macOS runtime

### 3.1 Platform flags

`IS_MAC = sys.platform == "darwin"` alongside `IS_WIN`. Windows-only
imports stay guarded by `IS_WIN`; Mac-only `ctypes` handles are created
under `IS_MAC` at import time, each wrapped in `try/except` so a failure
degrades to "feature off", never a crash.

### 3.2 Typing detection

`any_key_pressed()` gains a macOS branch:

```
_cg = ctypes.cdll.LoadLibrary(ctypes.util.find_library("ApplicationServices"))
_cg.CGEventSourceSecondsSinceLastEventType.restype  = c_double
_cg.CGEventSourceSecondsSinceLastEventType.argtypes = [c_uint32, c_uint32]
# kCGEventSourceStateHIDSystemState = 1, kCGEventKeyDown = 10
secs = _cg.CGEventSourceSecondsSinceLastEventType(1, 10)
return secs < 0.20
```

Polled on the existing 60 ms `key_timer`. Verified on this machine: no
Input Monitoring / Accessibility prompt, no new dependency. Like the
Windows path it only learns *that* a key went down, never *which* — the
privacy statement in `README.txt` stays literally true on both platforms.

The **"Preview typing animation"** menu item is shown only when
`not IS_WIN and not IS_MAC` (i.e. Linux), since the Mac no longer needs it.

### 3.3 Single instance

On macOS `single_instance_guard()` opens `<settings dir>/instance.lock` and
takes `fcntl.flock(LOCK_EX | LOCK_NB)`. The file handle is kept in the
module-level `_mutex_handle` for the process lifetime. On failure to lock,
return `False` (a cat is already running). Any other exception → `True`.

### 3.4 Settings path

`settings_path()`:

- Windows: `%APPDATA%\DesktopCat\settings.json` (unchanged).
- macOS: `~/Library/Application Support/DesktopCat/settings.json`.
- Other: `~/.config/DesktopCat/settings.json` (was `~/DesktopCat/`).

One-time migration: if the new file does not exist and the legacy
`~/DesktopCat/settings.json` does, copy it to the new location (leave the
old file in place; no deletion).

### 3.5 Window behaviour on macOS

After the window is first shown, `apply_mac_window_behaviour()` uses
`objc_msgSend` via `ctypes` to fetch the `NSWindow` from `winId()` (an
`NSView*`) and set
`collectionBehavior = CanJoinAllSpaces (1<<0) | Stationary (1<<4) |
FullScreenAuxiliary (1<<8)`. Verified on this machine (readback `0x111`).
Effect: the cat is visible on every desktop/Space and is not swept by
Mission Control. Best-effort: wrapped in `try/except`, and re-applied
whenever `setWindowFlags()` recreates the native window (`set_on_top`).

`reassert_top()` remains Windows-only; Qt's stay-on-top hint is sufficient
on macOS.

The existing `WA_MacAlwaysShowToolWindow` attribute stays.

### 3.6 Menu on macOS

Same menu as Windows minus **"Start with Windows"**. The tray icon appears
in the menu bar (Qt handles this); left- or right-click opens the menu.

---

## 4. macOS packaging

### 4.1 Workflow

New file `.github/workflows/build-macos.yml`. The Windows workflow is not
modified. Triggers are identical (`workflow_dispatch`, tags `v*`), so one
tag push produces both downloads on the same GitHub Release
(`softprops/action-gh-release@v2` appends to an existing release).

Steps on `macos-latest` (arm64), Python 3.12:

1. `pip install PySide6 pyinstaller`
2. `python -m PyInstaller --noconfirm --windowed --name "Desktop Cat"
   --icon cat.icns --osx-bundle-identifier com.rigvedrs.desktopcat`
   plus the same `--exclude-module` list as Windows. **No `--splash`** —
   PyInstaller's splash is Windows/Linux only and fails the build on macOS.
   `--onedir` (the default) is used; inside an `.app` it starts faster
   than `--onefile`.
3. `plutil -replace LSUIElement -bool true
   "dist/Desktop Cat.app/Contents/Info.plist"` — no Dock icon, no menu bar;
   the pet is controlled from the tray menu.
4. `codesign --force --deep --sign - "dist/Desktop Cat.app"` — ad-hoc
   re-sign, required because step 3 invalidated PyInstaller's own ad-hoc
   signature.
5. Stage a folder containing `Desktop Cat.app` and a symlink named
   `Applications` → `/Applications`; `hdiutil create -volname "Desktop Cat"
   -srcfolder <staging> -ov -format UDZO DesktopCat-macos.dmg`.
6. Report the size; upload artifact `DesktopCat-macos`; on a tag, attach
   `DesktopCat-macos.dmg` to the release with a body that points to the
   Gatekeeper instructions.

`cat.py` keeps the `pyi_splash` try/except; on macOS the import simply
fails and is ignored.

### 4.2 Recipient instructions

New file `SEND-THIS-WITH-THE-MAC-FILE.txt`, same tone as the Windows one:

1. Open the `.dmg`, drag *Desktop Cat* onto *Applications*.
2. First launch: macOS will say the app "could not be verified" / is from
   an unidentified developer. Click *Done*, open **System Settings →
   Privacy & Security**, scroll down, click **Open Anyway** next to Desktop
   Cat, then confirm. This is once only.
3. If macOS says the app is "damaged", open Terminal and paste
   `xattr -dr com.apple.quarantine "/Applications/Desktop Cat.app"`.
4. The cat lives in the menu bar (top right); click its icon for the menu.

`README.txt` gets a short macOS paragraph (where the settings live, how
to quit, that it appears on every desktop). `BUILD-FROM-MAC.txt` gets a
"local dev" section: `conda activate yolo`, `pip install PySide6`,
`python cat.py`, and `python tools/make_icons.py` after art changes.

---

## 5. Testing

Automated (`tests/test_render.py`, run with `QT_QPA_PLATFORM=offscreen`,
plain `pytest`):

- Every cat × every eye style rasterises all layers without error and
  every pixmap is non-empty.
- Nyx's and Nora's tail layer contains no pixel of the old fur colour and
  does contain `#2E2A33` / `#332F38`.
- `load_settings()` maps each legacy id to its new id and leaves unknown
  ids at the default.
- Gaze math: `(0,0)` for a cursor on the anchor; exactly `GAZE_MAX` at a
  far cursor along each axis; sign correct; offsets never exceed
  `GAZE_MAX` for random cursor positions.
- Gaze target is `(0,0)` when the setting is off.
- `settings_path()` returns the platform-specific location.

Manual on the Mac (documented in the plan as a checklist):

- Eyes track the cursor around the screen, ease rather than snap, close on
  pet/blink/sleep, and the menu toggle turns tracking off.
- Typing in another app makes the paws tap without any permission dialog.
- Launching `cat.py` twice yields one cat.
- Switching desktops keeps the cat visible.
- The DMG from Actions installs and launches after the "Open Anyway" step.

---

## 6. Files touched

| file | change |
|------|--------|
| `cat.py` | tails, names/ids + migration, eye layer split, gaze, `gaze` setting + menu item, `IS_MAC`, mac typing detection, lockfile, settings path + migration, `apply_mac_window_behaviour` |
| `tools/make_icons.py` | new — regenerates `cat.ico`, `cat.icns`, `splash.png` |
| `cat.ico`, `splash.png` | regenerated |
| `cat.icns` | new, generated |
| `tests/test_render.py` | new |
| `.github/workflows/build-macos.yml` | new |
| `SEND-THIS-WITH-THE-MAC-FILE.txt` | new |
| `README.txt`, `BUILD-FROM-MAC.txt` | names, macOS notes, dev section |
