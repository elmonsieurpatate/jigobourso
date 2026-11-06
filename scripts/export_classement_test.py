"""Export the isolated interface as a single offline HTML file (no backend)."""
import argparse
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=Path)
parser.add_argument('--page', choices=['classement-test.html','admin-categories-test.html'], default='classement-test.html')
args = parser.parse_args()
public = Path(__file__).resolve().parents[1] / 'app' / 'public'
html = (public / args.page).read_text()
html = re.sub(r'<link rel="stylesheet" href="assets/([^?]+)\?[^\"]+">',
              lambda m: '<style>' + (public / 'assets' / m[1]).read_text() + '</style>', html)
definitions = json.loads((public.parent / 'config' / 'explorer_secondary_filters.json').read_text())
metadata = json.loads((public.parent / 'config' / 'secondary_metadata_groups.json').read_text())
defaults = {'schema': 1, 'revision': 1, 'filters': {}}
for f in definitions['filters']:
    defaults['filters'][f['id']] = {m['id']: {'mode': 'all', 'selected': []} for m in f['measures']}
    if not f['editable']:
        f['values'] = [dict(v, value=None if v['id'] == 'unknown' else v['id'], count=0) for v in metadata['groups'][f['id']]]
        defaults['filters'][f['id']]['values'] = {'mode': 'all', 'selected': []}
category_payload = {'schema': 2, 'definitions': {'schema': 1, 'revision': 1, 'filters': definitions['filters']},
                    'defaults': defaults, 'metadata_mapping': metadata, 'source': 'offline',
                    'source_label': 'Propositions de catégories · aperçu hors ligne, sans catalogue réel'}
category_script = 'window.ClassementTestCategoryConfig = ' + json.dumps(category_payload, ensure_ascii=False).replace('<', chr(92) + 'u003c') + ';' + chr(10)
shim = '''
// Aperçu hors ligne : aucune donnée réelle et aucun appel réseau.
window.JigoSecondaryOffline = true;
J.api = async route => { if (route === 'portfolios') return {portfolios:[]}; throw new Error('Aperçu hors ligne'); };
J.init = async page => {
  const user = {username:'Aperçu local',is_admin:false,prefs:{}};
  J.user=user; J.applyTheme(localStorage.getItem('jigo_theme') || 'light'); J.buildShell(page,user); return user;
};
'''


def inline_script(match):
    source = (public / 'assets' / match[1]).read_text()
    if match[1] == 'app.js':
        # The hosted password helper relies on currentScript.src, absent inline.
        source = '\n'.join(line for line in source.splitlines() if 'document.currentScript.src' not in line)
        offline_shim = shim
        if args.page == 'admin-categories-test.html':
            offline_shim = offline_shim.replace("is_admin:false", "is_admin:true")
        offline_shim += '\nconst currentPreviewId = ' + json.dumps('admin-categories-test' if args.page == 'admin-categories-test.html' else 'classement-test') + ';\n'
        # Give each exported page an active, usable dedicated menu entry.
        offline_shim += '''
const offlineNav=J.NAV;
J.NAV = admin => offlineNav(admin).map(item => {
  const files={'classement-test':'classement-test-donnees-fictives.html','admin-categories-test':'administration-filtres-categories.html'};
  files[currentPreviewId] = location.pathname.split('/').pop();
  if (!files[item.id]) return item;
  return {...item,href:files[item.id],file:[...item.file,files[item.id]]};
});
'''
        source += '\n' + (category_script if args.page == 'classement-test.html' else '') + offline_shim
    return '<script>' + source.replace('</script', '<\\/script') + '</script>'


html = re.sub(r'<script src="assets/([^?]+)\?[^\"]+"></script>', inline_script, html)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(html)
print(args.output)
