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
    _migrate_automated_runs_list_a_optional()

    # Seed network printer endpoint configs (no secrets)
    from services.printer_config_service import ensure_network_printer_configs

    db = SessionLocal()
    try:
        ensure_network_printer_configs(db)
    finally:
        db.close()


def _migrate_automated_runs_list_a_optional() -> None:
    """Allow printer-fetch / ISBN-search runs without a List A upload (SQLite)."""
    from sqlalchemy import text

    with engine.begin() as conn:
        tables = {
            r[0]
            for r in conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).fetchall()
        }
        if "automated_runs" not in tables:
            return
        cols = conn.execute(text("PRAGMA table_info(automated_runs)")).fetchall()
        list_a_col = next((c for c in cols if c[1] == "list_a_upload_id"), None)
        if not list_a_col or list_a_col[3] == 0:
            # Missing or already nullable (notnull=0)
            return

        conn.execute(text("PRAGMA foreign_keys=OFF"))
        conn.execute(
            text(
                """
                CREATE TABLE automated_runs_new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    list_a_upload_id INTEGER,
                    printer_slots_json TEXT NOT NULL,
                    start_date VARCHAR(10) NOT NULL,
                    end_date VARCHAR(10) NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    steps_json TEXT NOT NULL,
                    summary_json TEXT,
                    error_message TEXT,
                    started_at DATETIME NOT NULL,
                    completed_at DATETIME,
                    FOREIGN KEY(list_a_upload_id) REFERENCES uploads (id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO automated_runs_new (
                    id, list_a_upload_id, printer_slots_json, start_date, end_date,
                    status, steps_json, summary_json, error_message, started_at, completed_at
                )
                SELECT
                    id, list_a_upload_id, printer_slots_json, start_date, end_date,
                    status, steps_json, summary_json, error_message, started_at, completed_at
                FROM automated_runs
                """
            )
        )
        conn.execute(text("DROP TABLE automated_runs"))
        conn.execute(text("ALTER TABLE automated_runs_new RENAME TO automated_runs"))
        conn.execute(text("PRAGMA foreign_keys=ON"))
