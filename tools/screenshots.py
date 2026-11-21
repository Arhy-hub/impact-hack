"""Phone-sized screenshots of the Heatwise app for docs and slides.

Drives a local Chrome through the DevTools protocol so the page is laid out
at an exact iPhone size (390 x 844 points, 2x), which headless Chrome's
--window-size can't do on Windows (it won't go below about 500px).

    python tools/screenshots.py [base_url]

Needs: the app running (uvicorn heatwise.app:app), Chrome installed, and
`pip install websocket-client`. Writes PNGs to docs/screenshots/.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket

CHROME = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
]
OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
SHOTS = {
    "home-light": "?theme=light",
    "home-dark": "?theme=dark",
    "room-light": "?theme=light&room=living",
    "budget-light": "?theme=light&tab=budget",
    "schedule-light": "?theme=light&tab=schedule",
    "settings-light": "?theme=light&tab=settings",
    "settings-dark": "?theme=dark&tab=settings",
    "room-dark": "?theme=dark&room=living",
}
PORT = 9333


def main(base: str = "http://127.0.0.1:8010/") -> None:
    exe = next((c for c in CHROME if Path(c).exists()), CHROME[-1])
    profile = tempfile.mkdtemp(prefix="heatwise-shots-")
    proc = subprocess.Popen([exe, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={profile}",
                             "--disable-gpu", "--hide-scrollbars", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
                break
            except OSError:
                time.sleep(0.2)
        page = next(t for t in tabs if t["type"] == "page")
        ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=20)
        ids = iter(range(1, 10_000))

        def cdp(method, **params):
            i = next(ids)
            ws.send(json.dumps({"id": i, "method": method, "params": params}))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == i:
                    return msg.get("result", {})

        cdp("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
        OUT.mkdir(parents=True, exist_ok=True)
        for name, query in SHOTS.items():
            cdp("Page.navigate", url=base + query)
            time.sleep(2.5)  # page loads, fetches /api/home and renders
            data = cdp("Page.captureScreenshot", format="png")["data"]
            (OUT / f"{name}.png").write_bytes(base64.b64decode(data))
            print("wrote", OUT / f"{name}.png")
        ws.close()
    finally:
        proc.terminate()


if __name__ == "__main__":
    main(*sys.argv[1:])
