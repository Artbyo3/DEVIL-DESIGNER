import ast
import operator
import re
from dataclasses import dataclass
import math

OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def evaluate(text):
    def walk(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
            return OPERATORS[type(node.op)](walk(node.left), walk(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return walk(node.operand) if isinstance(node.op, ast.UAdd) else -walk(node.operand)
        raise ValueError('Only numbers and + - * / are allowed.')
    cleaned = re.sub(r'(?<![\d.])0+(?=\d)', '', text.replace(',', '.').strip())
    return float(walk(ast.parse(cleaned, mode='eval').body))


@dataclass(frozen=True)
class Setting:
    key: str
    label: str
    factor: float
    unit: str
    step: float
    low: float
    high: float

    def format(self, value):
        return f"{value * self.factor:.15g}"

    def display(self, value):
        return f"{value * self.factor:.6g}"

    def parse(self, text):
        try:
            value = evaluate(text)
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError, RecursionError) as exc:
            raise ValueError('Enter a number for ' + self.label.lower() + '.') from exc
        value /= self.factor
        if not math.isfinite(value) or not self.low <= value <= self.high:
            raise ValueError(f'{self.label}: enter {self.low * self.factor:g} to {self.high * self.factor:g} {self.unit}.')
        return value

SETTINGS = {
    spec.key: spec for spec in (
        Setting('dd_point_x', 'Point X', 100, 'cm', 1, -100, 100),
        Setting('dd_point_y', 'Point Y', 100, 'cm', 1, -100, 100),
        Setting('dd_segment_length', 'Segment length', 100, 'cm', .1, .0001, 100),
        Setting('dd_weld_distance', 'Weld distance', 1000, 'mm', .5, .0001, .05),
    )
}

LOCAL_SETTINGS = {
    spec.key: spec for spec in (
        Setting('dd_trace_length', 'Measured length', 100, 'cm', .1, .000001, 1000),
        Setting('dd_trace_width', 'Image width', 100, 'cm', 1, .000001, 1000),
        Setting('dd_trace_x', 'Image X', 100, 'cm', 1, -1000, 1000),
        Setting('dd_trace_y', 'Image Y', 100, 'cm', 1, -1000, 1000),
        Setting('dd_fabric_structural', 'Stretch stiffness', 1, '', 1, .1, 500),
        Setting('dd_fabric_bending', 'Bending stiffness', 1, '', .05, .001, 120),
        Setting('dd_fabric_density', 'Mass density', 1, '', .05, .01, 10),
        Setting('dd_fabric_weft', 'Weft stretch', 100, '%', .05, .05, 4),
        Setting('dd_fabric_bias', 'Bias stiffness', 100, '%', .05, .05, 4),
        Setting('dd_fabric_shrink_warp', 'Shrink lengthwise', 100, '%', .01, -.3, .3),
        Setting('dd_fabric_shrink_weft', 'Shrink widthwise', 100, '%', .01, -.3, .3),
    )
}

@dataclass(frozen=True)
class TextSetting:
    key: str
    label: str
    unit: str = ''
    maximum: int = 80
    def format(self, value):
        return value
    def parse(self, text):
        if not text.strip() or len(text) > self.maximum:
            raise ValueError(f'{self.label}: use up to {self.maximum} characters.')
        return text.strip()

    def display(self, value):
        return value

SETTINGS['dd_library_name'] = TextSetting('dd_library_name', 'Garment name')
CONTROL_SETTINGS = {**SETTINGS, **LOCAL_SETTINGS}
