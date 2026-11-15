"""CSS syntax and ownership shared by the builder and its policy checks."""

import re
import tinycss2
from cssselect2.parser import parse, SelectorError

APPEARANCE = {
    'color',
    'background',
    'background-color',
    'background-image',
    'background-size',
    'background-position',
    'background-repeat',
    'background-clip',
    'background-origin',
    'box-shadow',
    'text-shadow',
    'font',
    'font-size',
    'font-family',
    'font-weight',
    'font-style',
    'font-variant',
    'font-variant-numeric',
    'line-height',
    'letter-spacing',
    'text-transform',
    'text-decoration',
    'text-decoration-line',
    'text-decoration-color',
    'text-decoration-thickness',
    'accent-color',
    'color-scheme',
    'scrollbar-color',
    'filter',
    'backdrop-filter',
    'caret-color',
    'fill',
    'stroke',
    'outline',
    'outline-color',
    'outline-style',
    'outline-width',
    'outline-offset',
}
CONTROL_GEOMETRY = {'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left', 'height', 'min-height'}
COMMON_CLASSES = {'btn', 'badge', 'card', 'tab', 'seg', 'chip', 'switch', 'q', 'notice', 'empty', 'spinner', 'metric', 'kpi'}
COMMON_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'button', 'input', 'select', 'textarea', 'th', 'td'}
GROUPS = {'media', 'supports', 'container', 'layer', 'scope'}


def rules(source):
    return tinycss2.parse_stylesheet(source, skip_whitespace=True, skip_comments=False)


def selectors(prelude):
    # Vendor pseudo-elements do not change the element targeted by the selector.
    source = tinycss2.serialize(prelude).strip()
    source = re.sub(r'::-(?:webkit|moz|ms)-[\w-]+', '::before', source)
    try:
        return list(parse(source))
    except SelectorError as exc:
        raise ValueError(f'Sélecteur CSS non analysable : {source}') from exc


def targets_shared(tree):
    if hasattr(tree, 'right'):
        return targets_shared(tree.right)
    for item in getattr(tree, 'simple_selectors', []):
        if getattr(item, 'class_name', None) in COMMON_CLASSES or getattr(item, 'local_name', None) in COMMON_TAGS:
            return True
        if type(item).__name__ in ('MatchesAnySelector', 'SpecificityAdjustmentSelector'):
            if any(targets_shared(s.parsed_tree) for s in item.selector_list):
                return True
    return False


def utility(prelude):
    return bool(re.fullmatch(r'\.(?:u-[\w-]+|is-off)', tinycss2.serialize(prelude).strip()))


def visual(name):
    return name in APPEARANCE or name.startswith(('--', 'border-', 'font-')) and name not in ('border-collapse', 'border-spacing') or name == 'border'


def declarations(node):
    return tinycss2.parse_declaration_list(node.content, skip_whitespace=True, skip_comments=True)


def walk(nodes):
    for node in nodes:
        if node.type == 'qualified-rule':
            yield node
        elif node.type == 'at-rule' and node.lower_at_keyword in GROUPS and node.content is not None:
            yield from walk(tinycss2.parse_rule_list(node.content, skip_whitespace=True, skip_comments=False))
        elif node.type == 'error':
            raise ValueError(node.message)


def scope(nodes, sheet):
    """Limit migrated feature appearances to pages that load that feature.

    :where has zero specificity; the selector's original priority is retained.
    The condition is the existing stylesheet link, including dynamic admin links.
    """
    for node in nodes:
        if node.type == 'at-rule' and node.lower_at_keyword in GROUPS and node.content is not None:
            children = tinycss2.parse_rule_list(node.content)
            scope(children, sheet)
            node.content = tinycss2.parse_component_value_list(tinycss2.serialize(children))
        elif node.type == 'qualified-rule':
            branches = []
            current = []
            for token in node.prelude + [tinycss2.ast.LiteralToken(0, 0, ',')]:
                if token.type == 'literal' and token.value == ',':
                    text = tinycss2.serialize(current).strip()
                    condition = f':has(link[href^="assets/{sheet}"])'
                    if text.startswith(':root'):
                        text = text.replace(':root', f':root:where({condition})', 1)
                    elif re.match(r'html(?:\b|[.[:#])', text):
                        text = text.replace('html', f'html:where({condition})', 1)
                    else:
                        text = f':where(html{condition}) {text}'
                    branches.append(text)
                    current = []
                else:
                    current.append(token)
            node.prelude = tinycss2.parse_component_value_list(',\n'.join(branches))
    return nodes
