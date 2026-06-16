import json
from pathlib import Path

STARS_PATH = Path(__file__).resolve().parent.parent / "data" / "stars.json"


def test_stars_file_exists():
    assert STARS_PATH.exists()


def test_stars_is_list():
    with open(STARS_PATH) as f:
        data = json.load(f)
    assert isinstance(data, list)


def test_stars_count_in_range():
    with open(STARS_PATH) as f:
        data = json.load(f)
    assert 5000 <= len(data) <= 10000


def test_stars_have_required_fields():
    with open(STARS_PATH) as f:
        data = json.load(f)
    for star in data[:50]:
        assert "x" in star
        assert "y" in star
        assert "z" in star
        assert "size" in star


def test_stars_values_are_numeric():
    with open(STARS_PATH) as f:
        data = json.load(f)
    for star in data[:50]:
        assert isinstance(star["x"], (int, float))
        assert isinstance(star["y"], (int, float))
        assert isinstance(star["z"], (int, float))
        assert isinstance(star["size"], (int, float))


def test_stars_size_positive():
    with open(STARS_PATH) as f:
        data = json.load(f)
    for star in data:
        assert star["size"] >= 0.5
