import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.observability import langfuse_configured


def test_langfuse_is_optional_without_credentials(monkeypatch):
    for key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    assert langfuse_configured() is False
