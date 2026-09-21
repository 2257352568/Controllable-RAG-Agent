"""Verify the schema and SHA256 envelope of one persisted runtime trace."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from controllable_rag.tracing import verify_trace  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", type=Path)
    args = parser.parse_args()
    valid, reason = verify_trace(args.trace)
    print(f"valid={str(valid).lower()} reason={reason}")
    raise SystemExit(0 if valid else 1)


if __name__ == "__main__":
    main()
