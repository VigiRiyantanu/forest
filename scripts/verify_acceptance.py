"""Independent script to verify all acceptance checks from Section 14."""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from scripts.reset import reset_repository
from src.tick import run_tick


def check_1_pytest():
    print("\n--- Acceptance Check 1: pytest ---")
    res = subprocess.run([sys.executable, "-m", "pytest", "-v"], cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8")
    passed = res.returncode == 0
    print(f"Result: {'PASS' if passed else 'FAIL'}")
    lines = [l for l in res.stdout.splitlines() if "passed" in l or "failed" in l]
    print("\n".join(lines[-3:]))
    assert passed, f"pytest failed:\n{res.stdout}\n{res.stderr}"


def check_2_dry_run():
    print("\n--- Acceptance Check 2: Dry Run Changes No Files ---")
    os.environ["LLM_PROVIDER"] = "mock"
    # Take file hash / contents
    state_file = os.path.join(REPO_ROOT, "state.json")
    readme_file = os.path.join(REPO_ROOT, "README.md")
    chat_file = os.path.join(REPO_ROOT, "chat.log")

    with open(state_file, "r", encoding="utf-8") as f:
        s_before = f.read()
    with open(readme_file, "r", encoding="utf-8") as f:
        r_before = f.read()
    with open(chat_file, "r", encoding="utf-8") as f:
        c_before = f.read()

    ran = run_tick(repo_root=REPO_ROOT, force=True, override_config={"dry_run": True})
    assert ran is True, "dry-run tick failed"

    with open(state_file, "r", encoding="utf-8") as f:
        s_after = f.read()
    with open(readme_file, "r", encoding="utf-8") as f:
        r_after = f.read()
    with open(chat_file, "r", encoding="utf-8") as f:
        c_after = f.read()

    assert s_before == s_after, "state.json was modified in dry_run!"
    assert r_before == r_after, "README.md was modified in dry_run!"
    assert c_before == c_after, "chat.log was modified in dry_run!"
    print("Result: PASS (Dry run printed full turn and zero files changed)")


def check_3_4_5_twelve_turns():
    print("\n--- Acceptance Checks 3, 4, 5: 12 Consecutive Turns in Scratch Repo ---")
    with tempfile.TemporaryDirectory() as temp_dir:
        # Copy repo
        for item in ["animals", "prompts", "src", "scripts", "config.json", "state.json", "chat.log", "knowledge.json", "README.md", "playground"]:
            s = os.path.join(REPO_ROOT, item)
            d = os.path.join(temp_dir, item)
            if os.path.isdir(s):
                shutil.copytree(s, d)
            elif os.path.isfile(s):
                shutil.copy2(s, d)

        reset_repository(repo_root=temp_dir)

        # Init git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=temp_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test Runner"], cwd=temp_dir, check=True)
        subprocess.run(["git", "config", "user.email", "runner@test.local"], cwd=temp_dir, check=True)
        subprocess.run(["git", "add", "."], cwd=temp_dir, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_dir, check=True)

        with open(os.path.join(temp_dir, "README.md"), "r", encoding="utf-8") as f:
            r_orig = f.read()
        manual_before = r_orig[: r_orig.find("<!-- CHAT:START -->")]

        expected_cast = [
            ("ayam-jantan", "🐓", "pagi"),
            ("kucing", "🐱", "siang"),
            ("burung-hantu", "🦉", "malam"),
            ("burung-pipit", "🐦", "pagi"),
            ("rubah", "🦊", "siang"),
            ("kelelawar", "🦇", "malam"),
        ]

        print("Running 12 turns...")
        for turn_idx in range(12):
            ok = run_tick(repo_root=temp_dir, force=True, override_config={"mode": "test", "dry_run": False, "push": False})
            assert ok is True, f"Turn {turn_idx} failed"

        # Check 3: Rotation
        with open(os.path.join(temp_dir, "chat.log"), "r", encoding="utf-8") as f:
            chat_log = f.read()

        entry_headers = re.findall(r"\[\d+\s+[A-Za-z]+\s+\d{2}:\d{2}\]\s+(\S+)\s+(\S+)@(\S+)", chat_log)
        assert len(entry_headers) == 12, f"Expected 12 headers, found {len(entry_headers)}"

        actual_emojis = []
        actual_slots = []
        for idx, (emoji, slug, slot) in enumerate(entry_headers):
            exp_slug, exp_emoji, exp_slot = expected_cast[idx % 6]
            assert slug == exp_slug, f"Turn {idx}: expected {exp_slug}, got {slug}"
            assert emoji == exp_emoji, f"Turn {idx}: expected {exp_emoji}, got {emoji}"
            assert slot == exp_slot, f"Turn {idx}: expected {exp_slot}, got {slot}"
            actual_emojis.append(emoji)
            actual_slots.append(slot)

        print(f"Rotation verified: {' '.join(actual_emojis)}")
        print(f"Slots verified: {' '.join(actual_slots)}")
        print("Check 3 Result: PASS")

        # Check 4: Quota & <= 50 words on interactions
        entries = chat_log.split("\n\n")
        assert len(entries) == 12
        for idx, entry in enumerate(entries):
            if "interaksi" in entry:
                # check quota format e.g. 1/1
                assert "interaksi 1/1" in entry
                # check message length
                msg_lines = [l.strip()[2:].strip() for l in entry.splitlines() if l.strip().startswith(">")]
                full_msg = " ".join(msg_lines)
                w_count = len(full_msg.split())
                assert w_count <= 50, f"Turn {idx} interaction message has {w_count} words (> 50)"

        print("Check 4 Result: PASS (All interactions <= 50 words, quota 1/1 maintained)")

        # Check 5: README manual zone unchanged & CHAT block shows entries
        with open(os.path.join(temp_dir, "README.md"), "r", encoding="utf-8") as f:
            r_final = f.read()

        manual_after = r_final[: r_final.find("<!-- CHAT:START -->")]
        assert manual_before == manual_after, "README manual zone was modified!"
        assert "```console" in r_final
        assert "playground@desa-hewan:~$ tail -n 20 chat.log" in r_final
        assert "playground@desa-hewan:~$ █" in r_final

        print("Check 5 Result: PASS (README manual zone strictly byte-identical, CHAT block formatted)")


def check_6_network_isolation():
    print("\n--- Acceptance Check 6: Network Isolation Grep ---")
    network_libs = ["urllib", "requests", "http", "socket", "ftplib", "aiohttp", "httpx", "urllib3"]
    pattern = re.compile(r"^\s*(?:import|from)\s+(" + "|".join(network_libs) + r")\b", re.MULTILINE)

    violations = []
    scanned = []

    for folder in ["src", "scripts"]:
        folder_path = os.path.join(REPO_ROOT, folder)
        for root_dir, _, files in os.walk(folder_path):
            for file in files:
                if not file.endswith(".py"):
                    continue
                full_path = os.path.join(root_dir, file)
                rel_path = os.path.relpath(full_path, REPO_ROOT).replace("\\", "/")
                scanned.append(rel_path)
                if rel_path == "src/llm.py":
                    continue
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                m = pattern.search(content)
                if m:
                    violations.append(f"{rel_path} imports {m.group(1)}")

    print(f"Scanned files ({len(scanned)}): {', '.join(scanned)}")
    assert len(violations) == 0, f"Network isolation violations: {violations}"
    print("Check 6 Result: PASS (No module besides src/llm.py imports any network library)")


def main():
    print("==========================================")
    print("🐾 ANIMAL PLAYGROUND ACCEPTANCE SUITE 🐾")
    print("==========================================")
    check_1_pytest()
    check_2_dry_run()
    check_3_4_5_twelve_turns()
    check_6_network_isolation()
    print("\n==========================================")
    print("✅ ALL 6 ACCEPTANCE CHECKS PASSED!")
    print("==========================================")


if __name__ == "__main__":
    main()
