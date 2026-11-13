"""Politique de sécurité du front : aucun script en ligne (donc CSP sans 'unsafe-inline' pour les scripts), en-têtes présents."""
import glob
import os
import re

PUBLIC = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'app', 'public')


def test_no_inline_script_or_handler_in_pages():
    for page in glob.glob(os.path.join(PUBLIC, '*.html')):
        html = open(page, encoding='utf-8').read()
        assert not re.search(r'<script(?![^>]*\ssrc=)[^>]*>', html), os.path.basename(page) + ' : script en ligne'
        assert not re.search(r'\son(click|load|error|submit|change|input)\s*=', html, re.I), os.path.basename(page) + ' : gestionnaire en ligne'
        assert 'javascript:' not in html.lower()


def test_csp_and_transport_headers():
    conf = open(os.path.join(PUBLIC, '.htaccess'), encoding='utf-8').read()
    csp = re.search(r'Content-Security-Policy "([^"]+)"', conf).group(1)
    script_src = re.search(r"script-src ([^;]+)", csp).group(1)
    assert script_src.strip() == "'self'"
    for directive in ("object-src 'none'", "base-uri 'self'", "form-action 'self'", "frame-ancestors 'none'"):
        assert directive in csp
    assert 'Strict-Transport-Security' in conf and 'unset X-Powered-By' in conf


def test_dynamic_html_escapes_catalogue_codes():
    # Les codes de place (mic) viennent d'un catalogue tiers : ils passent par J.esc dans les modèles HTML.
    for name in ('admin.js', 'explorer.js'):
        js = open(os.path.join(PUBLIC, 'assets', name), encoding='utf-8').read()
        assert not re.search(r'\$\{(p\.mic|m)\}', js), name


def test_csp_has_no_unsafe_inline_at_all():
    csp = re.search(r'Content-Security-Policy "([^"]+)"', open(os.path.join(PUBLIC, '.htaccess'), encoding='utf-8').read()).group(1)
    assert re.search(r"style-src 'self'(;|$)", csp), "style-src doit être 'self' seul (pas de <style> ni de feuille injectée)"
    assert 'unsafe-inline' not in csp and 'style-src-attr' not in csp


def test_no_style_element_and_no_inline_handler_in_scripts():
    for name in sorted(os.listdir(os.path.join(PUBLIC, 'assets'))):
        if not name.endswith('.js'):
            continue
        js = open(os.path.join(PUBLIC, 'assets', name), encoding='utf-8').read()
        assert not re.search(r"createElement\(['\"]style['\"]\)|<style[\s>]", js), name + ' : élément <style> généré'
        assert not re.search(r"""\son(click|change|input|submit|load|error|keydown)=["'\\]""", js), name + ' : gestionnaire en ligne dans un gabarit HTML'


def test_no_inline_style_attribute_in_scripts_or_pages():
    # Les styles de données passent par data-style (appliqué en CSSOM par core.js) : un attribut style= serait bloqué par la CSP.
    files = [os.path.join(PUBLIC, 'assets', n) for n in os.listdir(os.path.join(PUBLIC, 'assets')) if n.endswith('.js')]
    files += [os.path.join(PUBLIC, n) for n in os.listdir(PUBLIC) if n.endswith('.html')]
    for f in sorted(files):
        assert not re.search(r'(?<![-\w])style\s*=\s*["\'\\]', open(f, encoding='utf-8').read()), os.path.basename(f) + ' : attribut style= (utiliser data-style)'


# Interpolations nues d'un champ de texte libre : chacune a été relue, la sortie est du texte (J.confirm échappe, messages via textContent).
REVIEWED_FREE_TEXT = {
    ('admin-categories-model.js', '${other.name}'), ('filtres.js', '${category.name}'), ('filtres.js', '${filter().name}'), ('splits.js', '${row.symbol}'),
}


def test_free_text_fields_are_escaped_in_templates():
    pattern = re.compile(r'\$\{([A-Za-z_][\w.?\[\]()]*\.(?:name|username|email|symbol|isin|message|description))\}')
    found = set()
    for name in sorted(os.listdir(os.path.join(PUBLIC, 'assets'))):
        if not name.endswith('.js') or name.startswith(('help-ch-', 'filtres-catalogue')):
            continue
        for m in pattern.finditer(open(os.path.join(PUBLIC, 'assets', name), encoding='utf-8').read()):
            found.add((name, '${' + m.group(1) + '}'))
    unknown = found - REVIEWED_FREE_TEXT
    assert not unknown, f'texte libre non échappé dans un gabarit (passer par J.esc) : {sorted(unknown)}'
