"""Check registry prices for Claude entries against the published pricing page."""

from __future__ import annotations

import html
import re
from typing import Any

import httpx

from lexbench.records import utc_now
from lexbench.registry import ModelEntry

PRICING_URL = "https://platform.claude.com/docs/en/about-claude/pricing"


def page_text(raw_html: str) -> str:
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw_html, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", text)


def display_name(entry: ModelEntry) -> str:
    """claude-opus-5-5 becomes Claude Opus 5.5 unless pricing.page_name is set."""
    if entry.pricing.page_name:
        return entry.pricing.page_name
    m = re.match(r"claude-([a-z]+)-(\d+)(?:-(\d+))?", entry.model)
    if not m:
        return entry.model
    version = m.group(2) + (f".{m.group(3)}" if m.group(3) and len(m.group(3)) < 3 else "")
    return f"Claude {m.group(1).capitalize()} {version}"


def _two_prices(section: str, name: str) -> tuple[float, float] | None:
    pattern = re.escape(name) + r"(?![\d.])[^$]*\$([\d.]+) / MTok[^$]*\$([\d.]+) / MTok"
    m = re.search(pattern, section)
    return (float(m.group(1)), float(m.group(2))) if m else None


def parse_prices(text: str, name: str) -> dict[str, float] | None:
    """Base and batch input and output prices per million tokens for one model name."""
    base_at = text.find("Model pricing")
    batch_at = text.find("Batch processing")
    if base_at < 0 or batch_at < 0:
        return None
    base = _two_prices(text[base_at:batch_at] if batch_at > base_at else text[base_at:], name)
    batch = _two_prices(text[batch_at:], name)
    if not base or not batch:
        return None
    return {"input": base[0], "output": base[1], "batch_input": batch[0], "batch_output": batch[1]}


def check(entries: list[ModelEntry], fetch: bool = True) -> dict[str, Any]:
    record: dict[str, Any] = {"url": PRICING_URL, "fetched_at": None, "entries": {}}
    claude = [e for e in entries if e.provider == "anthropic"]
    if not claude or not fetch:
        record["status"] = "not checked"
        return record
    try:
        resp = httpx.get(PRICING_URL, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        record["status"] = f"unverified: {type(exc).__name__}"
        return record
    record["fetched_at"] = utc_now()
    text = page_text(resp.text)
    all_match = True
    for e in claude:
        name = display_name(e)
        page = parse_prices(text, name)
        p = e.pricing
        if page is None:
            record["entries"][e.name] = {"page_name": name, "status": "not found on page"}
            all_match = False
            continue
        factor = 1.0 - p.batch_discount
        match = (
            abs(page["input"] - p.input_per_mtok) < 1e-9
            and abs(page["output"] - p.output_per_mtok) < 1e-9
            and abs(page["batch_input"] - p.input_per_mtok * factor) < 1e-9
            and abs(page["batch_output"] - p.output_per_mtok * factor) < 1e-9
        )
        all_match &= match
        record["entries"][e.name] = {
            "page_name": name,
            "page": page,
            "registry": {
                "input": p.input_per_mtok,
                "output": p.output_per_mtok,
                "batch_discount": p.batch_discount,
            },
            "match": match,
        }
    record["status"] = "match" if all_match else "mismatch"
    return record
