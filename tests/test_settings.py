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
