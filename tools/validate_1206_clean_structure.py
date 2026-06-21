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
print("\\n".join(missing) if missing else "none")
print("\\nBAD PATHS:")
print("\\n".join(bad_existing) if bad_existing else "none")
print("\\nPY ERRORS:")
print("\\n".join(py_errors) if py_errors else "none")

if missing or bad_existing or py_errors:
    sys.exit(1)
