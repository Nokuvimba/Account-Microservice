# tests/conftest.py
import os
import pytest
from fastapi.testclient import TestClient

# Use a throwaway SQLite DB just for tests (set BEFORE importing the app)
os.environ["DATABASE_URL"] = "sqlite:///./test_accounts.db"

from app.main import app
from app.database import engine
from app.models import Base

@pytest.fixture(autouse=True)
def _fresh_db():
    """Recreate tables before each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)