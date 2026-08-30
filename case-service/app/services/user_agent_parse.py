"""Parse User-Agent string into device/browser/os columns."""

from __future__ import annotations

from urllib.parse import urlparse

from user_agents import parse as parse_ua

# UA ของ HTTP client ฝั่ง server — ไม่ใช่เบราว์เซอร์ผู้ใช้
_SERVER_UA_MARKERS = (
    "python-requests",
    "python-httpx",
    "httpx/",
    "aiohttp/",
    "curl/",
    "wget/",
    "go-http-client",
    "java/",
    "apache-httpclient",
    "okhttp",
)

_SERVER_BROWSER_FAMILIES = {
    "python requests",
    "httpx",
    "aiohttp",
    "curl",
    "wget",
    "go-http-client",
}

_EMPTY_UA_FIELDS: dict[str, str | None] = {
    "device": None,
    "browser": None,
    "browser_version": None,
    "os": None,
    "os_version": None,
}


def is_server_user_agent(ua: str | None) -> bool:
    if not ua or not ua.strip():
        return True
    lower = ua.lower()
    return any(marker in lower for marker in _SERVER_UA_MARKERS)


def is_server_browser_family(browser: str | None) -> bool:
    if not browser or not browser.strip():
        return False
    return browser.strip().lower() in _SERVER_BROWSER_FAMILIES


def sanitize_client_user_agent(ua: str | None) -> str | None:
    if is_server_user_agent(ua):
        return None
    return ua.strip() if ua else None


def sanitize_client_request_url(url: str | None) -> str | None:
    """เก็บเฉพาะ URL หน้าจอ — ทิ้ง URL ของ API mso-forward / send-data."""
    if not url or not url.strip():
        return None
    cleaned = url.strip()
    path = urlparse(cleaned).path.rstrip("/").lower()
    if path.endswith("/mso-forward") or path.endswith("/send-data"):
        return None
    return cleaned


def parse_user_agent(ua: str | None) -> dict[str, str | None]:
    client_ua = sanitize_client_user_agent(ua)
    if not client_ua:
        return dict(_EMPTY_UA_FIELDS)

    parsed = parse_ua(client_ua)
    browser = parsed.browser.family if parsed.browser.family and parsed.browser.family != "Other" else None
    if is_server_browser_family(browser):
        return dict(_EMPTY_UA_FIELDS)

    browser_version = parsed.browser.version_string or None
    os_name = parsed.os.family if parsed.os.family and parsed.os.family != "Other" else None
    os_version = parsed.os.version_string or None

    if parsed.is_mobile:
        device = parsed.device.family if parsed.device.family != "Other" else "Mobile"
    elif parsed.is_tablet:
        device = parsed.device.family if parsed.device.family != "Other" else "Tablet"
    elif parsed.is_pc:
        device = "Desktop"
    elif parsed.device.family and parsed.device.family != "Other":
        device = parsed.device.family
    else:
        device = None

    return {
        "device": device,
        "browser": browser,
        "browser_version": browser_version,
        "os": os_name,
        "os_version": os_version,
    }


def client_display_fields(
    *,
    user_agent: str | None,
    request_url: str | None,
    device: str | None = None,
    browser: str | None = None,
    browser_version: str | None = None,
    os: str | None = None,
    os_version: str | None = None,
) -> dict[str, str | None]:
    """ค่าที่โชว์ใน log — ทิ้งของ HTTP client ฝั่ง server แม้แถวเก่าเก็บไว้แล้ว."""
    client_ua = sanitize_client_user_agent(user_agent)
    if client_ua is None:
        return {
            "user_agent": None,
            "url": sanitize_client_request_url(request_url),
            **dict(_EMPTY_UA_FIELDS),
        }
    parsed = parse_user_agent(client_ua)
    return {
        "user_agent": client_ua,
        "url": sanitize_client_request_url(request_url),
        "device": parsed["device"] or device,
        "browser": parsed["browser"] or browser,
        "browser_version": parsed["browser_version"] or browser_version,
        "os": parsed["os"] or os,
        "os_version": parsed["os_version"] or os_version,
    }
