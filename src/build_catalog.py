#!/usr/bin/env python3
"""Classify, filter, dedupe listings → data/listings.json (+ cz-flats mirror)."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import config
from .util import (
    ATYPICAL_RE,
    UNIT_GROUND_RE,
    detect_internal_stairs,
    district_for,
    fold,
    name_val,
)

PRAGUE = timezone(timedelta(hours=2))
MIRROR = Path("/workspace/cz-flats-2026-10-02")


def ownership_bucket(item: dict) -> str:
    own = fold(item.get("ownership") or item.get("ownership_raw") or "")
    if "osobni" in own:
        return "osobní"
    if "druzstev" in own:
        return "družstevní"
    return "unclear"


def classify_floor(item: dict) -> tuple[str | None, bool]:
    """Return (exclude_reason, floor_unknown). Mezonets are NOT excluded here."""
    fn = item.get("floor_number")
    try:
        fn_i = int(fn) if fn is not None else None
    except (TypeError, ValueError):
        fn_i = None

    blob = fold(
        f"{item.get('name') or ''}\n{item.get('description') or ''}\n"
        f"{item.get('notes') or ''}\n{item.get('note_field') or ''}"
    )

    if fn_i is not None and fn_i < config.MIN_FLOOR:
        return "přízemí/suterén", False

    if UNIT_GROUND_RE.search(blob):
        return "přízemí/suterén", False

    if ATYPICAL_RE.search(blob):
        return "atypical", False

    # Mezzanine spanning 1.NP + 1.PP as the unit (underground atypical)
    if re.search(r"1\.?\s*np.{0,40}1\.?\s*pp|1\.?\s*pp.{0,40}1\.?\s*np", blob):
        if "mezoni" in blob or "apartman" in blob or "jednotka" in blob:
            # only exclude if clearly underground combo without higher floors
            if fn_i is None or fn_i < config.MIN_FLOOR:
                return "přízemí/suterén", False

    if fn_i is None:
        m = re.search(r"ve?\s*(\d+)\.?\s*(?:np|podlaz|patre|patro)", blob)
        if m:
            parsed = int(m.group(1))
            item["floor_number"] = parsed
            item["floor"] = str(parsed)
            if parsed < config.MIN_FLOOR:
                return "přízemí/suterén", False
            return None, False
        return None, True

    return None, False


def notes_for(item: dict) -> str:
    bits: list[str] = []
    if item.get("notes"):
        bits.append(str(item["notes"]))
    if item.get("condition"):
        bits.append(str(item["condition"]))
    elev = item.get("elevator")
    if elev in ("Ano", "ano", True) or elev is True:
        bits.append("výtah: ano")
    elif elev in ("Ne", "ne", False) or elev is False:
        bits.append("výtah: ne")
    if item.get("building_type"):
        bits.append(str(item["building_type"]).lower())
    if item.get("flat_class"):
        bits.append(str(item["flat_class"]))
    if item.get("has_internal_stairs"):
        bits.append("mezonet/internal stairs")
    out: list[str] = []
    seen = set()
    for b in bits:
        for part in [p.strip() for p in b.split(";")]:
            if not part:
                continue
            k = fold(part)
            if k not in seen:
                seen.add(k)
                out.append(part)
    return "; ".join(out)


def dedupe_key(it: dict):
    return (fold(it.get("street") or ""), it.get("m2"), it.get("price_czk"))


def merge_dedupe(rows: list[dict]) -> list[dict]:
    groups: dict = {}
    order: list = []
    for r in rows:
        k = dedupe_key(r)
        if k not in groups:
            groups[k] = dict(r)
            order.append(k)
            continue
        primary = groups[k]
        srcs = sorted(set(str(primary["source"]).split("+")) | set(str(r["source"]).split("+")))
        primary["source"] = "+".join(srcs)
        if r.get("url") and r["url"] != primary.get("url"):
            primary["twin_url"] = r["url"]
            note = f"twin {r['source']}"
            if note not in (primary.get("notes") or ""):
                primary["notes"] = (
                    (primary["notes"] + "; " if primary.get("notes") else "") + note
                )
        if not primary.get("floor") and r.get("floor"):
            primary["floor"] = r["floor"]
            primary["floor_number"] = r.get("floor_number")
            primary["floors_total"] = r.get("floors_total")
        if r.get("has_internal_stairs"):
            primary["has_internal_stairs"] = True
        # Prefer sreality url as primary when merging
        if "sreality" in str(r.get("source")) and "sreality" not in str(primary.get("source")):
            primary["url"], primary["twin_url"] = r.get("url"), primary.get("url")
    return [groups[k] for k in order]


def geo_ok(item: dict, bucket: str) -> bool:
    cp = fold(item.get("city_part") or "")
    dist = fold(item.get("district") or "")
    q = fold(item.get("quarter") or "")
    addr = fold(item.get("address") or "")
    url = fold(item.get("url") or "")
    street = fold(item.get("street") or "")
    blob = f"{cp} {dist} {q} {addr} {url} {street}"
    if bucket == "karlin":
        return "karlin" in blob
    if bucket == "prague":
        # Karlín stays in its own bucket when building multi; prague view includes all
        return "praha" in blob or "prague" in blob or bool(item.get("city_part"))
    if bucket == "decin":
        return "decin" in blob
    if bucket == "usti":
        return "usti" in blob
    return True


def load_sreality_details() -> list[dict]:
    path = config.RAW / "sreality-details.json"
    if path.exists():
        return json.loads(path.read_text())
    # assemble from cache
    items = []
    if config.SREALITY_DETAIL_CACHE.exists():
        for p in config.SREALITY_DETAIL_CACHE.glob("*.json"):
            try:
                items.append(json.loads(p.read_text()))
            except Exception:
                pass
    return items


def load_bez() -> list[dict]:
    path = config.RAW / "bezrealitky-all.json"
    if path.exists():
        return json.loads(path.read_text())
    return []


def load_idnes() -> list[dict]:
    path = config.RAW / "idnes-all.json"
    if not path.exists():
        return []
    # only keep cards that have price+m2 (otherwise useless for catalog)
    out = []
    for x in json.loads(path.read_text()):
        if x.get("price_czk") and x.get("m2"):
            out.append(x)
    return out


def to_record(it: dict, bucket: str) -> dict:
    has_stairs = detect_internal_stairs(
        it.get("name") or "",
        it.get("description") or "",
        it.get("note_field") or "",
        it.get("notes") or "",
        flat_class=it.get("flat_class"),
    )
    it = dict(it)
    it["has_internal_stairs"] = has_stairs
    district = district_for(
        bucket,
        it.get("locality") if isinstance(it.get("locality"), dict) else {
            "cityPart": it.get("city_part"),
            "quarter": it.get("quarter"),
            "district": it.get("district"),
        },
        it.get("street") or "",
        it.get("address") or "",
    )
    # For Prague bucket, if city_part is Karlín still label district as Karlín
    return {
        "street": it.get("street"),
        "disposition": it.get("disposition") or it.get("disp"),
        "m2": it.get("m2"),
        "price_czk": it.get("price_czk") or it.get("price"),
        "kc_m2": it.get("kc_m2"),
        "floor": it.get("floor"),
        "floor_number": it.get("floor_number"),
        "floors_total": it.get("floors_total"),
        "ownership": "osobní",
        "region_bucket": bucket,
        "district": district,
        "has_internal_stairs": has_stairs,
        "url": it.get("url"),
        "source": it.get("source"),
        "notes": notes_for(it),
        "id": it.get("id"),
    }


def _ex(it: dict, reason: str) -> dict:
    return {
        "id": it.get("id"),
        "url": it.get("url"),
        "street": it.get("street"),
        "disposition": it.get("disposition") or it.get("disp"),
        "m2": it.get("m2"),
        "price_czk": it.get("price_czk") or it.get("price"),
        "kc_m2": it.get("kc_m2"),
        "floor": it.get("floor"),
        "ownership_raw": it.get("ownership_raw") or it.get("ownership"),
        "source": it.get("source"),
        "region_bucket": it.get("region_bucket"),
        "exclude_reason": reason,
    }


def assign_bucket(it: dict) -> str | None:
    """Prefer explicit region_bucket; Karlín carved out of Prague."""
    rb = it.get("region_bucket")
    cp = fold(it.get("city_part") or "")
    url = fold(it.get("url") or "")
    addr = fold(it.get("address") or "")
    if "karlin" in cp or "karlin" in url or "karlin" in addr:
        return "karlin"
    if rb in ("karlin", "prague", "decin", "usti"):
        # if listed under prague scrape but is karlin → already handled
        if rb == "prague" and ("karlin" in cp or "karlin" in url):
            return "karlin"
        return rb
    if "decin" in cp or "decin" in url or "decin" in addr:
        return "decin"
    if "usti" in cp or "usti" in url or "usti" in addr:
        return "usti"
    if "praha" in cp or "praha" in url or it.get("city_part"):
        return "prague"
    return rb


def build() -> dict:
    sreality = load_sreality_details()
    bez = load_bez()
    idnes = load_idnes()
    all_items = sreality + bez + idnes

    tallies: Counter = Counter()
    excluded = []
    kept_by_bucket: dict[str, list] = {k: [] for k in config.REGIONS}
    floor_unknown_by_bucket: dict[str, list] = {k: [] for k in config.REGIONS}
    by_source = Counter()

    for it in all_items:
        tallies["scanned"] += 1
        by_source[it.get("source") or "?"] += 1
        bucket = assign_bucket(it)
        if not bucket or bucket not in config.REGIONS:
            tallies["excluded_geo"] += 1
            excluded.append(_ex(it, "geo/unknown-region"))
            continue
        if not geo_ok(it, bucket):
            tallies["excluded_geo"] += 1
            excluded.append(_ex(it, f"non-{bucket}"))
            continue

        # Sanity: usable flat area (exclude whole-building / parse errors)
        try:
            m2v = float(it.get("m2") or 0)
        except (TypeError, ValueError):
            m2v = 0
        if m2v and (m2v < 10 or m2v > 400):
            tallies["excluded_bad_area"] += 1
            excluded.append(_ex(it, f"bad_area:{m2v}"))
            continue

        disp = it.get("disposition") or it.get("disp")
        if disp and disp not in config.LAYOUTS:
            # allow slight variants
            if disp not in config.LAYOUTS:
                tallies["excluded_disposition"] += 1
                excluded.append(_ex(it, f"disposition:{disp}"))
                continue

        ob = ownership_bucket(it)
        if ob == "družstevní":
            tallies["excluded_družstevní"] += 1
            excluded.append(_ex(it, "družstevní"))
            continue
        if ob == "unclear":
            # Bezrealitky sometimes omits ownership — treat missing as unclear exclude
            tallies["excluded_unclear_ownership"] += 1
            excluded.append(_ex(it, "unclear ownership"))
            continue

        reason, unk = classify_floor(it)
        if reason == "přízemí/suterén":
            tallies["excluded_přízemí/suterén"] += 1
            excluded.append(_ex(it, reason))
            continue
        if reason == "atypical":
            tallies["excluded_atypical"] += 1
            excluded.append(_ex(it, reason))
            continue

        rec = to_record(it, bucket)
        if not rec.get("kc_m2") and rec.get("price_czk") and rec.get("m2"):
            rec["kc_m2"] = int(round(rec["price_czk"] / rec["m2"]))

        if unk:
            tallies["floor_unknown"] += 1
            floor_unknown_by_bucket[bucket].append(rec)
        else:
            tallies["kept_pre_dedupe"] += 1
            kept_by_bucket[bucket].append(rec)

    # Dedupe per bucket
    dedupe_removed = 0
    for b in list(kept_by_bucket):
        before = len(kept_by_bucket[b])
        kept_by_bucket[b] = merge_dedupe(kept_by_bucket[b])
        floor_unknown_by_bucket[b] = merge_dedupe(floor_unknown_by_bucket[b])
        dedupe_removed += before - len(kept_by_bucket[b])
        kept_by_bucket[b].sort(
            key=lambda r: (r.get("kc_m2") is None, r.get("kc_m2") or 10**12)
        )
        floor_unknown_by_bucket[b].sort(
            key=lambda r: (r.get("kc_m2") is None, r.get("kc_m2") or 10**12)
        )

    listings = []
    floor_unknown = []
    for b in ("karlin", "prague", "decin", "usti"):
        listings.extend(kept_by_bucket[b])
        floor_unknown.extend(floor_unknown_by_bucket[b])

    now = datetime.now(PRAGUE)
    counts = {
        "total_scanned": tallies["scanned"],
        "kept": len(listings),
        "floor_unknown": len(floor_unknown),
        "by_bucket": {b: len(kept_by_bucket[b]) for b in kept_by_bucket},
        "floor_unknown_by_bucket": {
            b: len(floor_unknown_by_bucket[b]) for b in floor_unknown_by_bucket
        },
        "excluded": {
            "družstevní": tallies["excluded_družstevní"],
            "unclear_ownership": tallies["excluded_unclear_ownership"],
            "přízemí/suterén": tallies["excluded_přízemí/suterén"],
            "atypical": tallies["excluded_atypical"],
            "geo": tallies["excluded_geo"],
            "disposition": tallies["excluded_disposition"],
            "bad_area": tallies["excluded_bad_area"],
        },
        "dedupe_removed": dedupe_removed,
        "by_source": dict(by_source),
    }

    out = {
        "generated": now.isoformat(),
        "filters": {
            "offer": "prodej",
            "dispositions": config.LAYOUTS,
            "ownership": "osobní only (exclude družstevní / unclear)",
            "floor_rule": (
                "Portal floorNumber/etage 1 = 1.NP = přízemí. KEEP floor >= 2. "
                "Mezonet/internal stairs INCLUDED (has_internal_stairs=true). "
                "Unknown floor → separate section."
            ),
            "regions": list(config.REGIONS.keys()),
            "sources": ["sreality", "bezrealitky", "idnes (secondary)"],
            "dedupe": "street + m2 + price_czk across portals",
        },
        "counts": counts,
        "listings": listings,
        "floor_unknown": floor_unknown,
        "excluded": excluded,
        "listings_by_bucket": kept_by_bucket,
        "floor_unknown_by_bucket": floor_unknown_by_bucket,
    }
    return out


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "-o",
        "--output",
        default=str(config.DATA / "listings.json"),
    )
    p.add_argument("--keep-excluded", action="store_true")
    args = p.parse_args(argv)
    out = build()
    if not args.keep_excluded:
        out.pop("excluded", None)
        out.pop("listings_by_bucket", None)
        out.pop("floor_unknown_by_bucket", None)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    MIRROR.mkdir(parents=True, exist_ok=True)
    (MIRROR / "listings.json").write_text(path.read_text())
    print(
        json.dumps(
            {
                "wrote": str(path),
                "kept": out["counts"]["kept"],
                "by_bucket": out["counts"]["by_bucket"],
                "floor_unknown": out["counts"]["floor_unknown_by_bucket"],
                "excluded": out["counts"]["excluded"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
