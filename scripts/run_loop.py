"""Local execution loop for test mode.

Loops on the local machine, re-reads config every iteration, sleeps until
the next due time, stops after max_commits_test turns or on Ctrl+C.
"""

import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure repo root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.tick import run_tick


def load_config() -> dict:
    cfg_path = os.path.join(REPO_ROOT, "config.json")
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_state() -> dict:
    state_path = os.path.join(REPO_ROOT, "state.json")
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"counter": 0}


def main():
    print("🐾 Starting Animal Playground test loop...")
    print("Press Ctrl+C at any time to halt.\n")

    try:
        while True:
            config = load_config()
            state = load_state()

            counter = int(state.get("counter", 0))
            max_commits = int(config.get("max_commits_test", 12))

            if counter >= max_commits:
                print(f"[LOOP] Reached max_commits_test target ({counter}/{max_commits}). Loop completed.")
                break

            # Run turn
            ran = run_tick(repo_root=REPO_ROOT, force=False)

            # Re-read config in case interval was modified live
            config = load_config()
            interval_sec = int(config.get("interval_minutes", {}).get("test", 1)) * 60

            if ran:
                sleep_sec = min(interval_sec, 60)
            else:
                sleep_sec = 5

            time.sleep(sleep_sec)

    except KeyboardInterrupt:
        print("\n[LOOP] Gracefully stopped by user (Ctrl+C).")


if __name__ == "__main__":
    main()
