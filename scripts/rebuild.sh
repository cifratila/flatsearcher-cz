#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
python3 -m src.build_catalog
python3 -m src.build_html
echo rebuilt data/listings.json site/index.html docs/index.html
