import os

# The Kubernetes manager is created when the app is imported and reads
# DEMO_MODE at that moment, so it must be set before any app import.
os.environ["DEMO_MODE"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    return TestClient(app)
