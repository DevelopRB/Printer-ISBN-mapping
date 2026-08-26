"""Base printer adapter interface.

Phase 2A/2B: connection testing only.
Job-log retrieval (get_job_log / fetch_job_log) will be implemented after
inspecting the real /goform/joblog.cgi request structure — do not invent params.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass
class ConnectionTestResult:
    ok: bool
    category: str
    message: str
    http_status: int | None = None
    latency_ms: int | None = None


class BasePrinterAdapter(ABC):
    """Common contract for all printer integrations."""

    @abstractmethod
    def connect(self) -> ConnectionTestResult:
        """Establish reachability to the printer base URL."""

    @abstractmethod
    def authenticate(self) -> ConnectionTestResult:
        """Authenticate using credentials from environment variables."""

    @abstractmethod
    def disconnect(self) -> None:
        """Release session resources."""

    def get_job_log(self) -> Any:
        raise NotImplementedError(
            "Job log retrieval is not implemented yet. "
            "Inspect the real /goform/joblog.cgi request structure first."
        )

    def fetch_job_log(self, start_date: date, end_date: date) -> Any:
        raise NotImplementedError(
            "Date-range job log retrieval is not implemented yet. "
            "Inspect the real /goform/joblog.cgi request structure first."
        )

    def download_job_log(self, start_date: date, end_date: date) -> Any:
        raise NotImplementedError(
            "Job log download/export is not implemented yet. "
            "Inspect the real /goform/joblog.cgi request structure first."
        )
