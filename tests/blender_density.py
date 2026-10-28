from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

suite = unittest.TestSuite()
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('test_density'))
suite.addTests(unittest.defaultTestLoader.loadTestsFromName('test_meshing_regression'))
result = unittest.TextTestRunner(verbosity=2).run(suite)
if not result.wasSuccessful() or result.skipped:
    raise RuntimeError('Native per-piece density and meshing regression verification failed or skipped.')
