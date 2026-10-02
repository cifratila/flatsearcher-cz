# Method

## Floor convention

On Sreality and Bezrealitky, numeric `floorNumber` / `etage` **1** means **1. nadzemní podlaží = přízemí**.
Catalog keeps floors **≥ 2**. Unit-located suterén / sklepní / atypical underground atelier copy is excluded via regex on description.

**Mezonet / internal stairs are kept.** Detected from description / `flatClass` (`mezonet`, `vnitřní schodiště`, `schody v bytě`, duplex / víceúrovňové) → `has_internal_stairs`.

## Ownership

Search uses `vlastnictvi=osobni` (Sreality) where possible. Final keep requires detail/list `ownership` containing osobní. Družstevní and unclear are excluded and tallied.

## Sources

1. **Sreality** (primary): HTML search SSR `__NEXT_DATA__` → `estatesSearch`; details → `estate.params` for floor/ownership.
2. **Bezrealitky**: GraphQL `listAdverts` with `regionOsmIds` (Karlín `R435856`, Praha `R435514`, Děčín `R439579`, Ústí `R440166`). Fields: `etage`, `ownership`, `description`.
3. **Reality.iDNES**: secondary link harvest; only rows with price+m² enter catalog.

## Deduping

Across portals: ASCII-folded `street` + `m2` + `price_czk`. Twin URLs noted in `notes`.

## Region assignment

Karlín carved out first (cityPart/url/address contains karlín). Praha = remaining Prague. Děčín / Ústí filtered to city name (okres spill dropped).
