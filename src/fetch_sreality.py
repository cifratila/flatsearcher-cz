#!/usr/bin/env python3
"""Fetch Sreality BUY flat list pages (+ optional detail enrichment).

Uses Seznam CMP cookies (euconsent-v2) from data/cookies-sreality.txt.
List payloads do NOT include floor/ownership — details required for those.
Ownership filter vlastnictvi=osobni is applied on search but still verified
from detail pages (list filter is imperfect).
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from . import config
from .util import fold, name_val

def ascii_seo(s: str) -> str:
    """ASCII SEO slug; fold Czech diacritics."""
    s = fold(s or "")
    s = re.sub(r"[^a-z0-9+]+", "-", s).strip("-")
    return s or "x"


NEXT_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)


def _opener() -> urllib.request.OpenerDirector:
    jar = http.cookiejar.MozillaCookieJar()
    if config.COOKIES.exists():
        jar.load(str(config.COOKIES), ignore_discard=True, ignore_expires=True)
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


OPENER = _opener()


def http_get(url: str, timeout: int = 60) -> bytes:
    # Ensure path/query are ASCII-safe (Sreality SEO sometimes leaks diacritics).
    parts = urllib.parse.urlsplit(url)
    path = urllib.parse.quote(parts.path, safe="/+,-_")
    query = urllib.parse.quote(parts.query, safe="=&%+,")
    safe_url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))
    req = urllib.request.Request(
        safe_url,
        headers={
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "cs,en;q=0.8",
        },
    )
    with OPENER.open(req, timeout=timeout) as resp:
        return resp.read()


def parse_next_data(html: str) -> dict:
    m = NEXT_RE.search(html)
    if not m:
        raise RuntimeError("No __NEXT_DATA__ in HTML (CMP/consent or block?)")
    return json.loads(m.group(1))


def estates_search_from_next(data: dict) -> tuple[dict, list[dict]]:
    pp = data["props"]["pageProps"]
    qs = pp.get("dehydratedState", {}).get("queries") or []
    for q in qs:
        if q.get("queryKey", [None])[0] == "estatesSearch":
            payload = q["state"]["data"]
            return q["queryKey"][1], payload.get("results") or []
    raise RuntimeError("estatesSearch query missing")


def search_url(region_key: str, page: int = 1) -> str:
    reg = config.REGIONS[region_key]
    params = {
        "velikost": config.VELIKOST,
        "vlastnictvi": "osobni",
    }
    params.update(reg.get("sreality_query") or {})
    if page > 1:
        params["strana"] = str(page)
    path = reg.get("sreality_path")
    if path:
        base = f"https://www.sreality.cz/hledani/prodej/byty/{path}"
    else:
        base = "https://www.sreality.cz/hledani/prodej/byty"
    return base + "?" + urllib.parse.urlencode(params, safe="+, ")


def list_item_to_seed(est: dict, region_key: str, page: int) -> dict:
    loc = est.get("locality") or {}
    sub = name_val(est.get("categorySubCb")) or ""
    m2 = None
    # usable area often only in name: "Prodej bytu 2+kk 56 m²"
    m = re.search(r"(\d+)\s*m", est.get("name") or "")
    if m:
        m2 = int(m.group(1))
    price = est.get("priceCzk")
    kc = est.get("priceCzkPerSqM")
    if not kc and price and m2:
        kc = int(round(price / m2))
    street = loc.get("street") or ""
    city_part = loc.get("cityPart") or ""
    seo_city = ascii_seo(loc.get("citySeoName") or loc.get("city") or "praha")
    seo_part = ascii_seo(
        loc.get("cityPartSeoName")
        or loc.get("cityPart")
        or loc.get("districtSeoName")
        or loc.get("district")
        or "x"
    )
    seo_street = ascii_seo(loc.get("streetSeoName") or loc.get("street") or "x")
    url = (
        f"https://www.sreality.cz/detail/prodej/byt/{sub}/"
        f"{seo_city}-{seo_part}-{seo_street}/{est['id']}"
    )
    # Better: reconstruct from premise-less pattern used by site
    # Actual URLs use cityPartSeoName; keep seed URL, detail fetch will confirm
    return {
        "id": str(est["id"]),
        "url": url,
        "street": street,
        "disp": sub,
        "m2": m2,
        "price": price,
        "kc_m2": kc,
        "locality": loc,
        "name": est.get("name") or "",
        "source": "sreality",
        "region_bucket": region_key,
        "page": page,
        "city_part": city_part,
        "district": loc.get("district") or "",
        "quarter": loc.get("quarter") or "",
    }


def fetch_list_region(region_key: str, max_pages: int | None = None, sleep: float = 0.35) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    page = 1
    total = None
    while True:
        if max_pages and page > max_pages:
            break
        url = search_url(region_key, page)
        try:
            html = http_get(url).decode("utf-8", errors="replace")
            data = parse_next_data(html)
            qk, results = estates_search_from_next(data)
            pag = None
            for q in data["props"]["pageProps"]["dehydratedState"]["queries"]:
                if q.get("queryKey", [None])[0] == "estatesSearch":
                    pag = q["state"]["data"].get("pagination") or {}
                    break
            if total is None:
                total = (pag or {}).get("total") or 0
                print(
                    f"[{region_key}] total={total} page1_n={len(results)} q={qk.get('localityEntityId') or qk.get('localityRegionId') or qk.get('localityDistrictId')}",
                    file=sys.stderr,
                )
        except Exception as e:
            print(f"[{region_key}] page {page} ERROR: {e}", file=sys.stderr)
            break
        if not results:
            break
        for est in results:
            sid = str(est.get("id") or "")
            if not sid or sid in seen:
                continue
            # skip promo tips without real id shape
            if not isinstance(est.get("priceCzk"), (int, float)) and not est.get("categorySubCb"):
                continue
            seen.add(sid)
            seed = list_item_to_seed(est, region_key, page)
            # Drop atypical / out-of-layout dispositions early
            if seed.get("disp") and seed["disp"] not in config.LAYOUTS:
                continue
            loc = seed.get("locality") or {}
            city = (loc.get("city") or "").lower()
            if region_key == "decin" and "děčín" not in city and "decin" not in city.replace("ě","e").replace("č","c"):
                from .util import fold
                if fold(loc.get("city") or "") != "decin":
                    continue
            if region_key == "usti":
                from .util import fold
                if "usti" not in fold(loc.get("city") or ""):
                    continue
            if region_key == "karlin":
                from .util import fold
                cp = fold(loc.get("cityPart") or "")
                if "karlin" not in cp:
                    continue
            out.append(seed)
        offset = (pag or {}).get("offset", 0) + len(results)
        if offset >= (total or 0) or len(results) < 1:
            break
        page += 1
        time.sleep(sleep)
    print(f"[{region_key}] listed {len(out)}", file=sys.stderr)
    return out


def parse_estate_detail(html: str, seed: dict | None = None) -> dict | None:
    seed = seed or {}
    try:
        data = parse_next_data(html)
    except RuntimeError:
        return None
    estate = None
    for q in data["props"]["pageProps"].get("dehydratedState", {}).get("queries") or []:
        if q.get("queryKey", [None])[0] == "estate":
            estate = q["state"]["data"]
            break
    if not estate:
        return None
    params = estate.get("params") or {}
    loc = estate.get("locality") or {}
    street = loc.get("street") or seed.get("street") or ""
    own = name_val(params.get("ownership"))
    fn = params.get("floorNumber")
    floors = params.get("floors")
    elev = name_val(params.get("elevator"))
    cond = name_val(params.get("buildingCondition"))
    btype = name_val(params.get("buildingType"))
    flat_class = name_val(params.get("flatClass"))
    if flat_class and str(flat_class).startswith("-"):
        flat_class = None
    usable = params.get("usableArea") or params.get("floorArea")
    m2 = usable or seed.get("m2")
    price = estate.get("priceCzk") or seed.get("price")
    kc = estate.get("priceCzkPerSqM")
    if not kc and price and m2:
        kc = int(round(price / m2))
    floor_str = None
    if fn is not None:
        floor_str = f"{fn}/{floors}" if floors else str(fn)
    disp = name_val(estate.get("categorySubCb")) or seed.get("disp")
    # canonical SEO url if present
    url = seed.get("url")
    seo = estate.get("seo") or {}
    if seo.get("locality") and seo.get("name"):
        # sometimes available
        pass
    return {
        "id": str(seed.get("id") or estate.get("id") or ""),
        "url": url,
        "street": street,
        "disposition": disp,
        "m2": m2,
        "price_czk": price,
        "kc_m2": kc,
        "floor": floor_str,
        "floor_number": fn,
        "floors_total": floors,
        "ownership": (own or "").lower() if own else None,
        "ownership_raw": own,
        "elevator": elev,
        "condition": cond,
        "building_type": btype,
        "flat_class": flat_class,
        "city_part": loc.get("cityPart") or seed.get("city_part") or "",
        "district": loc.get("district") or seed.get("district") or "",
        "quarter": loc.get("quarter") or seed.get("quarter") or "",
        "locality": loc,
        "description": estate.get("description") or "",
        "name": estate.get("name") or seed.get("name") or "",
        "note_field": estate.get("note") or "",
        "source": "sreality",
        "region_bucket": seed.get("region_bucket"),
        "notes": "",
    }


def detail_cache_path(listing_id: str) -> Path:
    return config.SREALITY_DETAIL_CACHE / f"{listing_id}.json"


def fetch_detail(seed: dict, sleep: float = 0.0, refresh: bool = False) -> dict | None:
    lid = str(seed["id"])
    cache = detail_cache_path(lid)
    if cache.exists() and not refresh:
        try:
            cached = json.loads(cache.read_text())
            # re-attach seed fields
            cached.setdefault("region_bucket", seed.get("region_bucket"))
            cached.setdefault("url", seed.get("url"))
            return cached
        except Exception:
            pass
    # Prefer SEO URL from list; fall back to id-only redirect pattern
    urls = [seed.get("url")]
    loc = seed.get("locality") or {}
    sub = seed.get("disp") or "x"
    alt = (
        f"https://www.sreality.cz/detail/prodej/byt/{sub}/"
        f"{loc.get('citySeoName') or 'praha'}-"
        f"{loc.get('cityPartSeoName') or loc.get('districtSeoName') or 'x'}-"
        f"{loc.get('streetSeoName') or 'x'}/{lid}"
    )
    if alt not in urls:
        urls.append(alt)
    last_err = None
    for url in urls:
        if not url:
            continue
        try:
            html = http_get(url).decode("utf-8", errors="replace")
            item = parse_estate_detail(html, {**seed, "url": url})
            if item:
                item["url"] = url
                config.SREALITY_DETAIL_CACHE.mkdir(parents=True, exist_ok=True)
                cache.write_text(json.dumps(item, ensure_ascii=False))
                if sleep:
                    time.sleep(sleep)
                return item
        except Exception as e:
            last_err = e
            continue
    print(f"detail fail {lid}: {last_err}", file=sys.stderr)
    return None


def enrich_details(
    seeds: list[dict],
    *,
    workers: int = 6,
    limit: int | None = None,
    refresh: bool = False,
) -> list[dict]:
    todo = seeds[:limit] if limit else seeds
    out: list[dict] = []
    config.SREALITY_DETAIL_CACHE.mkdir(parents=True, exist_ok=True)
    misses = []
    for s in todo:
        cache = detail_cache_path(str(s["id"]))
        if cache.exists() and not refresh:
            try:
                item = json.loads(cache.read_text())
                item.setdefault("region_bucket", s.get("region_bucket"))
                item.setdefault("url", s.get("url"))
                out.append(item)
                continue
            except Exception:
                pass
        misses.append(s)
    print(f"details cached={len(out)} to_fetch={len(misses)}", file=sys.stderr)

    def _one(s):
        return fetch_detail(s, sleep=0.05, refresh=refresh)

    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_one, s): s for s in misses}
        for fut in as_completed(futs):
            done += 1
            if done % 50 == 0 or done == len(misses):
                print(f"  details progress {done}/{len(misses)}", file=sys.stderr)
            item = fut.result()
            if item:
                out.append(item)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--regions",
        default="karlin,prague,decin,usti",
        help="Comma-separated region keys",
    )
    p.add_argument("--max-pages", type=int, default=None)
    p.add_argument("--details", action="store_true", help="Fetch detail pages")
    p.add_argument("--detail-limit", type=int, default=None)
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--refresh-details", action="store_true")
    args = p.parse_args(argv)

    config.RAW.mkdir(parents=True, exist_ok=True)
    regions = [r.strip() for r in args.regions.split(",") if r.strip()]
    all_seeds = []
    for rk in regions:
        seeds = fetch_list_region(rk, max_pages=args.max_pages)
        path = config.RAW / f"sreality-list-{rk}.json"
        path.write_text(json.dumps(seeds, ensure_ascii=False, indent=2) + "\n")
        print(f"wrote {path} n={len(seeds)}", file=sys.stderr)
        all_seeds.extend(seeds)

    combined = config.RAW / "sreality-list-all.json"
    combined.write_text(json.dumps(all_seeds, ensure_ascii=False, indent=2) + "\n")

    if args.details:
        details = enrich_details(
            all_seeds,
            workers=args.workers,
            limit=args.detail_limit,
            refresh=args.refresh_details,
        )
        dpath = config.RAW / "sreality-details.json"
        dpath.write_text(json.dumps(details, ensure_ascii=False, indent=2) + "\n")
        print(f"wrote {dpath} n={len(details)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
