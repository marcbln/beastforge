"""Opt-in browser smoke check (FR-021, SC-010).

Runs only with ``BEASTFORGE_VIEWER_SMOKE=1`` and Playwright installed. The
default suite imports this module, sees the gate, and skips.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

from tests.conftest import ROOT

pytestmark = pytest.mark.viewer

if os.environ.get("BEASTFORGE_VIEWER_SMOKE") != "1":
    pytest.skip(
        "set BEASTFORGE_VIEWER_SMOKE=1 to run the browser smoke check", allow_module_level=True
    )

sync_api = pytest.importorskip("playwright.sync_api")
sync_playwright = sync_api.sync_playwright


def _start(env: dict[str, str], cache: Path) -> tuple[subprocess.Popen[str], str]:
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "beastforge",
            "view",
            "--no-browser",
            "--port",
            "0",
            "--json",
            "--cache-dir",
            str(cache),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    url = json.loads(process.stdout.readline())["url"]
    return process, url


def test_browser_smoke(env, tmp_path, settings) -> None:
    process, url = _start(env, tmp_path / "cache")
    try:
        with urllib.request.urlopen(f"{url}catalog.json", timeout=10) as response:
            catalog = json.loads(response.read())
        entry = catalog["creatures"][0]
        with urllib.request.urlopen(f"{url}{entry['manifest']}", timeout=30) as response:
            manifest = json.loads(response.read())

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page()
            page.goto(url)
            page.wait_for_selector(".card")
            assert page.locator(".card").count() == len(catalog["creatures"])

            page.locator(".card").first.click()
            page.wait_for_selector("#stage-view:not([hidden])")
            page.wait_for_selector("#stage-canvas")
            page.wait_for_selector(".clip-button")
            buttons = page.locator(".clip-button")
            assert buttons.count() == len(manifest["clips"])

            clips = manifest["clips"]
            events = manifest["events"]
            target = clips[0]["name"] if len(clips) == 1 else clips[1]["name"]
            buttons.nth(1 if len(clips) > 1 else 0).click()
            expected = len([event for event in events if event["clip"] == target])
            page.wait_for_function(
                "expected => document.querySelectorAll('.event-mark').length === expected",
                expected,
            )
            assert page.locator(".event-mark").count() == expected

            page.reload()
            page.wait_for_selector("#stage-view:not([hidden])")
            assert page.locator("#stage-title").inner_text() == entry["name"]
            assert f"/{entry['name']}/" in page.url
            browser.close()
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
        process.wait(timeout=15)
