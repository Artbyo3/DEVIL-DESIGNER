import unittest
try:
    import bpy
except ModuleNotFoundError:
    bpy = None

if bpy is not None:
    from devil_designer.operators import run


class FakeOperator:
    def __init__(self):
        self.reports = []
        self.bl_label = 'Keep Draped Mesh'

    def report(self, level, message):
        self.reports.append((level, message))


@unittest.skipUnless(bpy is not None, 'Requires Blender')
class KeepErrorBoundaryTests(unittest.TestCase):
    def test_run_catches_expected_value_error(self):
        op = FakeOperator()
        def fail():
            raise ValueError('Start a drape before keeping or resetting it.')
        result = run(op, fail)
        self.assertEqual(result, {'CANCELLED'})
        self.assertEqual(op.reports, [({'ERROR'}, 'Start a drape before keeping or resetting it.')])

    def test_run_catches_unexpected_type_error(self):
        op = FakeOperator()
        def fail():
            raise TypeError('object of type NoneType has no len()')
        result = run(op, fail)
        self.assertEqual(result, {'CANCELLED'})
        self.assertEqual(len(op.reports), 1)
        level, msg = op.reports[0]
        self.assertEqual(level, {'ERROR'})
        self.assertTrue(msg.startswith('Unexpected error: TypeError:'))

    def test_run_catches_unexpected_key_error(self):
        op = FakeOperator()
        def fail():
            raise KeyError('dd_sewing_pairs')
        result = run(op, fail)
        self.assertEqual(result, {'CANCELLED'})
        self.assertEqual(len(op.reports), 1)
        level, msg = op.reports[0]
        self.assertEqual(level, {'ERROR'})
        self.assertTrue(msg.startswith('Unexpected error: KeyError:'))

    def test_run_catches_unexpected_attribute_error(self):
        op = FakeOperator()
        def fail():
            raise AttributeError("'NoneType' object has no attribute 'name'")
        result = run(op, fail)
        self.assertEqual(result, {'CANCELLED'})
        self.assertEqual(len(op.reports), 1)
        level, msg = op.reports[0]
        self.assertEqual(level, {'ERROR'})
        self.assertTrue(msg.startswith('Unexpected error: AttributeError:'))

    def test_run_succeeds_on_normal_action(self):
        op = FakeOperator()
        result = run(op, lambda: {'FINISHED'})
        self.assertEqual(result, {'FINISHED'})
        self.assertEqual(op.reports, [])
