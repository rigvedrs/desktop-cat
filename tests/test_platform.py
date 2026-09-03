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
    # Without this, a failed ApplicationServices load leaves _cg None, the probe
    # returns 1e9 and typing detection is silently dead -- while both assertions
    # below still pass.
    assert C._cg is not None
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
