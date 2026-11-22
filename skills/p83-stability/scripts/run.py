"""Skill script: runs the P.8.3 stability writer through the same entry point as tools/writer_run.py --kind p83."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import writer_run  # noqa: E402  (tools/writer_run.py: the same file the direct run uses)


def main(argv=None):
    """Pass every argument on to writer_run with --kind p83 fixed."""
    return writer_run.main(["--kind", "p83"] + list(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    sys.exit(main())
