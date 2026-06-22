from pathlib import Path
import py_compile
import sys

ROOT = Path(__file__).resolve().parents[1]
CHARACTERS = ["akira", "jun", "ray", "raiden", "irey", "emma", "yuna"]

missing = []
for cid in CHARACTERS:
    for fname in ["main.yaml", "character.yaml", "past.yaml"]:
        p = ROOT / "characters" / cid / fname
        if not p.exists():
            missing.append(str(p.relative_to(ROOT)))

bad_paths = [
    ROOT / "characters" / "main",
    ROOT / "knowledge" / "characters",
    ROOT / "data" / "scenes",
]
bad_existing = [str(p.relative_to(ROOT)) for p in bad_paths if p.exists()]

py_files = [
    ROOT / "app" / "character_registry_runtime_patch.py",
    ROOT / "app" / "production_runtime_patch.py",
]
py_errors = []
for p in py_files:
    if p.exists():
        try:
            py_compile.compile(str(p), doraise=True)
        except Exception as exc:
            py_errors.append(f"{p.relative_to(ROOT)}: {exc}")

print("MISSING:")
print("\n".join(missing) if missing else "none")
print("\nBAD PATHS:")
print("\n".join(bad_existing) if bad_existing else "none")
print("\nPY ERRORS:")
print("\n".join(py_errors) if py_errors else "none")

if missing or bad_existing or py_errors:
    sys.exit(1)

# v5 additional expected files
extra_expected = [
    ROOT / "state" / "initial_relationships_1206.json",
    ROOT / "state" / "akira_status_metrics.json",
]
extra_missing = [str(p.relative_to(ROOT)) for p in extra_expected if not p.exists()]
if extra_missing:
    print("\nEXTRA MISSING:")
    print("\n".join(extra_missing))
    sys.exit(1)

# v8 additional expected file
v8_expected = ROOT / "state" / "raiden_akira_dynamic_rules.json"
if not v8_expected.exists():
    print("\nV8 MISSING:")
    print(v8_expected.relative_to(ROOT))
    sys.exit(1)

# v9 expected files
for rel in [
    "app/lean_context_loading_runtime_patch.py",
    "state/context_loading_rules_1206.json",
    "state/east_sector_1206_context.json",
    "characters/miki/main.yaml",
    "characters/miki/character.yaml",
    "characters/miki/past.yaml",
    "characters/yuna/main.yaml",
    "characters/yuna/character.yaml",
    "characters/yuna/past.yaml",
]:
    p = ROOT / rel
    if not p.exists():
        print("\nV9 MISSING:")
        print(rel)
        sys.exit(1)

# v11 expected time-flow file
v11_expected = ROOT / "state" / "time_flow_rules_1206.json"
if not v11_expected.exists():
    print("\nV11 MISSING:")
    print(v11_expected.relative_to(ROOT))
    sys.exit(1)

# v12 expected director/input/style files
for rel in [
    "state/player_input_parsing_rules.json",
    "state/narrative_director_rules.json",
]:
    p = ROOT / rel
    if not p.exists():
        print("\nV12 MISSING:")
        print(rel)
        sys.exit(1)
