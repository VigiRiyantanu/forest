import pytest
from src.validate import (
    count_words,
    is_single_sentence,
    validate_anti_greeting,
    validate_anti_repetition,
    validate_hygiene,
    validate_persona_sanity,
    validate_turn,
)

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
    "similarity_threshold": 0.6,
    "chat_language": "id",
}

KNOWLEDGE = [{"id": "pohon-beringin", "title": "Pohon Beringin", "lesson": "Akar kokoh."}]
CHAT_HIST = ["[24 Okt 10:00] 🐓 ayam-jantan@pagi (bossy)\n  > Fajar telah tiba."]
STATE = {"counter": 1, "cycle": {"id": 0, "interactions_used": {}}}


def test_word_count_limits_49_50_51():
    # Construct exact word count messages
    words_49 = " ".join(["kata"] * 49)
    words_50 = " ".join(["kata"] * 50)
    words_51 = " ".join(["kata"] * 51)

    assert count_words(words_49) == 49
    assert count_words(words_50) == 50
    assert count_words(words_51) == 51

    base_payload = {
        "action": "interact",
        "interaction": {"target": "ayam-jantan", "type": "ask", "topic_id": "pohon-beringin"},
        "knowledge": None,
        "memory_note": "Ingatan singkat.",
        "relationship_note": None,
    }

    # 49 words -> Valid
    p49 = dict(base_payload, message=words_49)
    valid_49, errs_49 = validate_turn(p49, "kucing", CAST, STATE, CONFIG, CHAT_HIST, KNOWLEDGE)
    assert valid_49 is True, f"49 words should be valid, got: {errs_49}"

    # 50 words -> Valid (limit is <= 50)
    p50 = dict(base_payload, message=words_50)
    valid_50, errs_50 = validate_turn(p50, "kucing", CAST, STATE, CONFIG, CHAT_HIST, KNOWLEDGE)
    assert valid_50 is True, f"50 words should be valid, got: {errs_50}"

    # 51 words -> Invalid (> 50 words)
    p51 = dict(base_payload, message=words_51)
    valid_51, errs_51 = validate_turn(p51, "kucing", CAST, STATE, CONFIG, CHAT_HIST, KNOWLEDGE)
    assert valid_51 is False
    assert any("exceeds 50 words" in e.lower() for e in errs_51)


def test_greeting_blocker():
    disallowed_greetings = [
        "halo kawan semua",
        "Hai teman-teman desa!",
        "Hi ayam jantan,",
        "hey apa yang terjadi",
        "Hello semuanya!",
        "Selamat pagi penghuni desa",
        "selamat siang desa tercinta",
        "Selamat malam semuanya",
        "apa kabar kawan?",
        "salam sejahtera wahai burung hantu",
    ]

    for g in disallowed_greetings:
        ok, err = validate_anti_greeting(g)
        assert ok is False, f"Greeting '{g}' should be blocked, but was accepted"


def test_greeting_not_triggered_on_regular_words():
    allowed_messages = [
        "Haluan perahu kayu itu mengarah ke muara sungai.",
        "Hanya burung hantu yang terbang di kala malam.",
        "Selimut kabut tebal menyelimuti lembah hijau.",
    ]
    for msg in allowed_messages:
        ok, _ = validate_anti_greeting(msg)
        assert ok is True, f"Allowed message '{msg}' was falsely blocked"


def test_similarity_blocker():
    recent = ["Fajar merekah di perbukitan timur desa yang indah."]

    # High similarity (> 0.6)
    too_similar = "Fajar merekah di bukit timur desa yang sangat indah."
    ok, err = validate_anti_repetition(too_similar, recent, threshold=0.6)
    assert ok is False
    assert "too similar" in err.lower()

    # Low similarity (< 0.6)
    distinct = "Malam gelap gulita diterangi bintang utara yang sunyi."
    ok2, err2 = validate_anti_repetition(distinct, recent, threshold=0.6)
    assert ok2 is True


def test_url_rejection():
    bad_urls = [
        "Kunjungi https://desa-hewan.com untuk melihat kabar.",
        "Lihat info di http://github.com/mbg/village sekarang.",
        "Buka www.hewan.org di dekat pohon beringin.",
        "Ada berkas di storage.io yang bisa dibaca.",
    ]
    for msg in bad_urls:
        ok, err = validate_hygiene(msg)
        assert ok is False
        assert "URL" in err or "domain" in err


def test_markdown_rejection():
    bad_markdowns = [
        "Pagi ini cuaca **sangat cerah** sekali.",
        "Jangan lupa *membawa* biji gandum.",
        "### Pengumuman Penting Desa",
        "Berikut tautan [beringin](file://desa) kita.",
        "```python\nprint('hello')\n```",
    ]
    for msg in bad_markdowns:
        ok, err = validate_hygiene(msg)
        assert ok is False


def test_persona_sanity():
    cast_slugs = {a["slug"] for a in CAST}
    # Current slug is ayam-jantan, claims to be kucing
    bad_msg = "Saya kucing yang suka tidur di bawah terik matahari siang."
    ok, err = validate_persona_sanity(bad_msg, "ayam-jantan", cast_slugs)
    assert ok is False
    assert "claims to be another cast member" in err.lower()


def test_knowledge_lesson_rules():
    # More than 25 words
    long_lesson = " ".join(["kata"] * 26) + "."
    payload = {
        "action": "discover",
        "message": "Penemuan penting di lereng bukit.",
        "interaction": None,
        "knowledge": {
            "topic_id": "topik-baru",
            "title": "Topik Baru",
            "lesson": long_lesson,
            "learned_from": None,
        },
        "memory_note": "Catatan singkat.",
        "relationship_note": None,
    }
    valid, errs = validate_turn(payload, "kucing", CAST, STATE, CONFIG, CHAT_HIST, KNOWLEDGE)
    assert valid is False
    assert any("exceeds 25 words" in e.lower() for e in errs)

    # Multiple sentences
    multi_sentence_lesson = "Pohon ini memiliki akar dalam. Airnya mengalir deras."
    payload["knowledge"]["lesson"] = multi_sentence_lesson
    valid, errs = validate_turn(payload, "kucing", CAST, STATE, CONFIG, CHAT_HIST, KNOWLEDGE)
    assert valid is False
    assert any("one sentence" in e.lower() for e in errs)


def test_action_consistency():
    # action "note" but interaction is set
    p1 = {
        "action": "note",
        "message": "Catatan biasa saja.",
        "interaction": {"target": "kucing", "type": "ask", "topic_id": "pohon-beringin"},
        "knowledge": None,
        "memory_note": "Catatan.",
        "relationship_note": None,
    }
    valid, errs = validate_turn(p1, "ayam-jantan", CAST, STATE, CONFIG, CHAT_HIST, KNOWLEDGE)
    assert valid is False
    assert any("must have interaction set to null" in e.lower() for e in errs)

    # action "learn" but topic does not exist
    p2 = {
        "action": "learn",
        "message": "Belajar topik yang belum ada.",
        "interaction": None,
        "knowledge": {
            "topic_id": "topik-hantu",
            "title": "Topik Hantu",
            "lesson": "Pelajaran fiktif.",
            "learned_from": None,
        },
        "memory_note": "Catatan.",
        "relationship_note": None,
    }
    valid, errs = validate_turn(p2, "ayam-jantan", CAST, STATE, CONFIG, CHAT_HIST, KNOWLEDGE)
    assert valid is False
    assert any("must target an existing topic" in e.lower() for e in errs)
