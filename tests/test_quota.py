import pytest
from src.validate import validate_turn

CAST = [
    {"slug": "ayam-jantan", "name": "Ayam Jantan"},
    {"slug": "kucing", "name": "Kucing"},
    {"slug": "burung-hantu", "name": "Burung Hantu"},
    {"slug": "burung-pipit", "name": "Burung Pipit"},
    {"slug": "rubah", "name": "Rubah"},
    {"slug": "kelelawar", "name": "Kelelawar"},
]

CONFIG = {
    "interactions_per_cycle": 1,
    "max_words_interaction": 50,
    "max_words_free": 120,
    "chat_language": "id",
}

KNOWLEDGE = [{"id": "pohon-beringin", "title": "Pohon Beringin", "lesson": "Akar kokoh."}]


def test_interaction_quota_exceeded():
    state = {
        "counter": 2,
        "cycle": {
            "id": 0,
            "interactions_used": {"kucing": 1},  # Quota 1/1 reached
        },
    }
    chat_history = ["[24 Okt 10:00] 🐓 ayam-jantan@pagi (bossy)\n  > Fajar telah tiba."]

    payload = {
        "action": "interact",
        "message": "Ayam jantan tolong jangan terlalu berisik saat tidur siang.",
        "interaction": {
            "target": "ayam-jantan",
            "type": "debate",
            "topic_id": "pohon-beringin",
        },
        "knowledge": None,
        "memory_note": "Catatan singkat.",
        "relationship_note": None,
    }

    is_valid, errors = validate_turn(payload, "kucing", CAST, state, CONFIG, chat_history, KNOWLEDGE)
    assert is_valid is False
    assert any("quota exceeded" in e.lower() for e in errors)


def test_self_interaction_rejected():
    state = {"counter": 1, "cycle": {"id": 0, "interactions_used": {}}}
    chat_history = ["[24 Okt 10:00] 🐓 ayam-jantan@pagi (bossy)\n  > Pesan lama."]

    payload = {
        "action": "interact",
        "message": "Saya berbicara dengan diri saya sendiri.",
        "interaction": {
            "target": "ayam-jantan",
            "type": "ask",
            "topic_id": "pohon-beringin",
        },
        "knowledge": None,
        "memory_note": "Catatan.",
        "relationship_note": None,
    }

    is_valid, errors = validate_turn(payload, "ayam-jantan", CAST, state, CONFIG, chat_history, KNOWLEDGE)
    assert is_valid is False
    assert any("cannot interact with itself" in e.lower() for e in errors)


def test_target_not_spoken_rejected():
    state = {"counter": 1, "cycle": {"id": 0, "interactions_used": {}}}
    # Chat history only has ayam-jantan, but kucing tries to interact with rubah (who hasn't spoken)
    chat_history = ["[24 Okt 10:00] 🐓 ayam-jantan@pagi (bossy)\n  > Fajar telah tiba."]

    payload = {
        "action": "interact",
        "message": "Rubah mari kita barter barang di tepi telaga.",
        "interaction": {
            "target": "rubah",
            "type": "barter",
            "topic_id": "pohon-beringin",
        },
        "knowledge": None,
        "memory_note": "Catatan.",
        "relationship_note": None,
    }

    is_valid, errors = validate_turn(payload, "kucing", CAST, state, CONFIG, chat_history, KNOWLEDGE)
    assert is_valid is False
    assert any("has not spoken yet" in e.lower() for e in errors)
