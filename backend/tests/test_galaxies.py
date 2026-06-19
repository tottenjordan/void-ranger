import json
from pathlib import Path

GALAXIES_PATH = Path(__file__).resolve().parent.parent / "data" / "galaxies.json"


def test_galaxies_file_exists():
    assert GALAXIES_PATH.exists()


def test_galaxies_is_list():
    with open(GALAXIES_PATH) as f:
        data = json.load(f)
    assert isinstance(data, list)


def test_galaxies_count_in_range():
    with open(GALAXIES_PATH) as f:
        data = json.load(f)
    assert 30000 <= len(data) <= 50000


def test_galaxies_values_are_numeric():
    with open(GALAXIES_PATH) as f:
        data = json.load(f)
    for g in data[:50]:
        assert isinstance(g["x"], (int, float))
        assert isinstance(g["y"], (int, float))
        assert isinstance(g["z"], (int, float))
        assert isinstance(g["m"], (int, float))
        assert isinstance(g["mag"], (int, float))


def test_galaxies_have_label_fields():
    with open(GALAXIES_PATH) as f:
        data = json.load(f)
    for g in data[:50]:
        assert isinstance(g["name"], str)
        assert isinstance(g["desig"], str)


def test_some_galaxies_have_proper_names():
    with open(GALAXIES_PATH) as f:
        data = json.load(f)
    named = [g for g in data if g.get("name")]
    assert len(named) >= 10
