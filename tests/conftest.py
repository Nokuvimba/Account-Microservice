# tests/conftest.py

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_db
from app.models import Base

# In-memory SQLite engine shared across threads
engine = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Make sure foreign keys are on (SQLite default is off)
@event.listens_for(engine, "connect")
def _fk_on(dbapi_conn, _):
    dbapi_conn.execute("PRAGMA foreign_keys=ON")

TestingSessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

@pytest.fixture(autouse=True)
def _schema():
   #Create/drop schema around each test for isolation.
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    #FastAPI TestClient wired to the testing DB session.
    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()

@pytest.fixture
def mock_login_service():
    """Mock the external login service calls"""
    def mock_fetch_user(user_id: int):
        return {
            "id": user_id,
            "full_name": f"Test User {user_id}",
            "email": f"user{user_id}@example.com"
        }
    
    def mock_publish_event(*args, **kwargs):
        # Mock publisher - do nothing during tests
        pass
    
    with patch('app.main.fetch_user_from_login', side_effect=mock_fetch_user), \
         patch('app.main.publish_transaction_event', side_effect=mock_publish_event):
        yield