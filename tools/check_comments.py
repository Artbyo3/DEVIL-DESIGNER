import ast
import io
import tokenize
from pathlib import Path


def check_source(text, filename='<source>'):
    tree = ast.parse(text, filename=filename)
    violations = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT:
            violations.append(f'{filename}:{token.start[0]}: code comment')
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and (
            isinstance(node.value, ast.JoinedStr)
            or isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        ):
            violations.append(f'{filename}:{node.lineno}: docstring or standalone string')
    if violations:
        raise ValueError('\n'.join(violations))


def check_repository(root):
    count = 0
    for directory in ('devil_designer', 'tests', 'tools'):
        for source in sorted((root / directory).rglob('*.py')):
            check_source(source.read_text(encoding='utf-8-sig'), str(source.relative_to(root)))
            count += 1
    return count


if __name__ == '__main__':
    print(f'Checked {check_repository(Path(__file__).resolve().parents[1])} Python files: zero comments or docstrings.')
