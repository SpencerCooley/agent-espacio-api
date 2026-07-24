#!/usr/bin/env python3
"""Rewrite post-receive hooks for all bare repos under STORAGE_PATH/repos."""
import os
import sys

# Allow running inside the API container
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controllers.artifact.create import REPOS_DIR, write_post_receive_hook


def main() -> int:
    if not os.path.isdir(REPOS_DIR):
        print(f"No repos dir: {REPOS_DIR}")
        return 1

    count = 0
    for name in sorted(os.listdir(REPOS_DIR)):
        if not name.endswith(".git"):
            continue
        repo_path = os.path.join(REPOS_DIR, name)
        if not os.path.isdir(repo_path):
            continue
        artifact_id = name[: -len(".git")]
        write_post_receive_hook(repo_path, artifact_id)
        print(f"updated {name}")
        count += 1

    print(f"done: {count} hook(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
