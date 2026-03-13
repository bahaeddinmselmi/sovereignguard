import os
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("TARGET_API_KEY", "test-key")

from sovereignguard.main import app
from sovereignguard.engine.masker import MaskingEngine


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def engine():
    return MaskingEngine()
