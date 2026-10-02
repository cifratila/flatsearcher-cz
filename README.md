# FlatSearcher CZ

Czech BUY flat catalog for **Karlín**, **all Praha districts**, **Děčín**, and **Ústí nad Labem**.

## Scope
- Layouts: 1+kk through 4+1
- Ownership: osobní only
- Exclude: přízemí / suterén / atypical underground
- Flag (include): mezonet / internal stairs (`has_internal_stairs`)

## Layout
- `src/` — fetch + build scripts
- `data/` — generated JSON catalogs
- `site/` — multi-view HTML (`index.html`) for GitHub Pages

## Run
```bash
python3 -m src.build_catalog
python3 -m src.build_html
```

Commits go through the **GitHub connector**, not a local PAT.
