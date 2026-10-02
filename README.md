# FlatSearcher CZ

Czech **BUY** flat catalog for **Karlín**, **all Praha districts**, **Děčín**, and **Ústí nad Labem**.

**Generated:** 2026-10-02T10:10:50.884893+02:00 (Europe/Prague)

## Live UI

- `docs/index.html` — GitHub Pages (`/docs`)
- `site/index.html` — same build

## Latest counts

| Bucket | Kept | Floor unknown |
|--------|-----:|--------------:|
| Karlín | 89 | 0 |
| Praha | 2979 | 0 |
| Děčín | 36 | 0 |
| Ústí | 126 | 0 |
| **Total kept** | **3230** | **0** |

Scanned (detail/list rows before filter): 4709 · by source: {'sreality': 4204, 'bezrealitky': 505}

### Excluded

| Reason | N |
|--------|--:|
| družstevní | 45 |
| unclear ownership | 6 |
| přízemí/suterén | 1213 |
| atypical | 1 |
| geo | 0 |
| dedupe removed | 212 |

## Scope

| Filter | Rule |
|--------|------|
| Offer | Prodej only |
| Layouts | 1+kk … 4+1 |
| Ownership | **osobní** only |
| Floor | Portal floor 1 = 1.NP = přízemí → keep **≥ 2** |
| Mezonet | **Included**; `has_internal_stairs` |
| Dedupe | street + m² + price |

## Regions

| Bucket | Sreality | Bezrealitky OSM |
|--------|----------|-----------------|
| karlin | ward `mestska-cast-karlin-praha` | R435856 |
| prague | region Praha | R435514 |
| decin | `/byty/decin` (city-filtered) | R439579 |
| usti | `/byty/usti-nad-labem` | R440166 |

## How to run

```bash
# 1. Seznam CMP cookies → data/cookies-sreality.txt (gitignored)
export PYTHONPATH=.
python3 -m src.fetch_bezrealitky
# lists (or use scripts/fetch_sreality_lists_curl.sh prague for large Praha)
python3 -m src.fetch_sreality --regions karlin,decin,usti
./scripts/fetch_sreality_lists_curl.sh prague
python3 -m src.parse_sreality_pages --region prague
python3 -m src.fetch_sreality --details --workers 10
python3 -m src.fetch_idnes --regions karlin,decin,usti --max-pages 2 || true
python3 -m src.build_catalog
python3 -m src.build_html
```

Or `./scripts/run_all.sh` for a simpler path (Python list pagination; Praha may be slow).

## Cheapest 3 / bucket (Kč/m²)

### karlin
- **121,939** — Pernerova 1+kk 82 m² · 9,999,000 Kč · fl 4
- **133,500** — Vítkova 2+1 100 m² · 13,350,000 Kč · fl 3/5
- **134,931** — Sokolovská 2+1 72 m² · 9,715,000 Kč · fl 2/4

### prague
- **40,765** — Imrychova 1+kk 31 m² · 1,263,720 Kč · fl 9/10
- **54,198** —  1+kk 36 m² · 1,951,126 Kč · fl 3
- **58,032** — Pavla Beneše 4+kk 310 m² · 17,990,000 Kč · fl 3/6

### decin
- **28,121** — Přímá 2+1 58 m² · 1,631,000 Kč · fl 2/5
- **29,333** — Čsl. partyzánů 3+1 75 m² · 2,200,000 Kč · fl 3
- **32,468** — Čsl. partyzánů 3+1 77 m² · 2,500,000 Kč · fl 7/8

### usti
- **10,714** — Jindřicha Plachty 1+1 35 m² · 375,000 Kč · fl 2/8
- **12,500** — Jindřicha Plachty 4+1 100 m² · 1,250,000 Kč · fl 7/8
- **12,500** — Jindřicha Plachty 3+1 76 m² · 950,000 Kč · fl 3/8

## Layout

```
src/           fetch + build
data/          listings.json (committed) + raw/cache (gitignored)
docs/          GitHub Pages site + METHOD.md
site/          duplicate of docs/index.html
scripts/       run_all.sh, rebuild.sh, curl list helper
```

See `docs/METHOD.md` for floor/ownership rules.

Commits to GitHub go through the **GitHub connector** (parent agent), not a local PAT push.
