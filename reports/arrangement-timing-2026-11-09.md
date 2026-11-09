# Arrangement timing flake fix

Base: origin/master at 81ce681 (0.15.0). Branch: next/arrangement-timing.

The old assertion rejected any individual longest fitting slice above 8 ms. The replacement measures seven idle GUI timer intervals before fitting and uses twice their median, bounded to 8?50 ms. Each mesh size is judged by the median longest slice of five completed fits. Calibration does not execute arrangement code, so an arrangement slowdown cannot inflate its own reference. The 50 ms ceiling matches the existing input responsiveness budget; a sustained 80 ms slice fails regardless of calibration. The existing per-run callback, input-gap and completion-time checks remain unchanged.

This measures cooperative timer wall time, including scheduler pauses, not pure CPU cost. Median aggregation tolerates two anomalous fits per fixture but still rejects sustained regressions. Idle cadence is a responsiveness reference rather than a CPU throughput benchmark. No production code, garment math, or released package changed.

## Final targeted verification

Only gui_arrangement ran, three sequential real-Blender GUI executions using tools/run_blender_gui.py, with factory startup and event simulation. Every execution passed 46 assertions and completed all ten fits (17,856 and 72,576 triangles, five each). No mid-work suites or full battery ran.

- Run 1: idle cadence 11.74 ms; budget 23.49 ms; median longest slices 5.03 / 7.02 ms; PASS.
- Run 2: idle cadence 11.63 ms; budget 23.26 ms; median longest slices 5.38 / 6.43 ms; PASS.
- Run 3: idle cadence 10.02 ms; budget 20.04 ms; median longest slices 5.38 / 7.13 ms; PASS.

Changed Python file passed syntax parsing, COMMENT-token rejection and AST standalone-string/docstring rejection. git diff --check passed. No Blender process was running before verification; the machine reports 20 logical processors. These runs establish repeatability on this machine, not a performance improvement or cross-hardware guarantee.

Unverified: synthetic slowdown injection, other hardware/load conditions, full test battery, package validation, privacy/dead-code gates and artist acceptance. No build or shipping readiness is claimed. No GitHub writes were performed; existing unrelated reports/md-feature-matrix-2026-11-03.md was preserved.
