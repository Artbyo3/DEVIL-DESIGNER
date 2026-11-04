import ast
import json
import re
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = ROOT / 'devil_designer'
PROTECTED = {'core', 'garment', 'meshing', 'placement', 'tack_binding'}
ENTRY_POINTS = {'__init__.register', '__init__.unregister', '__init__.bl_info'}
BLENDER_CALLBACKS = {'invoke', 'execute', 'modal', 'poll', 'draw', 'cancel', 'check'}
IDENTIFIER = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


class Definition:
    def __init__(self, key, module, name, node, owner=None):
        self.key = key
        self.module = module
        self.name = name
        self.node = node
        self.owner = owner

    @property
    def lines(self):
        return self.node.end_lineno - self.node.lineno + 1


def target_names(target):
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [name for element in target.elts for name in target_names(element)]
    return []


def collect():
    definitions = {}
    roots = set()
    imports = defaultdict(dict)
    for path in sorted(PACKAGE.glob('*.py')):
        module = path.stem
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                key = f'{module}.{node.name}'
                definitions[key] = Definition(key, module, node.name, node)
            elif isinstance(node, ast.ClassDef):
                key = f'{module}.{node.name}'
                definitions[key] = Definition(key, module, node.name, node)
                for member in node.body:
                    if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        member_key = f'{key}.{member.name}'
                        definitions[member_key] = Definition(member_key, module, member.name, member, key)
            elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    for name in target_names(target):
                        key = f'{module}.{name}'
                        definitions.setdefault(key, Definition(key, module, name, node))
            elif isinstance(node, ast.ImportFrom):
                source = node.module.split('.')[0] if node.module and node.level else None
                for alias in node.names:
                    imports[module][alias.asname or alias.name] = (source, alias.name)
            elif isinstance(node, ast.Import):
                pass
            else:
                key = f'{module}.<toplevel:{node.lineno}>'
                definitions[key] = Definition(key, module, key, node)
                roots.add(key)
    return definitions, roots, imports


def mentions(node, skip_members):
    names, attributes, strings = set(), set(), set()
    stack = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, ast.ImportFrom) or isinstance(current, ast.Import):
            for alias in current.names:
                attributes.add(alias.name)
            continue
        if isinstance(current, ast.Name):
            names.add(current.id)
        elif isinstance(current, ast.Attribute):
            attributes.add(current.attr)
        elif isinstance(current, ast.Constant) and isinstance(current.value, str):
            if IDENTIFIER.fullmatch(current.value):
                strings.add(current.value)
        children = ast.iter_child_nodes(current)
        for child in children:
            if skip_members and current is node and isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            stack.append(child)
    return names, attributes, strings


def trace():
    definitions, roots, imports = collect()
    by_name = defaultdict(set)
    for definition in definitions.values():
        by_name[definition.name].add(definition.key)
    members = defaultdict(set)
    for definition in definitions.values():
        if definition.owner:
            members[definition.owner].add(definition.key)
    parents = {}
    queue = deque()
    for key in sorted(ENTRY_POINTS | roots):
        parents[key] = None
        queue.append(key)

    def reach(target, source):
        if target not in parents:
            parents[target] = source
            queue.append(target)

    while queue:
        key = queue.popleft()
        definition = definitions[key]
        if definition.owner:
            reach(definition.owner, key)
        is_class = isinstance(definition.node, ast.ClassDef)
        names, attributes, strings = mentions(definition.node, is_class)
        for name in names:
            local = f'{definition.module}.{name}'
            if local in definitions:
                reach(local, key)
            imported = imports[definition.module].get(name)
            if imported and imported[0]:
                target = f'{imported[0]}.{imported[1]}'
                if target in definitions:
                    reach(target, key)
            if not imported:
                for target in by_name.get(name, ()):
                    if definitions[target].owner is None and target.split('.')[0] == definition.module:
                        reach(target, key)
        for name in attributes | strings:
            for target in by_name.get(name, ()):
                reach(target, key)
        if is_class:
            for member in members[key]:
                short = definitions[member].name
                if short in BLENDER_CALLBACKS or short.startswith('__'):
                    reach(member, key)
    return definitions, parents


def path_to(key, parents):
    chain = []
    while key is not None:
        chain.append(key)
        key = parents.get(key)
    return ' <- '.join(chain)


def main(arguments):
    definitions, parents = trace()
    dead = [definition for key, definition in definitions.items() if key not in parents]
    if arguments and arguments[0] == '--why':
        for key in arguments[1:]:
            print(key, ':', path_to(key, parents) if key in parents else 'UNREACHABLE')
        return 0
    if arguments and arguments[0] == '--json':
        print(json.dumps(sorted(definition.key for definition in dead), indent=1))
        return 0
    owners = {definition.key for definition in dead}
    for definition in sorted(dead, key=lambda item: (item.module, item.node.lineno)):
        if definition.owner in owners:
            continue
        marker = ' [protected]' if definition.module in PROTECTED else ''
        print(f'{definition.key}:{definition.node.lineno} ({definition.lines} lines){marker}')
    print(f'{len(dead)} unreachable definitions of {len(definitions)}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
