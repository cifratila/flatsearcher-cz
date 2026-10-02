#!/usr/bin/env python3
"""Parse saved Sreality search HTML pages into list JSON."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from . import config
from .fetch_sreality import list_item_to_seed, parse_next_data, estates_search_from_next
from .util import fold

NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--region", required=True)
    args = p.parse_args()
    root = config.RAW / "sreality-pages" / args.region
    pages = sorted(root.glob("p*.html"), key=lambda x: int(re.search(r"p(\d+)", x.name).group(1)))
    out = []
    seen = set()
    for path in pages:
        html = path.read_text(errors="replace")
        m = NEXT_RE.search(html)
        if not m:
            print("skip no next", path)
            continue
        data = json.loads(m.group(1))
        try:
            _, results = estates_search_from_next(data)
        except Exception as e:
            print("skip", path, e)
            continue
        page_no = int(re.search(r"p(\d+)", path.name).group(1))
        for est in results:
            sid = str(est.get("id") or "")
            if not sid or sid in seen:
                continue
            if not est.get("categorySubCb"):
                continue
            seen.add(sid)
            seed = list_item_to_seed(est, args.region, page_no)
            if seed.get("disp") and seed["disp"] not in config.LAYOUTS:
                continue
            loc = seed.get("locality") or {}
            if args.region == "decin" and fold(loc.get("city") or "") != "decin":
                continue
            if args.region == "usti" and "usti" not in fold(loc.get("city") or ""):
                continue
            if args.region == "karlin" and "karlin" not in fold(loc.get("cityPart") or ""):
                continue
            out.append(seed)
    dest = config.RAW / f"sreality-list-{args.region}.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {dest} n={len(out)} from {len(pages)} pages")


if __name__ == "__main__":
    main()
