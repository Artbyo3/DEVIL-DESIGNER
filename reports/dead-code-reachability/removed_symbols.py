import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REMOVED_ATTRIBUTES = {
    'chain_stage', 'stage', 'set_stage', 'advance_stage', 'window_gesture', 'toast_message',
    'shape_committed_frame', 'minimal', 'integer', 'allow_empty', 'generate_volumes',
    'dd_width', 'dd_height', 'dd_offset', 'dd_wrap_radius',
}
EDITOR_ONLY_ATTRIBUTES = {'chain_a', 'chain_b'}
REMOVED_NAMES = {'ICON_ALIASES', 'BG_PANEL', 'INSPECTOR', 'RADIUS_DOCK', 'RADIUS_DOCK_ITEM', 'RADIUS_CARD'}
REMOVED_TOKENS = {
    'ADD_PANEL', 'START_PANEL', 'NUM_RECT', 'NUM_ELLIPSE', 'OFFSET', 'PRESET', 'CHAIN_A', 'CHAIN_B',
    'CHAIN_SEW', 'LIBRARY_PREV', 'LIBRARY_NEXT', 'TOGGLE_MEASURE', 'EDIT_ACTIONS', 'BODY_CHANGE', 'BODY_PICK_',
    'WORKSPACE_FIT', 'GUIDED_NEXT', 'HELP', 'BUILD', 'ARRANGE', 'DEMO', 'ARRANGEMENT', 'EDIT',
    'INSPECTOR_TOGGLE', 'INSPECTOR_COLLAPSE', 'SET_PRESET_', 'SELECT_TARGET_',
}


def main():
    findings = []
    for path in sorted((ROOT / 'devil_designer').glob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                receiver = node.value.id if isinstance(node.value, ast.Name) else ''
                if node.attr in REMOVED_ATTRIBUTES:
                    findings.append((path.name, node.lineno, 'attribute', node.attr))
                if node.attr in EDITOR_ONLY_ATTRIBUTES and receiver in {'ed', 'editor', 'workspace'}:
                    findings.append((path.name, node.lineno, 'attribute', node.attr))
                if node.attr in EDITOR_ONLY_ATTRIBUTES and receiver == 'self' and path.stem in {'design_tools', 'editor', 'interaction', 'minimal', 'draw'}:
                    findings.append((path.name, node.lineno, 'attribute', node.attr))
            elif isinstance(node, ast.Name) and node.id in REMOVED_NAMES:
                findings.append((path.name, node.lineno, 'name', node.id))
            elif isinstance(node, ast.Constant) and node.value in REMOVED_TOKENS:
                findings.append((path.name, node.lineno, 'token', node.value))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {'getattr', 'hasattr', 'setattr'}:
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant) and node.args[1].value in REMOVED_ATTRIBUTES | EDITOR_ONLY_ATTRIBUTES:
                    findings.append((path.name, node.lineno, 'dynamic', node.args[1].value))
    for finding in findings:
        print(*finding)
    print(f'{len(findings)} references to removed symbols')
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main())
