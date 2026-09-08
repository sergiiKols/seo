#!/usr/bin/env python3
"""
Shared headless renderer for claude-seo.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from typing import Any, Optional

from bs4 import BeautifulSoup

try:
    from playwright.sync_api import (
        TimeoutError as PlaywrightTimeout,
    )
    from playwright.sync_api import (
        sync_playwright,
    )
except ImportError:
    sync_playwright = None
    PlaywrightTimeout = Exception

try:
    import trafilatura
except ImportError:
    trafilatura = None

try:
    from htmldate import find_date
except ImportError:
    find_date = None

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from url_safety import (
    URLSafetyError,
    make_safe_playwright_route_handler,
    safe_requests_get,
    validate_url_strict,
)

VIEWPORTS: dict[str, dict[str, int]] = {
    "desktop": {"width": 1920, "height": 1080, "device_scale": 1},
    "laptop": {"width": 1366, "height": 768, "device_scale": 1},
    "tablet": {"width": 768, "height": 1024, "device_scale": 1},
    "mobile": {"width": 375, "height": 812, "device_scale": 2},
}

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.7871.115 Safari/537.36 ClaudeSEO/2.0"
)

_SPA_SHELL_PATTERNS = (
    '<div id="root"></div>',
    '<div id="__next">',
    '<div id="app"></div>',
    '<div id="__nuxt">',
    'data-svelte-h=',
    '<astro-island ',
    'you need to enable javascript',
    'please enable javascript',
)

_BUILDER_FINGERPRINT_GROUPS = (
    ("wix-warmup-data", "static.parastorage.com", 'content="wix.com'),
    ("data-wf-page", "data-wf-site"),
    ('content="squarespace', "static1.squarespace.com"),
)

_TAG_STRIP = re.compile(r"<[^>]+>")
_WHITESPACE = re.compile(r"\s+")
_NON_VISIBLE_STRIP = re.compile(
    r"<(script|style|template|noscript)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_BUILDER_SPARSE_TEXT_MAX = 400

JSON_LD_MAX_BLOCKS = 50
JSON_LD_MAX_BLOCK_BYTES = 256 * 1024
JSON_LD_MAX_TOTAL_BYTES = 1024 * 1024
JSON_LD_MAX_NODES = 10_000
JSON_LD_MAX_DEPTH = 40
ACCESSIBILITY_MAX_NODES = 10_000
ACCESSIBILITY_MAX_DEPTH = 50


def _visible_body_text(lower_html: str) -> str:
    body_start = lower_html.find("<body")
    body_end = lower_html.rfind("</body>")
    if body_start == -1 or body_end <= body_start:
        return ""
    body = _NON_VISIBLE_STRIP.sub(" ", lower_html[body_start:body_end])
    return _WHITESPACE.sub(" ", _TAG_STRIP.sub(" ", body)).strip()


def _schema_types(data: object) -> tuple[list[str], bool]:
    types: set[str] = set()
    stack: list[tuple[object, int]] = [(data, 0)]
    visited = 0
    truncated = False
    while stack:
        value, depth = stack.pop()
        visited += 1
        if visited > JSON_LD_MAX_NODES or depth > JSON_LD_MAX_DEPTH:
            truncated = True
            break
        if isinstance(value, dict):
            schema_type = value.get("@type")
            if isinstance(schema_type, str):
                types.add(schema_type)
            elif isinstance(schema_type, list):
                types.update(item for item in schema_type if isinstance(item, str))
            stack.extend((item, depth + 1) for item in value.values())
        elif isinstance(value, list):
            stack.extend((item, depth + 1) for item in value)
    return sorted(types)[:100], truncated or len(types) > 100


def _extract_json_ld(html: Optional[str], *, include_full: bool = False) -> dict:
    result = {
        "block_count": 0,
        "processed_count": 0,
        "total_bytes": 0,
        "truncated": False,
        "blocks": [],
    }
    if not html:
        return result

    soup = BeautifulSoup(html, "html.parser")
    scripts = [
        script for script in soup.find_all("script")
        if str(script.get("type", "")).strip().lower() == "application/ld+json"
    ]
    result["block_count"] = len(scripts)

    for index, script in enumerate(scripts):
        if index >= JSON_LD_MAX_BLOCKS:
            result["truncated"] = True
            break
        raw = script.string if script.string is not None else script.get_text()
        raw = str(raw or "").strip()
        size_bytes = len(raw.encode("utf-8"))
        if result["total_bytes"] + size_bytes > JSON_LD_MAX_TOTAL_BYTES:
            result["truncated"] = True
            break
        result["total_bytes"] += size_bytes
        result["processed_count"] += 1

        entry = {"index": index + 1, "size_bytes": size_bytes}
        if size_bytes > JSON_LD_MAX_BLOCK_BYTES:
            entry.update({
                "valid": None,
                "error": "block exceeds the JSON-LD per-block byte limit",
            })
            result["truncated"] = True
            result["blocks"].append(entry)
            continue

        try:
            parsed = json.loads(raw)
            types, types_truncated = _schema_types(parsed)
            entry.update({
                "valid": True,
                "types": types,
                "types_truncated": types_truncated,
            })
            if include_full:
                entry["data"] = parsed
        except (json.JSONDecodeError, RecursionError) as exc:
            entry.update({
                "valid": False,
                "error": f"{type(exc).__name__}: {exc}",
            })
            if include_full:
                entry["raw"] = raw
        result["blocks"].append(entry)
    return result


def _is_spa(raw_html: Optional[str]) -> bool:
    if not raw_html:
        return True
    lc = raw_html.lower()
    visible_text = _visible_body_text(lc)
    if (
        len(visible_text) < _BUILDER_SPARSE_TEXT_MAX
        and any(pattern in lc for pattern in _SPA_SHELL_PATTERNS)
    ):
        return True
    if len(visible_text) < _BUILDER_SPARSE_TEXT_MAX:
        for markers in _BUILDER_FINGERPRINT_GROUPS:
            if sum(marker in lc for marker in markers) >= 2:
                return True
    body_start = lc.find("<body")
    body_end = lc.rfind("</body>")
    if body_start != -1 and body_end > body_start:
        if len(visible_text) < 100:
            return True
    return False


def _wait_for_dom_stability(page, timeout_ms: int) -> bool:
    budget_ms = max(250, min(timeout_ms, 5000))
    previous = None
    stable_samples = 0
    elapsed_ms = 0
    while elapsed_ms < budget_ms:
        try:
            signature = tuple(page.evaluate(
                "() => ["
                "(document.body && document.body.innerText || '').trim().length,"
                "document.querySelectorAll('*').length"
                "]"
            ))
        except Exception:
            return False
        if signature == previous and signature[0] >= 100:
            stable_samples += 1
            if stable_samples >= 2:
                return True
        else:
            stable_samples = 0
        previous = signature
        page.wait_for_timeout(250)
        elapsed_ms += 250
    return False


def _ax_value(node: dict[str, Any], key: str) -> str:
    value = node.get(key)
    if isinstance(value, dict):
        raw = value.get("value")
        return str(raw) if raw is not None else ""
    return str(value) if value is not None else ""


def _accessibility_tree_from_cdp(nodes: object) -> tuple[Optional[dict], bool]:
    if not isinstance(nodes, list) or not nodes:
        return None, False

    usable = [node for node in nodes if isinstance(node, dict)]
    truncated = len(usable) > ACCESSIBILITY_MAX_NODES
    usable = usable[:ACCESSIBILITY_MAX_NODES]
    by_id = {
        str(node["nodeId"]): node
        for node in usable
        if node.get("nodeId") is not None
    }
    if not by_id:
        return None, truncated

    known_children = {
        str(child_id)
        for node in by_id.values()
        for child_id in (node.get("childIds") or [])
        if str(child_id) in by_id
    }
    root_id = next((node_id for node_id in by_id if node_id not in known_children), None)
    if root_id is None:
        return None, True

    def build(node_id: str, depth: int, ancestors: frozenset[str]) -> dict:
        nonlocal truncated
        node = by_id[node_id]
        result = {
            "role": _ax_value(node, "role"),
            "name": _ax_value(node, "name"),
            "ignored": bool(node.get("ignored", False)),
        }
        child_ids = [
            str(child_id)
            for child_id in (node.get("childIds") or [])
            if str(child_id) in by_id
        ]
        if depth >= ACCESSIBILITY_MAX_DEPTH:
            if child_ids:
                truncated = True
            return result
        children = []
        for child_id in child_ids:
            if child_id in ancestors:
                truncated = True
                continue
            children.append(build(child_id, depth + 1, ancestors | {child_id}))
        if children:
            result["children"] = children
        return result

    return build(root_id, 0, frozenset({root_id})), truncated


def _capture_accessibility_tree(context: Any, page: Any) -> tuple[Optional[dict], bool]:
    session = context.new_cdp_session(page)
    try:
        session.send("Accessibility.enable")
        payload = session.send(
            "Accessibility.getFullAXTree", {"depth": ACCESSIBILITY_MAX_DEPTH}
        )
        return _accessibility_tree_from_cdp(payload.get("nodes"))
    finally:
        try:
            session.send("Accessibility.disable")
        except Exception:
            pass
        detach = getattr(session, "detach", None)
        if detach:
            try:
                detach()
            except Exception:
                pass


def render_page(
    url: str,
    *,
    mode: str = "auto",
    viewport: str = "desktop",
    timeout_ms: int = 15000,
    block_resources: Optional[list[str]] = None,
    extract_content: bool = True,
    extract_accessibility: bool = False,
    user_agent: Optional[str] = None,
) -> dict:
    result: dict = {
        "url": url,
        "status_code": None,
        "content": None,
        "raw_content": None,
        "is_spa": None,
        "extracted_text": None,
        "publication_date": None,
        "accessibility_tree": None,
        "accessibility_error": None,
        "accessibility_partial": False,
        "headers": {},
        "redirect_chain": [],
        "console_errors": [],
        "render_diagnostics": [],
        "render_engine": None,
        "render_ms": None,
        "mode_used": None,
        "error": None,
    }

    if mode not in ("auto", "always", "never"):
        result["error"] = f"Invalid mode: {mode!r}"
        return result
    if viewport not in VIEWPORTS:
        result["error"] = f"Invalid viewport: {viewport!r}"
        return result

    try:
        norm_url, _pinned_ip = validate_url_strict(url)
        result["url"] = norm_url
    except URLSafetyError as exc:
        result["error"] = f"url_safety: {exc}"
        return result

    try:
        resp = safe_requests_get(norm_url, timeout=30, allow_redirects=True)
        result["raw_content"] = resp.text
        if resp.history:
            result["redirect_chain"] = [
                {"url": r.url, "status_code": r.status_code} for r in resp.history
            ]
        raw_status = resp.status_code
        raw_headers = dict(resp.headers)
        final_raw_url = resp.url
    except Exception as exc:
        result["error"] = f"raw fetch failed: {exc}"
        return result

    result["is_spa"] = _is_spa(result["raw_content"])
    should_render = mode == "always" or (mode == "auto" and result["is_spa"])

    if not should_render:
        result["mode_used"] = "raw"
        result["url"] = final_raw_url
        result["status_code"] = raw_status
        result["headers"] = raw_headers
        result["content"] = result["raw_content"]
    else:
        result["mode_used"] = "rendered"
        if sync_playwright is None:
            result["error"] = "playwright is required for rendered mode."
            return result

        vp = VIEWPORTS[viewport]
        blocked = set(block_resources or [])
        route_handler = make_safe_playwright_route_handler(blocked)
        start = time.monotonic()

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={"width": vp["width"], "height": vp["height"]},
                    device_scale_factor=vp["device_scale"],
                    user_agent=user_agent or USER_AGENT,
                )
                page = context.new_page()

                def _on_console(msg):
                    if msg.type == "error":
                        result["console_errors"].append(msg.text)

                page.on("console", _on_console)
                page.route("**/*", route_handler)

                try:
                    response = page.goto(
                        norm_url, wait_until="domcontentloaded", timeout=timeout_ms
                    )
                except PlaywrightTimeout:
                    response = None
                    result["render_diagnostics"].append(f"DOMContentLoaded timed out after {timeout_ms}ms")
                
                _wait_for_dom_stability(page, timeout_ms)

                result["url"] = page.url
                result["content"] = page.content()
                result["status_code"] = response.status if response else raw_status
                result["headers"] = dict(response.all_headers()) if response else raw_headers
                result["render_engine"] = "playwright-chromium"

                if extract_accessibility:
                    try:
                        (result["accessibility_tree"], result["accessibility_partial"]) = _capture_accessibility_tree(context, page)
                    except Exception as exc:
                        result["accessibility_error"] = f"accessibility capture failed: {exc}"
                browser.close()
        except Exception as exc:
            result["error"] = f"playwright error: {exc}"
            return result
        finally:
            result["render_ms"] = (time.monotonic() - start) * 1000.0

    if extract_content and result["content"]:
        if trafilatura is not None:
            try:
                result["extracted_text"] = trafilatura.extract(result["content"])
            except Exception: pass
        if find_date is not None:
            try:
                result["publication_date"] = find_date(result["content"])
            except Exception: pass

    return result

def _cli():
    parser = argparse.ArgumentParser(description="claude-seo shared headless renderer")
    parser.add_argument("url", help="URL to render")
    parser.add_argument("--mode", choices=("auto", "always", "never"), default="auto")
    parser.add_argument("--viewport", choices=list(VIEWPORTS), default="desktop")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    res = render_page(args.url, mode=args.mode, viewport=args.viewport)
    if args.json:
        print(json.dumps(res, indent=2, default=str))
    else:
        if res["error"]:
            print(f"Error: {res['error']}", file=sys.stderr)
            sys.exit(1)
        print(res["content"])

if __name__ == "__main__":
    _cli()
