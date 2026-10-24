"""Reset Animal Playground repository to initial clean state."""

import argparse
import glob
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.render_readme import render_readme_file

SEED_KNOWLEDGE = [
    {
        "id": "pohon-beringin",
        "title": "Pohon Beringin Tua",
        "lesson": "Akar beringin tua menjaga tanah dan mata air desa tetap mengalir jernih.",
        "discovered_by": "alam",
        "learned_by": [],
        "built_on": [],
    },
    {
        "id": "aliran-sungai",
        "title": "Aliran Sungai Hulu",
        "lesson": "Bebatuan licin di aliran hulu sungai menjadi penanda arus bawah yang deras.",
        "discovered_by": "alam",
        "learned_by": [],
        "built_on": [],
    },
    {
        "id": "rasi-bintang",
        "title": "Rasi Bintang Malam",
        "lesson": "Rasi bintang utara memandu hewan pengelana kembali saat kabut malam menutupi bukit.",
        "discovered_by": "alam",
        "learned_by": [],
        "built_on": [],
    },
]

INITIAL_STATE = {
    "counter": 0,
    "last_run_at": None,
    "cycle": {
        "id": 0,
        "interactions_used": {},
    },
}

INITIAL_MEMORY = {
    "memory_lines": [],
    "relationships": {},
    "known_topics": [],
}


def reset_repository(repo_root: str = REPO_ROOT) -> None:
    """Reset repository state, memories, chat log, and generated README zones."""
    # 1. Reset state.json
    state_path = os.path.join(repo_root, "state.json")
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump(INITIAL_STATE, f, indent=2)
        f.write("\n")

    # 2. Reset chat.log
    chat_log_path = os.path.join(repo_root, "chat.log")
    with open(chat_log_path, "w", encoding="utf-8") as f:
        f.write("")

    # 3. Reset knowledge.json
    knowledge_path = os.path.join(repo_root, "knowledge.json")
    with open(knowledge_path, "w", encoding="utf-8") as f:
        json.dump(SEED_KNOWLEDGE, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # 4. Reset animal memories
    cast_path = os.path.join(repo_root, "animals", "cast.json")
    animals_dir = os.path.join(repo_root, "animals")
    with open(cast_path, "r", encoding="utf-8") as f:
        cast = json.load(f)

    for animal in cast:
        slug = animal["slug"]
        mem_path = os.path.join(animals_dir, f"{slug}.json")
        with open(mem_path, "w", encoding="utf-8") as f:
            json.dump(INITIAL_MEMORY, f, indent=2)
            f.write("\n")

    # 5. Clean playground notes
    playground_dir = os.path.join(repo_root, "playground")
    for md_file in glob.glob(os.path.join(playground_dir, "*.md")):
        try:
            os.remove(md_file)
        except Exception:
            pass

    # 6. Re-render README.md
    readme_path = os.path.join(repo_root, "README.md")
    render_readme_file(
        readme_path=readme_path,
        chat_log_path=chat_log_path,
        cast=cast,
        animals_dir=animals_dir,
        knowledge_list=SEED_KNOWLEDGE,
        tail_count=20,
    )

    # 7. Remove lock and error logs
    lock_file = os.path.join(repo_root, ".tick.lock")
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
        except Exception:
            pass

    err_log = os.path.join(repo_root, "logs", "errors.log")
    if os.path.exists(err_log):
        try:
            os.remove(err_log)
        except Exception:
            pass

    print("✨ Animal Playground successfully reset to initial clean state.")


def main():
    parser = argparse.ArgumentParser(description="Reset Animal Playground to initial state")
    parser.add_argument("--yes", action="store_true", help="Confirm reset without interactive prompt")
    args = parser.parse_args()

    if not args.yes:
        if sys.stdin.isatty():
            confirm = input("⚠️  Are you sure you want to reset the village state and memories? (y/N): ")
            if confirm.strip().lower() != "y":
                print("Reset aborted.")
                sys.exit(0)
        else:
            print("Error: --yes flag required to reset repository in non-interactive mode.", file=sys.stderr)
            sys.exit(1)

    reset_repository()


if __name__ == "__main__":
    main()
