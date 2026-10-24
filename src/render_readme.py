"""README rendering with marker-based substitution.

Manual zones are preserved byte-identically.
Generated zones:
- CHAT: terminal-styled console block showing the tail of chat.log
- ROSTER: table of 6 animals, slots, lessons, and relationships
- KNOWLEDGE: total topics, newest topic, and 5 newest topic titles
"""

import json
import os
import re
import textwrap
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

ID_MONTHS = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "Mei",
    6: "Jun",
    7: "Jul",
    8: "Agu",
    9: "Sep",
    10: "Okt",
    11: "Nov",
    12: "Des",
}


def format_timestamp(dt: datetime, tz_name: str = "Asia/Jakarta") -> str:
    """Format datetime into Indonesian style timestamp, e.g. '24 Okt 12:00'."""
    try:
        tz = ZoneInfo(tz_name)
        local_dt = dt.astimezone(tz)
    except Exception:
        local_dt = dt
    m_name = ID_MONTHS.get(local_dt.month, local_dt.strftime("%b"))
    return f"{local_dt.day} {m_name} {local_dt.strftime('%H:%M')}"


def format_chat_entry(
    timestamp_str: str,
    animal: Dict[str, Any],
    slot: str,
    turn_data: Dict[str, Any],
    interactions_used: int,
    interactions_limit: int,
    cast_by_slug: Optional[Dict[str, Dict[str, Any]]] = None,
) -> str:
    """Format a single turn into the standard chat log entry block."""
    cast_map = cast_by_slug or {}
    slug = animal["slug"]
    emoji = animal["emoji"]
    personality = animal.get("personality", "").split(",")[0].strip()

    header = f"[{timestamp_str}] {emoji} {slug}@{slot} ({personality})"
    lines = [header]

    action = turn_data.get("action", "note")
    knowledge = turn_data.get("knowledge")
    interaction = turn_data.get("interaction")
    message = turn_data.get("message", "").replace("```", "")

    # Knowledge announcement line
    if action == "learn" and isinstance(knowledge, dict):
        top_title = knowledge.get("title") or knowledge.get("topic_id", "")
        learned_from = knowledge.get("learned_from")
        if learned_from and learned_from in cast_map:
            from_emoji = cast_map[learned_from].get("emoji", "")
            lines.append(f"  [belajar] {top_title} ← dari {from_emoji} {learned_from}")
        elif learned_from:
            lines.append(f"  [belajar] {top_title} ← dari @{learned_from}")
        else:
            lines.append(f"  [belajar] {top_title}")
    elif action == "discover" and isinstance(knowledge, dict):
        top_title = knowledge.get("title") or knowledge.get("topic_id", "")
        lines.append(f"  [temukan] {top_title}")

    # Message lines wrapped to ~60 characters
    wrapped = textwrap.wrap(message, width=60)
    if not wrapped:
        wrapped = [""]
    for w in wrapped:
        lines.append(f"  > {w}")

    # Bracket line (plain note turns have NO bracket line)
    if action == "interact" and isinstance(interaction, dict):
        itype = interaction.get("type", "tanya")
        target = interaction.get("target", "")
        k_tag = " · +1 pengetahuan" if knowledge else ""
        lines.append(f"  [{itype} @{target} · interaksi {interactions_used}/{interactions_limit} ✓{k_tag}]")
    elif knowledge and action in ("learn", "discover"):
        # If knowledge gained in non-interaction turn
        lines.append(f"  [+1 pengetahuan · topik: {knowledge.get('topic_id', '')}]")

    return "\n".join(lines)


def get_chat_tail_entries(chat_log_content: str, tail_count: int = 20) -> List[str]:
    """Parse chat.log into discrete entry blocks and return the last tail_count entries."""
    if not chat_log_content.strip():
        return []
    # Entries are separated by double newlines or lines starting with [DD Mon HH:MM]
    raw_blocks = re.split(r"\n\n+(?=\[\d+\s+[A-Za-z]+\s+\d{2}:\d{2}\])", chat_log_content.strip())
    # Clean blocks
    blocks = [b.strip() for b in raw_blocks if b.strip()]
    return blocks[-tail_count:]


def render_chat_block(chat_log_content: str, tail_count: int = 20) -> str:
    """Render the console fenced block for CHAT zone."""
    entries = get_chat_tail_entries(chat_log_content, tail_count)
    lines = [
        "```console",
        f"playground@desa-hewan:~$ tail -n {tail_count} chat.log",
        "",
    ]
    if entries:
        for entry in entries:
            lines.append(entry)
            lines.append("")
    lines.append("playground@desa-hewan:~$ █")
    lines.append("```")
    return "\n".join(lines)


def render_roster_block(
    cast: List[Dict[str, Any]],
    animals_dir: str,
) -> str:
    """Render markdown table for ROSTER zone."""
    rows = [
        "| Emoji | Nama | Kepribadian | Jadwal | Pelajaran | Hubungan Terdekat |",
        "|---|---|---|---|---|---|",
    ]
    slots_map = {
        0: "A / pagi",
        1: "A / siang",
        2: "A / malam",
        3: "B / pagi",
        4: "B / siang",
        5: "B / malam",
    }
    for idx, animal in enumerate(cast):
        slug = animal["slug"]
        emoji = animal.get("emoji", "")
        name = animal.get("name", slug)
        personality = animal.get("personality", "")
        slot = slots_map.get(idx % 6, "-")

        # Load per-animal memory
        mem_file = os.path.join(animals_dir, f"{slug}.json")
        lessons_count = 0
        closest_rel = "-"
        if os.path.exists(mem_file):
            try:
                with open(mem_file, "r", encoding="utf-8") as f:
                    mem_data = json.load(f)
                    lessons_count = len(mem_data.get("known_topics", []))
                    rels = mem_data.get("relationships", {})
                    if rels:
                        # Grab the most recent relationship entry
                        last_target, last_note = list(rels.items())[-1]
                        closest_rel = f"@{last_target}: {last_note}"
            except Exception:
                pass

        lesson_str = f"{lessons_count} topik"
        rows.append(f"| {emoji} | {name} | {personality} | {slot} | {lesson_str} | {closest_rel} |")

    return "\n".join(rows)


def render_knowledge_block(knowledge_list: List[Dict[str, Any]]) -> str:
    """Render summary line and 5 newest topic titles for KNOWLEDGE zone."""
    total = len(knowledge_list)
    newest_title = knowledge_list[-1].get("title", "-") if knowledge_list else "-"
    summary_line = f"**Total Topik:** {total} | **Topik Terbaru:** {newest_title}\n"

    # Up to 5 newest topics (newest first)
    newest_5 = list(reversed(knowledge_list))[:5]
    items = []
    for item in newest_5:
        title = item.get("title", item.get("id", ""))
        lesson = item.get("lesson", "")
        items.append(f"- 📖 **{title}**: {lesson}")

    return summary_line + "\n" + "\n".join(items)


def update_readme_content(
    readme_content: str,
    chat_block: str,
    roster_block: str,
    knowledge_block: str,
) -> str:
    """Replace only text between markers in readme_content, preserving manual zones byte-identically."""
    zones = {
        "CHAT": chat_block,
        "ROSTER": roster_block,
        "KNOWLEDGE": knowledge_block,
    }

    result = readme_content
    for zone_name, new_content in zones.items():
        start_marker = f"<!-- {zone_name}:START -->"
        end_marker = f"<!-- {zone_name}:END -->"

        start_pos = result.find(start_marker)
        if start_pos == -1:
            raise ValueError(f"Marker '{start_marker}' not found in README")
        end_pos = result.find(end_marker, start_pos)
        if end_pos == -1:
            raise ValueError(f"Marker '{end_marker}' not found in README")

        # Keep everything up to the end of start marker line
        prefix = result[: start_pos + len(start_marker)]
        suffix = result[end_pos:]

        result = f"{prefix}\n{new_content}\n{suffix}"

    return result


def render_readme_file(
    readme_path: str,
    chat_log_path: str,
    cast: List[Dict[str, Any]],
    animals_dir: str,
    knowledge_list: List[Dict[str, Any]],
    tail_count: int = 20,
) -> None:
    """Read files, render generated zones, and write back to README.md."""
    with open(readme_path, "r", encoding="utf-8") as f:
        original_readme = f.read()

    chat_log_content = ""
    if os.path.exists(chat_log_path):
        with open(chat_log_path, "r", encoding="utf-8") as f:
            chat_log_content = f.read()

    chat_block = render_chat_block(chat_log_content, tail_count)
    roster_block = render_roster_block(cast, animals_dir)
    knowledge_block = render_knowledge_block(knowledge_list)

    new_readme = update_readme_content(
        original_readme,
        chat_block,
        roster_block,
        knowledge_block,
    )

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_readme)
