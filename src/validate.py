"""Validator for all Animal Playground hard rules."""

import difflib
import re
from typing import Any, Dict, List, Optional, Set, Tuple

GREETINGS = [
    "halo",
    "hai",
    "hi",
    "hey",
    "hello",
    "selamat pagi",
    "selamat siang",
    "selamat malam",
    "selamat sore",
    "selamat petang",
    "apa kabar",
    "salam",
]

MARKDOWN_PATTERNS = [
    r"\*\*",           # Bold
    r"\*[^*]+\*",      # Italic
    r"__",             # Bold or italic
    r"^#+\s",          # Headings
    r"```",            # Code fence
    r"`[^`]+`",        # Inline code
    r"\[.+?\]\(.+?\)", # Markdown link
    r"^>\s",           # Blockquote
]

URL_PATTERN = re.compile(
    r"(https?://|www\.|ftp://|\b[a-zA-Z0-9.-]+\.(com|org|net|io|id|dev|co|xyz|app)\b)",
    re.IGNORECASE,
)

EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
)

PHONE_PATTERN = re.compile(
    r"(?:\+?\d{1,3}[- ]?)?\(?\d{3,4}\)?[- ]?\d{3,4}[- ]?\d{3,4}"
)

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def count_words(text: Optional[str]) -> int:
    """Count words in text split by whitespace."""
    if not text:
        return 0
    return len(text.strip().split())


def is_single_sentence(text: str) -> bool:
    """Check if the text represents exactly one single sentence."""
    stripped = text.strip()
    if not stripped:
        return False
    # Must end with sentence terminator
    if not (stripped.endswith(".") or stripped.endswith("!") or stripped.endswith("?")):
        return False
    # Remove terminal punctuation
    inner = stripped[:-1].rstrip()
    # If inner text still contains sentence-ending punctuation followed by space, it's multiple sentences
    if re.search(r"[.!?]\s+[A-Za-z0-9]", inner):
        return False
    if "\n" in inner:
        return False
    return True


def validate_anti_greeting(message: str) -> Tuple[bool, Optional[str]]:
    """Reject if message starts with greeting variants in any language."""
    stripped = message.strip()
    # Normalize punctuation at start
    cleaned = re.sub(r"^[^\w]+", "", stripped).lower()
    for g in GREETINGS:
        # Check if starts with greeting followed by punctuation, whitespace, or end of string
        pattern = r"^" + re.escape(g) + r"(\b|[!?,.\s]|$)"
        if re.search(pattern, cleaned):
            return False, f"Message starts with greeting '{g}' which is disallowed"
    return True, None


def validate_anti_repetition(
    message: str,
    last_10_messages: List[str],
    threshold: float = 0.6,
) -> Tuple[bool, Optional[str]]:
    """Reject if similarity to any of the last 10 messages >= threshold."""
    msg_clean = message.strip().lower()
    for prev in last_10_messages:
        prev_clean = prev.strip().lower()
        if not prev_clean:
            continue
        sim = difflib.SequenceMatcher(None, msg_clean, prev_clean).ratio()
        if sim >= threshold:
            return False, f"Message is too similar to a recent message (similarity: {sim:.2f} >= {threshold})"
    return True, None


def validate_hygiene(message: str, chat_language: str = "id") -> Tuple[bool, Optional[str]]:
    """Check output hygiene: no URLs, no markdown, no code, no ANSI, no PII, matches language."""
    # Control / ANSI characters
    for ch in message:
        if ord(ch) < 32 and ch not in "\n\r\t":
            return False, "Message contains control or ANSI characters"

    # Code fences
    if "```" in message:
        return False, "Message contains code fences"

    # Markdown formatting
    for pat in MARKDOWN_PATTERNS:
        if re.search(pat, message, re.MULTILINE):
            return False, f"Message contains forbidden markdown pattern '{pat}'"

    # URLs
    if URL_PATTERN.search(message):
        return False, "Message contains forbidden URL or domain link"

    # Personal identifiable information (email, phone)
    if EMAIL_PATTERN.search(message):
        return False, "Message contains forbidden personal email address"
    if PHONE_PATTERN.search(message):
        return False, "Message contains forbidden phone number"

    # Language sanity check for Indonesian
    if chat_language == "id":
        # Check that it isn't predominantly English
        english_words = {"the", "and", "is", "this", "that", "with", "from", "today", "yesterday", "tomorrow"}
        words = set(re.findall(r"\b[a-zA-Z]+\b", message.lower()))
        eng_count = len(words.intersection(english_words))
        if eng_count >= 3 and len(words) > 0 and (eng_count / len(words)) > 0.3:
            return False, f"Message does not appear to be in Indonesian ({chat_language})"

    return True, None


def validate_persona_sanity(
    message: str,
    current_slug: str,
    cast_slugs: Set[str],
) -> Tuple[bool, Optional[str]]:
    """Ensure the animal does not claim to be another animal in the village."""
    lower = message.lower()
    for slug in cast_slugs:
        if slug == current_slug:
            continue
        # Patterns like "saya kucing", "aku rubah", "namaku kelelawar"
        clean_slug = slug.replace("-", " ")
        if re.search(rf"\b(saya|aku|namaku)\s+{re.escape(slug)}\b", lower) or re.search(
            rf"\b(saya|aku|namaku)\s+{re.escape(clean_slug)}\b", lower
        ):
            return False, f"Animal claims to be another cast member '{slug}'"
    return True, None


def validate_turn(
    turn_data: Any,
    current_slug: str,
    cast: List[Dict[str, Any]],
    state: Dict[str, Any],
    config: Dict[str, Any],
    chat_history: List[str],
    knowledge_list: List[Dict[str, Any]],
) -> Tuple[bool, List[str]]:
    """Validate all hard rules for a turn. Returns (is_valid, error_list)."""
    errors: List[str] = []

    # 1. JSON structure & types
    if not isinstance(turn_data, dict):
        return False, ["Output must be a JSON object"]

    required_keys = {"action", "message", "interaction", "knowledge", "memory_note", "relationship_note"}
    missing = required_keys - set(turn_data.keys())
    if missing:
        errors.append(f"Missing required keys: {sorted(list(missing))}")

    action = turn_data.get("action")
    valid_actions = {"note", "learn", "discover", "interact"}
    if action not in valid_actions:
        errors.append(f"Invalid action '{action}'. Must be one of {sorted(list(valid_actions))}")

    message = turn_data.get("message")
    if not isinstance(message, str) or not message.strip():
        errors.append("Field 'message' must be a non-empty string")
        message = ""

    interaction = turn_data.get("interaction")
    knowledge = turn_data.get("knowledge")
    memory_note = turn_data.get("memory_note")
    relationship_note = turn_data.get("relationship_note")

    cast_slugs = {animal["slug"] for animal in cast}
    existing_topic_ids = {item["id"] for item in knowledge_list}

    # Consistency checks per action
    if action == "note":
        if interaction is not None:
            errors.append("Action 'note' must have interaction set to null")
        if knowledge is not None:
            errors.append("Action 'note' must have knowledge set to null")

    elif action == "learn":
        if interaction is not None:
            errors.append("Action 'learn' must have interaction set to null")
        if not isinstance(knowledge, dict):
            errors.append("Action 'learn' requires a 'knowledge' object")
        else:
            top_id = knowledge.get("topic_id")
            if top_id not in existing_topic_ids:
                errors.append(f"Action 'learn' must target an existing topic in knowledge.json (got '{top_id}')")

    elif action == "discover":
        if interaction is not None:
            errors.append("Action 'discover' must have interaction set to null")
        if not isinstance(knowledge, dict):
            errors.append("Action 'discover' requires a 'knowledge' object")
        else:
            top_id = knowledge.get("topic_id")
            if not top_id or not SLUG_PATTERN.match(str(top_id)):
                errors.append(f"Action 'discover' topic_id must be slug format (got '{top_id}')")
            elif top_id in existing_topic_ids:
                errors.append(f"Action 'discover' topic_id must be new and unique (got existing '{top_id}')")

    elif action == "interact":
        if not isinstance(interaction, dict):
            errors.append("Action 'interact' requires an 'interaction' object")

    # Interaction details validation
    if interaction is not None:
        if not isinstance(interaction, dict):
            errors.append("Field 'interaction' must be null or an object")
        else:
            target = interaction.get("target")
            itype = interaction.get("type")
            top_id = interaction.get("topic_id")

            valid_types = {"ask", "teach", "debate", "barter", "request_help", "story"}
            if itype not in valid_types:
                errors.append(f"Interaction type '{itype}' is invalid. Must be one of {sorted(list(valid_types))}")

            if target not in cast_slugs:
                errors.append(f"Interaction target '{target}' does not exist in cast")
            elif target == current_slug:
                errors.append(f"Animal cannot interact with itself ('{current_slug}')")
            else:
                # Target must have spoken before
                # Check chat_history for target slug
                target_has_spoken = any(f"{target}@" in line for line in chat_history)
                if not target_has_spoken:
                    errors.append(f"Target '{target}' has not spoken yet in village history")

            # Check interaction quota in current cycle
            cycle_info = state.get("cycle", {})
            interactions_used = cycle_info.get("interactions_used", {}).get(current_slug, 0)
            quota_limit = config.get("interactions_per_cycle", 1)
            if interactions_used >= quota_limit:
                errors.append(
                    f"Interaction quota exceeded for '{current_slug}' in this cycle ({interactions_used}/{quota_limit})"
                )

            # Topic ID must exist in knowledge.json OR be created in this turn
            created_in_turn = False
            if isinstance(knowledge, dict) and knowledge.get("topic_id") == top_id:
                created_in_turn = True
            if top_id not in existing_topic_ids and not created_in_turn:
                errors.append(f"Interaction topic_id '{top_id}' does not exist in knowledge.json")

            # Knowledge in interaction: only allowed if teach
            if knowledge is not None and itype != "teach":
                errors.append(f"Knowledge in interaction is only permitted for 'teach' interactions (got '{itype}')")

    # Knowledge details validation
    if knowledge is not None:
        if not isinstance(knowledge, dict):
            errors.append("Field 'knowledge' must be null or an object")
        else:
            lesson = knowledge.get("lesson")
            if not isinstance(lesson, str) or not lesson.strip():
                errors.append("Knowledge 'lesson' must be a non-empty string")
            else:
                wcount = count_words(lesson)
                if wcount > 25:
                    errors.append(f"Knowledge lesson exceeds 25 words ({wcount} words)")
                if not is_single_sentence(lesson):
                    errors.append("Knowledge lesson must be exactly ONE sentence ending with punctuation")

            top_id = knowledge.get("topic_id")
            if not top_id or not SLUG_PATTERN.match(str(top_id)):
                errors.append(f"Knowledge topic_id '{top_id}' is not in valid slug format")

    # Word counts for message
    max_words_interaction = int(config.get("max_words_interaction", 50))
    max_words_free = int(config.get("max_words_free", 120))
    msg_word_count = count_words(message)

    if action == "interact" or interaction is not None:
        if msg_word_count > max_words_interaction:
            errors.append(
                f"Interaction message exceeds {max_words_interaction} words (got {msg_word_count} words)"
            )
    else:
        if msg_word_count > max_words_free:
            errors.append(
                f"Free message exceeds {max_words_free} words (got {msg_word_count} words)"
            )

    # Memory note word count
    if memory_note is not None:
        if not isinstance(memory_note, str):
            errors.append("Field 'memory_note' must be a string")
        else:
            mn_count = count_words(memory_note)
            if mn_count > 25:
                errors.append(f"memory_note exceeds 25 words ({mn_count} words)")

    # Relationship note
    if relationship_note is not None:
        if not isinstance(relationship_note, dict):
            errors.append("Field 'relationship_note' must be null or an object")
        else:
            rel_target = relationship_note.get("target")
            rel_note = relationship_note.get("note")
            if rel_target not in cast_slugs or rel_target == current_slug:
                errors.append(f"relationship_note target '{rel_target}' is invalid")
            if not isinstance(rel_note, str) or not rel_note.strip():
                errors.append("relationship_note 'note' must be a non-empty string")
            else:
                rn_count = count_words(rel_note)
                if rn_count > 15:
                    errors.append(f"relationship_note exceeds 15 words ({rn_count} words)")

    # Anti-greeting check
    if message:
        ok_greeting, err_greeting = validate_anti_greeting(message)
        if not ok_greeting and err_greeting:
            errors.append(err_greeting)

    # Anti-repetition check (against last 10 messages)
    if message:
        # Extract the raw message strings from the last 10 log entries
        recent_messages: List[str] = []
        for line in chat_history[-10:]:
            # If line is from chat.log formatted lines, extract message portion if indented
            m = re.search(r"^\s*>\s*(.+)$", line)
            if m:
                recent_messages.append(m.group(1))
            else:
                recent_messages.append(line)
        threshold = float(config.get("similarity_threshold", 0.6))
        ok_rep, err_rep = validate_anti_repetition(message, recent_messages, threshold)
        if not ok_rep and err_rep:
            errors.append(err_rep)

    # Output hygiene
    if message:
        ok_hygiene, err_hygiene = validate_hygiene(message, config.get("chat_language", "id"))
        if not ok_hygiene and err_hygiene:
            errors.append(err_hygiene)

    # Persona sanity
    if message:
        ok_persona, err_persona = validate_persona_sanity(message, current_slug, cast_slugs)
        if not ok_persona and err_persona:
            errors.append(err_persona)

    return len(errors) == 0, errors
