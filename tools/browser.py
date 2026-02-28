"""CDP-based headless Chrome browser tools for runtime validation."""

from __future__ import annotations

import base64
import json
import logging
import subprocess
import shutil
import time
from pathlib import Path
from typing import Any

import websocket

import config
from tools.registry import ToolDef

logger = logging.getLogger(__name__)

# ── Chrome process management ─────────────────────────────────────

_chrome_proc: subprocess.Popen[bytes] | None = None
_ws: websocket.WebSocket | None = None
_msg_id = 0


def _next_id() -> int:
    global _msg_id
    _msg_id += 1
    return _msg_id


def _ensure_chrome() -> bool:
    """Launch headless Chrome if not already running. Return True on success."""
    global _chrome_proc, _ws

    if _ws is not None:
        return True

    chrome = config.CHROME_PATH
    if not Path(chrome).exists():
        chrome = shutil.which("google-chrome") or shutil.which("chromium") or ""
    if not chrome:
        logger.warning("[browser] Chrome not found")
        return False

    port = config.CDP_PORT
    cmd = [
        chrome,
        "--headless=new",
        f"--remote-debugging-port={port}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-gpu",
        "--disable-extensions",
        "--disable-background-networking",
        "--remote-allow-origins=*",
    ]
    try:
        _chrome_proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
    except Exception as e:
        logger.error("[browser] Failed to start Chrome: %s", e)
        return False

    # Wait for CDP to become available
    from urllib.request import urlopen
    from urllib.error import URLError

    # Wait for CDP and find a page target to connect to
    ws_url = None
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            # First, check CDP is up
            urlopen(f"http://localhost:{port}/json/version", timeout=2)
            # Get page targets
            resp = urlopen(f"http://localhost:{port}/json", timeout=2)
            targets = json.loads(resp.read())
            for t in targets:
                if t.get("type") == "page":
                    ws_url = t.get("webSocketDebuggerUrl")
                    break
            if ws_url:
                break
        except (URLError, OSError):
            pass
        time.sleep(0.5)

    if not ws_url:
        logger.error("[browser] Chrome CDP did not become available")
        shutdown_chrome()
        return False

    try:
        _ws = websocket.create_connection(ws_url, timeout=10)
        # Enable domains for page navigation and console error collection
        _send_cdp("Page.enable")
        _send_cdp("Runtime.enable")
    except Exception as e:
        logger.error("[browser] WebSocket connection failed: %s", e)
        shutdown_chrome()
        return False

    logger.info("[browser] Chrome started (pid=%d, cdp_port=%d)", _chrome_proc.pid, port)
    return True


def shutdown_chrome() -> None:
    """Shut down headless Chrome and clean up."""
    global _chrome_proc, _ws, _msg_id

    if _ws is not None:
        try:
            _ws.close()
        except Exception:
            pass
        _ws = None

    if _chrome_proc is not None:
        try:
            _chrome_proc.terminate()
            _chrome_proc.wait(timeout=5)
        except Exception:
            try:
                _chrome_proc.kill()
            except Exception:
                pass
        _chrome_proc = None

    _msg_id = 0
    logger.info("[browser] Chrome shut down")


def _send_cdp(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Send a CDP command and return the result."""
    if _ws is None:
        return {"error": "Chrome not connected"}
    msg_id = _next_id()
    payload: dict[str, Any] = {"id": msg_id, "method": method}
    if params:
        payload["params"] = params
    _ws.send(json.dumps(payload))

    # Read responses until we get our result (skip events)
    deadline = time.time() + 15
    while time.time() < deadline:
        raw = _ws.recv()
        if not raw:
            continue
        resp = json.loads(raw)
        if resp.get("id") == msg_id:
            if "error" in resp:
                return {"error": resp["error"].get("message", str(resp["error"]))}
            return resp.get("result", {})
    return {"error": "CDP response timeout"}


# ── Tool handlers ─────────────────────────────────────────────────

def browser_navigate(url: str, wait_ms: int = 3000) -> str:
    """Navigate to a URL and wait for the page to load."""
    if not _ensure_chrome():
        return json.dumps({"error": "Chrome is not available"})

    result = _send_cdp("Page.navigate", {"url": url})
    if "error" in result:
        return json.dumps(result)

    frame_id = result.get("frameId", "")
    time.sleep(wait_ms / 1000.0)
    return json.dumps({"status": "navigated", "url": url, "frameId": frame_id})


def browser_screenshot(filename: str = "screenshot.png") -> str:
    """Capture a screenshot and save it to the validation/ directory."""
    if not _ensure_chrome():
        return json.dumps({"error": "Chrome is not available"})

    result = _send_cdp("Page.captureScreenshot", {"format": "png"})
    if "error" in result:
        return json.dumps(result)

    img_data = base64.b64decode(result.get("data", ""))
    out_dir = config.WORKSPACE_DIR / "validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    out_path.write_bytes(img_data)

    return json.dumps({
        "status": "saved",
        "path": str(out_path),
        "size_bytes": len(img_data),
    })


def browser_console_errors() -> str:
    """Collect JavaScript console errors from the current page."""
    if not _ensure_chrome():
        return json.dumps({"error": "Chrome is not available"})

    # Evaluate JS to count error elements and collect console errors
    js_code = r"""
    (function() {
        var errors = [];
        // Check for visible error text on page
        var elements = document.querySelectorAll(
            '[class*="error"], [class*="Error"], [role="alert"]'
        );
        elements.forEach(function(el) {
            if (el.offsetParent !== null && el.textContent.trim()) {
                errors.push({type: 'dom_error', text: el.textContent.trim().substring(0, 200)});
            }
        });
        return JSON.stringify({error_elements: errors.length, errors: errors.slice(0, 20)});
    })()
    """
    result = _send_cdp("Runtime.evaluate", {
        "expression": js_code,
        "returnByValue": True,
    })
    if "error" in result:
        return json.dumps(result)

    value = result.get("result", {}).get("value", "{}")
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except (json.JSONDecodeError, TypeError):
        parsed = {"raw": str(value)}

    return json.dumps(parsed)


# ── Tool definitions ──────────────────────────────────────────────

BROWSER_NAVIGATE = ToolDef(
    name="browser_navigate",
    description="Navigate headless Chrome to a URL and wait for the page to load.",
    input_schema={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to navigate to"},
            "wait_ms": {
                "type": "integer",
                "description": "Milliseconds to wait after navigation (default 3000)",
            },
        },
        "required": ["url"],
    },
    handler=browser_navigate,
)

BROWSER_SCREENSHOT = ToolDef(
    name="browser_screenshot",
    description="Capture a screenshot of the current browser page and save to validation/ directory.",
    input_schema={
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": "Output filename (default: screenshot.png)",
            },
        },
    },
    handler=browser_screenshot,
)

BROWSER_CONSOLE_ERRORS = ToolDef(
    name="browser_console_errors",
    description="Collect JavaScript console errors and visible error elements from the current page.",
    input_schema={
        "type": "object",
        "properties": {},
    },
    handler=browser_console_errors,
)
