import os
import subprocess
from src.gitops import commit_turn

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def test_dry_run_commits_nothing():
    animal = {
        "slug": "ayam-jantan",
        "name": "Ayam Jantan",
    }
    slot = "pagi"
    message = "Catatan giliran fajar yang sangat indah dan penuh semangat."

    result = commit_turn(
        animal=animal,
        slot=slot,
        message=message,
        repo_root=REPO_ROOT,
        dry_run=True,
        push=False,
    )

    assert result["dry_run"] is True
    assert result["author_name"] == "Ayam Jantan"
    assert result["author_email"] == "ayam-jantan@playground.local"
    assert result["commit_message"].startswith("ayam-jantan@pagi: Catatan giliran fajar")
    assert result["committed"] is False


def test_commit_identity_format():
    animal = {
        "slug": "kucing",
        "name": "Kucing",
    }
    slot = "siang"
    message = "Tidur siang di bawah pohon rindang sangat menenangkan suasana."

    result = commit_turn(
        animal=animal,
        slot=slot,
        message=message,
        repo_root=REPO_ROOT,
        dry_run=True,
        push=False,
    )

    assert result["author_name"] == "Kucing"
    assert result["author_email"] == "kucing@playground.local"
    assert result["commit_message"] == f"kucing@siang: {message[:60]}"
