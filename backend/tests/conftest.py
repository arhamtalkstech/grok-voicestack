import os
import tempfile
from pathlib import Path

import pytest

# Settings are cached on first import, so point everything at a throwaway directory first.
_TMP = Path(tempfile.mkdtemp(prefix="voicestack-test-"))
os.environ.setdefault("DATA_DIR", str(_TMP))
os.environ["SEED_EXAMPLE"] = "false"
os.environ["APP_ENV"] = "test"
os.environ.setdefault("APP_ENCRYPTION_KEY", "test-only-key-not-secret")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = PROJECT_ROOT / "examples" / "landscapes" / "front-desk.yaml"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
async def _close_persistence():
    yield
    from voicestack.runtime.persistence import close_persistence

    await close_persistence()
