import json
import sys
from pathlib import Path
import bpy

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import devil_designer
from devil_designer.core import EdgeRef, Session
from tools import sewing_diagnosis


original_fixture = sewing_diagnosis.fixture


def fixture(name):
    document = original_fixture('sleeve_correct' if name.startswith('sleeve') else 'trousers_full')
    if name in {'sleeve_long_reversed', 'trousers_reversed'}:
        document.seams[0].reverse = not document.seams[0].reverse
    elif name.endswith('both_long_reversed'):
        for seam in document.seams[:2]:
            seam.reverse = not seam.reverse
    elif name.endswith('cuff_reversed'):
        document.seams[2].reverse = not document.seams[2].reverse
    elif 'free_default' in name or 'free_fixed' in name or 'free_native_correct' in name:
        seam = document.seams[0]
        seam.chain_b = tuple(EdgeRef(edge.pattern, edge.start, edge.end, edge.t1, edge.t0, edge.path) for edge in reversed(seam.side(1)))
        seam.b = seam.chain_b[0]
        if 'free_fixed' in name:
            session = Session(document)
            session.reverse_seam(seam.id)
            assert session.document is document
        elif 'free_native_correct' in name:
            seam.reverse = False
    document.validate()
    return document


def main():
    devil_designer.register()
    sewing_diagnosis.fixture = fixture
    report = ROOT / 'scratch' / 'sewing-direction-diagnosis.json'
    results = []
    cases = ('sleeve_correct', 'sleeve_long_reversed', 'sleeve_both_long_reversed', 'sleeve_cuff_reversed',
             'trousers_full', 'trousers_reversed', 'sleeve_free_default', 'sleeve_free_fixed',
             'sleeve_free_native_correct', 'trousers_free_default', 'trousers_free_fixed', 'trousers_free_native_correct')
    for name in cases:
        results.append(sewing_diagnosis.measure(name))
        report.write_text(json.dumps(results, indent=2), encoding='utf-8')
        print('MEASURED', name, flush=True)
    for prefix in ('sleeve', 'trousers'):
        fixed = next(result for result in results if result['name'] == prefix + '_free_fixed')
        native = next(result for result in results if result['name'] == prefix + '_free_native_correct')
        assert fixed['compiled_fingerprint'] == native['compiled_fingerprint']
    print('DIRECTION DIAGNOSIS PASSED', flush=True)


if __name__ == '__main__':
    main()
