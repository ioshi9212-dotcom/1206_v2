"""Ensure East Sector lore/location files stay available in current 1206 context."""
from __future__ import annotations

try:
    import app.lean_context_loading_runtime_patch as lean
except Exception:  # pragma: no cover
    lean = None  # type: ignore[assignment]

EAST_SECTOR_CONTEXT_FILES = [
    "canon_lore/core/world_background.yaml",
    "canon_lore/world/energy_system.yaml",
    "canon_lore/east_sector/east_sector_base.yaml",
    "locations/east_sector_locations.yaml",
]

if lean is not None:
    for path in EAST_SECTOR_CONTEXT_FILES:
        try:
            if path not in lean.ALWAYS_SMALL_FILES:
                lean.ALWAYS_SMALL_FILES.append(path)
        except Exception:
            pass
