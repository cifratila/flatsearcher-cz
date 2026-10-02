"""Shared scope for FlatSearcher CZ catalogs."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
CACHE = DATA / "cache"
SREALITY_DETAIL_CACHE = CACHE / "sreality-details"
BEZ_CACHE = CACHE / "bezrealitky"
SITE = ROOT / "site"
DOCS = ROOT / "docs"
COOKIES = DATA / "cookies-sreality.txt"

LAYOUTS = ["1+kk", "1+1", "2+kk", "2+1", "3+kk", "3+1", "4+kk", "4+1"]
# Sreality categorySubCb values for those layouts
SREALITY_SUB_CB = [2, 3, 4, 5, 6, 7, 8, 9]
BEZ_DISPOSITIONS = [
    "DISP_1_KK",
    "DISP_1_1",
    "DISP_2_KK",
    "DISP_2_1",
    "DISP_3_KK",
    "DISP_3_1",
    "DISP_4_KK",
    "DISP_4_1",
]
DISP_LABEL = {
    "DISP_1_KK": "1+kk",
    "DISP_1_1": "1+1",
    "DISP_2_KK": "2+kk",
    "DISP_2_1": "2+1",
    "DISP_3_KK": "3+kk",
    "DISP_3_1": "3+1",
    "DISP_4_KK": "4+kk",
    "DISP_4_1": "4+1",
}

# Portal floor 1 = 1.NP = přízemí → keep floor >= 2
MIN_FLOOR = 2

REGIONS = {
    "karlin": {
        "label": "Karlín",
        "bucket": "karlin",
        # Search URL pieces that resolve to ward 13707
        "sreality_path": None,
        "sreality_query": {
            "region": "mestska-cast-karlin-praha",
            "municipality": "mestska-cast-karlin-praha",
        },
        "bez_osm": "R435856",
        "post_filter": "karlin",  # cityPart / address must contain karlin
    },
    "prague": {
        "label": "Praha (all districts)",
        "bucket": "prague",
        "sreality_path": "praha",
        "sreality_query": {},
        "bez_osm": "R435514",
        "post_filter": "prague",
    },
    "decin": {
        "label": "Děčín",
        "bucket": "decin",
        "sreality_path": "decin",
        "sreality_query": {},
        "bez_osm": "R439579",
        "post_filter": "decin",
    },
    "usti": {
        "label": "Ústí nad Labem",
        "bucket": "usti",
        "sreality_path": "usti-nad-labem",
        "sreality_query": {},
        "bez_osm": "R440166",
        "post_filter": "usti",
    },
}

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

VELIKOST = "1+kk,1+1,2+kk,2+1,3+kk,3+1,4+kk,4+1"
