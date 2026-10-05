#!/usr/bin/env python3
"""Print installed `herdr --skill`; check caller context, without controlling a session."""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=30,
                        help="Seconds for printing the skill only; NOT a work/review limit")
    args = parser.parse_args(argv)
    if not 0 < args.timeout < float("inf"):
        parser.error("--timeout must be a finite positive number")
    executable = shutil.which("herdr")
    if not executable:
        print("herdr is not in PATH. No session was inspected or controlled.", file=sys.stderr)
        return 2
    try:
        result = subprocess.run([executable, "--skill"], capture_output=True,
                                timeout=args.timeout, check=False)
    except subprocess.TimeoutExpired:
        print("herdr --skill timed out; no session control command was issued.", file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"Cannot run herdr --skill: {exc}", file=sys.stderr)
        return 3
    if result.stderr:
        sys.stderr.write(result.stderr.decode("utf-8", errors="replace"))
    if result.returncode != 0:
        print(f"herdr --skill failed (exit {result.returncode}); do not guess the CLI.", file=sys.stderr)
        return 3
    if not result.stdout.strip():
        print("herdr --skill returned an empty guide; do not continue.", file=sys.stderr)
        return 4
    try:
        guide = result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        print("herdr --skill was not UTF-8 text; guide could not be read.", file=sys.stderr)
        return 4
    sys.stdout.write(guide)
    sys.stdout.flush()
    digest = hashlib.sha256(result.stdout).hexdigest()
    print(f"\nsource={executable} --skill\nsha256={digest}", file=sys.stderr)
    if os.environ.get("HERDR_ENV") != "1":
        print("HERDR_ENV is not 1. Read-only guide retrieval completed, but session control is not allowed. "
              "Start the coding agent inside a real herdr pane; do not forge this variable.", file=sys.stderr)
        return 5
    print("Guide printed; caller declares a herdr environment. Read the guide before any control command. "
          "Live server connectivity and model availability have NOT been tested.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
