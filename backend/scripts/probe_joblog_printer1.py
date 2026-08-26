"""Phase 2C: probe Printer 1 authentication and joblog.cgi behavior.

Does not invent parameters — explores actual HTML forms and responses.
Never prints password values.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from printers.connection import build_printer_ssl_context
from settings import get_printer_credentials, settings

OUT = Path(__file__).resolve().parents[1] / "data" / "joblog_probe"
OUT.mkdir(parents=True, exist_ok=True)


def redact(text: str, password: str | None) -> str:
    if password and password in text:
        text = text.replace(password, "<REDACTED>")
    # common session-ish patterns
    text = re.sub(r"(sessionid|sid|token|auth)=([^&\s;]+)", r"\1=<REDACTED>", text, flags=re.I)
    return text


def save(name: str, content: str | bytes, password: str | None = None):
    path = OUT / name
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(redact(content, password), encoding="utf-8", errors="replace")
    print(f"saved {path.name} ({path.stat().st_size} bytes)")


def extract_forms(html: str) -> list[dict]:
    forms = []
    for m in re.finditer(r"<form\b([^>]*)>(.*?)</form>", html, flags=re.I | re.S):
        attrs = m.group(1)
        body = m.group(2)
        action = re.search(r'action=["\']([^"\']*)["\']', attrs, re.I)
        method = re.search(r'method=["\']([^"\']*)["\']', attrs, re.I)
        inputs = []
        for inp in re.finditer(r"<input\b([^>]*)/?>", body, flags=re.I):
            ia = inp.group(1)
            name = re.search(r'name=["\']([^"\']*)["\']', ia, re.I)
            typ = re.search(r'type=["\']([^"\']*)["\']', ia, re.I)
            val = re.search(r'value=["\']([^"\']*)["\']', ia, re.I)
            inputs.append(
                {
                    "name": name.group(1) if name else None,
                    "type": typ.group(1) if typ else "text",
                    "value": val.group(1) if val else "",
                }
            )
        selects = []
        for sel in re.finditer(r"<select\b([^>]*)>(.*?)</select>", body, flags=re.I | re.S):
            sa = sel.group(1)
            name = re.search(r'name=["\']([^"\']*)["\']', sa, re.I)
            options = re.findall(r'<option\b[^>]*value=["\']([^"\']*)["\']', sel.group(2), flags=re.I)
            selects.append({"name": name.group(1) if name else None, "options_sample": options[:20]})
        forms.append(
            {
                "action": action.group(1) if action else "",
                "method": (method.group(1) if method else "get").upper(),
                "inputs": inputs,
                "selects": selects,
            }
        )
    return forms


def extract_links(html: str) -> list[str]:
    return re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I)


def main():
    creds = get_printer_credentials(1)
    user = creds.username() or "admin"
    password = creds.password()
    print("user=", user, "password_configured=", bool(password))

    verify = build_printer_ssl_context(verify=settings.printer_verify_ssl)
    base = "https://192.168.2.7:30092"
    summary: dict = {"base": base, "steps": []}

    # --- Step A: no auth ---
    with httpx.Client(base_url=base, verify=verify, timeout=30.0, follow_redirects=False) as c:
        r = c.get("/")
        summary["steps"].append(
            {
                "step": "GET / no auth",
                "status": r.status_code,
                "content_type": r.headers.get("content-type"),
                "location": r.headers.get("location"),
                "www_authenticate": r.headers.get("www-authenticate"),
                "set_cookie_present": bool(r.headers.get("set-cookie")),
            }
        )
        save("01_root_noauth.html", r.text, password)

        r = c.get("/goform/joblog.cgi")
        summary["steps"].append(
            {
                "step": "GET /goform/joblog.cgi no auth",
                "status": r.status_code,
                "content_type": r.headers.get("content-type"),
                "location": r.headers.get("location"),
                "www_authenticate": r.headers.get("www-authenticate"),
                "body_len": len(r.content),
                "body_preview": redact(r.text[:500], password),
            }
        )
        save("02_joblog_noauth.bin", r.content, password)

    # --- Step B: HTTP Basic ---
    with httpx.Client(
        base_url=base,
        verify=verify,
        timeout=30.0,
        follow_redirects=True,
        auth=(user, password) if password else None,
    ) as c:
        r = c.get("/")
        summary["steps"].append(
            {
                "step": "GET / with basic auth follow",
                "status": r.status_code,
                "final_url": str(r.url),
                "content_type": r.headers.get("content-type"),
                "cookies": [f"{ck.name}=<REDACTED>" for ck in c.cookies.jar],
                "title": (re.search(r"<title[^>]*>(.*?)</title>", r.text, re.I | re.S) or [None, ""])[1].strip()
                if re.search(r"<title", r.text, re.I)
                else None,
            }
        )
        save("03_root_basic.html", r.text, password)
        links = extract_links(r.text)
        jobish = [l for l in links if any(k in l.lower() for k in ("job", "log", "goform", "cgi", "login"))]
        summary["root_interesting_links"] = jobish[:50]
        summary["root_forms"] = extract_forms(r.text)

        # Try common login/index pages
        for path in [
            "/index.html",
            "/home.html",
            "/main.html",
            "/login.html",
            "/cgi-bin/",
            "/goform/",
            "/web/guest/en/websys/webArch/mainFrame.cgi",
            "/web/guest/en/websys/webArch/topPage.cgi",
        ]:
            try:
                rr = c.get(path)
                summary["steps"].append(
                    {
                        "step": f"GET {path}",
                        "status": rr.status_code,
                        "final_url": str(rr.url),
                        "content_type": rr.headers.get("content-type"),
                        "len": len(rr.content),
                    }
                )
                if rr.status_code < 400 and len(rr.content) > 50:
                    safe = path.strip("/").replace("/", "_") or "rootpath"
                    save(f"04_probe_{safe}.html", rr.text[:200000], password)
            except Exception as exc:
                summary["steps"].append({"step": f"GET {path}", "error": type(exc).__name__})

        # Job log GET
        r = c.get("/goform/joblog.cgi")
        summary["steps"].append(
            {
                "step": "GET /goform/joblog.cgi basic",
                "status": r.status_code,
                "final_url": str(r.url),
                "content_type": r.headers.get("content-type"),
                "len": len(r.content),
                "cookies": [f"{ck.name}=<REDACTED>" for ck in c.cookies.jar],
            }
        )
        save("05_joblog_get.html", r.text, password)
        forms = extract_forms(r.text)
        summary["joblog_get_forms"] = forms
        summary["joblog_get_links"] = [
            l
            for l in extract_links(r.text)
            if any(k in l.lower() for k in ("job", "log", "export", "csv", "xls", "download", "goform"))
        ][:80]

        # Look for JS that posts to joblog
        js_hints = re.findall(
            r".{0,80}joblog\.cgi.{0,120}",
            r.text,
            flags=re.I,
        )
        summary["joblog_js_hints"] = [redact(h, password) for h in js_hints[:30]]

        # Parameter name hints in page
        param_hints = sorted(
            set(
                re.findall(
                    r"(?:name|id)=[\"']([A-Za-z0-9_]*(?:date|Date|from|to|start|end|export|csv|page|sort|job)[A-Za-z0-9_]*)[\"']",
                    r.text,
                    flags=re.I,
                )
            )
        )
        summary["param_name_hints"] = param_hints

        # If forms exist, try submitting each with default values (no invented dates yet —
        # use whatever defaults the form already has)
        for i, form in enumerate(forms):
            action = form["action"] or "/goform/joblog.cgi"
            if not action.startswith("http") and not action.startswith("/"):
                action = "/" + action
            data = {}
            for inp in form["inputs"]:
                if not inp["name"]:
                    continue
                if (inp["type"] or "").lower() == "password":
                    data[inp["name"]] = "<REDACTED_SKIP>"
                    continue
                data[inp["name"]] = inp["value"]
            # replace password fields with real password only in outbound request, not logs
            post_data = {}
            for inp in form["inputs"]:
                if not inp["name"]:
                    continue
                if (inp["type"] or "").lower() == "password":
                    post_data[inp["name"]] = password or ""
                else:
                    post_data[inp["name"]] = inp["value"]

            method = form["method"]
            print(f"submitting form {i} {method} {action} fields={list(post_data.keys())}")
            if method == "POST":
                rr = c.post(action, data=post_data)
            else:
                rr = c.get(action, params=post_data)
            summary["steps"].append(
                {
                    "step": f"submit form {i}",
                    "method": method,
                    "action": action,
                    "field_names": list(post_data.keys()),
                    "status": rr.status_code,
                    "content_type": rr.headers.get("content-type"),
                    "len": len(rr.content),
                    "final_url": str(rr.url),
                }
            )
            save(f"06_form_{i}_response.html", rr.text, password)
            save(
                f"06_form_{i}_request_fields.json",
                json.dumps({"action": action, "method": method, "fields": list(post_data.keys())}, indent=2),
            )

        # Try POST joblog with empty body / known Ricoh-ish patterns ONLY if page hints them
        # Do not invent — only retry GET with query keys found on page.
        if param_hints:
            params = {k: "" for k in param_hints[:15]}
            rr = c.get("/goform/joblog.cgi", params=params)
            summary["steps"].append(
                {
                    "step": "GET joblog with page-hint empty params",
                    "params": list(params.keys()),
                    "status": rr.status_code,
                    "len": len(rr.content),
                    "content_type": rr.headers.get("content-type"),
                }
            )
            save("07_joblog_hint_params.html", rr.text, password)

    save("00_summary.json", json.dumps(summary, indent=2), password)
    print("DONE — see", OUT)


if __name__ == "__main__":
    main()
