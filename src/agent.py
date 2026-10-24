"""Agent module: builds context, calls LLM adapter, and parses JSON output."""

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .llm import call_llm


def clean_json_text(raw_text: str) -> str:
    """Strip markdown code fences and extraneous whitespace to extract clean JSON."""
    text = raw_text.strip()
    # Match ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    return text


def load_prompt_templates(prompts_dir: str) -> Tuple[str, str]:
    """Load system prompt and user prompt template files."""
    sys_path = os.path.join(prompts_dir, "agent_system.md")
    user_path = os.path.join(prompts_dir, "agent_user.md.tmpl")

    with open(sys_path, "r", encoding="utf-8") as f:
        system_tmpl = f.read()
    with open(user_path, "r", encoding="utf-8") as f:
        user_tmpl = f.read()

    return system_tmpl, user_tmpl


def build_system_prompt(template: str, animal: Dict[str, Any], config: Dict[str, Any]) -> str:
    """Fill variables in the system prompt safely without JSON brace collision."""
    res = template
    replacements = {
        "{name}": animal.get("name", animal["slug"]),
        "{slug}": animal["slug"],
        "{personality}": animal.get("personality", ""),
        "{speech_style}": animal.get("speech_style", ""),
        "{likes}": ", ".join(animal.get("likes", [])),
        "{chat_language}": config.get("chat_language", "id"),
        "{max_words_free}": str(config.get("max_words_free", 120)),
    }
    for placeholder, val in replacements.items():
        res = res.replace(placeholder, str(val))
    return res


def build_user_prompt(
    template: str,
    animal: Dict[str, Any],
    slot: str,
    day_type: str,
    memory_data: Dict[str, Any],
    recent_chat_lines: List[str],
    recent_knowledge: List[Dict[str, Any]],
    cycle_interactions_used: int,
    cycle_interactions_limit: int,
    eligible_targets: List[str],
    error_feedback: Optional[str] = None,
) -> str:
    """Format user prompt context for the turn safely without JSON brace collision."""
    mem_lines = memory_data.get("memory_lines", [])
    mem_text = "\n".join(f"- {line}" for line in mem_lines) if mem_lines else "(Belum ada ingatan)"

    rels = memory_data.get("relationships", {})
    rels_text = (
        "\n".join(f"- @{target}: {note}" for target, note in rels.items())
        if rels
        else "(Belum ada hubungan khusus)"
    )

    known_topics = memory_data.get("known_topics", [])
    known_text = ", ".join(known_topics) if known_topics else "(Belum mempelajari topik)"

    chat_text = "\n".join(recent_chat_lines[-10:]) if recent_chat_lines else "(Belum ada obrolan)"

    k_items = []
    for k in recent_knowledge[-8:]:
        k_items.append(f"- [{k.get('id')}]: {k.get('title')} — {k.get('lesson')}")
    knowledge_text = "\n".join(k_items) if k_items else "(Belum ada topik)"

    err_text = ""
    if error_feedback:
        err_text = f"\nPERINGATAN DARI SISTEM (Upaya sebelumnya ditolak karena kesalahan berikut):\n{error_feedback}\nPerbaiki kesalahan ini dan jangan ulangi.\n"

    can_interact_str = "Ya" if cycle_interactions_used < cycle_interactions_limit else "Tidak (kuota habis)"
    eligible_str = ", ".join(eligible_targets) if eligible_targets else "(Belum ada hewan lain yang berbicara)"

    res = template
    replacements = {
        "{name}": animal.get("name", animal["slug"]),
        "{slug}": animal["slug"],
        "{emoji}": animal.get("emoji", ""),
        "{slot}": slot,
        "{day_type}": day_type,
        "{interactions_used}": str(cycle_interactions_used),
        "{interactions_limit}": str(cycle_interactions_limit),
        "{can_interact}": can_interact_str,
        "{eligible_targets}": eligible_str,
        "{memory_lines}": mem_text,
        "{relationships}": rels_text,
        "{known_topics}": known_text,
        "{recent_chat}": chat_text,
        "{recent_knowledge}": knowledge_text,
        "{error_feedback}": err_text,
    }
    for placeholder, val in replacements.items():
        res = res.replace(placeholder, str(val))
    return res


def run_agent_turn(
    animal: Dict[str, Any],
    slot: str,
    day_type: str,
    memory_data: Dict[str, Any],
    recent_chat_lines: List[str],
    recent_knowledge: List[Dict[str, Any]],
    cycle_interactions_used: int,
    cycle_interactions_limit: int,
    eligible_targets: List[str],
    config: Dict[str, Any],
    prompts_dir: str,
    counter: int,
    error_feedback: Optional[str] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Run one agent turn through LLM adapter and return (parsed_json, error_message)."""
    sys_tmpl, user_tmpl = load_prompt_templates(prompts_dir)
    sys_prompt = build_system_prompt(sys_tmpl, animal, config)
    user_prompt = build_user_prompt(
        user_tmpl,
        animal,
        slot,
        day_type,
        memory_data,
        recent_chat_lines,
        recent_knowledge,
        cycle_interactions_used,
        cycle_interactions_limit,
        eligible_targets,
        error_feedback,
    )

    llm_context = {
        "counter": counter,
        "slug": animal["slug"],
        "name": animal.get("name", animal["slug"]),
        "eligible_targets": eligible_targets,
        "can_interact": cycle_interactions_used < cycle_interactions_limit,
        "known_topics": memory_data.get("known_topics", []),
        "village_topics": [k.get("id") for k in recent_knowledge if k.get("id")],
    }

    try:
        raw_output = call_llm(sys_prompt, user_prompt, config, llm_context)
    except Exception as e:
        return None, f"LLM call failed: {str(e)}"

    cleaned = clean_json_text(raw_output)
    try:
        data = json.loads(cleaned)
    except Exception as e:
        return None, f"Failed to parse LLM response as JSON: {str(e)} | Raw: {raw_output[:200]}"

    return data, None
