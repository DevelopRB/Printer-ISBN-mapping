"""Printer connection testing against configured network endpoints.

Passwords are read from environment variables only and never logged or returned.
SSL verification for printers is controlled solely by PRINTER_VERIFY_SSL.
"""

from __future__ import annotations

import socket
import ssl
import time

import httpx

from logging_config import logger
from printers.base import BasePrinterAdapter, ConnectionTestResult
from settings import Settings, get_printer_credentials, settings as app_settings

# User-facing error categories (no stack traces / credentials)
CONNECTION_REFUSED = "connection_refused"
CONNECTION_TIMEOUT = "connection_timeout"
HOST_UNREACHABLE = "host_unreachable"
AUTHENTICATION_FAILED = "authentication_failed"
SSL_TLS_ERROR = "ssl_tls_error"
ENDPOINT_UNAVAILABLE = "endpoint_unavailable"
INVALID_RESPONSE = "invalid_response"
CREDENTIALS_MISSING = "credentials_missing"
CONNECTED = "connected"
UNKNOWN_ERROR = "unknown_error"

CATEGORY_LABELS = {
    CONNECTION_REFUSED: "Unable to connect to the printer. Please check that the computer is connected to the printer network.",
    CONNECTION_TIMEOUT: "The printer did not respond in time. Please check that the computer is connected to the printer network.",
    HOST_UNREACHABLE: "Unable to reach the printer. Please check that the computer is connected to the printer network.",
    AUTHENTICATION_FAILED: "Could not sign in to the printer. Please ask IT to verify the printer password.",
    SSL_TLS_ERROR: "Unable to open a secure connection to the printer. Please check the printer network connection.",
    ENDPOINT_UNAVAILABLE: "Unable to connect to the printer. Please check that the computer is connected to the printer network.",
    INVALID_RESPONSE: "The printer returned unexpected data. Please try again or ask IT for help.",
    CREDENTIALS_MISSING: "Printer password is not configured. Please ask IT to set it up.",
    CONNECTED: "Connected",
    UNKNOWN_ERROR: "Unable to connect to the printer. Please check that the computer is connected to the printer network.",
}


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, CATEGORY_LABELS[UNKNOWN_ERROR])


def build_printer_ssl_context(*, verify: bool) -> ssl.SSLContext | bool:
    """Build SSL context for internal printer HTTPS.

    When verify is False (PRINTER_VERIFY_SSL=false), disable cert checks and
    lower OpenSSL security level so older printer TLS stacks (common cipher
    suites) can complete the handshake. Applies ONLY to printer clients.
    """
    if verify:
        return True

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    # Industrial printer firmware often needs legacy ciphers / SECLEVEL=0
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
    except ssl.SSLError:
        try:
            ctx.set_ciphers("ALL:@SECLEVEL=0")
        except ssl.SSLError:
            pass
    try:
        # Allow TLS 1.0+ if the runtime still exposes it (deprecated but needed
        # for some printer firmware). Prefer negotiated TLSv1.2 when available.
        ctx.minimum_version = ssl.TLSVersion.TLSv1  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    return ctx


class JobLogPrinterAdapter(BasePrinterAdapter):
    """Adapter for printers exposing /goform/joblog.cgi.

    Phase 2B implements connect + light auth probe only.
    """

    def __init__(
        self,
        *,
        slot: int,
        name: str,
        protocol: str,
        host: str,
        port: int,
        joblog_path: str = "/goform/joblog.cgi",
        app_settings_override: Settings | None = None,
    ):
        self.slot = slot
        self.name = name
        self.protocol = protocol.lower().rstrip(":/")
        self.host = host.strip()
        self.port = int(port)
        self.joblog_path = joblog_path if joblog_path.startswith("/") else f"/{joblog_path}"
        self._settings = app_settings_override or app_settings
        self._client: httpx.Client | None = None

    @property
    def base_url(self) -> str:
        return f"{self.protocol}://{self.host}:{self.port}"

    @property
    def joblog_url(self) -> str:
        return f"{self.base_url}{self.joblog_path}"

    def _build_client(self) -> httpx.Client:
        verify: ssl.SSLContext | bool = True
        if self.protocol == "https":
            # PRINTER_VERIFY_SSL applies only to printer HTTPS connections.
            verify = build_printer_ssl_context(verify=self._settings.printer_verify_ssl)
        timeout = httpx.Timeout(
            connect=self._settings.printer_connect_timeout_seconds,
            read=self._settings.printer_read_timeout_seconds,
            write=self._settings.printer_connect_timeout_seconds,
            pool=self._settings.printer_connect_timeout_seconds,
        )
        return httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            verify=verify,
            follow_redirects=True,
        )

    def connect(self) -> ConnectionTestResult:
        """TCP + HTTP reachability check against the printer base URL."""
        start = time.perf_counter()
        try:
            self._tcp_probe()
        except OSError as exc:
            return self._map_os_error(exc, start)

        try:
            client = self._build_client()
            self._client = client
            response = client.get("/", follow_redirects=True)
            latency = int((time.perf_counter() - start) * 1000)

            # Any HTTP response (including 401/403/404) means the host is reachable.
            if response.status_code >= 500:
                return ConnectionTestResult(
                    ok=False,
                    category=ENDPOINT_UNAVAILABLE,
                    message=category_label(ENDPOINT_UNAVAILABLE),
                    http_status=response.status_code,
                    latency_ms=latency,
                )

            return ConnectionTestResult(
                ok=True,
                category=CONNECTED,
                message=category_label(CONNECTED),
                http_status=response.status_code,
                latency_ms=latency,
            )
        except Exception as exc:
            return self._map_httpx_error(exc, start)

    def authenticate(self) -> ConnectionTestResult:
        """Probe authentication using env credentials.

        Does not invent joblog form parameters. Uses HTTP Basic against the
        base URL / joblog path as a connectivity+credential sanity check.
        Full session/cookie auth will be implemented after UI inspection.
        """
        creds = get_printer_credentials(self.slot)
        username = creds.username() or "admin"
        password = creds.password()

        if password is None:
            logger.warning(
                "Printer slot %s missing password env %s",
                self.slot,
                creds.password_env,
            )
            return ConnectionTestResult(
                ok=False,
                category=CREDENTIALS_MISSING,
                message=f"{category_label(CREDENTIALS_MISSING)} ({creds.password_env})",
            )

        start = time.perf_counter()
        try:
            if self._client is None:
                connect_result = self.connect()
                if not connect_result.ok:
                    return connect_result

            assert self._client is not None
            # Probe joblog endpoint with basic auth — response shape is unknown;
            # treat 401/403 as auth failure, other 2xx/3xx/404 as reachable+authed probe.
            response = self._client.get(
                self.joblog_path,
                auth=(username, password),
            )
            latency = int((time.perf_counter() - start) * 1000)

            if response.status_code in (401, 403):
                return ConnectionTestResult(
                    ok=False,
                    category=AUTHENTICATION_FAILED,
                    message=category_label(AUTHENTICATION_FAILED),
                    http_status=response.status_code,
                    latency_ms=latency,
                )

            if response.status_code >= 500:
                return ConnectionTestResult(
                    ok=False,
                    category=ENDPOINT_UNAVAILABLE,
                    message=category_label(ENDPOINT_UNAVAILABLE),
                    http_status=response.status_code,
                    latency_ms=latency,
                )

            return ConnectionTestResult(
                ok=True,
                category=CONNECTED,
                message=category_label(CONNECTED),
                http_status=response.status_code,
                latency_ms=latency,
            )
        except Exception as exc:
            return self._map_httpx_error(exc, start)

    def test_connection(self, *, include_auth: bool = True) -> ConnectionTestResult:
        """Full connection test used by the API.

        Order:
        1) Reachability (TCP + HTTP)
        2) Credential presence
        3) Light auth probe (no invented joblog form params)
        """
        result = self.connect()
        if not result.ok:
            self.disconnect()
            creds = get_printer_credentials(self.slot)
            if not creds.has_password_configured():
                # Surface both issues: network failed, and password also missing
                return ConnectionTestResult(
                    ok=False,
                    category=result.category,
                    message=f"{result.message} (also: {category_label(CREDENTIALS_MISSING)} — {creds.password_env})",
                    http_status=result.http_status,
                    latency_ms=result.latency_ms,
                )
            return result

        if include_auth:
            auth_result = self.authenticate()
            self.disconnect()
            return auth_result

        self.disconnect()
        return result

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def _tcp_probe(self) -> None:
        with socket.create_connection(
            (self.host, self.port),
            timeout=self._settings.printer_connect_timeout_seconds,
        ):
            pass

    def _map_os_error(self, exc: OSError, start: float) -> ConnectionTestResult:
        latency = int((time.perf_counter() - start) * 1000)
        errno = getattr(exc, "errno", None)
        winerror = getattr(exc, "winerror", None)
        msg = str(exc).lower()

        logger.info(
            "Printer TCP probe failed slot=%s host=%s error_type=%s",
            self.slot,
            self.host,
            type(exc).__name__,
        )

        if isinstance(exc, TimeoutError) or "timed out" in msg:
            category = CONNECTION_TIMEOUT
        elif errno in (10061, 111) or winerror == 10061 or "refused" in msg:
            category = CONNECTION_REFUSED
        elif errno in (10051, 10065, 113, 101, 51) or "unreachable" in msg or "no route" in msg:
            category = HOST_UNREACHABLE
        elif "getaddrinfo" in msg or "name or service not known" in msg:
            category = HOST_UNREACHABLE
        else:
            category = CONNECTION_REFUSED if "connect" in msg else UNKNOWN_ERROR

        return ConnectionTestResult(
            ok=False,
            category=category,
            message=category_label(category),
            latency_ms=latency,
        )

    def _map_httpx_error(self, exc: Exception, start: float) -> ConnectionTestResult:
        latency = int((time.perf_counter() - start) * 1000)
        logger.info(
            "Printer HTTP probe failed slot=%s host=%s error_type=%s detail=%s",
            self.slot,
            self.host,
            type(exc).__name__,
            # Never log credentials; exception text from httpx is safe
            str(exc)[:300],
        )

        if isinstance(exc, (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.TimeoutException)):
            category = CONNECTION_TIMEOUT
        elif isinstance(exc, httpx.ConnectError):
            msg = str(exc).lower()
            # Prefer network categories; SSL only when clearly a cert/handshake issue
            if "refused" in msg or "10061" in msg or "actively refused" in msg:
                category = CONNECTION_REFUSED
            elif "unreachable" in msg or "no route" in msg or "10051" in msg or "10065" in msg:
                category = HOST_UNREACHABLE
            elif "timed out" in msg or "timeout" in msg:
                category = CONNECTION_TIMEOUT
            elif "certificate" in msg or "cert verify" in msg or "hostname mismatch" in msg:
                category = SSL_TLS_ERROR
            elif "ssl" in msg or "tls" in msg:
                # Handshake aborted often means host reachable but TLS failed,
                # or the route reset mid-handshake — still report as SSL/TLS.
                category = SSL_TLS_ERROR
            else:
                category = CONNECTION_REFUSED
        elif isinstance(exc, httpx.UnsupportedProtocol):
            category = INVALID_RESPONSE
        else:
            name = type(exc).__name__.lower()
            msg = str(exc).lower()
            if "certificate" in msg or "cert verify" in msg:
                category = SSL_TLS_ERROR
            elif "ssl" in name or "tls" in name:
                category = SSL_TLS_ERROR
            else:
                category = UNKNOWN_ERROR

        return ConnectionTestResult(
            ok=False,
            category=category,
            message=category_label(category),
            latency_ms=latency,
        )


def build_adapter_from_config(config) -> JobLogPrinterAdapter:
    """Build adapter from a NetworkPrinterConfig ORM row."""
    return JobLogPrinterAdapter(
        slot=config.slot,
        name=config.name,
        protocol=config.protocol,
        host=config.host,
        port=config.port,
        joblog_path=config.joblog_path,
    )
