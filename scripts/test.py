from __future__ import annotations

import argparse
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--filter")
    args, unknown = parser.parse_known_args()
    if unknown:
        raise SystemExit(f"unsupported test arguments: {' '.join(unknown)}")
    pattern = f"test_*{args.filter}*.py" if args.filter else "test_*.py"
    suite = unittest.defaultTestLoader.discover("tests", pattern=pattern)
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
