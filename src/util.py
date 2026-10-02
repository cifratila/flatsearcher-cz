"""Shared helpers."""
from __future__ import annotations

import re
import unicodedata
from typing import Any


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    return "".join(c for c in s if not unicodedata.combining(c))


def name_val(x: Any) -> Any:
    if isinstance(x, dict):
        return x.get("name")
    return x


INTERNAL_STAIRS_RE = re.compile(
    r"(?:"
    r"mezonet|duplex|maisonette"
    r"|vnitrni\s+schodist"
    r"|schod(?:y|iste)\s+v\s+(?:byte|jednotce)"
    r"|dvouurovn|viceurovn|vice\s+urovn"
    r"|patrovy\s+byt"
    r")",
    re.I,
)


def detect_internal_stairs(*parts: str, flat_class: str | None = None) -> bool:
    blob = fold(" ".join(p for p in parts if p))
    if INTERNAL_STAIRS_RE.search(blob):
        return True
    fc = fold(flat_class or "")
    if "mezonet" in fc or "duplex" in fc or "maisonette" in fc:
        return True
    if "vicepodlaz" in fc or "dvoupodlaz" in fc:
        return True
    return False


UNIT_GROUND_RE = re.compile(
    r"(?:"
    r"byt(?:ova jednotka)?[^\n.]{0,60}(?:se nachazi|je situovan[ay]|umisten[ay]|je)\s+"
    r"(?:ve?\s+)?(?:snizenem\s+)?prizemi"
    r"|jednotka[^\n.]{0,60}(?:se nachazi|je situovan[ay]|umisten[ay]|je)\s+"
    r"(?:ve?\s+)?(?:snizenem\s+)?prizemi"
    r"|(?:nachazi|situovan[ay]|umisten[ay])\s+ve?\s+(?:snizenem\s+)?prizemi"
    r"|situovan[ay]?\s+v\s+prizemi"
    r"|ve?\s+snizenem\s+prizemi"
    r"|ve?\s+suterenu?"
    r"|sklepni\s+(?:byt|jednotka|atelier|atelie)"
    r"|atelier[^\n.]{0,40}(?:suteren|prizemi|sklepn|podzem)"
    r"|(?:byt|jednotka)[^\n.]{0,40}(?:1\.?\s*pp|podzemni(?:m)?\s+podlaz)"
    r")",
    re.I,
)


ATYPICAL_RE = re.compile(
    r"(?:atelier|atelie).{0,80}(?:atyp|snizen|suteren|sklepn|nebyt|k bydleni nelze)",
    re.I,
)


KARLIN_SUBAREA_RULES: list[tuple[str, list[str]]] = [
    (
        "River / Port",
        [
            "rohanske nabrezi",
            "za karlinskym pristavem",
            "u mlynskeho kanalu",
            "pobrezni",
        ],
    ),
    (
        "Invalidovna / east",
        [
            "invalidovna",
            "za invalidovnou",
            "u sluncove",
            "molakova",
            "sokolova",
            "sokolovska",
            "brezinova",
            "svarcova",
            "nekvasilova",
            "na strelnici",
            "kaizlovy sady",
            "negrelliho",
        ],
    ),
    (
        "Pernerova / Jirsíkova corridor",
        ["pernerova", "jirsikova", "kubicova"],
    ),
    ("Prvního pluku / south edge", ["prvniho pluku"]),
    (
        "Karlínské náměstí / west",
        [
            "karlinske namesti",
            "vitkova",
            "saldova",
            "krizikova",
            "peckova",
            "kollarova",
            "karolinska",
            "havanova",
        ],
    ),
]


def karlin_subarea(street: str) -> str:
    fs = fold(street)
    fs = re.sub(r"\d+.*$", "", fs).strip()
    for bucket, streets in KARLIN_SUBAREA_RULES:
        for st in streets:
            if fs == st or fs.startswith(st + " "):
                return bucket
    return "Karlín (other)"


def district_for(bucket: str, locality: dict | None, street: str, address: str = "") -> str:
    loc = locality or {}
    if bucket == "karlin":
        return karlin_subarea(street)
    if bucket == "prague":
        return (
            loc.get("cityPart")
            or loc.get("quarter")
            or loc.get("district")
            or "Praha (other)"
        )
    if bucket == "decin":
        return loc.get("cityPart") or loc.get("quarter") or "Děčín"
    if bucket == "usti":
        return loc.get("cityPart") or loc.get("quarter") or "Ústí nad Labem"
    # fallback from address
    return address.split(",")[-1].strip() if address else bucket
