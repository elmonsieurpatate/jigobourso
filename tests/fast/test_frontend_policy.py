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
