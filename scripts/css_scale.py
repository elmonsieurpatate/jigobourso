"""Échelle commune des feuilles CSS : définit les valeurs autorisées, convertit les anciennes valeurs vers la plus proche et vérifie qu'aucune valeur hors échelle ne revient.

Usage : python scripts/css_scale.py check            (liste les valeurs hors échelle ; code 1 s'il y en a)
        python scripts/css_scale.py apply [fichier]  (réécrit les feuilles en jetons de l'échelle)
Les égalités se résolvent vers la valeur supérieure (plus d'air, plus de lisibilité)."""

import pathlib
import re
import sys

ASSETS = pathlib.Path(__file__).resolve().parents[1] / 'app' / 'public' / 'assets'
ROOT_PX = 14  # html { font-size: 14px } dans halo.css : 1rem = 14px

SPACING = (2, 4, 6, 8, 10, 12, 14, 16, 20, 24, 32, 40, 48)  # px ; au-delà de 48, la valeur appartient à une mise en page précise
FONT = (10, 11, 12, 13, 14, 15, 16, 18, 20, 24, 28, 32)
LINE = (1, 1.25, 1.4, 1.5, 1.6)
RADIUS = (4, 8, 12, 16)
BORDER = (1, 2, 3, 4)
BREAKPOINTS = (380, 600, 760, 900, 1100, 1400)  # largeurs de fenêtre max ; les min-width valent la limite + 1
LETTER = (-0.06, -0.035, -0.02, 0, 0.04, 0.08, 0.12, 0.16)  # em
Z_LAYERS = {20: '--z-bar', 30: '--z-header', 50: '--z-pop', 55: '--z-backdrop', 60: '--z-drawer', 80: '--z-fly', 1000: '--z-top'}  # niveaux globaux ; 1 à 10 : empilement local d'un composant
OPACITY = (0.5, 0.7, 0.85)  # états atténués ; en dessous de 0.3 : voiles décoratifs conservés

SPACING_PROPS = r'(?:margin|padding)(?:-(?:top|right|bottom|left|inline|block)(?:-(?:start|end))?)?|gap|row-gap|column-gap'
TOKEN_NAMES = {'spacing': 'sp', 'font': 'fs'}
NUM = r'(-?\d*\.?\d+)(px|rem)?'


def snap(value, scale):
    """Valeur de l'échelle la plus proche ; à égale distance, la plus grande."""
    best = min(scale, key=lambda s: (abs(s - value), -s))
    return best


def px_of(num, unit):
    v = float(num)
    return v * ROOT_PX if unit == 'rem' else v


def fmt(v):
    return str(int(v)) if float(v).is_integer() else str(v)


def spacing_token(px):
    return f'var(--sp-{fmt(px)})'


def convert_spacing(val):
    """margin/padding/gap : chaque longueur en px/rem ≤ 48 devient le jeton le plus proche ; 0, auto, %, em, calc(), var() sont conservés."""
    if 'calc(' in val or 'clamp(' in val or 'min(' in val or 'max(' in val:
        return val

    def one(m):
        num, unit = m.group(1), m.group(2)
        v = px_of(num, unit)
        if v == 0 or abs(v) > 48 or unit is None or abs(v) < 2:  # 1px : recouvrement de bordures ou masquage (sr-only), jamais un espacement
            return m.group(0)
        if v < 0:
            return f'-{fmt(snap(-v, SPACING))}px'
        return spacing_token(snap(v, SPACING))

    return re.sub(r'(?<![\w.#-])' + NUM + r'(?![\w%.])', one, val)


def convert_font(val):
    m = re.fullmatch(r'\s*' + NUM + r'(\s*!important)?\s*', val)
    if not m or m.group(2) is None:
        return val
    px = snap(px_of(m.group(1), m.group(2)), FONT)
    return f'var(--fs-{fmt(px)})' + (m.group(3) or '')


def convert_font_shorthand(val):
    """font: [style] [weight] taille[/interligne] famille : seule la taille est ramenée à l'échelle."""
    return re.sub(r'(?<![\w.#/-])(\d*\.?\d+)px(?=\s|/)', lambda m: f'var(--fs-{fmt(snap(float(m.group(1)), FONT))})', val, count=1)


def convert_line(val):
    m = re.fullmatch(r'\s*(\d*\.?\d+)\s*', val)
    if not m or float(m.group(1)) == 0:
        return val
    return {1: 'var(--lh-none)', 1.25: 'var(--lh-tight)', 1.4: 'var(--lh-snug)', 1.5: 'var(--lh-normal)', 1.6: 'var(--lh-loose)'}[snap(float(m.group(1)), LINE)]


def convert_radius(val):
    if re.search(r'var\(|%|calc\(', val) and not re.search(r'\d+px', val):
        return val

    def one(m):
        v = float(m.group(1))
        if v == 0:
            return m.group(0)
        if v >= 99:
            return 'var(--radius-pill)'
        return f'var(--radius-{fmt(snap(v, RADIUS))})'

    return re.sub(r'(?<![\w.#-])(\d*\.?\d+)px', one, val)


def convert_border_width(val):
    return re.sub(r'(?<![\w.#-])(\d*\.?\d+)px', lambda m: fmt(snap(float(m.group(1)), BORDER)) + 'px' if float(m.group(1)) >= 1 else m.group(0), val, count=1)


def convert_letter(val):
    m = re.fullmatch(r'\s*(-?\d*\.?\d+)em\s*', val)
    if not m:
        return val
    v = snap(float(m.group(1)), LETTER)
    return '0' if v == 0 else f'{fmt(v)}em'


def convert_opacity(val):
    m = re.fullmatch(r'\s*(\d*\.?\d+)(\s*!important)?\s*', val)
    if not m or float(m.group(1)) < 0.3 or float(m.group(1)) >= 1:
        return val
    return fmt(snap(float(m.group(1)), OPACITY)) + (m.group(2) or '')


def convert_z(val):
    m = re.fullmatch(r'\s*(-?\d+)\s*', val)
    if not m or int(m.group(1)) <= 10:
        return val
    n = int(m.group(1))
    return f'var({Z_LAYERS[min(Z_LAYERS, key=lambda k: (abs(k - n), -k))]})'


def map_breakpoint(n):
    return snap(n, BREAKPOINTS)


def convert_media(text):
    def one(m):
        kind, n = m.group(1), int(m.group(2))
        if kind == 'min' and (n - 1 in BREAKPOINTS or n in BREAKPOINTS):  # déjà sur l'échelle (limite + 1 pour la paire d'un max-width)
            return f'min-width:{n}px'
        if kind == 'min' and n - 1 in (600, 700, 960):  # ancienne paire d'une limite max : n = limite + 1
            return f'min-width:{map_breakpoint(n - 1) + 1}px'
        return f'{kind}-width:{map_breakpoint(n)}px'

    return re.sub(r'(max|min)-width\s*:\s*(\d+)px', one, text)


RULES = (
    (re.compile(r'^(' + SPACING_PROPS + r')$'), convert_spacing),
    (re.compile(r'^font-size$'), convert_font),
    (re.compile(r'^line-height$'), convert_line),
    (re.compile(r'^font$'), convert_font_shorthand),
    (re.compile(r'^border-radius$|^border-(?:top|bottom)-(?:left|right)-radius$'), convert_radius),
    (re.compile(r'^letter-spacing$'), convert_letter),
    (re.compile(r'^opacity$'), convert_opacity),
    (re.compile(r'^z-index$'), convert_z),
    (re.compile(r'^border(?:-(?:top|right|bottom|left))?(?:-width)?$'), convert_border_width),
    (re.compile(r'^--[\w-]*-pad(?:-sm)?$'), convert_spacing),
)
DECL = re.compile(r'(?m)^(\s*)([\w-]+)(\s*:\s*)([^;{}]+?)(\s*;)')


def convert(text):
    def decl(m):
        indent, prop, colon, val, end = m.groups()
        for rx, fn in RULES:
            if rx.match(prop):
                return indent + prop + colon + fn(val) + end
        return m.group(0)

    text = DECL.sub(decl, text)
    return re.sub(r'@media[^{]*\{', lambda m: convert_media(m.group(0)), text)


def violations(text, name=''):
    """Valeurs qui ne sont ni un jeton ni une valeur de l'échelle."""
    out = []
    for m in DECL.finditer(text):
        _, prop, _, val, _ = m.groups()
        line = text.count('\n', 0, m.start()) + 1
        for rx, fn in RULES:
            if rx.match(prop):
                new = fn(val)
                if new != val and 'var(--' not in val:
                    out.append(f'{name}:{line}: {prop}: {val.strip()}  (échelle : {new.strip()})')
                elif new != val:
                    out.append(f'{name}:{line}: {prop}: {val.strip()}  (échelle : {new.strip()})')
    for m in re.finditer(r'@media[^{]*\{', text):
        if re.findall(r'\d+', convert_media(m.group(0))) != re.findall(r'\d+', m.group(0)):
            out.append(f'{name}:{text.count(chr(10), 0, m.start()) + 1}: {m.group(0).strip()}  (point de rupture hors échelle)')
    return out


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    files = [ASSETS / sys.argv[2]] if len(sys.argv) > 2 else sorted(ASSETS.glob('*.css'))
    bad = 0
    for f in files:
        text = f.read_text(encoding='utf-8')
        if cmd == 'apply':
            f.write_text(convert(text), encoding='utf-8')
        else:
            v = violations(text, f.name)
            bad += len(v)
            print('\n'.join(v))
    if cmd == 'check':
        print(f'{bad} valeur(s) hors échelle')
        sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
