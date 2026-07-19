import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "host"))


@pytest.fixture(scope="session")
def repo_root():
    return ROOT
