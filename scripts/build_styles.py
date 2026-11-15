"""Build the existing public CSS URLs from owned sources, without a JS bundler.

Usage: python scripts/build_styles.py [--check]. Readable source CSS is formatted with Prettier; generated CSS only loses
whitespace through the pinned CSS compiler (no syntax or identifier rewriting). The check never rewrites the checkout.
"""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tinycss2
from style_tools import rules, scope

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/styles'
PUBLIC = ROOT / 'app/public/assets'


def outputs():
    manifest = json.loads((SOURCE / 'manifest.json').read_text())
    result = {}
    header = '/* GENERATED — edit app/styles sources, then run make css-build. */\n'
    for name, sources in manifest['outputs'].items():
        parts = []
        for entry in sources:
            file = SOURCE / entry['source']
            text = file.read_text()
            if entry.get('when_stylesheet'):
                text = tinycss2.serialize(scope(rules(text), entry['when_stylesheet']))
            parts.append(f'/* Source: {entry["source"]} */\n{text}\n')
        result[name] = header + '\n'.join(parts)
    return result


def build(check=False):
    result = outputs()
    with tempfile.TemporaryDirectory(prefix='jigo-styles-') as temp:
        directory = Path(temp)
        for name, text in result.items():
            (directory / name).write_text(text)
        compiler = ROOT / 'node_modules/.bin/esbuild'
        if not compiler.exists():
            raise RuntimeError('Compilateur CSS absent : exécuter npm ci --ignore-scripts')
        compiled = directory / 'compiled'
        subprocess.run(
            [
                str(compiler),
                *map(str, directory.glob('*.css')),
                '--outdir=' + str(compiled),
                '--minify-whitespace',
                '--target=safari16.4',
                '--log-level=error',
                '--banner:css=/* GENERATED — edit app/styles sources, then make css-build. */',
            ],
            check=True,
            capture_output=True,
        )
        bad = []
        for name in result:
            generated = compiled / name
            if check:
                if not (PUBLIC / name).exists() or (PUBLIC / name).read_bytes() != generated.read_bytes():
                    bad.append(name)
            else:
                shutil.copyfile(generated, PUBLIC / name)
    if bad:
        print('CSS désynchronisés : ' + ', '.join(bad) + ' ; exécuter make css-build', file=sys.stderr)
        return 1
    print(f'CSS : {len(result)} sorties ' + ('conformes aux sources' if check else 'construites'))
    return 0


if __name__ == '__main__':
    sys.exit(build('--check' in sys.argv))
