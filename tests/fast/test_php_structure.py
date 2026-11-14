"""Structure PHP : fonctions globales uniques, dépendances explicites (require_once) et couches respectées (F10)."""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
APP = os.path.join(ROOT, 'app')


def php_files():
    out = {}
    for d in ('lib', 'services', 'routes', 'public'):
        base = os.path.join(APP, d)
        for f in sorted(os.listdir(base)):
            if f.endswith('.php'):
                out[f'{d}/{f}'] = open(os.path.join(base, f), encoding='utf-8').read()
    return out


FILES = php_files()
DEFS = {}
for name, text in FILES.items():
    for fn in re.findall(r'^function\s+([A-Za-z_]\w*)\s*\(', text, flags=re.M):
        DEFS.setdefault(fn, []).append(name)


def requires(name):
    base = os.path.dirname(name)
    out = []
    for rel in re.findall(r"require(?:_once)?\s+__DIR__\s*\.\s*'/([^']+)'", FILES[name]):
        target = os.path.normpath(os.path.join(base, rel))
        if target in FILES:
            out.append(target)
    return out


def closure(name, seen=None):
    seen = seen if seen is not None else set()
    for r in requires(name):
        if r not in seen:
            seen.add(r)
            closure(r, seen)
    return seen


def test_global_functions_are_defined_once():
    dup = {fn: files for fn, files in DEFS.items() if len(files) > 1}
    assert not dup, dup


def test_every_called_application_function_is_required_explicitly():
    """Un fichier qui appelle une fonction d'un autre fichier doit le charger lui-même (directement ou par ses require_once),
    sans compter sur l'ordre de chargement d'un autre module."""
    missing = []
    for name, text in FILES.items():
        code = re.sub(r'//[^\n]*|/\*.*?\*/', '', text, flags=re.S)
        own = {fn for fn, files in DEFS.items() if name in files}
        deps = closure(name)
        for fn, files in DEFS.items():
            if fn in own or not re.search(r'(?<![\w>:$])' + fn + r'\s*\(', code):
                continue
            if not any(f in deps for f in files):
                missing.append((name, fn, files))
    assert not missing, missing


def test_services_do_not_depend_on_routes_or_the_http_request():
    for name, text in FILES.items():
        if not name.startswith('services/'):
            continue
        assert not any(r.startswith('routes/') for r in closure(name)), name
    # Cas d'usage des portefeuilles : jamais d'accès direct à la requête.
    code = re.sub(r'//[^\n]*', '', FILES['services/portfolios.php'])
    assert '$_GET' not in code and '$_POST' not in code and 'body()' not in code and 'header(' not in code
