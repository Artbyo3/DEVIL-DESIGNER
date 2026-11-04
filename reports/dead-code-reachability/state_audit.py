import ast
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'devil_designer'


def modules():
    for path in sorted(PACKAGE.glob('*.py')):
        yield path.stem, ast.parse(path.read_text(encoding='utf-8-sig'))


def attribute_usage():
    stores, loads = defaultdict(list), defaultdict(list)
    for name, tree in modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                bucket = stores if isinstance(node.ctx, ast.Store) else loads
                bucket[node.attr].append(f'{name}:{node.lineno}')
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {'getattr', 'setattr', 'hasattr'}:
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[1].value, str):
                    bucket = stores if node.func.id == 'setattr' else loads
                    bucket[node.args[1].value].append(f'{name}:{node.lineno}')
    return stores, loads


def string_uses(pattern):
    found = defaultdict(list)
    for name, tree in modules():
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and re.fullmatch(pattern, node.value):
                found[node.value].append(f'{name}:{node.lineno}')
    return found


def main():
    stores, loads = attribute_usage()
    print('WRITE-ONLY ATTRIBUTES (stored, never loaded by name)')
    for attr in sorted(stores):
        if attr not in loads:
            print(' ', attr, stores[attr][:6])
    print('READ-ONLY dd_ ATTRIBUTES (loaded, never stored outside registration)')
    for attr in sorted(loads):
        if attr.startswith('dd_') and attr not in stores:
            print(' ', attr, loads[attr][:6])
    print('SCENE PROPERTY MENTIONS')
    for key, places in sorted(string_uses(r'dd_[a-z0-9_]+').items()):
        print(' ', key, 'strings:', len(places), 'loads:', len(loads.get(key, [])), 'stores:', len(stores.get(key, [])))
    print('UPPERCASE TOKENS (string constant, count, places)')
    for key, places in sorted(string_uses(r'[A-Z][A-Z0-9_]{2,}_?').items()):
        print(' ', key, len(places), places[:8])


if __name__ == '__main__':
    sys.exit(main())
