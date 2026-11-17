"""
Baileys WhatsApp sidecar client for ARA.

Replaces the Playwright-based WhatsAppManager with HTTP calls to a Node.js Baileys sidecar.
Usage in server.py:

    from whatsapp_sidecar_client import wa
    wa.send_message_sync(phone, text)
    wa.status_sync()
    wa.get_qr()
"""
import logging
import json
import time
import urllib.request
import urllib.error

SIDECAR_BASE = "http://localhost:8767"
logger = logging.getLogger(__name__)


class BaileysWA:
    """HTTP client for the Baileys Node.js sidecar on port 8767."""

    def __init__(self):
        self._ready = False

    def _request(self, method: str, path: str, body: dict = None, timeout: int = 10):
        url = f"{SIDECAR_BASE}{path}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method)
        if body:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode()
                if resp.status == 200 and text:
                    return json.loads(text)
                return text
        except urllib.error.HTTPError as e:
            return {"error": f"HTTP {e.code}: {e.read().decode()[:200]}"}
        except Exception as e:
            return {"error": str(e)}

    def status_sync(self) -> dict:
        """Get connection status from sidecar."""
        return self._request("GET", "/status")

    def get_qr(self) -> str:
        """Get base64 QR code PNG, or 'NOT_READY' / 'WAITING'."""
        try:
            resp = urllib.request.urlopen(f"{SIDECAR_BASE}/qr", timeout=10)
            return resp.read().decode()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "NOT_READY"
            return f"ERROR: {e}"
        except Exception as e:
            return f"ERROR: {e}"

    def send_message_sync(self, phone: str, text: str) -> dict:
        """Send a WhatsApp message via sidecar. Returns dict with 'ok' and 'msgId' or 'error'."""
        return self._request("POST", "/send", {"phone": phone, "text": text}, timeout=30)

    @property
    def is_connected(self) -> bool:
        return self.status_sync().get("connected", False)

    @property
    def is_authenticated(self) -> bool:
        return self.status_sync().get("authenticated", False)

    @property
    def page(self):
        """Compatibility shim — Baileys has no page object. Returns None."""
        return None

    @property
    def context(self):
        """Compatibility shim — Baileys has no browser context."""
        return None


# Singleton instance (imported by server.py)
wa = BaileysWA()
