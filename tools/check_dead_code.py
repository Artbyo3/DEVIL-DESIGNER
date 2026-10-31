import ast
from pathlib import Path
import sys


def _extract_target_names(target):
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        names = []
        for elt in target.elts:
            names.extend(_extract_target_names(elt))
        return names
    return []


def _collect_module_exports(py_files, all_texts):
    exports = {}
    submodules = {pf.stem for pf in py_files if pf.stem != '__init__'}
    for pf in py_files:
        tree = ast.parse(all_texts[pf])
        defined = set(submodules) if pf.stem == '__init__' else set()
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    defined.update(_extract_target_names(t))
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                defined.update(_extract_target_names(node.target))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined.add(node.name)
            elif isinstance(node, ast.Import):
                for a in node.names:
                    defined.add(a.asname or a.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                for a in node.names:
                    defined.add(a.asname or a.name)
        exports[pf.stem] = defined
    return exports


def find_missing_imports(root):
    pkg = root / 'devil_designer'
    py_files = sorted(pkg.glob('*.py'))
    all_texts = {p: p.read_text(encoding='utf-8-sig') for p in py_files}
    exports = _collect_module_exports(py_files, all_texts)
    violations = []
    for pf in py_files:
        tree = ast.parse(all_texts[pf])
        imported_submods = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                target_mod = None
                if node.level == 1:
                    target_mod = node.module or '__init__'
                elif node.level == 0 and node.module == 'devil_designer':
                    target_mod = '__init__'
                elif node.level == 0 and node.module and node.module.startswith('devil_designer.'):
                    target_mod = node.module.split('.', 1)[1]
                if target_mod is not None:
                    if target_mod not in exports:
                        violations.append(f'{pf.name}:{node.lineno}: missing module {target_mod}')
                    else:
                        for a in node.names:
                            if a.name != '*' and a.name not in exports[target_mod]:
                                violations.append(f'{pf.name}:{node.lineno}: missing import {a.name} from {target_mod}')
                            elif a.name in exports:
                                imported_submods[a.asname or a.name] = a.name

        class ScopeVisitor(ast.NodeVisitor):
            def __init__(self):
                self.scopes = [set()]
            def visit_FunctionDef(self, node):
                params = {arg.arg for arg in node.args.args + node.args.kwonlyargs}
                if node.args.vararg: params.add(node.args.vararg.arg)
                if node.args.kwarg: params.add(node.args.kwarg.arg)
                self.scopes.append(set(params))
                self.generic_visit(node)
                self.scopes.pop()
            def visit_AsyncFunctionDef(self, node):
                self.visit_FunctionDef(node)
            def visit_Assign(self, node):
                for t in node.targets:
                    if isinstance(t, ast.Name):
                        self.scopes[-1].add(t.id)
                self.generic_visit(node)
            def visit_Attribute(self, node):
                if isinstance(node.value, ast.Name):
                    var_name = node.value.id
                    is_local = any(var_name in s for s in self.scopes)
                    if not is_local and var_name in imported_submods:
                        mod = imported_submods[var_name]
                        if node.attr not in exports[mod]:
                            violations.append(f'{pf.name}:{node.lineno}: missing attribute {node.attr} on module {mod}')
                self.generic_visit(node)

        ScopeVisitor().visit(tree)
    return violations


def find_draw_integrity_violations(root):
    pkg = root / 'devil_designer'
    draw_files = [pkg / 'draw.py', pkg / 'minimal.py', pkg / 'ui.py']
    classes = {
        'EdgeRef': {'pattern', 'start', 'end', 't0', 't1', 'path', 'full'},
        'Seam': {'a', 'b', 'reverse', 'id', 'chain_a', 'chain_b', 'shrink', 'side'},
        'Anchor': {'x', 'y', 'kind', 'id', 'pattern', 'binding', 'target'},
        'Rect': {'x', 'y', 'w', 'h', 'contains', 'right', 'bottom'},
    }
    known_dicts = {
        'linked_pair': {'members', 'enabled', 'transform', 'mapping'},
    }
    def infer_expr_type(expr):
        if isinstance(expr, ast.Call):
            func = expr.func
            if isinstance(func, ast.Name):
                if func.id in classes:
                    return func.id
                if func.id == 'pair_for':
                    return 'linked_pair'
            elif isinstance(func, ast.Attribute):
                if func.attr in classes:
                    return func.attr
                if func.attr in ('edge', 'design_hit_edge'):
                    return 'EdgeRef'
                if func.attr == 'pair_for':
                    return 'linked_pair'
        elif isinstance(expr, ast.Attribute):
            if expr.attr in ('pending_edge', 'segment'):
                return 'EdgeRef'
        return None
    violations = []
    for pf in draw_files:
        if not pf.exists():
            continue
        tree = ast.parse(pf.read_text(encoding='utf-8-sig'))
        class DrawIntegrityVisitor(ast.NodeVisitor):
            def __init__(self):
                self.scopes = [{}]
            def visit_FunctionDef(self, node):
                self.scopes.append({})
                self.generic_visit(node)
                self.scopes.pop()
            def visit_AsyncFunctionDef(self, node):
                self.scopes.append({})
                self.generic_visit(node)
                self.scopes.pop()
            def visit_Assign(self, node):
                t_type = infer_expr_type(node.value)
                if t_type:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            self.scopes[-1][target.id] = t_type
                self.generic_visit(node)
            def visit_For(self, node):
                if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Attribute) and node.iter.func.attr == 'edges':
                    if isinstance(node.target, ast.Name):
                        self.scopes[-1][node.target.id] = 'EdgeRef'
                elif isinstance(node.iter, ast.Attribute) and node.iter.attr == 'linked_pairs':
                    if isinstance(node.target, ast.Name):
                        self.scopes[-1][node.target.id] = 'linked_pair'
                elif isinstance(node.iter, ast.Attribute) and node.iter.attr == 'seams':
                    if isinstance(node.target, ast.Name):
                        self.scopes[-1][node.target.id] = 'Seam'
                elif isinstance(node.iter, ast.Attribute) and node.iter.attr == 'anchors':
                    if isinstance(node.target, ast.Name):
                        self.scopes[-1][node.target.id] = 'Anchor'
                self.generic_visit(node)
            def visit_Attribute(self, node):
                if isinstance(node.value, ast.Name):
                    for s in reversed(self.scopes):
                        if node.value.id in s:
                            cls_name = s[node.value.id]
                            if cls_name in classes and node.attr not in classes[cls_name]:
                                violations.append(f"{pf.name}:{node.lineno}: invalid attribute '{node.attr}' on {cls_name}")
                            break
                elif isinstance(node.value, ast.Attribute):
                    if node.value.attr in ('pending_edge', 'segment'):
                        if node.attr not in classes.get('EdgeRef', set()):
                            violations.append(f"{pf.name}:{node.lineno}: invalid attribute '{node.attr}' on EdgeRef")
                self.generic_visit(node)
            def visit_Subscript(self, node):
                if isinstance(node.value, ast.Name):
                    for s in reversed(self.scopes):
                        if node.value.id in s:
                            d_type = s[node.value.id]
                            if d_type in known_dicts and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                                if node.slice.value not in known_dicts[d_type]:
                                    violations.append(f"{pf.name}:{node.lineno}: invalid key '{node.slice.value}' on {d_type}")
                            break
                self.generic_visit(node)
        DrawIntegrityVisitor().visit(tree)
    return violations


def check_draw_integrity(root):
    violations = find_draw_integrity_violations(root)
    if violations:
        raise ValueError('\n'.join(violations))
    return len(violations)


def check_import_integrity(root):
    violations = find_missing_imports(root)
    if violations:
        raise ValueError('\n'.join(violations))
    return len(list((root / 'devil_designer').glob('*.py')))


def find_dead_code(root):
    pkg = root / 'devil_designer'
    py_files = sorted(pkg.glob('*.py'))
    all_py = sorted([p for p in root.rglob('*.py') if '__pycache__' not in p.parts and '.git' not in p.parts])
    all_texts = {p: p.read_text(encoding='utf-8-sig') for p in all_py}
    violations = list(find_missing_imports(root)) + list(find_draw_integrity_violations(root))
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
    check_import_integrity(root)
    check_draw_integrity(root)
    print(f'Checked {count} package modules: zero dead code, unused imports, missing cross-module imports, or draw integrity violations detected.')
