"""Shared scope for FlatSearcher CZ catalogs."""
LAYOUTS = ["1+kk", "1+1", "2+kk", "2+1", "3+kk", "3+1", "4+kk", "4+1"]
BEZ_DISPOSITIONS = [
    "DISP_1_KK", "DISP_1_1", "DISP_2_KK", "DISP_2_1",
    "DISP_3_KK", "DISP_3_1", "DISP_4_KK", "DISP_4_1",
]
REGIONS = {
    "karlin": {"label": "Karlín", "sreality_region": "mestska-cast-karlin-praha", "bez_osm": "R435856"},
    "prague": {"label": "Praha", "sreality_region": "praha", "bez_osm": "R435514"},
    "decin": {"label": "Děčín", "sreality_region": "decin", "bez_osm": None},
    "usti": {"label": "Ústí nad Labem", "sreality_region": "usti-nad-labem", "bez_osm": None},
}
MIN_FLOOR = 2
OWNERSHIP_KEEP = {"osobní", "osobni"}
