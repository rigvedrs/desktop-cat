"""
Desktop Cat -- a small always-on-top cat that sits on your screen.

It reacts when you type, purrs when you pet it, and naps when you go quiet.
Right-click the cat (or its tray icon) to change cat, eyes, and size.
"""

import sys
import os
import json
import math
import random
import time

IS_WIN = sys.platform.startswith("win")

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QByteArray, QPoint
from PySide6.QtGui import (
    QPainter, QColor, QPainterPath, QAction, QActionGroup, QIcon, QPixmap,
    QImage, QFont, QTransform,
)
from PySide6.QtWidgets import QApplication, QWidget, QMenu, QSystemTrayIcon
from PySide6.QtSvg import QSvgRenderer

if IS_WIN:
    import ctypes
    import winreg
    _user32 = ctypes.windll.user32
else:
    _user32 = None


# --------------------------------------------------------------------------
# Cat artwork
# --------------------------------------------------------------------------
# Everything is drawn on a 120 x 132 canvas and scaled up at paint time,
# so the cat stays crisp at any size.

BODY = ("M60 54 C41 54 27 78 25 104 C24 114 31 120 42 120 "
        "L78 120 C89 120 96 114 95 104 C93 78 79 54 60 54 Z")
EAR_L = "M31 36 L27 5 L59 22 Z"
EAR_R = "M89 36 L93 5 L61 22 Z"
TAIL = "M92 112 C117 110 115 78 100 66"

CATS = [
    {
        "id": "mochi",
        "name": "Mochi",
        "fur": "#F6F3EC", "belly": "#FFFFFF", "tail": "#F6F3EC",
        "line": "#4A4550", "ear": "#F0C3BE", "eye": "#EFC44B",
        "marks": (
            '<ellipse cx="47" cy="24" rx="15" ry="10.5" '
            'transform="rotate(-14 47 24)" fill="#2E2A33"/>'
            '<ellipse cx="36" cy="17" rx="8" ry="7" fill="#2E2A33"/>'
        ),
    },
    {
        "id": "patches",
        "name": "Patches",
        "fur": "#F7F4EE", "belly": "#FFFFFF", "tail": "#E8913C",
        "line": "#4A4550", "ear": "#F0C3BE", "eye": "#57996A",
        "marks": (
            '<path d="M63 4 L98 2 L102 42 Q82 44 68 26 Z" fill="#E8913C"/>'
            '<ellipse cx="89" cy="67" rx="9" ry="8" fill="#E8913C"/>'
            '<ellipse cx="32" cy="98" rx="15" ry="19" fill="#E8913C"/>'
            '<ellipse cx="53" cy="87" rx="10" ry="8" fill="#E8913C"/>'
            '<ellipse cx="34" cy="18" rx="17" ry="14" fill="#332F38"/>'
            '<ellipse cx="25" cy="44" rx="9" ry="12" fill="#332F38"/>'
            '<ellipse cx="66" cy="21" rx="8" ry="6" fill="#332F38"/>'
            '<ellipse cx="88" cy="90" rx="13" ry="15" fill="#332F38"/>'
            '<ellipse cx="37" cy="78" rx="9" ry="7" fill="#332F38"/>'
        ),
    },
    {
        "id": "marmalade",
        "name": "Marmalade",
        "fur": "#F2A03D", "belly": "#FDEBD2", "tail": "#F2A03D",
        "line": "#8C4E17", "ear": "#EFB1A6", "eye": "#9A6430",
        "marks": (
            '<path d="M46 18 L48 31 M60 15 L60 30 M74 18 L72 31" '
            'stroke="#D2762A" stroke-width="4.5" stroke-linecap="round" fill="none"/>'
            '<path d="M28 86 L44 84 M27 99 L45 97" '
            'stroke="#D2762A" stroke-width="4.5" stroke-linecap="round" fill="none"/>'
            '<ellipse cx="60" cy="63" rx="17" ry="9.5" fill="#FDEBD2"/>'
        ),
    },
    {
        "id": "noir",
        "name": "Noir",
        "fur": "#35323C", "belly": "#433F4D", "tail": "#35323C",
        "line": "#6E6880", "ear": "#8A6A72", "eye": "#F5C74F",
        "marks": "",
    },
]

CAT_BY_ID = {c["id"]: c for c in CATS}

EYE_STYLES = [("round", "Round pupils"), ("slim", "Slim pupils")]


def _svg(inner):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 132">'
            + inner + '</svg>')


def layer_tail(c):
    return _svg(
        f'<path d="{TAIL}" fill="none" stroke="{c["line"]}" stroke-width="13.6" '
        f'stroke-linecap="round"/>'
        f'<path d="{TAIL}" fill="none" stroke="{c["tail"]}" stroke-width="11" '
        f'stroke-linecap="round"/>'
    )


def layer_base(c):
    return _svg(
        f'<path d="{BODY}" fill="{c["fur"]}" stroke="{c["line"]}" stroke-width="1.6"/>'
        f'<ellipse cx="60" cy="101" rx="23" ry="18" fill="{c["belly"]}"/>'
        f'<path d="{EAR_L}" fill="{c["fur"]}" stroke="{c["line"]}" stroke-width="1.6" '
        f'stroke-linejoin="round"/>'
        f'<path d="{EAR_R}" fill="{c["fur"]}" stroke="{c["line"]}" stroke-width="1.6" '
        f'stroke-linejoin="round"/>'
        f'<path d="M36 30 L34 13 L52 23 Z" fill="{c["ear"]}"/>'
        f'<path d="M84 30 L86 13 L68 23 Z" fill="{c["ear"]}"/>'
        f'<ellipse cx="60" cy="48" rx="33" ry="29" fill="{c["fur"]}" '
        f'stroke="{c["line"]}" stroke-width="1.6"/>'
    )


def layer_marks(c):
    return _svg(c["marks"]) if c["marks"] else None


def layer_face(c):
    return _svg(
        f'<path d="M56 59.5 L64 59.5 L60 64.5 Z" fill="#E48B9B"/>'
        f'<path d="M60 64.5 Q56 69 52 66 M60 64.5 Q64 69 68 66" fill="none" '
        f'stroke="{c["line"]}" stroke-width="1.8" stroke-linecap="round"/>'
        f'<path d="M27 58 L12 54 M27 63 L12 64 M93 58 L108 54 M93 63 L108 64" '
        f'stroke="{c["line"]}" stroke-width="1.5" stroke-linecap="round" opacity="0.45"/>'
    )


def layer_blush(c):
    return _svg(
        '<ellipse cx="33" cy="59" rx="6.5" ry="4" fill="#EC8FA4" opacity="0.75"/>'
        '<ellipse cx="87" cy="59" rx="6.5" ry="4" fill="#EC8FA4" opacity="0.75"/>'
    )


def _eye_round(x, c, d):
    return (
        f'<ellipse cx="{x}" cy="50" rx="6.6" ry="7.2" fill="{c["eye"]}" '
        f'stroke="{c["line"]}" stroke-width="1.2"/>'
        f'<ellipse cx="{x + 0.5 * d}" cy="50.6" rx="3.7" ry="4.4" fill="#241F2C"/>'
        f'<circle cx="{x - 1.8}" cy="47.6" r="2.1" fill="#ffffff"/>'
        f'<circle cx="{x + 2.4}" cy="52.8" r="0.9" fill="#ffffff" opacity="0.75"/>'
    )


def _eye_slim(x, c, d):
    return (
        f'<ellipse cx="{x}" cy="49" rx="6.2" ry="7.8" fill="{c["eye"]}"/>'
        f'<ellipse cx="{x}" cy="49" rx="2.7" ry="6.4" fill="#221F2A"/>'
        f'<circle cx="{x + 2.4}" cy="45.6" r="1.9" fill="#ffffff"/>'
    )


def layer_eyes_open(c, style):
    fn = _eye_slim if style == "slim" else _eye_round
    return _svg(fn(46, c, 1) + fn(74, c, -1))


def layer_eyes_shut(c):
    return _svg(
        '<path d="M40 52 Q46 45 52 52 M68 52 Q74 45 80 52" fill="none" '
        'stroke="#2A2632" stroke-width="3" stroke-linecap="round"/>'
    )


def layer_paw(c, x):
    return _svg(
        f'<rect x="{x}" y="106" width="21" height="14" rx="7" fill="{c["fur"]}" '
        f'stroke="{c["line"]}" stroke-width="1.6"/>'
        f'<path d="M{x + 7} 108 L{x + 7} 113 M{x + 14} 108 L{x + 14} 113" '
        f'stroke="{c["line"]}" stroke-width="1.3" stroke-linecap="round" opacity="0.35"/>'
    )


def make_renderer(svg_text):
    if svg_text is None:
        return None
    r = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
    return r if r.isValid() else None


class CatArt:
    """The SVG layers for one cat, plus bitmaps cached at the display size."""

    NAMES = ("tail", "base", "marks", "face", "blush",
             "eyes_open", "eyes_shut", "paw_l", "paw_r")

    def __init__(self, cat, eye_style):
        self.cat = cat
        self.tail = make_renderer(layer_tail(cat))
        self.base = make_renderer(layer_base(cat))
        self.marks = make_renderer(layer_marks(cat))
        self.face = make_renderer(layer_face(cat))
        self.blush = make_renderer(layer_blush(cat))
        self.eyes_open = make_renderer(layer_eyes_open(cat, eye_style))
        self.eyes_shut = make_renderer(layer_eyes_shut(cat))
        self.paw_l = make_renderer(layer_paw(cat, 35))
        self.paw_r = make_renderer(layer_paw(cat, 64))
        self.px = {}
        self._key = None

    def rasterize(self, w, h, dpr):
        """Draw each layer into a bitmap once, so painting is just a blit.

        Re-rasterising SVG on every frame is what makes desktop pets eat
        battery on slow machines. This keeps the paint loop nearly free.
        """
        key = (round(w), round(h), round(dpr, 2))
        if key == self._key:
            return
        self._key = key
        self.px = {}
        pw, ph = max(1, int(w * dpr)), max(1, int(h * dpr))
        clip = None
        for name in self.NAMES:
            r = getattr(self, name)
            if r is None:
                continue
            pm = QPixmap(pw, ph)
            pm.setDevicePixelRatio(dpr)
            pm.fill(Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing, True)
            if name == "marks":
                if clip is None:
                    tf = QTransform().scale(w / 120.0, h / 132.0)
                    clip = tf.map(QPainterPath(get_silhouette()))
                p.setClipPath(clip)
            r.render(p, QRectF(0, 0, w, h))
            p.end()
            self.px[name] = pm


def silhouette_path():
    """The cat outline, used to clip markings so they never spill over."""
    p = QPainterPath()
    p.moveTo(60, 54)
    p.cubicTo(41, 54, 27, 78, 25, 104)
    p.cubicTo(24, 114, 31, 120, 42, 120)
    p.lineTo(78, 120)
    p.cubicTo(89, 120, 96, 114, 95, 104)
    p.cubicTo(93, 78, 79, 54, 60, 54)
    p.closeSubpath()

    head = QPainterPath()
    head.addEllipse(QPointF(60, 48), 33, 29)

    ear_l = QPainterPath()
    ear_l.moveTo(31, 36)
    ear_l.lineTo(27, 5)
    ear_l.lineTo(59, 22)
    ear_l.closeSubpath()

    ear_r = QPainterPath()
    ear_r.moveTo(89, 36)
    ear_r.lineTo(93, 5)
    ear_r.lineTo(61, 22)
    ear_r.closeSubpath()

    return p.united(head).united(ear_l).united(ear_r)


_SIL = None


def get_silhouette():
    global _SIL
    if _SIL is None:
        _SIL = silhouette_path()
    return _SIL


def heart_path(cx, cy, s):
    p = QPainterPath()
    p.moveTo(cx, cy + 0.75 * s)
    p.cubicTo(cx - 1.5 * s, cy - 0.1 * s, cx - 0.62 * s, cy - 1.0 * s, cx, cy - 0.32 * s)
    p.cubicTo(cx + 0.62 * s, cy - 1.0 * s, cx + 1.5 * s, cy - 0.1 * s, cx, cy + 0.75 * s)
    p.closeSubpath()
    return p


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------

SIZES = [("Small", 1.2), ("Medium", 1.6), ("Large", 2.2)]

DEFAULTS = {
    "cat": "mochi",
    "eyes": "round",
    "scale": 1.6,
    "x": None,
    "y": None,
    "on_top": True,
    "click_through": False,
    "seen_tip": False,
}


def settings_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, "DesktopCat")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "settings.json")


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(settings_path(), "r", encoding="utf-8") as f:
            s.update(json.load(f))
    except Exception:
        pass
    if s.get("cat") not in CAT_BY_ID:
        s["cat"] = DEFAULTS["cat"]
    if s.get("eyes") not in ("round", "slim"):
        s["eyes"] = DEFAULTS["eyes"]
    return s


def save_settings(s):
    try:
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)
    except Exception:
        pass


def autostart_enabled():
    if not IS_WIN:
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
        try:
            winreg.QueryValueEx(key, "DesktopCat")
            return True
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


def set_autostart(on):
    if not IS_WIN:
        return
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        try:
            if on:
                winreg.SetValueEx(key, "DesktopCat", 0, winreg.REG_SZ,
                                  f'"{sys.executable}"')
            else:
                try:
                    winreg.DeleteValue(key, "DesktopCat")
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(key)
    except Exception:
        pass


# --------------------------------------------------------------------------
# Global typing detection (Windows)
# --------------------------------------------------------------------------
# Polls whether any typing key has been pressed since the last check.
# It never records which key, and nothing is stored or sent anywhere.

VK_CODES = list(range(0x30, 0x5B))                      # 0-9 and A-Z
VK_CODES += [0x08, 0x09, 0x0D, 0x20]                    # backspace, tab, enter, space
VK_CODES += [0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF, 0xC0]  # ; = , - . / `
VK_CODES += [0xDB, 0xDC, 0xDD, 0xDE]                    # [ \ ] '
VK_CODES += list(range(0x60, 0x70))                     # numpad


_mutex_handle = None


def single_instance_guard():
    """Stop a second cat appearing when an impatient user double-clicks twice."""
    global _mutex_handle
    if not IS_WIN:
        return True
    try:
        k32 = ctypes.windll.kernel32
        _mutex_handle = k32.CreateMutexW(None, False, "DesktopCat_SingleInstance")
        return k32.GetLastError() != 183  # ERROR_ALREADY_EXISTS
    except Exception:
        return True


def any_key_pressed():
    if not IS_WIN:
        return False
    for vk in VK_CODES:
        if _user32.GetAsyncKeyState(vk) & 0x0001:
            return True
    return False


# --------------------------------------------------------------------------
# The cat window
# --------------------------------------------------------------------------

class Cat(QWidget):
    MARGIN_TOP = 62      # headroom for hearts and Zzz
    MARGIN_SIDE = 26

    def __init__(self):
        super().__init__()
        self.s = load_settings()
        self.art = None
        self.hearts = []
        self.t = 0.0
        self.blink_at = 3.0
        self.blink_until = -1.0
        self.typing_until = -1.0
        self.pet_until = -1.0
        self.last_heart = -1.0
        self.last_active = time.monotonic()
        self.pet_travel = 0.0
        self.pet_travel_at = 0.0
        self.drag_from = None
        self.drag_dist = 0.0

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        if not IS_WIN:
            # macOS hides tool windows when the app loses focus; this keeps
            # the preview on screen while you click around.
            attr = getattr(Qt, "WA_MacAlwaysShowToolWindow", None)
            if attr is not None:
                self.setAttribute(attr, True)

        self.rebuild_art()
        self.apply_geometry(first=True)
        self.apply_click_through()

        self.tray = None
        self.build_tray()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)
        self._interval = 33

        self.key_timer = QTimer(self)
        self.key_timer.timeout.connect(self.poll_keys)
        self.key_timer.start(60)

        self.top_timer = QTimer(self)
        self.top_timer.timeout.connect(self.reassert_top)
        self.top_timer.start(4000)

        self.show()

    # ---- setup -----------------------------------------------------------

    def rebuild_art(self):
        self.art = CatArt(CAT_BY_ID[self.s["cat"]], self.s["eyes"])

    def cat_size(self):
        sc = float(self.s["scale"])
        return 120.0 * sc, 132.0 * sc

    def apply_geometry(self, first=False):
        cw, ch = self.cat_size()
        w = int(cw + self.MARGIN_SIDE * 2)
        h = int(ch + self.MARGIN_TOP)

        if first and (self.s["x"] is None or self.s["y"] is None):
            scr = QApplication.primaryScreen().availableGeometry()
            x = scr.right() - w - 40
            y = scr.bottom() - h + 10
        else:
            x, y = int(self.s["x"]), int(self.s["y"])

        self.setGeometry(x, y, w, h)
        self.clamp_to_screen()

    def clamp_to_screen(self):
        scr = QApplication.primaryScreen().availableGeometry()
        g = self.geometry()
        x = min(max(g.x(), scr.left() - g.width() // 3), scr.right() - g.width() // 3)
        y = min(max(g.y(), scr.top() - 10), scr.bottom() - g.height() // 3)
        if (x, y) != (g.x(), g.y()):
            self.move(x, y)

    def apply_click_through(self):
        self.setAttribute(Qt.WA_TransparentForMouseEvents, bool(self.s["click_through"]))

    def reassert_top(self):
        if not (IS_WIN and self.s["on_top"]):
            return
        try:
            HWND_TOPMOST = -1
            SWP = 0x0001 | 0x0002 | 0x0010  # NOSIZE | NOMOVE | NOACTIVATE
            _user32.SetWindowPos(int(self.winId()), HWND_TOPMOST, 0, 0, 0, 0, SWP)
        except Exception:
            pass

    # ---- menu ------------------------------------------------------------

    def build_menu(self):
        m = QMenu(self)

        cat_menu = m.addMenu("Cat")
        g1 = QActionGroup(cat_menu)
        g1.setExclusive(True)
        for c in CATS:
            a = QAction(c["name"], cat_menu, checkable=True)
            a.setChecked(self.s["cat"] == c["id"])
            a.triggered.connect(lambda _=False, cid=c["id"]: self.set_cat(cid))
            g1.addAction(a)
            cat_menu.addAction(a)

        eye_menu = m.addMenu("Eyes")
        g2 = QActionGroup(eye_menu)
        g2.setExclusive(True)
        for key, label in EYE_STYLES:
            a = QAction(label, eye_menu, checkable=True)
            a.setChecked(self.s["eyes"] == key)
            a.triggered.connect(lambda _=False, k=key: self.set_eyes(k))
            g2.addAction(a)
            eye_menu.addAction(a)

        size_menu = m.addMenu("Size")
        g3 = QActionGroup(size_menu)
        g3.setExclusive(True)
        for label, val in SIZES:
            a = QAction(label, size_menu, checkable=True)
            a.setChecked(abs(float(self.s["scale"]) - val) < 0.01)
            a.triggered.connect(lambda _=False, v=val: self.set_scale(v))
            g3.addAction(a)
            size_menu.addAction(a)

        m.addSeparator()

        a_top = QAction("Always on top", m, checkable=True)
        a_top.setChecked(bool(self.s["on_top"]))
        a_top.triggered.connect(self.set_on_top)
        m.addAction(a_top)

        a_ct = QAction("Click through (ignore mouse)", m, checkable=True)
        a_ct.setChecked(bool(self.s["click_through"]))
        a_ct.triggered.connect(self.set_click_through)
        m.addAction(a_ct)

        if IS_WIN:
            a_auto = QAction("Start with Windows", m, checkable=True)
            a_auto.setChecked(autostart_enabled())
            a_auto.triggered.connect(set_autostart)
            m.addAction(a_auto)

        m.addSeparator()

        if not IS_WIN:
            a_demo = QAction("Preview typing animation", m)
            a_demo.triggered.connect(self.demo_typing)
            m.addAction(a_demo)

        a_home = QAction("Bring cat back", m)
        a_home.triggered.connect(self.go_home)
        m.addAction(a_home)

        a_quit = QAction("Quit", m)
        a_quit.triggered.connect(self.quit)
        m.addAction(a_quit)
        return m

    def build_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self)
        self.tray.setIcon(self.make_icon())
        self.tray.setToolTip("Desktop Cat")
        self.tray.activated.connect(self.on_tray)
        self.tray.setContextMenu(self.build_menu())
        self.tray.show()
        if not self.s.get("seen_tip"):
            QTimer.singleShot(2500, self.show_first_tip)

    def show_first_tip(self):
        if not self.tray:
            return
        self.s["seen_tip"] = True
        save_settings(self.s)
        self.tray.showMessage(
            "Your cat is here",
            "Drag to move it. Right-click for cats, eyes and sizes.",
            self.make_icon(), 6000)

    def refresh_tray(self):
        if self.tray:
            self.tray.setIcon(self.make_icon())
            self.tray.setContextMenu(self.build_menu())

    def make_icon(self):
        img = QImage(64, 64, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(-4, 2, 72, 72 * 132 / 120)
        for lay in (self.art.tail, self.art.base):
            if lay:
                lay.render(p, r)
        if self.art.marks:
            p.save()
            p.setClipPath(self.scaled_silhouette(r))
            self.art.marks.render(p, r)
            p.restore()
        for lay in (self.art.face, self.art.eyes_open, self.art.paw_l, self.art.paw_r):
            if lay:
                lay.render(p, r)
        p.end()
        return QIcon(QPixmap.fromImage(img))

    def on_tray(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.go_home()

    # ---- settings actions ------------------------------------------------

    def set_cat(self, cid):
        self.s["cat"] = cid
        self.rebuild_art()
        self.refresh_tray()
        save_settings(self.s)
        self.update()

    def set_eyes(self, key):
        self.s["eyes"] = key
        self.rebuild_art()
        self.refresh_tray()
        save_settings(self.s)
        self.update()

    def set_scale(self, val):
        g = self.geometry()
        anchor_x = g.x() + g.width() // 2
        anchor_y = g.y() + g.height()
        self.s["scale"] = val
        cw, ch = self.cat_size()
        w = int(cw + self.MARGIN_SIDE * 2)
        h = int(ch + self.MARGIN_TOP)
        self.setGeometry(anchor_x - w // 2, anchor_y - h, w, h)
        self.clamp_to_screen()
        self.remember_position()
        self.refresh_tray()
        self.update()

    def set_on_top(self, on):
        self.s["on_top"] = bool(on)
        flags = Qt.FramelessWindowHint | Qt.Tool
        if on:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()
        save_settings(self.s)
        self.refresh_tray()

    def set_click_through(self, on):
        self.s["click_through"] = bool(on)
        self.apply_click_through()
        save_settings(self.s)
        self.refresh_tray()

    def go_home(self):
        scr = QApplication.primaryScreen().availableGeometry()
        self.move(scr.right() - self.width() - 40, scr.bottom() - self.height() + 10)
        self.remember_position()
        if self.s["click_through"]:
            self.set_click_through(False)
        self.show()
        self.raise_()

    def demo_typing(self):
        """Off Windows there is no key hook, so this fakes it for previewing."""
        self.typing_until = self.t + 5.0
        self.last_active = time.monotonic()

    def remember_position(self):
        g = self.geometry()
        self.s["x"], self.s["y"] = g.x(), g.y()
        save_settings(self.s)

    def quit(self):
        self.remember_position()
        if self.tray:
            self.tray.hide()
        QApplication.quit()

    # ---- input -----------------------------------------------------------

    def poll_keys(self):
        if any_key_pressed():
            self.typing_until = self.t + 1.1
            self.last_active = time.monotonic()

    def cat_rect(self):
        cw, ch = self.cat_size()
        return QRectF(self.MARGIN_SIDE, self.MARGIN_TOP, cw, ch)

    def over_cat(self, pos):
        return self.cat_rect().contains(QPointF(pos))

    def pet(self, strength=1):
        self.pet_until = self.t + 1.6
        self.last_active = time.monotonic()
        if self.t - self.last_heart > 0.18:
            self.last_heart = self.t
            cw, _ = self.cat_size()
            for _ in range(strength):
                self.hearts.append({
                    "x": self.MARGIN_SIDE + cw * (0.3 + random.random() * 0.4),
                    "y": self.MARGIN_TOP + 24,
                    "vy": 26 + random.random() * 16,
                    "dx": (random.random() - 0.5) * 22,
                    "life": 0.0,
                    "size": 6 + random.random() * 4,
                })

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.over_cat(e.position()):
            self.drag_from = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.drag_dist = 0.0
            e.accept()
        elif e.button() == Qt.RightButton:
            self.build_menu().exec(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self.drag_from is not None and (e.buttons() & Qt.LeftButton):
            new = e.globalPosition().toPoint() - self.drag_from
            self.drag_dist += (new - self.frameGeometry().topLeft()).manhattanLength()
            self.move(new)
            return
        if not e.buttons() and self.over_cat(e.position()):
            now = self.t
            if now - self.pet_travel_at > 0.7:
                self.pet_travel = 0.0
            self.pet_travel_at = now
            self.pet_travel += 6
            if self.pet_travel > 40:
                self.pet_travel = 0.0
                self.pet(2)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.drag_from is not None:
            if self.drag_dist < 6:
                self.pet(4)
            else:
                self.remember_position()
            self.drag_from = None

    def leaveEvent(self, e):
        self.pet_travel = 0.0

    # ---- animation -------------------------------------------------------

    def tick(self):
        self.t += self._interval / 1000.0

        want = 66 if self.state() == "sleep" else 33
        if want != self._interval:
            self._interval = want
            self.timer.start(want)

        if self.t >= self.blink_at and self.t > self.blink_until:
            self.blink_until = self.t + 0.13
            self.blink_at = self.t + 3.5 + random.random() * 3.5

        dt = self._interval / 1000.0
        alive = []
        for h in self.hearts:
            h["life"] += dt
            h["y"] -= h["vy"] * dt
            h["x"] += h["dx"] * dt
            if h["life"] < 1.4:
                alive.append(h)
        self.hearts = alive

        self.update()

    def state(self):
        if self.t < self.pet_until:
            return "pet"
        if self.t < self.typing_until:
            return "type"
        if time.monotonic() - self.last_active > 90:
            return "sleep"
        return "idle"

    def scaled_silhouette(self, rect):
        sx = rect.width() / 120.0
        sy = rect.height() / 132.0
        path = QPainterPath(get_silhouette())
        tf = QTransform().translate(rect.x(), rect.y()).scale(sx, sy)
        return tf.map(path)

    # ---- painting --------------------------------------------------------

    def paintEvent(self, _):
        st = self.state()
        cw, ch = self.cat_size()
        sc = cw / 120.0
        rect = QRectF(self.MARGIN_SIDE, self.MARGIN_TOP, cw, ch)

        self.art.rasterize(cw, ch, self.devicePixelRatioF())
        px = self.art.px
        top = rect.topLeft()

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        # whole-cat motion
        p.save()
        base_x = rect.center().x()
        base_y = rect.bottom()
        if st == "pet":
            wob = math.sin(self.t * 12.0)
            p.translate(base_x, base_y)
            p.rotate(wob * 2.2)
            p.translate(0, abs(wob) * 3.0 * sc)
            p.translate(-base_x, -base_y)
        breathe_speed = 0.9 if st == "sleep" else 1.75
        amp = 0.035 if st == "sleep" else 0.022
        sy = 1.0 + amp * math.sin(self.t * breathe_speed)
        p.translate(0, base_y)
        p.scale(1.0, sy)
        p.translate(0, -base_y)

        # shadow
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(60, 55, 70, 32))
        p.drawEllipse(QPointF(base_x, rect.y() + 125 * sc), 33 * sc, 5 * sc)

        # tail
        tail_speed = 0.7 if st == "sleep" else (3.4 if st == "pet" else 1.5)
        ang = math.sin(self.t * tail_speed) * (11 if st != "sleep" else 5)
        p.save()
        p.translate(rect.x() + 92 * sc, rect.y() + 112 * sc)
        p.rotate(ang)
        p.translate(-(rect.x() + 92 * sc), -(rect.y() + 112 * sc))
        if "tail" in px:
            p.drawPixmap(top, px["tail"])
        p.restore()

        # body, then markings (already clipped to the silhouette when cached)
        p.drawPixmap(top, px["base"])
        if "marks" in px:
            p.drawPixmap(top, px["marks"])
        p.drawPixmap(top, px["face"])

        if st == "pet" and "blush" in px:
            p.drawPixmap(top, px["blush"])

        # eyes
        shut = (st in ("pet", "sleep")) or (self.t < self.blink_until)
        p.drawPixmap(top, px["eyes_shut" if shut else "eyes_open"])

        # paws -- they tap while you type
        lift_l = lift_r = 0.0
        if st == "type":
            lift_l = max(0.0, math.sin(self.t * 15.0)) * 6.0 * sc
            lift_r = max(0.0, math.sin(self.t * 15.0 + math.pi)) * 6.0 * sc
        for name, lift in (("paw_l", lift_l), ("paw_r", lift_r)):
            p.save()
            p.translate(0, -lift)
            p.drawPixmap(top, px[name])
            p.restore()
        p.restore()

        # hearts
        p.setPen(Qt.NoPen)
        for h in self.hearts:
            fade = max(0.0, 1.0 - h["life"] / 1.4)
            p.setBrush(QColor(228, 87, 126, int(235 * fade)))
            grow = 0.7 + 0.5 * min(1.0, h["life"] * 4)
            p.drawPath(heart_path(h["x"], h["y"], h["size"] * sc * grow))

        # Zzz
        if st == "sleep":
            f = QFont()
            f.setPointSizeF(max(9.0, 11.0 * sc))
            f.setWeight(QFont.Medium)
            p.setFont(f)
            for i in range(3):
                ph = (self.t * 0.42 + i * 0.33) % 1.0
                a = int(200 * math.sin(math.pi * ph))
                p.setPen(QColor(120, 114, 140, max(0, a)))
                zx = rect.x() + 92 * sc + ph * 22 * sc
                zy = rect.y() + 22 * sc - ph * 34 * sc
                p.drawText(QPointF(zx, zy), "z")
        p.end()


def main():
    if not single_instance_guard():
        return  # a cat is already on screen
    QApplication.setQuitOnLastWindowClosed(False)
    app = QApplication(sys.argv)
    app.setApplicationName("Desktop Cat")
    cat = Cat()  # noqa: F841 -- kept alive for the lifetime of the app
    try:
        import pyi_splash          # only exists inside the packaged exe
        pyi_splash.close()
    except Exception:
        pass
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
