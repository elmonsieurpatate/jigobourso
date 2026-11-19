"""Socle de composants : tailles de contrôles, base commune des badges, variantes de tableaux et budget de `!important`.
Complète `scripts/check_halo_css.py` (frontières de responsabilité) et `test_css_scale.py` (échelle des valeurs)."""

import pathlib
import re

STYLES = pathlib.Path(__file__).resolve().parents[2] / 'app' / 'styles'


def css(name):
    return (STYLES / name).read_text(encoding='utf-8')


def test_control_heights_are_shared_tokens():
    tokens = css('theme/tokens.css')
    assert '--control-h: 35px;' in tokens and '--control-h-sm: 29px;' in tokens
    # chaque famille de contrôle prend sa hauteur dans ces jetons, jamais dans une valeur de page
    assert re.search(r'\.btn,[\s\S]*?\{[^}]*min-height: var\(--control-h\)', css('components/buttons.css'))
    assert re.search(r'\.btn\.sm,[\s\S]*?\.px-per button[\s\S]*?\{[^}]*min-height: var\(--control-h-sm\)', css('components/buttons.css'))
    assert 'min-height: var(--control-h-sm)' in css('components/segments.css')
    assert 'min-height: var(--control-h)' in css('components/tabs.css')
    assert 'min-height: var(--control-h)' in css('components/choices.css')
    assert 'height: var(--control-h)' in css('components/fields.css')


def test_business_badges_share_the_badge_base():
    badges = css('components/badges.css')
    base = re.search(r':is\(([^)]*)\) \{', badges).group(1)
    for name in ('.badge', '.as-pill', '.ps-tag', '.ac-badge', '.ct-demo-badge', '.ct-tag'):
        assert name in base, name


def test_table_variants_are_defined_in_the_shared_stylesheet():
    tables = css('components/tables.css')
    assert 'table.dense :is(th, td)' in tables
    assert '--cell-pad-dense' in css('theme/tokens.css')


def test_important_budget_does_not_grow():
    # 69 déclarations historiques (utilitaires et impression de layout/base.css) : aucune nouvelle sans décision explicite
    total = sum(f.read_text(encoding='utf-8').count('!important') for f in STYLES.rglob('*.css'))
    assert total <= 69, f'{total} `!important` : réduire plutôt qu\'ajouter'


REMOVED = (
    'px-sum',
    'px-head',
    'px-table-wrap',
    'ac-indicators',
    'ac-layout',
    'ac-search',
    'ac-sidebar',
    'ac-status',
    'ct-provisional',
    'eyebrow',
    'hb-example',
    'hb-jigo',
    'hb-tip',
    'hb-warn',
    'strat-cards',
    'strat-extra',
    'strat-grid',
)


def test_removed_classes_do_not_return():
    """Classes sans aucun usage dans le HTML, le JS ou le PHP : retirées du CSS ; leur retour sans balisage est une règle morte."""
    for f in STYLES.rglob('*.css'):
        source = f.read_text(encoding='utf-8')
        for name in REMOVED:
            assert not re.search(rf'\.{name}(?![\w-])', source), f'{f.name} : .{name}'
