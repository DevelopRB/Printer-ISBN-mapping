"""Unit tests for direct ISBN search (single + batch) validation — no live printers."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from services.direct_isbn_search import (
    DirectSearchOccurrence,
    PrinterSearchStatus,
    direct_search_isbn,
    direct_search_isbns,
)
from services.printer_config_service import ensure_network_printer_configs


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ensure_network_printer_configs(session)
    try:
        yield session
    finally:
        session.close()


def test_empty_isbn_rejected(db):
    with pytest.raises(ValueError, match="Enter an ISBN or identifier"):
        direct_search_isbn(
            db,
            isbn="  ",
            printer_slots=[1],
            start_date="2026-08-20",
            end_date="2026-08-27",
        )


def test_from_after_to_rejected(db):
    with pytest.raises(ValueError, match="From date cannot be later than To date"):
        direct_search_isbn(
            db,
            isbn="9788182054370",
            printer_slots=[1],
            start_date="2026-08-27",
            end_date="2026-08-20",
        )


def test_no_printers_rejected(db):
    with pytest.raises(ValueError, match="Select at least one"):
        direct_search_isbn(
            db,
            isbn="9788182054370",
            printer_slots=[],
            start_date="2026-08-20",
            end_date="2026-08-27",
        )


def test_batch_empty_rejected(db):
    with pytest.raises(ValueError, match="at least one"):
        direct_search_isbns(
            db,
            isbns=["  ", ""],
            printer_slots=[1],
            start_date="2026-08-20",
            end_date="2026-08-27",
        )


def test_batch_dedupes_input_preserves_order_and_jobs(db):
    """Input duplicates searched once; printer job duplicates must both appear."""

    def fake_fetch(db, *, targets, printer_slots, start, end):
        matches = [
            DirectSearchOccurrence(
                isbn="9788182054370",
                print_date="2026-08-24",
                printer_name="Printer 1",
                printer_slot=1,
                source_filename="9788182054370.pdf",
                source_row=1,
                job_id="100",
                result="Complete",
                set_number="2",
                output_set="2",
            ),
            DirectSearchOccurrence(
                isbn="9788182054370",
                print_date="2026-08-25",
                printer_name="Printer 1",
                printer_slot=1,
                source_filename="9788182054370.pdf",
                source_row=2,
                job_id="101",
                result="Complete",
                set_number="1",
                output_set="1",
            ),
        ]
        statuses = [
            PrinterSearchStatus(slot=1, name="Printer 1", ok=True, record_count=2, match_count=2)
        ]
        steps = [{"label": "done", "status": "done"}]
        assert targets == {"9788182054370", "9789362800398"}
        assert printer_slots == [1]
        return matches, statuses, steps

    with patch("services.direct_isbn_search._fetch_and_match_printers", side_effect=fake_fetch):
        result = direct_search_isbns(
            db,
            isbns=[
                "9788182054370",
                "9788182054370",
                "9789362800398",
            ],
            printer_slots=[1],
            start_date="2026-08-20",
            end_date="2026-08-27",
            entered_count=3,
        )

    assert result.entered_count == 3
    assert result.unique_count == 2
    assert result.found_count == 1
    assert result.not_found_count == 1
    assert [r.normalized_isbn for r in result.results] == [
        "9788182054370",
        "9789362800398",
    ]
    assert len(result.results[0].occurrences) == 2
    assert result.results[0].status == "FOUND IN PRINTER DATA"
    assert result.results[1].status == "NOT FOUND"
    assert result.results[1].printer is False


def test_batch_connection_issue_not_reported_as_not_found(db):
    def fake_fetch(db, *, targets, printer_slots, start, end):
        matches: list[DirectSearchOccurrence] = []
        statuses = [
            PrinterSearchStatus(slot=1, name="Printer 1", ok=True, record_count=0, match_count=0),
            PrinterSearchStatus(
                slot=2, name="Printer 2", ok=False, error="Unable to connect to Printer 2."
            ),
        ]
        return matches, statuses, []

    with patch("services.direct_isbn_search._fetch_and_match_printers", side_effect=fake_fetch):
        result = direct_search_isbns(
            db,
            isbns=["9789353242497"],
            printer_slots=[1, 2],
            start_date="2026-08-20",
            end_date="2026-08-27",
        )

    assert result.results[0].status == "CONNECTION ISSUE"
    assert result.connection_issue_count == 1
    assert result.not_found_count == 0


def test_single_search_wrapper_maps_connection_to_not_found(db):
    """Preserve prior single-search status labelling for partial printer failure."""

    def fake_fetch(db, *, targets, printer_slots, start, end):
        return (
            [],
            [
                PrinterSearchStatus(slot=1, name="Printer 1", ok=True, record_count=0, match_count=0),
                PrinterSearchStatus(slot=2, name="Printer 2", ok=False, error="down"),
            ],
            [],
        )

    with patch("services.direct_isbn_search._fetch_and_match_printers", side_effect=fake_fetch):
        result = direct_search_isbn(
            db,
            isbn="9789353242497",
            printer_slots=[1, 2],
            start_date="2026-08-20",
            end_date="2026-08-27",
        )

    assert result.status == "NOT FOUND"
    assert result.printer is False


def test_batch_over_limit_rejected(db):
    isbns = [f"978818205{i:04d}" for i in range(1001)]
    with pytest.raises(ValueError, match="smaller batches"):
        direct_search_isbns(
            db,
            isbns=isbns,
            printer_slots=[1],
            start_date="2026-08-20",
            end_date="2026-08-27",
        )
