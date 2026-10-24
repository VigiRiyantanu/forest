"""Tick engine: executes exactly one autonomous turn if due."""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

# Ensure safe utf-8 console output across all platforms
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .agent import run_agent_turn
from .gitops import commit_turn
from .render_readme import format_chat_entry, format_timestamp, render_readme_file
from .validate import validate_turn

LOCK_FILE = ".tick.lock"


def is_pid_alive(pid: int) -> bool:
    """Check if process with pid is currently alive."""
    if pid <= 0:
        return False
    try:
        # On Windows and Unix, sending signal 0 checks for process existence
        os.kill(pid, 0)
        return True
    except (OSError, PermissionError, ProcessLookupError):
        return False


class TickLock:
    """File-based lock to prevent concurrent tick executions."""

    def __init__(self, lock_path: str = LOCK_FILE):
        self.lock_path = lock_path
        self.acquired = False

    def acquire(self) -> bool:
        if os.path.exists(self.lock_path):
            try:
                with open(self.lock_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                data = json.loads(content)
                old_pid = int(data.get("pid", 0))
                if old_pid and is_pid_alive(old_pid):
                    return False
            except Exception:
                # Corrupt lockfile, can be overwritten
                pass

        # Write new lock
        try:
            with open(self.lock_path, "w", encoding="utf-8") as f:
                json.dump({"pid": os.getpid(), "timestamp": datetime.now(timezone.utc).isoformat()}, f)
            self.acquired = True
            return True
        except Exception:
            return False

    def release(self) -> None:
        if self.acquired and os.path.exists(self.lock_path):
            try:
                os.remove(self.lock_path)
            except Exception:
                pass
            self.acquired = False

    def __enter__(self):
        if not self.acquire():
            print("[INFO] Tick is currently locked by another running process. Exiting cleanly.")
            sys.exit(0)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def load_json_file(path: str, default: Any = None) -> Any:
    """Load JSON from file or return default."""
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(path: str, data: Any) -> None:
    """Save JSON data to file with clean formatting."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def is_turn_due(
    last_run_at: Optional[str],
    interval_minutes: int,
    tolerance_minutes: int,
    now_dt: datetime,
) -> bool:
    """Check if turn is due based on last_run_at, interval, and tolerance."""
    if not last_run_at:
        return True
    try:
        last_dt = datetime.fromisoformat(last_run_at)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
    except Exception:
        return True

    elapsed_seconds = (now_dt - last_dt).total_seconds()
    due_threshold_seconds = (interval_minutes - tolerance_minutes) * 60
    return elapsed_seconds >= due_threshold_seconds


def log_error(repo_root: str, message: str) -> None:
    """Append error message to logs/errors.log."""
    logs_dir = os.path.join(repo_root, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    err_file = os.path.join(logs_dir, "errors.log")
    ts = datetime.now(timezone.utc).isoformat()
    with open(err_file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")


def run_tick(
    repo_root: Optional[str] = None,
    force: bool = False,
    override_config: Optional[Dict[str, Any]] = None,
) -> bool:
    """Execute one full turn of the animal village."""
    root = repo_root or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config_path = os.path.join(root, "config.json")
    state_path = os.path.join(root, "state.json")
    cast_path = os.path.join(root, "animals", "cast.json")
    animals_dir = os.path.join(root, "animals")
    knowledge_path = os.path.join(root, "knowledge.json")
    chat_log_path = os.path.join(root, "chat.log")
    readme_path = os.path.join(root, "README.md")
    prompts_dir = os.path.join(root, "prompts")
    playground_dir = os.path.join(root, "playground")

    lock = TickLock(os.path.join(root, LOCK_FILE))
    with lock:
        config = load_json_file(config_path, {})
        if override_config:
            config.update(override_config)

        state = load_json_file(state_path, {"counter": 0, "last_run_at": None, "cycle": {"id": 0, "interactions_used": {}}})
        cast = load_json_file(cast_path, [])
        if not cast:
            raise ValueError(f"No cast found at {cast_path}")

        mode = config.get("mode", "test")
        intervals = config.get("interval_minutes", {"test": 1, "prod": 480})
        interval_min = intervals.get(mode, 1)
        tolerance_min = config.get("tolerance_minutes", 10)
        dry_run = bool(config.get("dry_run", False))
        push = bool(config.get("push", False))
        tz_name = config.get("timezone", "Asia/Jakarta")

        now_utc = datetime.now(timezone.utc)

        # Check due time unless forced
        if not force and not is_turn_due(state.get("last_run_at"), interval_min, tolerance_min, now_utc):
            print(f"[INFO] Turn not due yet (interval: {interval_min}m, tolerance: {tolerance_min}m).")
            return False

        counter = int(state.get("counter", 0))

        # Synchronize cycle
        cycle_id = counter // 6
        if state.get("cycle", {}).get("id") != cycle_id:
            state["cycle"] = {"id": cycle_id, "interactions_used": {}}

        # Deterministic cast rotation and slot
        animal = cast[counter % 6]
        slot = ["pagi", "siang", "malam"][counter % 3]
        day_type = "A" if (counter // 3) % 2 == 0 else "B"
        current_slug = animal["slug"]

        # Read animal's memory
        mem_file = os.path.join(animals_dir, f"{current_slug}.json")
        animal_memory = load_json_file(mem_file, {"memory_lines": [], "relationships": {}, "known_topics": []})

        # Read chat history
        chat_lines: List[str] = []
        if os.path.exists(chat_log_path):
            with open(chat_log_path, "r", encoding="utf-8") as f:
                chat_lines = [line.rstrip() for line in f if line.strip()]

        # Determine eligible interaction targets (animals who have spoken before)
        eligible_targets = [
            a["slug"]
            for a in cast
            if a["slug"] != current_slug and any(f"{a['slug']}@" in line for line in chat_lines)
        ]

        # Read knowledge topics
        knowledge_list = load_json_file(knowledge_path, [])

        # Quota info
        cycle_info = state["cycle"]
        interactions_used = cycle_info.get("interactions_used", {}).get(current_slug, 0)
        interactions_limit = int(config.get("interactions_per_cycle", 1))

        # Agent execution with retries
        max_retries = int(config.get("llm_max_retries", 2))
        turn_data = None
        validation_errors: List[str] = []
        error_feedback: Optional[str] = None

        for attempt in range(max_retries + 1):
            agent_result, agent_err = run_agent_turn(
                animal=animal,
                slot=slot,
                day_type=day_type,
                memory_data=animal_memory,
                recent_chat_lines=chat_lines,
                recent_knowledge=knowledge_list,
                cycle_interactions_used=interactions_used,
                cycle_interactions_limit=interactions_limit,
                eligible_targets=eligible_targets,
                config=config,
                prompts_dir=prompts_dir,
                counter=counter,
                error_feedback=error_feedback,
            )

            if agent_err:
                validation_errors = [agent_err]
                error_feedback = agent_err
                continue

            # Validate all hard rules
            is_valid, v_errors = validate_turn(
                turn_data=agent_result,
                current_slug=current_slug,
                cast=cast,
                state=state,
                config=config,
                chat_history=chat_lines,
                knowledge_list=knowledge_list,
            )

            if is_valid:
                turn_data = agent_result
                break
            else:
                validation_errors = v_errors
                error_feedback = "; ".join(v_errors)

        if turn_data is None:
            err_msg = f"Turn validation failed after {max_retries} retries for {current_slug} (turn {counter}): {validation_errors}"
            log_error(root, err_msg)
            print(f"[ERROR] {err_msg}")
            return False

        # If dry-run, display what would happen and return without touching files
        if dry_run:
            print(f"[DRY-RUN] Turn {counter} | Slot: {slot} (Day {day_type}) | Animal: {animal['emoji']} {current_slug}")
            print(f"[DRY-RUN] Action: {turn_data.get('action')} | Message: {turn_data.get('message')}")
            print(f"[DRY-RUN] Knowledge: {turn_data.get('knowledge')}")
            print(f"[DRY-RUN] Interaction: {turn_data.get('interaction')}")
            commit_turn(
                animal=animal,
                slot=slot,
                message=turn_data.get("message", ""),
                repo_root=root,
                dry_run=True,
                push=push,
            )
            return True

        # Turn approved: Apply state updates
        action = turn_data.get("action")
        knowledge_item = turn_data.get("knowledge")
        interaction_item = turn_data.get("interaction")
        memory_note = turn_data.get("memory_note")
        rel_note = turn_data.get("relationship_note")

        # 1. Update animal memory
        if memory_note:
            mem_lines = animal_memory.setdefault("memory_lines", [])
            mem_lines.append(memory_note)
            if len(mem_lines) > 8:
                animal_memory["memory_lines"] = mem_lines[-8:]

        if rel_note and isinstance(rel_note, dict):
            r_target = rel_note.get("target")
            r_text = rel_note.get("note")
            if r_target and r_text:
                animal_memory.setdefault("relationships", {})[r_target] = r_text

        if action == "learn" and isinstance(knowledge_item, dict):
            top_id = knowledge_item.get("topic_id")
            known = animal_memory.setdefault("known_topics", [])
            if top_id and top_id not in known:
                known.append(top_id)

        if action == "discover" and isinstance(knowledge_item, dict):
            top_id = knowledge_item.get("topic_id")
            known = animal_memory.setdefault("known_topics", [])
            if top_id and top_id not in known:
                known.append(top_id)

        save_json_file(mem_file, animal_memory)

        # 2. Update village knowledge
        if action == "discover" and isinstance(knowledge_item, dict):
            new_entry = {
                "id": knowledge_item.get("topic_id"),
                "title": knowledge_item.get("title", knowledge_item.get("topic_id")),
                "lesson": knowledge_item.get("lesson", ""),
                "discovered_by": current_slug,
                "learned_by": [current_slug],
                "built_on": [],
            }
            knowledge_list.append(new_entry)
            save_json_file(knowledge_path, knowledge_list)

        elif action == "learn" and isinstance(knowledge_item, dict):
            top_id = knowledge_item.get("topic_id")
            for k in knowledge_list:
                if k.get("id") == top_id:
                    learned_by = k.setdefault("learned_by", [])
                    if current_slug not in learned_by:
                        learned_by.append(current_slug)
                    break
            save_json_file(knowledge_path, knowledge_list)

        # 3. Update interaction quota
        if action == "interact" and isinstance(interaction_item, dict):
            cycle_info = state["cycle"]
            cur_used = cycle_info.setdefault("interactions_used", {}).get(current_slug, 0)
            cycle_info["interactions_used"][current_slug] = cur_used + 1
            interactions_used = cur_used + 1

            # If interaction is teach and contains knowledge
            if interaction_item.get("type") == "teach" and isinstance(knowledge_item, dict):
                top_id = knowledge_item.get("topic_id")
                # Add to knowledge if new
                if not any(k.get("id") == top_id for k in knowledge_list):
                    knowledge_list.append({
                        "id": top_id,
                        "title": knowledge_item.get("title", top_id),
                        "lesson": knowledge_item.get("lesson", ""),
                        "discovered_by": current_slug,
                        "learned_by": [current_slug],
                        "built_on": [],
                    })
                    save_json_file(knowledge_path, knowledge_list)

        # 4. Optional playground note
        os.makedirs(playground_dir, exist_ok=True)
        note_filename = f"{counter}-{current_slug}.md"
        note_path = os.path.join(playground_dir, note_filename)
        with open(note_path, "w", encoding="utf-8") as f:
            f.write(f"# Turn {counter}: {animal['name']} ({current_slug})\n\n")
            f.write(f"Slot: {slot} (Day {day_type})\n\n")
            f.write(f"{turn_data.get('message', '')}\n")
        extra_files = [f"playground/{note_filename}"]

        # 5. Format and append to chat.log
        cast_map = {a["slug"]: a for a in cast}
        ts_str = format_timestamp(now_utc, tz_name)
        chat_entry = format_chat_entry(
            timestamp_str=ts_str,
            animal=animal,
            slot=slot,
            turn_data=turn_data,
            interactions_used=interactions_used,
            interactions_limit=interactions_limit,
            cast_by_slug=cast_map,
        )

        with open(chat_log_path, "a", encoding="utf-8") as f:
            # Separate by double newlines
            if os.path.getsize(chat_log_path) > 0:
                f.write("\n\n")
            f.write(chat_entry)

        # 6. Render README.md
        tail_count = int(config.get("readme_chat_tail", 20))
        render_readme_file(
            readme_path=readme_path,
            chat_log_path=chat_log_path,
            cast=cast,
            animals_dir=animals_dir,
            knowledge_list=knowledge_list,
            tail_count=tail_count,
        )

        # 7. Advance state
        state["counter"] = counter + 1
        state["last_run_at"] = now_utc.isoformat()
        save_json_file(state_path, state)

        # 8. GitOps commit
        commit_res = commit_turn(
            animal=animal,
            slot=slot,
            message=turn_data.get("message", ""),
            repo_root=root,
            extra_files=extra_files,
            dry_run=False,
            push=push,
        )

        print(
            f"[TURN {counter}] {animal['emoji']} {current_slug}@{slot}: {turn_data.get('message', '')[:60]}... "
            f"(Committed: {commit_res['committed']})"
        )
        return True


def main():
    parser = argparse.ArgumentParser(description="Animal Playground Tick Runner")
    parser.add_argument("--force", action="store_true", help="Force turn execution even if not due")
    parser.add_argument("--repo-root", type=str, default=None, help="Root directory of repository")
    args = parser.parse_args()

    success = run_tick(repo_root=args.repo_root, force=args.force)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
