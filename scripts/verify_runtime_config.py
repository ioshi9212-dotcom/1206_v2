from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "gpt/system_prompt_1206_v2.md",
    "gpt/turn_runtime_contract_1206_v2.md",
    "docs/gpt_actions_schema.json",
    "calendar/east_sector_1206_calendar.yaml",
    "characters/akira/akira_main_profile.yaml",
    "characters/raiden/raiden_main_profile.yaml",
    "characters/ray/ray_main_profile.yaml",
    "characters/jun/jun_main_profile.yaml",
    "characters/emma/emma_main_profile.yaml",
    "characters/irey/irey_main_profile.yaml",
    "canon/relationships/akira_raiden_hidden_bond.yaml",
    "canon/hidden/reincarnation_cycle_hidden_lore.yaml",
]

missing = [p for p in REQUIRED if not (ROOT / p).exists()]
print("ROOT", ROOT)
print("PUBLIC_BASE_URL", os.getenv("PUBLIC_BASE_URL"))
print("DATA_DIR", os.getenv("DATA_DIR"))
if missing:
    print("MISSING:")
    for p in missing:
        print("-", p)
    sys.exit(1)
print("OK: runtime files present")
