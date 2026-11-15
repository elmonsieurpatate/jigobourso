"""Échelle commune des feuilles CSS : aucune valeur d'espacement, de texte, d'interlignage, de rayon ni de point de rupture hors échelle ne peut revenir."""

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('css_scale', ROOT / 'scripts' / 'css_scale.py')
S = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S)
ASSETS = ROOT / 'app' / 'styles'


def test_no_stylesheet_value_is_off_scale():
    bad = []
    for f in sorted(ASSETS.rglob('*.css')):
        bad += S.violations(f.read_text(encoding='utf-8'), f.name)
    assert not bad, 'valeurs hors échelle (python scripts/css_scale.py apply les convertit) :\n' + '\n'.join(bad[:30])


def test_every_scale_token_is_defined_once_in_halo():
    halo = (ASSETS / 'theme/tokens.css').read_text(encoding='utf-8')
    for v in S.SPACING:
        assert halo.count(f'--sp-{v}: {v}px;') == 1, v
    for v in S.FONT:
        assert halo.count(f'--fs-{v}: {v}px;') == 1, v
    for v in S.RADIUS:
        assert halo.count(f'--radius-{v}: {v}px;') == 1, v
    for name in ('none', 'tight', 'snug', 'normal', 'loose'):
        assert halo.count(f'--lh-{name}:') == 1, name
    for name in S.Z_LAYERS.values():
        assert halo.count(f'{name}:') == 1, name


def test_every_token_used_in_a_stylesheet_is_defined():
    import re

    halo = (ASSETS / 'theme/tokens.css').read_text(encoding='utf-8')
    used = set()
    for f in ASSETS.rglob('*.css'):
        used |= set(re.findall(r'var\((--(?:sp|fs|lh|radius|z)-[\w-]+)\)', f.read_text(encoding='utf-8')))
    missing = sorted(t for t in used if f'{t}:' not in halo)
    assert not missing, missing


def test_js_breakpoints_match_the_css_scale():
    import re

    for f in (ROOT / 'app/public/assets').glob('*.js'):
        for n in re.findall(r'max-width:\s*(\d+)px', f.read_text(encoding='utf-8')):
            assert int(n) in S.BREAKPOINTS, (f.name, n)


def test_page_blocks_are_spaced_by_the_container_only():
    halo = (ASSETS / 'components/rhythm.css').read_text(encoding='utf-8')
    assert 'gap: var(--sp-16);' in halo and 'margin-block: 0;' in halo
