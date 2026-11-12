"""Une seule version pour tous les fichiers CSS et JS des pages : le marqueur `__BUILD__`, remplacé au déploiement (ops/deploy.sh)."""
import pathlib
import re

PUBLIC = pathlib.Path(__file__).resolve().parents[2] / 'app/public'
REF = re.compile(r'''(?:src|href)=["'](assets/[^"'?#]+\.(?:js|css))(\?[^"']*)?["']''')


def refs():
    for page in sorted(PUBLIC.glob('*.html')):
        for m in REF.finditer(page.read_text(encoding='utf-8')):
            yield page.name, m.group(1), m.group(2)


def test_every_page_asset_carries_the_single_build_marker():
    bad = [(page, path, query) for page, path, query in refs() if query != '?v=__BUILD__']
    assert not bad, f'version autre que ?v=__BUILD__ : {bad[:5]}'


def test_every_referenced_asset_exists():
    missing = sorted({path for _, path, _ in refs() if not (PUBLIC / path).is_file()})
    assert not missing, missing


def test_no_page_ships_a_frozen_version():
    frozen = [p.name for p in PUBLIC.glob('*.html') if re.search(r'\?v=(?!__BUILD__)', p.read_text(encoding='utf-8'))]
    assert not frozen, frozen
