"""Le garde-fou refuse des surcharges réelles, pas seulement des noms de fichiers."""

import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_halo_css import layout_errors, check  # noqa: E402
from build_styles import outputs  # noqa: E402


@pytest.mark.parametrize(
    'source',
    [
        '.btn { color: var(--danger); }',
        'body :is(.title-page .btn) { padding: var(--sp-40); }',
        ':where(.x .btn) { padding: var(--sp-40); }',
        '@media (max-width: 600px) { .btn { color: var(--danger); } }',
        '@supports (display: grid) { :is(.btn,.card) { border-color: var(--danger); } }',
        '.layout { box-shadow: var(--shadow); }',
        '@keyframes disguise { to { color: red; } }',
        '@media (width < 600px) { @keyframes disguise { to { background: red; } } }',
        '@import url(other.css);',
        '@starting-style { .btn { color: red; } }',
        '@-moz-document url-prefix() { .btn { color: red; } }',
        '@future-group { .btn { color: red; } }',
        '@font-face { font-family: other; src: url(other.woff); }',
    ],
)
def test_appearance_cannot_hide_in_layout_sources(source):
    assert layout_errors(source, 'layout/test.css')


def test_layout_and_explicit_utilities_remain_allowed():
    assert not layout_errors('.row { display:flex; gap:var(--sp-8); } .u-font-weight-700 { font-weight:700 !important; }', 'base.css')
    assert not layout_errors('.row:has(.btn) { padding: var(--sp-8); }', 'base.css')  # le conteneur est visé


def test_all_current_sources_follow_the_ownership_policy():
    errors, pages = check()
    assert pages == 20 and not errors, errors


def test_features_are_scoped_without_adding_specificity():
    built = outputs()['halo.css']
    assert ':where(html:has(link[href^="assets/explorer.css"]))' in built
    assert ':root:where(:has(link[href^="assets/explorer.css"]))[data-theme="dark"]' in built
    manifest = json.loads((ROOT / 'app/styles/manifest.json').read_text())
    assert all(entry.get('when_stylesheet') for entry in manifest['outputs']['halo.css'] if entry['source'].startswith('features/'))
