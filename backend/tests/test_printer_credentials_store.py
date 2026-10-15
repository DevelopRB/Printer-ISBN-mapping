"""Tests for saving printer logins entered in the app."""

from __future__ import annotations

import pytest
from dotenv import dotenv_values

from services.printer_credentials_store import save_printer_credentials
from settings import get_printer_credentials

SLOT = 2
USER_ENV = "PRINTER_2_USERNAME"
PASS_ENV = "PRINTER_2_PASSWORD"


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    path = tmp_path / ".env"
    monkeypatch.setenv("PRINTING_RECON_ENV_FILE", str(path))
    monkeypatch.delenv(USER_ENV, raising=False)
    monkeypatch.delenv(PASS_ENV, raising=False)
    return path


def test_saves_to_file_and_applies_immediately(env_file):
    env_file.write_text(
        "# printer settings\nPRINTER_1_PASSWORD='keep-me'\nPRINTER_2_USERNAME=admin\n"
        "PRINTER_2_PASSWORD=\nPRINTER_VERIFY_SSL=false\n",
        encoding="utf-8",
    )

    save_printer_credentials(SLOT, "operator", "s3cret")

    values = dotenv_values(env_file)
    assert values[USER_ENV] == "operator"
    assert values[PASS_ENV] == "s3cret"
    assert values["PRINTER_1_PASSWORD"] == "keep-me"
    assert values["PRINTER_VERIFY_SSL"] == "false"
    assert env_file.read_text(encoding="utf-8").startswith("# printer settings\n")

    creds = get_printer_credentials(SLOT)
    assert creds.username() == "operator"
    assert creds.password() == "s3cret"


def test_creates_file_and_appends_missing_keys(env_file):
    save_printer_credentials(SLOT, "admin", "pw")
    values = dotenv_values(env_file)
    assert values[USER_ENV] == "admin"
    assert values[PASS_ENV] == "pw"


@pytest.mark.parametrize(
    "password",
    ["has space", "with#hash", "quote'single", 'quote"double', "back\\slash", "a = b", "$HOME"],
)
def test_special_characters_round_trip(env_file, password):
    save_printer_credentials(SLOT, "admin", password)
    assert dotenv_values(env_file)[PASS_ENV] == password


def test_blank_password_keeps_saved_one(env_file):
    save_printer_credentials(SLOT, "admin", "original")
    save_printer_credentials(SLOT, "newuser", "")
    values = dotenv_values(env_file)
    assert values[USER_ENV] == "newuser"
    assert values[PASS_ENV] == "original"
    assert get_printer_credentials(SLOT).password() == "original"


def test_password_required_when_none_saved(env_file):
    with pytest.raises(ValueError, match="password"):
        save_printer_credentials(SLOT, "admin", None)
    assert not env_file.exists()


def test_username_required(env_file):
    with pytest.raises(ValueError, match="username"):
        save_printer_credentials(SLOT, "   ", "pw")


def test_rejects_newlines(env_file):
    with pytest.raises(ValueError):
        save_printer_credentials(SLOT, "admin", "pw\nPRINTER_1_PASSWORD=x")


def test_api_never_returns_password(env_file):
    from fastapi.testclient import TestClient

    from main import app

    client = TestClient(app)
    res = client.put(f"/api/network-printers/{SLOT}/credentials", json={"username": "ops", "password": "top-secret-pw"})
    assert res.status_code == 200
    body = res.json()
    assert body["username"] == "ops"
    assert body["password_configured"] is True
    assert "top-secret-pw" not in res.text

    bad = client.put(f"/api/network-printers/{SLOT}/credentials", json={"username": "ops", "password": "x" * 500})
    assert bad.status_code == 400
    assert "xxxxx" not in bad.text
