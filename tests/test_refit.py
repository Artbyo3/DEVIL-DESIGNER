import ast
import io
import math
import tokenize
import unittest
from pathlib import Path

from devil_designer.core import Anchor, Session
from devil_designer.refit import girth_profile, refit_document

OLD = dict(height=150.0, chest=80.0, waist=60.0, hip=90.0, chest_z=1.05, waist_z=.93, hip_z=.80, low_z=0.0, high_z=1.5, fallback=False)
NEW = dict(height=165.0, chest=100.0, waist=66.0, hip=90.0, chest_z=1.16, waist_z=1.02, hip_z=.88, low_z=0.0, high_z=1.65, fallback=False)


def width_at(pattern, y):
    xs = [vertex.x for vertex in pattern.vertices if abs(vertex.y - y) < 1e-9]
    return max(xs) - min(xs)


def edge_length(document, edge):
    pattern = document.find(edge.pattern)
    ends = [next(vertex for vertex in pattern.vertices if vertex.id == identity) for identity in (edge.start, edge.end)]
    return math.dist((ends[0].x, ends[0].y), (ends[1].x, ends[1].y))


class RefitTests(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        self.session.add([(0, 0), (.4, 0), (.4, .25), (.4, .5), (0, .5), (0, .25)])
        self.session.add([(.6, 0), (1.0, 0), (1.0, .25), (1.0, .5), (.6, .5), (.6, .25)])
        self.front, self.back = self.session.document.patterns
        self.spans = {self.front.id: (.8 / 1.5, 1.05 / 1.5, True), self.back.id: (.8 / 1.5, 1.05 / 1.5, True)}

    def test_each_height_takes_the_girth_change_of_its_own_body_region(self):
        along, chest = refit_document(self.session.document, self.spans, OLD, NEW)
        self.assertAlmostEqual(along, 1.1)
        self.assertAlmostEqual(chest, 1.25)
        self.assertAlmostEqual(width_at(self.front, min(v.y for v in self.front.vertices)), .4 * 1.0)
        self.assertAlmostEqual(width_at(self.front, max(v.y for v in self.front.vertices)), .4 * 1.25)
        middle = sorted({v.y for v in self.front.vertices})[1]
        self.assertAlmostEqual(width_at(self.front, middle), .4 * girth_profile(OLD, NEW)((.8 + .125) / 1.5))
        heights = [v.y for v in self.front.vertices]
        self.assertAlmostEqual(max(heights) - min(heights), .5 * 1.1)

    def test_seams_at_the_same_body_height_stay_matched(self):
        document = self.session.document
        side = (document.edges(self.front.id)[1], document.edges(self.back.id)[5])
        top = (document.edges(self.front.id)[3], document.edges(self.back.id)[3])
        refit_document(document, self.spans, OLD, NEW)
        for first, second in (side, top):
            self.assertAlmostEqual(edge_length(document, first), edge_length(document, second))

    def test_upside_down_and_sideways_pieces_and_attached_records_follow_the_piece(self):
        self.session.document.anchors.append(Anchor(self.front.id, .2, .5))
        self.session.document.steam.append(dict(pattern=self.front.id, x=.2, y=0.0, radius=.02))
        spans = {self.front.id: (1.05 / 1.5, .8 / 1.5, True), self.back.id: (.9, .9, False)}
        refit_document(self.session.document, spans, OLD, NEW)
        self.assertAlmostEqual(width_at(self.front, min(v.y for v in self.front.vertices)), .4 * 1.25)
        self.assertAlmostEqual(width_at(self.front, max(v.y for v in self.front.vertices)), .4 * 1.0)
        anchor = self.session.document.anchors[0]
        self.assertAlmostEqual(anchor.x, .2)
        self.assertAlmostEqual(anchor.y, .25 + .25 * 1.1)
        self.assertAlmostEqual(self.session.document.steam[0]['radius'], .02 * 1.25)
        widths = {round(width_at(self.back, y), 9) for y in {v.y for v in self.back.vertices}}
        self.assertEqual(len(widths), 1)

    def test_extreme_or_unmeasured_bodies_are_bounded_or_refused(self):
        before = self.session.document.dumps()
        with self.assertRaises(ValueError):
            refit_document(self.session.document, {}, OLD, dict(NEW, height=600.0))
        self.assertEqual(self.session.document.dumps(), before)
        refit_document(self.session.document, {}, OLD, dict(NEW, chest=400.0))
        self.assertAlmostEqual(width_at(self.front, 0.0 - .025), .4 * 2.0)
        with self.assertRaises(ValueError):
            refit_document(self.session.document, {}, OLD, dict(NEW, chest=0.0))
        with self.assertRaises(ValueError):
            refit_document(self.session.document, {}, dict(OLD, high_z=0.0), NEW)

    def test_a_body_without_clear_landmarks_refits_evenly_by_height(self):
        refit_document(self.session.document, self.spans, OLD, dict(NEW, fallback=True))
        widths = {round(width_at(self.front, y), 9) for y in {v.y for v in self.front.vertices}}
        self.assertEqual(widths, {round(.4 * 1.1, 9)})

    def test_new_sources_have_no_comments_or_standalone_strings(self):
        root = Path(__file__).resolve().parents[1]
        for relative in ('devil_designer/refit.py', 'tests/test_refit.py'):
            source = (root / relative).read_text(encoding='utf-8')
            self.assertFalse(any(token.type == tokenize.COMMENT for token in tokenize.generate_tokens(io.StringIO(source).readline)))
            self.assertFalse(any(isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
                                 for node in ast.walk(ast.parse(source))))


if __name__ == '__main__':
    unittest.main()
