from __future__ import annotations

from pathlib import Path

DAY_PATH = Path("calendar/days/1206-08-31.yaml")
PATCH_PATH = Path("calendar/days/1206-08-31.scene_patch.yaml")
MARKER = "scene_specific_npc_rules:"
INSERT_BEFORE = "active_characters:"


def main() -> None:
    if not DAY_PATH.exists():
        raise SystemExit(f"Not found: {DAY_PATH}")
    if not PATCH_PATH.exists():
        raise SystemExit(f"Not found: {PATCH_PATH}")

    text = DAY_PATH.read_text(encoding="utf-8")
    if MARKER in text:
        print("1206-08-31 calendar patch already present; nothing changed.")
        return

    patch_text = PATCH_PATH.read_text(encoding="utf-8")
    lines = []
    for line in patch_text.splitlines():
        if line.startswith("#"):
            continue
        lines.append(line)
    patch_clean = "\n".join(lines).strip() + "\n"

    if INSERT_BEFORE not in text:
        DAY_PATH.write_text(text.rstrip() + "\n\n" + patch_clean, encoding="utf-8")
        print(f"Inserted calendar patch at end of {DAY_PATH}")
        return

    index = text.index(INSERT_BEFORE)
    new_text = text[:index].rstrip() + "\n" + patch_clean + "\n" + text[index:]
    DAY_PATH.write_text(new_text, encoding="utf-8")
    print(f"Inserted calendar patch before {INSERT_BEFORE} in {DAY_PATH}")


if __name__ == "__main__":
    main()
