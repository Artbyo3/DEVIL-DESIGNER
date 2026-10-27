import ast
from pathlib import Path
import sys


def find_dead_code(root):
    pkg = root / 'devil_designer'
    py_files = sorted(pkg.glob('*.py'))
    all_py = sorted([p for p in root.rglob('*.py') if '__pycache__' not in p.parts and '.git' not in p.parts])
    all_texts = {p: p.read_text(encoding='utf-8-sig') for p in all_py}
    violations = []
    for pf in py_files:
        tree = ast.parse(all_texts[pf])
        imported = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    imported[a.asname or a.name.split('.')[0]] = (a.name, node.lineno)
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    imported[a.asname or a.name] = (f'{node.module}.{a.name}', node.lineno)
        used = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Store):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                curr = node
                while isinstance(curr, ast.Attribute):
                    curr = curr.value
                if isinstance(curr, ast.Name):
                    used.add(curr.id)
        for name, (orig, lineno) in imported.items():
            if name not in used:
                violations.append(f'{pf.name}:{lineno}: unused import {orig}')
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and not t.id.startswith('_') and t.id != 'bl_info':
                        total = sum(text.count(t.id) for text in all_texts.values())
                        if total <= 1:
                            violations.append(f'{pf.name}:{node.lineno}: unused variable {t.id}')
            elif isinstance(node, ast.ClassDef):
                total = sum(text.count(node.name) for text in all_texts.values())
                if total <= 1:
                    violations.append(f'{pf.name}:{node.lineno}: unused class {node.name}')
            elif isinstance(node, ast.FunctionDef) and not node.name.startswith('__'):
                total = sum(text.count(node.name) for text in all_texts.values())
                if total <= 1:
                    violations.append(f'{pf.name}:{node.lineno}: unused function {node.name}')
    return violations


def check_dead_code(root):
    violations = find_dead_code(root)
    if violations:
        raise ValueError('\n'.join(violations))
    return len(list((root / 'devil_designer').glob('*.py')))


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    count = check_dead_code(root)
    print(f'Checked {count} package modules: zero dead code or unused imports detected.')
