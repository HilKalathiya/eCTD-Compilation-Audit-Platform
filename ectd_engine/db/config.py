"""Reads database settings from environment variables or the local .env file."""
import os
from pathlib import Path


def load_env(path=None):
    """Return os.environ overlaid on .env (real environment variables win)."""
    path = Path(path) if path else Path(__file__).resolve().parents[2] / ".env"
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                values[key.strip()] = val.strip()
    values.update(os.environ)
    return values
