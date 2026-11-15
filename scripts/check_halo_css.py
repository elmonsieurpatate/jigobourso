#!/usr/bin/env python3
"""Validate CSS ownership from parsed rules, including nested functional selectors."""

from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import tinycss2
from style_tools import CONTROL_GEOMETRY, declarations, rules, selectors, targets_shared, utility, visual, walk

ROOT = Path(__file__).resolve().parents[1]


class Stylesheets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'link' and values.get('rel') == 'stylesheet':
            self.links.append(values.get('href', '').split('?')[0])


def layout_errors(source, name):
    errors = []

    def forbidden_at_rules(nodes):
        for node in nodes:
            if node.type != 'at-rule':
                continue
            keyword = node.lower_at_keyword
            if keyword in ('import', 'font-face', 'property'):
                errors.append(f'{name}: @{keyword} réservé aux sources de thème et composants')
            elif node.content is not None:
                children = tinycss2.parse_rule_list(node.content, skip_whitespace=True, skip_comments=True)
                if keyword.endswith('keyframes'):
                    for frame in children:
                        if frame.type == 'qualified-rule':
                            for decl in declarations(frame):
                                if decl.type == 'declaration' and visual(decl.lower_name):
                                    errors.append(f'{name}: apparence animée « {decl.lower_name} » hors de sa source de composant')
                else:
                    forbidden_at_rules(children)

    parsed = rules(source)
    forbidden_at_rules(parsed)
    for node in walk(parsed):
        if utility(node.prelude):
            continue
        label = tinycss2.serialize(node.prelude).strip()
        common = any(targets_shared(s.parsed_tree) for s in selectors(node.prelude))
        for decl in declarations(node):
            if decl.type == 'error':
                errors.append(f'{name}: déclaration invalide : {decl.message}')
            elif decl.type == 'declaration' and (visual(decl.lower_name) or common and decl.lower_name in CONTROL_GEOMETRY):
                errors.append(f'{name}: apparence « {decl.lower_name} » hors de sa source de composant : {label}')
    return errors


def check(root=ROOT):
    public = root / 'app/public'
    assets = public / 'assets'
    sources = root / 'app/styles'
    manifest = json.loads((sources / 'manifest.json').read_text())
    errors = []
    referenced = set()
    for name, entries in manifest['outputs'].items():
        if not (assets / name).is_file():
            errors.append(f'Sortie absente : {name}')
        for entry in entries:
            source = sources / entry['source']
            if not source.resolve().is_relative_to(sources.resolve()):
                errors.append(f'Source hors du dossier de styles : {source}')
                continue
            referenced.add(source)
            if not source.is_file():
                errors.append(f'Source absente : {source}')
                continue
            if name != 'halo.css':
                errors.extend(layout_errors(source.read_text(), entry['source']))
    for source in sources.rglob('*.css'):
        if source not in referenced:
            errors.append(f'Source sans propriétaire dans le manifeste : {source.relative_to(sources)}')
    for css in assets.glob('*.css'):
        if css.name == 'halo.css':
            continue
        errors.extend(layout_errors(css.read_text(), css.name))
        if re.search(r'#[0-9a-fA-F]{3,8}\b|\brgba?\(', css.read_text()):
            errors.append(f'{css.name}: couleur littérale hors du thème')
    pages = sorted(public.glob('*.html'))
    for page in pages:
        parser = Stylesheets()
        parser.feed(page.read_text())
        if not parser.links or parser.links[-1] != 'assets/halo.css':
            errors.append(f'{page.name}: halo.css doit être la dernière feuille')
        for link in parser.links:
            if not (public / link).is_file():
                errors.append(f'{page.name}: feuille absente : {link}')
    # Une déclaration de token commun n'a qu'une source ; les variantes de thème
    # sont explicites dans tokens.css. Les composants ne redéfinissent pas la palette.
    for source in sources.rglob('*.css'):
        if source == sources / 'theme/tokens.css':
            continue
        if re.search(r'(?<![\w-])--(?:bg|surface|text|muted|accent|font|radius|shadow)\s*:', source.read_text()):
            errors.append(f'{source.relative_to(sources)}: token commun redéfini hors du thème')
    if (assets / 'tokens.css').exists():
        errors.append('Ancienne source publique tokens.css encore présente')
    return errors, len(pages)


def main():
    try:
        errors, count = check()
    except (ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if errors:
        print('\n'.join(errors), file=sys.stderr)
        return 1
    print(f'Halo CSS: {count} pages, sources explicites, aucune apparence dans les mises en page')
    return 0


if __name__ == '__main__':
    sys.exit(main())
