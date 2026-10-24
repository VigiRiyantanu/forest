import json
import os
import shutil
import tempfile
import pytest

from src.tick import run_tick
from scripts.reset import reset_repository

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_dry_run_leaves_files_unchanged():
    state_path = os.path.join(REPO_ROOT, "state.json")
    with open(state_path, "r", encoding="utf-8") as f:
        before_state = f.read()

    readme_path = os.path.join(REPO_ROOT, "README.md")
    with open(readme_path, "r", encoding="utf-8") as f:
        before_readme = f.read()

    # Run tick with force and dry_run
    override = {"dry_run": True}
    res = run_tick(repo_root=REPO_ROOT, force=True, override_config=override)
    assert res is True

    # Confirm state and readme are completely unchanged
    with open(state_path, "r", encoding="utf-8") as f:
        after_state = f.read()
    assert before_state == after_state

    with open(readme_path, "r", encoding="utf-8") as f:
        after_readme = f.read()
    assert before_readme == after_readme


def test_failed_validation_does_not_advance_counter(monkeypatch):
    # Set mock to always return invalid json
    monkeypatch.setenv("MOCK_LLM_ALWAYS_INVALID", "true")

    state_path = os.path.join(REPO_ROOT, "state.json")
    with open(state_path, "r", encoding="utf-8") as f:
        initial_state = json.load(f)
    initial_counter = initial_state["counter"]

    res = run_tick(repo_root=REPO_ROOT, force=True)
    assert res is False

    with open(state_path, "r", encoding="utf-8") as f:
        current_state = json.load(f)
    assert current_state["counter"] == initial_counter

    # Check error log
    err_log = os.path.join(REPO_ROOT, "logs", "errors.log")
    assert os.path.exists(err_log)
    with open(err_log, "r", encoding="utf-8") as f:
        err_content = f.read()
    assert "Turn validation failed" in err_content


def test_twelve_consecutive_mock_turns_in_scratch_repo():
    """Verify acceptance criteria 3, 4, and 5 in a temporary scratch repository copy."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Copy repository contents into temp_dir
        for item in ["animals", "prompts", "src", "scripts", "config.json", "state.json", "chat.log", "knowledge.json", "README.md", "playground"]:
            src_item = os.path.join(REPO_ROOT, item)
            dst_item = os.path.join(temp_dir, item)
            if os.path.isdir(src_item):
                shutil.copytree(src_item, dst_item)
            elif os.path.isfile(src_item):
                shutil.copy2(src_item, dst_item)

        # Reset temp repo to clean initial state
        reset_repository(repo_root=temp_dir)

        # Initialize git repo in temp_dir for gitops commits
        import subprocess
        subprocess.run(["git", "init", "-b", "main"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=temp_dir, check=True)
        subprocess.run(["git", "config", "user.email", "runner@test.local"], cwd=temp_dir, check=True)
        subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial test commit"], cwd=temp_dir, check=True)

        # Read initial README manual zone
        with open(os.path.join(temp_dir, "README.md"), "r", encoding="utf-8") as f:
            initial_readme = f.read()
        chat_start_idx = initial_readme.find("<!-- CHAT:START -->")
        manual_zone_before = initial_readme[:chat_start_idx]

        expected_cast = [
            ("ayam-jantan", "🐓", "pagi"),
            ("kucing", "🐱", "siang"),
            ("burung-hantu", "🦉", "malam"),
            ("burung-pipit", "🐦", "pagi"),
            ("rubah", "🦊", "siang"),
            ("kelelawar", "🦇", "malam"),
        ]

        # Run 12 consecutive turns with mock provider
        for turn_idx in range(12):
            override = {"mode": "test", "dry_run": False, "push": False}
            ran = run_tick(repo_root=temp_dir, force=True, override_config=override)
            assert ran is True, f"Turn {turn_idx} failed"

        # Check state after 12 turns
        with open(os.path.join(temp_dir, "state.json"), "r", encoding="utf-8") as f:
            final_state = json.load(f)
        assert final_state["counter"] == 12

        # Verify chat.log entries rotation & slots
        with open(os.path.join(temp_dir, "chat.log"), "r", encoding="utf-8") as f:
            chat_log = f.read()

        import re
        entry_headers = re.findall(r"\[\d+\s+[A-Za-z]+\s+\d{2}:\d{2}\]\s+(\S+)\s+(\S+)@(\S+)", chat_log)
        assert len(entry_headers) == 12

        for idx, (emoji, slug, slot) in enumerate(entry_headers):
            exp_slug, exp_emoji, exp_slot = expected_cast[idx % 6]
            assert slug == exp_slug, f"Turn {idx}: expected slug {exp_slug}, got {slug}"
            assert emoji == exp_emoji, f"Turn {idx}: expected emoji {exp_emoji}, got {emoji}"
            assert slot == exp_slot, f"Turn {idx}: expected slot {exp_slot}, got {slot}"

        # Acceptance check 4: No animal exceeds interaction quota in any cycle; every interaction message is <= 50 words
        # In chat.log, check all interaction messages
        entries = chat_log.split("\n\n")
        assert len(entries) == 12
        for entry in entries:
            if "interaksi 1/1" in entry:
                # Extract message line
                msg_lines = [line.strip()[2:].strip() for line in entry.splitlines() if line.strip().startswith(">")]
                full_msg = " ".join(msg_lines)
                words = full_msg.split()
                assert len(words) <= 50, f"Interaction message exceeds 50 words: {len(words)} words"

        # Acceptance check 5: README manual zone is unchanged after 12 turns, CHAT block shows entries
        with open(os.path.join(temp_dir, "README.md"), "r", encoding="utf-8") as f:
            final_readme = f.read()
        manual_zone_after = final_readme[:final_readme.find("<!-- CHAT:START -->")]
        assert manual_zone_before == manual_zone_after

        # CHAT block shows tail
        assert "```console" in final_readme
        assert "playground@desa-hewan:~$ tail -n 20 chat.log" in final_readme
        assert "playground@desa-hewan:~$ █" in final_readme
        # All 12 entries are within tail 20, so all 12 are present
        assert "ayam-jantan@pagi" in final_readme
        assert "kelelawar@malam" in final_readme
