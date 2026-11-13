#!/usr/bin/env python3
"""Verify that Halo remains the sole source of shared visual tokens."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "app/public"
ASSETS = PUBLIC / "assets"
HALO = ASSETS / "halo.css"
SHARED = {
    "--bg", "--surface", "--surface-2", "--line", "--text", "--muted",
    "--accent", "--font", "--radius", "--radius-sm", "--shadow",
    "--h1-size", "--btn-size", "--control-h", "--cell-pad",
}

errors = []
if not HALO.is_file():
    errors.append("halo.css est absent")
if (ASSETS / "tokens.css").exists():
    errors.append("tokens.css redéfinit encore la palette Halo")

pages = sorted(PUBLIC.glob("*.html"))
for page in pages:
    links = re.findall(r'<link\s+rel="stylesheet"\s+href="assets/([^"?]+)', page.read_text())
    if not links or links[-1] != "halo.css":
        errors.append(f"{page.name}: halo.css doit être la dernière feuille")
    if "tokens.css" in links:
        errors.append(f"{page.name}: référence obsolète à tokens.css")
    for link in links:
        if not (ASSETS / link).is_file():
            errors.append(f"{page.name}: feuille absente: {link}")

for sheet in ASSETS.glob("*.css"):
    if sheet == HALO:
        continue
    source = sheet.read_text()
    duplicated = SHARED & set(re.findall(r"(--[\w-]+)\s*:", source))
    if duplicated:
        errors.append(f"{sheet.name}: jetons communs redéfinis: {', '.join(sorted(duplicated))}")
    if re.search(r"#[0-9a-fA-F]{3,8}\b|\brgb\(", source):
        errors.append(f"{sheet.name}: couleur littérale hors halo.css")

if errors:
    raise SystemExit("\n".join(errors))
print(f"Halo CSS: {len(pages)} pages, jetons communs uniques, ordre des feuilles correct")
