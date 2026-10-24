import os
import re

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

NETWORK_LIBS = [
    "urllib",
    "requests",
    "http",
    "socket",
    "ftplib",
    "aiohttp",
    "httpx",
    "urllib3",
]


def test_network_isolation_check():
    """Verify that NO module besides src/llm.py imports any network library."""
    forbidden_import_pattern = re.compile(
        r"^\s*(?:import|from)\s+(" + "|".join(NETWORK_LIBS) + r")\b",
        re.MULTILINE,
    )

    scanned_files = []
    violations = []

    for folder in ["src", "scripts"]:
        folder_path = os.path.join(REPO_ROOT, folder)
        for root_dir, _, files in os.walk(folder_path):
            for file in files:
                if not file.endswith(".py"):
                    continue

                full_path = os.path.join(root_dir, file)
                rel_path = os.path.relpath(full_path, REPO_ROOT).replace("\\", "/")
                scanned_files.append(rel_path)

                # llm.py is explicitly the only allowed network adapter
                if rel_path == "src/llm.py":
                    continue

                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()

                match = forbidden_import_pattern.search(content)
                if match:
                    violations.append(f"{rel_path} imports network library '{match.group(1)}'")

    assert len(scanned_files) >= 5, f"Should have scanned multiple files, found: {scanned_files}"
    assert len(violations) == 0, f"Network isolation violated: {violations}"
