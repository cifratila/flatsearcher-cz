#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COOKIE="$ROOT/data/cookies-sreality.txt"
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36'
RAW="$ROOT/data/raw/sreality-pages"
REGION="${1:-prague}"
mkdir -p "$RAW/$REGION"

case "$REGION" in
  prague) BASE='https://www.sreality.cz/hledani/prodej/byty/praha?velikost=1%2Bkk,1%2B1,2%2Bkk,2%2B1,3%2Bkk,3%2B1,4%2Bkk,4%2B1&vlastnictvi=osobni' ;;
  karlin) BASE='https://www.sreality.cz/hledani/prodej/byty?velikost=1%2Bkk,1%2B1,2%2Bkk,2%2B1,3%2Bkk,3%2B1,4%2Bkk,4%2B1&vlastnictvi=osobni&region=mestska-cast-karlin-praha&municipality=mestska-cast-karlin-praha' ;;
  decin) BASE='https://www.sreality.cz/hledani/prodej/byty/decin?velikost=1%2Bkk,1%2B1,2%2Bkk,2%2B1,3%2Bkk,3%2B1,4%2Bkk,4%2B1&vlastnictvi=osobni' ;;
  usti) BASE='https://www.sreality.cz/hledani/prodej/byty/usti-nad-labem?velikost=1%2Bkk,1%2B1,2%2Bkk,2%2B1,3%2Bkk,3%2B1,4%2B1&vlastnictvi=osobni' ;;
  *) echo "unknown region"; exit 1 ;;
esac

# page 1 to learn total
curl -sS -m 45 -b "$COOKIE" -A "$UA" -o "$RAW/$REGION/p1.html" "$BASE"
TOTAL=$(python3 - << PY
import re,json
from pathlib import Path
h=Path("$RAW/$REGION/p1.html").read_text(errors="replace")
m=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', h)
d=json.loads(m.group(1))
est=next(q for q in d["props"]["pageProps"]["dehydratedState"]["queries"] if q["queryKey"][0]=="estatesSearch")
print(est["state"]["data"]["pagination"]["total"])
PY
)
PER=20
PAGES=$(( (TOTAL + PER - 1) / PER ))
echo "REGION=$REGION TOTAL=$TOTAL PAGES~$PAGES"
for p in $(seq 2 "$PAGES"); do
  out="$RAW/$REGION/p${p}.html"
  if [[ -s "$out" ]]; then
    # skip if already has nextdata
    if grep -q '__NEXT_DATA__' "$out"; then continue; fi
  fi
  url="${BASE}&strana=${p}"
  code=$(curl -sS -m 45 -b "$COOKIE" -A "$UA" -o "$out" -w '%{http_code}' "$url" || true)
  echo "page $p/$PAGES code=$code size=$(wc -c < "$out")"
  if [[ "$code" != "200" ]]; then
    sleep 2
    curl -sS -m 60 -b "$COOKIE" -A "$UA" -o "$out" "$url" || true
  fi
  sleep 0.25
done
echo DONE_PAGES "$REGION"
