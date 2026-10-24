import json
import os
import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def cast():
    cast_path = os.path.join(REPO_ROOT, "animals", "cast.json")
    with open(cast_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_cast_size_and_order(cast):
    assert len(cast) == 6
    expected_slugs = [
        "ayam-jantan",
        "kucing",
        "burung-hantu",
        "burung-pipit",
        "rubah",
        "kelelawar",
    ]
    for idx, expected in enumerate(expected_slugs):
        assert cast[idx]["slug"] == expected


def test_rotation_counter_mapping(cast):
    slots = ["pagi", "siang", "malam"]
    expected_sequence = [
        (0, "ayam-jantan", "pagi", "A", 0),
        (1, "kucing", "siang", "A", 0),
        (2, "burung-hantu", "malam", "A", 0),
        (3, "burung-pipit", "pagi", "B", 0),
        (4, "rubah", "siang", "B", 0),
        (5, "kelelawar", "malam", "B", 0),
        (6, "ayam-jantan", "pagi", "A", 1),
        (7, "kucing", "siang", "A", 1),
        (8, "burung-hantu", "malam", "A", 1),
        (9, "burung-pipit", "pagi", "B", 1),
        (10, "rubah", "siang", "B", 1),
        (11, "kelelawar", "malam", "B", 1),
        (12, "ayam-jantan", "pagi", "A", 2),
        (13, "kucing", "siang", "A", 2),
    ]

    for counter, exp_slug, exp_slot, exp_day, exp_cycle in expected_sequence:
        animal = cast[counter % 6]
        slot = slots[counter % 3]
        day_type = "A" if (counter // 3) % 2 == 0 else "B"
        cycle_id = counter // 6

        assert animal["slug"] == exp_slug, f"Turn {counter}: expected {exp_slug}, got {animal['slug']}"
        assert slot == exp_slot, f"Turn {counter}: expected slot {exp_slot}, got {slot}"
        assert day_type == exp_day, f"Turn {counter}: expected day {exp_day}, got {day_type}"
        assert cycle_id == exp_cycle, f"Turn {counter}: expected cycle {exp_cycle}, got {cycle_id}"
