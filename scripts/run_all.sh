#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
echo "== Bezrealitky =="
python3 -m src.fetch_bezrealitky --regions karlin,prague,decin,usti
echo "== Sreality lists =="
python3 -m src.fetch_sreality --regions karlin,decin,usti,prague
echo "== Sreality details =="
python3 -m src.fetch_sreality --regions karlin,decin,usti,prague --details --workers 8
echo "== iDNES (secondary, small) =="
python3 -m src.fetch_idnes --regions karlin,decin,usti --max-pages 2 || true
echo "== Build catalog + HTML =="
python3 -m src.build_catalog
python3 -m src.build_html
echo "DONE"
