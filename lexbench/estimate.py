"""`lexbench estimate`: token counts and USD per family and model entry. Submits nothing.

Each family estimate records the entry's settings fingerprint for that family and its
pricing; `lexbench run` refuses an estimate whose fingerprint or pricing differs from the
registry, so that the cap is never checked against an estimate made under other settings.
"""

from __future__ import annotations

from typing import Any

from lexbench import pricing
from lexbench.build import family_sha, load_cases
from lexbench.families import to_request
from lexbench.paths import FAMILIES, Layout
from lexbench.providers import make_provider
from lexbench.records import read_json, utc_now, write_json
from lexbench.registry import Registry


def estimate(
    layout: Layout, registry: Registry, models: list[str] | None = None, fetch_prices: bool = True
) -> dict[str, Any]:
    names = models or list(registry.entries)
    entries = [registry.get(n) for n in names]
    manifest = read_json(layout.manifest, default=None) or {"families": {}}
    families = [f for f in FAMILIES if f in manifest["families"]]
    out: dict[str, Any] = {
        "generated_at": utc_now(),
        "method": (
            "input tokens: characters / 3 plus 16 per request; output tokens: the output "
            "bound of each request"
        ),
        "spend_cap_usd": registry.spend_cap_usd,
        "data": {f: family_sha(layout, f) for f in families},
        "pricing_check": pricing.check(entries, fetch=fetch_prices),
        "entries": {},
        "totals_usd": {},
    }
    for entry in entries:
        per: dict[str, Any] = {}
        for family in families:
            provider = make_provider(entry.for_family(family), layout.cache)
            requests = [to_request(r) for r in load_cases(layout, family)]
            est = provider.estimate(requests)
            per[family] = {
                "requests": est.requests,
                "input_tokens": est.input_tokens,
                "output_tokens": est.output_tokens,
                "usd": est.usd,
                "batch": entry.batch,
                "paid": not entry.pricing.is_free,
                "config_sha256": entry.fingerprint(family),
                "pricing": entry.pricing.as_dict(),
            }
        out["entries"][entry.name] = per
        out["totals_usd"][entry.name] = round(sum(v["usd"] for v in per.values()), 4)
    out["total_usd"] = round(sum(out["totals_usd"].values()), 4)
    out["within_cap"] = out["total_usd"] <= registry.spend_cap_usd
    write_json(layout.estimate, out)
    return out
