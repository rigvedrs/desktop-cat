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
