"""SQLite database configuration and session management."""

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from runtime_paths import data_dir

DATA_DIR = data_dir()
DATA_DIR.mkdir(parents=True, exist_ok=True)

UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

PRINTER_DOWNLOADS_DIR = DATA_DIR / "printer_downloads"
PRINTER_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'reconciliation.db'}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from models import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Seed network printer endpoint configs (no secrets)
    from services.printer_config_service import ensure_network_printer_configs

    db = SessionLocal()
    try:
        ensure_network_printer_configs(db)
    finally:
        db.close()
