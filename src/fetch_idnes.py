#!/usr/bin/env python3
"""Optional Reality.iDNES secondary scrape (best-effort HTML list cards)."""
from __future__ import annotations__

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request

from . import config
from .util import fold

# Reality.iDNES search URLs (prodej byty)
REGION_URLS = {
    "karlin": "https://reality.idnes.cz/s/prodej/byty/praha-8/?s-qc%5BsubtypeFlat%5D%5B0%5D=1k&s-qc%5BsubtypeFlat%5D%5B1%5D=11&s-qc%5BsubtypeFlat%5D%5B2%5D=2k&s-qc%5BsubtypeFlat%5D%5B3%5D=21&s-qc%5BsubtypeFlat%5D%5B4%5D=3k&s-qc%5BsubtypeFlat%5D%5B5%5D=31&s-qc%5BsubtypeFlat%5D%5B6%5D=4k&s-qc%5BsubtypeFlat%5D%5B7%5D=41",
    "prague": "https://reality.idnes.cz/s/prodej/byty/praha/?s-qc%5BsubtypeFlat%5D%5B0%5D=1k&s-qc%5BsubtypeFlat%5D%5B1%5D=11&s-qc%5BsubtypeFlat%5D%5B2%5D=2k&s-qc%5BsubtypeFlat%5D%5B3%5D=21&s-qc%5BsubtypeFlat%5D%5B4%5D=3k&s-qc%5BsubtypeFlat%5D%5B5%5D=31&s-qc%5BsubtypeFlat%5D%5B6%5D=4k&s-qc%5BsubtypeFlat%5D%5B7%5D=41",
    "decin": "https://reality.idnes.cz/s/prodej/byty/decin/?s-qc%5BsubtypeFlat%5D%5B0%5D=1k&s-qc%5BsubtypeFlat%5D%5B1%5D=11&s-qc%5BsubtypeFlat%5D%5B2%5D=2k&s-qc%5BsubtypeFlat%5D%5B3%5D=21&s-qc%5BsubtypeFlat%5D%5B4%5D=3k&s-qc%5BsubtypeFlat%5D%5B5%5D=31&s-qc%5BsubtypeFlat%5D%5B6%5D=4k&s-qc%5BsubtypeFlat%5D%5B7%5D=41",
    "usti": "https://reality.idnes.cz/s/prodej/byty/usti-nad-labem/?s-qc%5BsubtypeFlat%5D%5B0%5D=1k&s-qc%5BsubtypeFlat%5D%5B1%5D=11&s-qc%5BsubtypeFlat%5D%5B2%5D=2k&s-qc%5BsubtypeFlat%5D%5B3%5D=21&s-qc%5BsubtypeFlat%5D%5B4%5D=3k&s-qc%5BsubtypeFlat%5D%5B5%5D=31&s-qc%5BsubtypeFlat%5D%5B6%5D=4k&s-qc%5BsubtypeFlat%5D%5B7%5D=41",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": config.USER_AGENT, "Accept-Language": "cs"},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return r.read().decode("utf-8", errors="replace")


CARD_RE = re.compile(
    r'href="(https://reality\.idnes\.cz/detail/[^"]+)"[^>]*>.*?'
    r'(?:<h[23][^>]*>|class="c-products__title"[^>]*>)(.*?)</h[23]>|'
    r'data-category="byt"',
    re.I | re.S,
)


def parse_cards(html: str, region_key: str) -> list[dict]:
    """Best-effort: extract detail links + rough price/m2 from listing page text blocks."""
    items = []
    seen = set()
    # links
    for m in re.finditer(r'href="(https://reality\.idnes\.cz/detail/[^"?]+)', html):
        url = m.group(1)
        if url in seen:
            continue
        seen.add(url)
        items.append(
            {
                "id": url.rstrip("/").split("/")[-1],
                "url": url,
                "street": "",
                "disposition": None,
                "m2": None,
                "price_czk": None,
                "kc_m2": None,
                "source": "idnes",
                "region_bucket": region_key,
                "notes": "idnes list stub — detail enrichment not always available",
            }
        )
    return items


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--regions", default="karlin,decin,usti")
    p.add_argument("--max-pages", type=int, default=3)
    args = p.parse_args(argv)
    config.RAW.mkdir(parents=True, exist_ok=True)
    all_items = []
    for rk in [r.strip() for r in args.regions.split(",") if r.strip()]:
        base = REGION_URLS.get(rk)
        if not base:
            continue
        region_items = []
        for page in range(1, args.max_pages + 1):
            url = base if page == 1 else (base + ("&" if "?" in base else "?") + f"page={page}")
            try:
                html = fetch(url)
            except Exception as e:
                print(f"[idnes {rk}] page {page} err {e}", file=sys.stderr)
                break
            cards = parse_cards(html, rk)
            if not cards:
                break
            region_items.extend(cards)
            time.sleep(0.4)
        # dedupe
        seen = set()
        uniq = []
        for it in region_items:
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            uniq.append(it)
        path = config.RAW / f"idnes-{rk}.json"
        path.write_text(json.dumps(uniq, ensure_ascii=False, indent=2) + "\n")
        print(f"wrote {path} n={len(uniq)}", file=sys.stderr)
        all_items.extend(uniq)
    (config.RAW / "idnes-all.json").write_text(
        json.dumps(all_items, ensure_ascii=False, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
