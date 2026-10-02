#!/usr/bin/env python3
"""Fetch Bezrealitky PRODEJ BYT via public GraphQL (no cookies required).

OSM region ids (nominatim.bezrealitky.cz):
  Karlín R435856, Praha R435514, Děčín R439579, Ústí nad Labem R440166
List query includes etage, ownership, description when requested.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any

from . import config
from .util import fold

GQL_URL = "https://api.bezrealitky.cz/graphql/"
LISTING_BASE = "https://www.bezrealitky.cz/nemovitosti-byty-domy/"
PAGE_SIZE = 50


def gql(query: str) -> dict[str, Any]:
    body = json.dumps({"query": query}).encode("utf-8")
    req = urllib.request.Request(
        GQL_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://www.bezrealitky.cz",
            "Referer": "https://www.bezrealitky.cz/",
            "User-Agent": config.USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GraphQL HTTP {e.code}: {err_body[:500]}") from e
    data = json.loads(raw)
    if data.get("errors"):
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]


def list_adverts(region_osm_id: str, *, limit: int, offset: int) -> dict:
    disp = ",".join(config.BEZ_DISPOSITIONS)
    query = (
        "{ listAdverts("
        "offerType:[PRODEJ], estateType:[BYT], "
        f"disposition:[{disp}], "
        f'regionOsmIds:["{region_osm_id}"], '
        f"limit:{int(limit)}, offset:{int(offset)}, "
        "order:TIMEORDER_DESC, currency:CZK"
        ") { totalCount list { id uri disposition surface price currency "
        "etage floor ownership "
        "gps { lat lng } address(locale:CS) imageAltText(locale:CS) "
        "description } } }"
    )
    return gql(query)["listAdverts"]


def street_from_address(address: str) -> str:
    if not address:
        return ""
    return address.split(",")[0].strip()


def normalize_ownership(raw: Any) -> tuple[str | None, str | None]:
    if raw is None:
        return None, None
    if isinstance(raw, dict):
        name = raw.get("name") or raw.get("label") or str(raw)
    else:
        name = str(raw)
    f = fold(name)
    if "osobni" in f or f in ("ov", "personal"):
        return "osobní", name
    if "druzstev" in f:
        return "družstevní", name
    return fold(name) or None, name


def advert_to_item(a: dict, region_key: str) -> dict:
    price = a.get("price")
    m2 = a.get("surface")
    kc = None
    if isinstance(price, (int, float)) and isinstance(m2, (int, float)) and m2:
        kc = int(round(price / m2))
    disp = a.get("disposition") or ""
    address = a.get("address") or ""
    uri = a.get("uri") or ""
    etage = a.get("etage")
    if etage is None:
        etage = a.get("floor")
    try:
        fn = int(etage) if etage is not None else None
    except (TypeError, ValueError):
        fn = None
    own_norm, own_raw = normalize_ownership(a.get("ownership"))
    return {
        "id": str(a.get("id") or ""),
        "url": f"{LISTING_BASE}{uri}" if uri else f"{LISTING_BASE}{a.get('id')}",
        "street": street_from_address(address),
        "disposition": config.DISP_LABEL.get(disp, disp),
        "m2": m2,
        "price_czk": price,
        "kc_m2": kc,
        "floor": str(fn) if fn is not None else None,
        "floor_number": fn,
        "floors_total": None,
        "ownership": own_norm,
        "ownership_raw": own_raw,
        "address": address,
        "description": a.get("description") or "",
        "name": a.get("imageAltText") or "",
        "note_field": "",
        "gps": a.get("gps"),
        "source": "bezrealitky",
        "region_bucket": region_key,
        "city_part": "",
        "district": "",
        "quarter": "",
        "locality": {},
        "flat_class": None,
        "elevator": None,
        "condition": None,
        "building_type": None,
        "notes": "",
    }


def in_region(item: dict, region_key: str) -> bool:
    """Defense-in-depth geo filter."""
    blob = fold(f"{item.get('address','')} {item.get('url','')} {item.get('street','')}")
    gps = item.get("gps") or {}
    if region_key == "karlin":
        if "karlin" in blob:
            return "hodonin" not in blob and "jihomorav" not in blob
        try:
            lat, lng = float(gps["lat"]), float(gps["lng"])
            return 50.0883434 <= lat <= 50.1032138 and 14.4363956 <= lng <= 14.4748670
        except (KeyError, TypeError, ValueError):
            return False
    if region_key == "prague":
        return "praha" in blob or "prague" in blob
    if region_key == "decin":
        return "decin" in blob
    if region_key == "usti":
        return "usti" in blob
    return True


def fetch_region(region_key: str, *, max_pages: int = 40, sleep: float = 0.4) -> list[dict]:
    osm = config.REGIONS[region_key]["bez_osm"]
    if not osm:
        print(f"[{region_key}] no bez_osm configured", file=sys.stderr)
        return []
    out: list[dict] = []
    seen: set[str] = set()
    offset = 0
    total = None
    for _ in range(max_pages):
        try:
            page = list_adverts(osm, limit=PAGE_SIZE, offset=offset)
        except Exception as e:
            print(f"[{region_key}] gql error at offset {offset}: {e}", file=sys.stderr)
            break
        if total is None:
            total = page.get("totalCount") or 0
            print(f"[{region_key}] bez total={total}", file=sys.stderr)
        items = page.get("list") or []
        if not items:
            break
        for a in items:
            aid = str(a.get("id") or "")
            if not aid or aid in seen:
                continue
            seen.add(aid)
            item = advert_to_item(a, region_key)
            if not in_region(item, region_key):
                continue
            out.append(item)
        offset += len(items)
        if offset >= (total or 0) or len(items) < PAGE_SIZE:
            break
        time.sleep(sleep)
    print(f"[{region_key}] bez kept geo-filtered {len(out)}", file=sys.stderr)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--regions", default="karlin,prague,decin,usti")
    p.add_argument("--max-pages", type=int, default=40)
    args = p.parse_args(argv)
    config.RAW.mkdir(parents=True, exist_ok=True)
    config.BEZ_CACHE.mkdir(parents=True, exist_ok=True)
    regions = [r.strip() for r in args.regions.split(",") if r.strip()]
    all_items = []
    for rk in regions:
        items = fetch_region(rk, max_pages=args.max_pages)
        path = config.RAW / f"bezrealitky-{rk}.json"
        path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n")
        print(f"wrote {path} n={len(items)}", file=sys.stderr)
        all_items.extend(items)
    (config.RAW / "bezrealitky-all.json").write_text(
        json.dumps(all_items, ensure_ascii=False, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
