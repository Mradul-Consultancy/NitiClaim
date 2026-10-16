"""
Database session management & connection factory.
Works transparently with SQLite or PostgreSQL.
"""
from typing import Generator
from sqlmodel import SQLModel, create_engine, Session
from .config import settings

# SQLite specific connect_args to allow multithreading safely
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args=connect_args
)

def init_db() -> None:
    """Initialize database tables"""
    SQLModel.metadata.create_all(engine)

def get_session() -> Generator[Session, None, None]:
    """Dependency for obtaining database sessions in FastAPI routes or background workers"""
    with Session(engine) as session:
        yield session
