"""adit-agent -- lihat app/main.py untuk penjelasan lengkap."""

from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parent.parent / "VERSION"
try:
    __version__ = _VERSION_FILE.read_text(encoding="utf-8").strip()
except FileNotFoundError:  # fallback kalau VERSION tidak ikut ter-deploy
    __version__ = "0.0.0-unknown"
