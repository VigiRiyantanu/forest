import os
import re
from src.render_readme import (
    get_chat_tail_entries,
    render_chat_block,
    render_knowledge_block,
    render_roster_block,
    update_readme_content,
)

SAMPLE_README = """# 🐾 Animal Playground
<!-- manual zone: owner writes intro, badges, images here -->
Owner custom intro paragraph.
Special badges: [![Build](https://img.shields.io/badge/status-active-green)]()
Custom notes:
- Item 1
- Item 2
<!-- manual zone end -->

## 💬 Obrolan Desa
<!-- CHAT:START -->
Old chat block here
<!-- CHAT:END -->

## 🏡 Penghuni
<!-- ROSTER:START -->
Old roster here
<!-- ROSTER:END -->

## 📚 Pengetahuan Desa
<!-- KNOWLEDGE:START -->
Old knowledge here
<!-- KNOWLEDGE:END -->

## Manual Footer
Custom owner footer text that must never be altered!
"""


def test_readme_manual_zones_byte_identical():
    # Extract everything before <!-- CHAT:START -->
    chat_start_idx = SAMPLE_README.find("<!-- CHAT:START -->")
    original_top = SAMPLE_README[:chat_start_idx]

    # Extract manual text between CHAT:END and ROSTER:START
    chat_end_idx = SAMPLE_README.find("<!-- CHAT:END -->") + len("<!-- CHAT:END -->")
    roster_start_idx = SAMPLE_README.find("<!-- ROSTER:START -->")
    original_mid1 = SAMPLE_README[chat_end_idx:roster_start_idx]

    # Extract manual text after KNOWLEDGE:END
    know_end_idx = SAMPLE_README.find("<!-- KNOWLEDGE:END -->") + len("<!-- KNOWLEDGE:END -->")
    original_footer = SAMPLE_README[know_end_idx:]

    updated = update_readme_content(
        SAMPLE_README,
        chat_block="NEW CHAT CONTENT",
        roster_block="NEW ROSTER CONTENT",
        knowledge_block="NEW KNOWLEDGE CONTENT",
    )

    # Check that manual zones are byte-identical
    new_chat_start = updated.find("<!-- CHAT:START -->")
    assert updated[:new_chat_start] == original_top

    new_chat_end = updated.find("<!-- CHAT:END -->") + len("<!-- CHAT:END -->")
    new_roster_start = updated.find("<!-- ROSTER:START -->")
    assert updated[new_chat_end:new_roster_start] == original_mid1

    new_know_end = updated.find("<!-- KNOWLEDGE:END -->") + len("<!-- KNOWLEDGE:END -->")
    assert updated[new_know_end:] == original_footer


def test_render_chat_block_empty():
    block = render_chat_block("", tail_count=20)
    assert "```console" in block
    assert "tail -n 20 chat.log" in block
    assert "playground@desa-hewan:~$ █" in block
    assert block.endswith("```")


def test_render_chat_tail_limits():
    # Generate 30 fake entries
    fake_entries = []
    for i in range(30):
        entry = f"[24 Okt {10 + i // 60:02d}:{i % 60:02d}] 🐓 ayam-jantan@pagi (bossy)\n  > Pesan ke-{i}"
        fake_entries.append(entry)

    full_log = "\n\n".join(fake_entries)
    tail_20 = get_chat_tail_entries(full_log, tail_count=20)
    assert len(tail_20) == 20
    # First entry in tail_20 should be entry 10, last should be 29
    assert "Pesan ke-10" in tail_20[0]
    assert "Pesan ke-29" in tail_20[-1]

    rendered = render_chat_block(full_log, tail_count=20)
    assert "Pesan ke-29" in rendered
    assert "Pesan ke-9" not in rendered
