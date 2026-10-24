"""Git operations for animal commits with per-animal identities."""

import os
import subprocess
from typing import Any, Dict, List, Optional


def commit_turn(
    animal: Dict[str, Any],
    slot: str,
    message: str,
    repo_root: str,
    extra_files: Optional[List[str]] = None,
    dry_run: bool = False,
    push: bool = True,
) -> Dict[str, Any]:
    """Stage specific files and commit with the animal's identity."""
    slug = animal["slug"]
    name = animal["name"]
    email = f"{slug}@playground.local"

    # Message format: <slug>@<slot>: <first 60 chars of message>
    first_60 = message.strip()[:60]
    commit_msg = f"{slug}@{slot}: {first_60}"

    files_to_stage = [
        "README.md",
        "chat.log",
        "state.json",
        "knowledge.json",
        f"animals/{slug}.json",
    ]
    if extra_files:
        files_to_stage.extend(extra_files)

    result = {
        "author_name": name,
        "author_email": email,
        "commit_message": commit_msg,
        "staged_files": files_to_stage,
        "dry_run": dry_run,
        "committed": False,
        "pushed": False,
    }

    if dry_run:
        print(f"[DRY-RUN] Would commit as '{name} <{email}>'")
        print(f"[DRY-RUN] Commit message: {commit_msg}")
        print(f"[DRY-RUN] Staged files: {files_to_stage}")
        return result

    # Stage files that exist
    for fpath in files_to_stage:
        full_path = os.path.join(repo_root, fpath)
        if os.path.exists(full_path):
            subprocess.run(
                ["git", "add", fpath],
                cwd=repo_root,
                check=True,
                capture_output=True,
                text=True,
            )

    # Set up environment variables for this commit only
    commit_env = os.environ.copy()
    commit_env["GIT_AUTHOR_NAME"] = name
    commit_env["GIT_AUTHOR_EMAIL"] = email
    commit_env["GIT_COMMITTER_NAME"] = name
    commit_env["GIT_COMMITTER_EMAIL"] = email

    # Execute commit
    commit_res = subprocess.run(
        ["git", "commit", "-m", commit_msg],
        cwd=repo_root,
        env=commit_env,
        capture_output=True,
        text=True,
    )
    if commit_res.returncode == 0:
        result["committed"] = True
    else:
        # If nothing to commit (e.g. no diff), check output
        if "nothing to commit" in commit_res.stdout or "nothing to commit" in commit_res.stderr:
            result["committed"] = True
        else:
            raise RuntimeError(f"Git commit failed: {commit_res.stderr.strip() or commit_res.stdout.strip()}")

    # Push if enabled and remote exists
    if push:
        remote_res = subprocess.run(
            ["git", "remote"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        remotes = remote_res.stdout.strip().split()
        if remotes:
            push_res = subprocess.run(
                ["git", "push"],
                cwd=repo_root,
                capture_output=True,
                text=True,
            )
            if push_res.returncode == 0:
                result["pushed"] = True
            else:
                print(f"[WARNING] git push failed (non-fatal): {push_res.stderr.strip()}")
        else:
            # No remote configured, skip push cleanly
            result["pushed"] = False

    return result
