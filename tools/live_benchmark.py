import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from tools.dev import BLENDER_PATH
from tools.workspace import prepare_scratch

SCRIPT = ROOT / 'tools' / 'live_benchmark_blender.py'
VARIANTS = ['full', 'no_shell', 'no_surface', 'no_collision', 'no_self']
PANELS = [3, 10, 20, 30]
SPREAD_LIMIT = .05


def other_blenders():
    if os.name != 'nt':
        return []
    listing = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq blender.exe', '/FO', 'CSV', '/NH'], capture_output=True, text=True).stdout
    return [line.split('","')[1] for line in listing.splitlines() if line.startswith('"blender.exe"')]


def blender(arguments, viewport, output):
    command = [BLENDER_PATH, '--factory-startup']
    command += ['--window-geometry', '0', '0', '1500', '1000', '--enable-event-simulate'] if viewport else ['--background', '--python-exit-code', '1']
    command += ['--python', str(SCRIPT), '--', json.dumps(dict(arguments, root=str(ROOT), output=str(output), viewport=viewport))]
    output.unlink(missing_ok=True)
    started = time.time()
    result = subprocess.run(command, cwd=str(ROOT), capture_output=True, text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    if not output.is_file():
        raise RuntimeError('Benchmark run produced no result:\n' + result.stdout[-4000:] + result.stderr[-4000:])
    print(f'    {output.name} ({time.time() - started:.0f}s)', flush=True)
    return json.loads(output.read_text(encoding='utf-8'))


def cases(arguments):
    jobs = [('headless', 'dense', dict(panels=arguments.panels, body='dense', variants=VARIANTS))]
    jobs.append(('headless', 'light', dict(panels=[arguments.panels[0]], body='light', variants=VARIANTS)))
    if not arguments.headless_only:
        jobs.append(('viewport', 'dense', dict(panels=arguments.panels, body='dense')))
    return jobs


def rows(runs):
    table = {}
    for run in runs:
        for result in run:
            mode = result['mode']
            for record in result['records']:
                for variant in VARIANTS:
                    if variant in record:
                        key = (mode, record['body'], record['panels'], variant)
                        entry = table.setdefault(key, dict(medians=[], p95s=[], samples=[], python=[], quality=[], intervals=[], facts={}))
                        measured = record[variant]
                        entry['medians'].append(measured['frame_ms']['median'])
                        entry['p95s'].append(measured['frame_ms']['p95'])
                        entry['samples'].extend(measured['samples'])
                        entry['python'].append(measured['python_ms']['median'])
                        if 'interval_ms' in measured:
                            entry['intervals'].append(measured['interval_ms']['median'])
                        entry['quality'].append({name: measured[name] for name in ('seam_gap_max_mm', 'seam_gap_p99_mm', 'stretch_p99', 'finite')})
                        entry['facts'] = {name: record[name] for name in ('body_triangles', 'shell_triangles', 'cloth_vertices', 'sewing_pairs', 'substeps')}
    summary = []
    for (mode, body, panels, variant), entry in sorted(table.items()):
        medians = entry['medians']
        summary.append(dict(mode=mode, body=body, panels=panels, variant=variant, median_ms=float(np.median(medians)), mean_ms=float(np.mean(entry['samples'])),
                            p95_ms=float(np.percentile(entry['samples'], 95)), run_medians=medians,
                            spread=float((max(medians) - min(medians)) / min(medians)) if len(medians) > 1 else 0.0,
                            python_ms=float(np.median(entry['python'])), interval_ms=float(np.median(entry['intervals'])) if entry['intervals'] else None,
                            seam_gap_max_mm=max(item['seam_gap_max_mm'] for item in entry['quality']),
                            stretch_p99=max(item['stretch_p99'] for item in entry['quality']),
                            finite=all(item['finite'] for item in entry['quality']), **entry['facts']))
    return summary


def lookup(summary, mode, body, panels, variant):
    return next((row for row in summary if (row['mode'], row['body'], row['panels'], row['variant']) == (mode, body, panels, variant)), None)


def cost_map(summary, panels):
    result = []
    for count in panels:
        full, shell, surface, bare, alone = (lookup(summary, 'headless', 'dense', count, variant) for variant in VARIANTS)
        if None in (full, shell, surface, bare, alone):
            continue
        self_contact = full['mean_ms'] - alone['mean_ms']
        result.append(dict(panels=count, cloth_vertices=full['cloth_vertices'], frame_ms=full['median_ms'], mean_ms=full['mean_ms'],
                           solver_ms=bare['mean_ms'] - self_contact - full['python_ms'], self_contact_ms=self_contact,
                           shell_ms=full['mean_ms'] - shell['mean_ms'], true_surface_ms=full['mean_ms'] - surface['mean_ms'], python_ms=full['python_ms']))
    return result


def report(summary, panels):
    print('\nmode      body   panels variant       median    p95  spread  python  seam_max_mm stretch_p99 verts')
    for row in summary:
        print(f"{row['mode']:<9} {row['body']:<6} {row['panels']:>6} {row['variant']:<12} {row['median_ms']:7.1f} {row['p95_ms']:6.1f} "
              f"{row['spread'] * 100:5.1f}% {row['python_ms']:6.2f} {row['seam_gap_max_mm']:11.2f} {row['stretch_p99']:11.3f} {row['cloth_vertices']:5d}"
              + (f"  delivered {row['interval_ms']:.1f} ms" if row['interval_ms'] else ''))
    print('\ncost map (headless, dense body, mean ms per frame; every part is an ablation delta)')
    print('panels verts median   mean  solver  self_contact  shell  true_surface  python')
    for row in cost_map(summary, panels):
        print(f"{row['panels']:>6} {row['cloth_vertices']:5d} {row['frame_ms']:6.1f} {row['mean_ms']:6.1f} {row['solver_ms']:7.1f} {row['self_contact_ms']:13.1f} {row['shell_ms']:6.1f} {row['true_surface_ms']:13.1f} {row['python_ms']:7.2f}")
    light, dense = lookup(summary, 'headless', 'light', panels[0], 'full'), lookup(summary, 'headless', 'dense', panels[0], 'full')
    if light and dense:
        print(f"\ndensity penalty at {panels[0]} panels: {dense['median_ms'] - light['median_ms']:.1f} ms "
              f"({dense['body_triangles']} vs {light['body_triangles']} body triangles)")
    worst = max((row['spread'] for row in summary if row['variant'] == 'full'), default=0.0)
    print(f"worst run-to-run spread of full-variant medians: {worst * 100:.1f}% ({'within' if worst <= SPREAD_LIMIT else 'OUTSIDE'} 5%)")


def main(argv=None):
    parser = argparse.ArgumentParser(description='Live drape frame-time benchmark on a ~70k-triangle body.')
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--panels', type=lambda text: [int(item) for item in text.split(',')], default=PANELS)
    parser.add_argument('--headless-only', action='store_true')
    parser.add_argument('--label', default='current')
    arguments = parser.parse_args(argv)
    scratch = prepare_scratch()
    others = other_blenders()
    if others:
        print(f'WARNING: {len(others)} other Blender process(es) running (pids {", ".join(others)}); timings may be disturbed.')
    runs = []
    for index in range(arguments.runs):
        print(f'run {index + 1}/{arguments.runs}', flush=True)
        runs.append([blender(job, mode == 'viewport', scratch / f'live-benchmark-{arguments.label}-{mode}-{body}-{index}.json')
                     for mode, body, job in cases(arguments)])
    summary = rows(runs)
    report(summary, arguments.panels)
    destination = scratch / f'live-benchmark-{arguments.label}.json'
    destination.write_text(json.dumps(dict(label=arguments.label, other_blenders=others, summary=summary, cost_map=cost_map(summary, arguments.panels)), indent=1), encoding='utf-8')
    print(f'\nsummary: {destination}')


if __name__ == '__main__':
    main()
