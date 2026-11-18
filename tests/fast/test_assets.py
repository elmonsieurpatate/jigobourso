"""Assets chargés : chaque fichier référencé existe, chaque fichier d'assets a au moins un consommateur (page HTML ou autre asset)."""

import glob
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PUB = os.path.join(ROOT, 'app', 'public')
ASSETS = set(os.listdir(os.path.join(PUB, 'assets')))


def page_assets():
    out = {}
    for page in glob.glob(os.path.join(PUB, '*.html')):
        text = open(page, encoding='utf-8').read()
        out[os.path.basename(page)] = re.findall(r'(?:src|href)="assets/([^"?]+)', text)
    return out


def test_every_referenced_asset_exists():
    missing = [(p, a) for p, files in page_assets().items() for a in files if a not in ASSETS]
    assert missing == []


def test_every_asset_has_a_consumer():
    used = {a for files in page_assets().values() for a in files}
    texts = {a: open(os.path.join(PUB, 'assets', a), encoding='utf-8', errors='ignore').read() for a in ASSETS if a.endswith(('.js', '.css'))}
    orphans = [a for a in sorted(ASSETS - used) if not any(b != a and (a in t or a.rsplit('.', 1)[0] in t) for b, t in texts.items())]
    assert orphans == []


def test_no_page_loads_the_same_asset_twice():
    assert {p: [a for a in files if files.count(a) > 1] for p, files in page_assets().items() if len(files) != len(set(files))} == {}


def test_page_weight_ceiling():
    """Poids cumulé des scripts et feuilles de style par page : plafond de non-régression (octets non compressés), pas un objectif d'optimisation."""
    heaviest = max(sum(os.path.getsize(os.path.join(PUB, 'assets', a)) for a in files if a in ASSETS) for files in page_assets().values())
    assert heaviest <= 480_000, heaviest  # 450 000 → 480 000 : la page Portefeuilles porte désormais le module des portefeuilles à liquidités (pf-perf2.js)
