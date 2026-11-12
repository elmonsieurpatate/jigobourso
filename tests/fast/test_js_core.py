"""Noyau JS commun (core.js) : le test Node du noyau passe, et aucun script de page ne recrée de copie locale
des sélecteurs, de l'échappement HTML, des formats de nombres ou de l'accès à localStorage."""
import glob
import os
import re
import shutil
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASSETS = os.path.join(ROOT, 'app', 'public', 'assets')
PAGES = os.path.join(ROOT, 'app', 'public')
# Modules volontairement autonomes : testés sous Node sans navigateur, ou exécutés avant le chargement du noyau.
STANDALONE = {'core.js', 'theme-init.js', 'pf-math.js', 'admin-categories-model.js', 'explorer-filters.js'}


def scripts():
    for path in sorted(glob.glob(os.path.join(ASSETS, '*.js'))):
        name = os.path.basename(path)
        if name in STANDALONE or name.startswith('help-ch-'):
            continue
        yield name, open(path, encoding='utf-8').read()


@pytest.mark.skipif(shutil.which('node') is None, reason='Node absent')
def test_core_unit_tests_pass():
    res = subprocess.run(['node', os.path.join(ROOT, 'tests', 'e2e', 'core.cjs')], capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stdout + res.stderr
    assert 'core.js : OK' in res.stdout


def test_core_is_loaded_before_app_on_every_page():
    for page in glob.glob(os.path.join(PAGES, '*.html')):
        html = open(page, encoding='utf-8').read()
        assert html.index('assets/core.js') < html.index('assets/app.js'), os.path.basename(page)


def test_no_local_copy_of_core_helpers():
    bad = []
    for name, js in scripts():
        for pat, why in [
            (r'(?:const|let|var)\s+\$\$?\s*=\s*\(?\s*\w+[^=]*=>\s*(?:\(\s*\w+\s*\|\|\s*)?(?:document|\w+)\.querySelector', 'copie locale de $'),
            (r'(?:const|let|var)\s+(?:esc|E)\s*=\s*\w+\s*=>\s*String', 'copie locale de esc'),
            (r'replace\(/\[&<>', "échappement HTML refait à la main"),
            (r'new Intl\.NumberFormat', 'formatage de nombre hors J.num/J.pct/J.eur'),
            (r'\blocalStorage\b', 'accès direct à localStorage (utiliser J.store)'),
        ]:
            for m in re.finditer(pat, js):
                line = js.count('\n', 0, m.start()) + 1
                if re.search(r'//.*localStorage|/\*.*localStorage', js.splitlines()[line - 1]):
                    continue                      # simple mention dans un commentaire
                bad.append(f'{name}:{line} {why}')
    assert not bad, '\n'.join(bad)
