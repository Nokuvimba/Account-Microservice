from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Dev: SQLite file. Switching to Postgres later.
SQLALCHEMY_DATABASE_URL = "sqlite:///./dev.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # needed for SQLite + FastAPI
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) 

def get_db():
    db = SessionLocal() # create a new session
    try:
        yield db
    finally:
        db.close()
