import ast
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'devil_designer' / 'minimal.py'
VALUE_ROWS = {'INFO', 'SLIDER', 'CHOICES', 'CHOICES_FABRIC', 'AVATAR_FIELD'}


def string_at(node, index):
    value = node.elts[index] if index < len(node.elts) else None
    return value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else None


def row_actions(card):
    actions = set()
    for node in ast.walk(card):
        if not isinstance(node, ast.Tuple) or not node.elts:
            continue
        kind = string_at(node, 0)
        if kind == 'PAIR_ACTIONS':
            actions |= {string_at(node, 1), string_at(node, 2)}
        elif kind == 'MENU':
            actions.add(string_at(node, 1))
        elif kind and kind.isupper() and kind not in VALUE_ROWS and len(node.elts) >= 2 and isinstance(node.elts[1], ast.Constant):
            actions.add(kind)
    return actions - {None}


def handled_actions(action):
    exact, prefixes = set(), set()
    for node in ast.walk(action):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == 'key':
            right = node.comparators[0]
            if isinstance(right, ast.Constant):
                exact.add(right.value)
            elif isinstance(right, ast.Set):
                exact |= {item.value for item in right.elts}
            elif isinstance(right, ast.Name) and right.id == 'SUBMENUS':
                exact |= set(submenus())
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'startswith'
                and isinstance(node.func.value, ast.Name) and node.func.value.id == 'key'):
            argument = node.args[0]
            if isinstance(argument, ast.Constant):
                prefixes.add(argument.value)
    return exact, tuple(prefixes)


def submenus():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    node = next(item for item in tree.body if isinstance(item, ast.Assign) and getattr(item.targets[0], 'id', '') == 'SUBMENUS')
    return ast.literal_eval(node.value)


class MenuRowTests(unittest.TestCase):
    def test_every_menu_row_has_a_handler(self):
        tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
        functions = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
        exact, prefixes = handled_actions(functions['minimal_action'])
        missing = {action for action in row_actions(functions['minimal_card'])
                   if action not in exact and not action.startswith(prefixes)}
        self.assertEqual(missing, set())


if __name__ == '__main__':
    unittest.main()
