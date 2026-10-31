import os
import sys
import time
import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
from tools.workspace import SCRATCH, clean_scratch, extension_archive, prepare_scratch
BLENDER_PATH = r"C:\Program Files (x86)\Steam\steamapps\common\Blender\blender.exe"
if not os.path.exists(BLENDER_PATH):
    for p in [r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
              r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe"]:
        if os.path.exists(p):
            BLENDER_PATH = p
            break

def run_cmd(cmd, cwd=str(ROOT), desc=""):
    if desc:
        print(f"--> {desc}...")
    t0 = time.time()
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=environment)
    dt = time.time() - t0
    gui_test = any(Path(argument).name == 'run_blender_gui.py' for argument in cmd)
    if res.returncode != 0 or (gui_test and ('GUI TEST FAILED:' in res.stdout or 'GUI TEST TIMED OUT' in res.stdout)):
        print(f"FAILED in {dt:.2f}s:")
        print(res.stdout)
        print(res.stderr)
        return False
    print(f"    OK ({dt:.2f}s)")
    return True

def do_quick_tests():
    print("\n=== RUNNING FAST HEADLESS UNIT TESTS ===")
    return run_cmd([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
                   desc="Headless Unit Tests")

def do_tests():
    print("\n=== RUNNING ALL TEST SUITES ===")
    
    if not do_quick_tests():
        return False

    for t in ["blender_smoke.py", "blender_garment.py", "blender_advanced.py", "blender_silhouette.py",
              "blender_density.py", "blender_arrangement.py", "blender_tack_binding.py", "blender_tracing.py", "blender_layering.py", "blender_piece_states.py", "blender_sewing_preview.py"]:
        if not run_cmd([BLENDER_PATH, "--background", "--factory-startup", "--python-exit-code", "1", "--python", f"tests/{t}"],
                       desc=f"Blender Background: {t}"):
            return False

    for t in ["gui_preview", "gui_silhouette", "gui_design", "gui_fast_flow", "gui_arrangement", "gui_arrangement_display", "gui_fit_map", "gui_viewport_sewing"]:
        if not run_cmd([BLENDER_PATH, "--enable-event-simulate", "--factory-startup", "--python", "tools/run_blender_gui.py", "--", t],
                       desc=f"In-Engine GUI: {t}"):
            return False

    print("ALL TESTS PASSED!\n")
    return True

def do_build():
    print("\n=== BUILDING & VALIDATING EXTENSION ===")
    
    if not run_cmd([sys.executable, "tools/build.py"], desc="Package extension zip"):
        return False
        
    zip_path = extension_archive()
    
    if not run_cmd([BLENDER_PATH, "--background", "--factory-startup", "--command", "extension", "validate", str(zip_path)],
                   desc="Validate extension package"):
        return False
        
    import shutil
    user_ext = Path(os.path.expandvars(r"%APPDATA%\Blender Foundation\Blender\5.2\extensions\user_default\devil_designer"))
    if user_ext.exists():
        shutil.copytree(ROOT / "devil_designer", user_ext, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        print(f"    Synced to {user_ext}")
    else:
        print(f"    (User extensions folder not found, skipping sync)")
        
    print("BUILD & VALIDATION COMPLETE!\n")
    return True


def do_arrangement_performance(label):
    report=SCRATCH / f"arrangement-performance-{label}.json"
    report.unlink(missing_ok=True)
    if not run_cmd([BLENDER_PATH, "--factory-startup", "--window-geometry", "0", "0", "1500", "1000",
                    "--python", "tests/gui_arrangement_performance.py", "--", label],
                   desc="Arrangement display orbit benchmark"):
        return False
    if not report.is_file():
        print("Arrangement benchmark did not produce its completed measurements.")
        return False
    print(json.dumps(json.loads(report.read_text(encoding="utf-8")),indent=2))
    return True

def do_action_performance(label):
    report = SCRATCH / f'action-performance-{label}.json'
    report.unlink(missing_ok=True)
    if not run_cmd([BLENDER_PATH, '--factory-startup', '--window-geometry', '0', '0', '1500', '1000',
                    '--python', 'tools/action_performance.py', '--', label],
                   desc='Action-time profiling matrix'):
        return False
    if not report.is_file():
        print('Action benchmark did not produce a report.')
        return False
    result = json.loads(report.read_text(encoding='utf-8'))
    if not result.get('complete'):
        print(result.get('error', 'Action benchmark is incomplete.'))
        return False
    print(f"Measured {len(result['records'])} action conditions: {report}")
    return True

def do_stage_screenshot(stage):
    print(f"\n=== CAPTURING SCREENSHOT FOR STAGE: {stage} ===")
    from tools.screenshot import capture
    out = f"screenshot_{stage.lower()}_clean.png"
    result = capture(stage=stage.upper(), output_name=out, full_mode=False)
    if result:
        print(f"Captured: {result}\n")
        return True
    return False

def do_screenshots():
    print("\n=== CAPTURING CLEAN IN-ENGINE SCREENSHOTS ===")
    from tools.screenshot import capture
    scenarios = [
        ('draft', {'tool': 'SELECT'}),
        ('empty', {'empty': True, 'tool': 'RECTANGLE'}),
        ('sew', {'demo': True, 'tool': 'SEW'}),
        ('arrange', {'demo': True, 'section': 'AVATAR'}),
        ('simulate', {'demo': True, 'section': 'CLOTH'}),
        ('library', {'demo': True, 'section': 'LIBRARY'}),
        ('fabric', {'demo': True, 'tool': 'SELECT', 'card_kind': 'FABRIC'}),
        ('compact', {'empty': True, 'panel_size': (620, 440), 'tool': 'RECTANGLE'}),
        ('expanded', {'demo': True, 'full_mode': True, 'tool': 'SELECT'}),
        ('side_by_side', {'demo': True, 'tool': 'SELECT', 'reveal_3d': True}),
        ('keep', {'demo': True, 'tool': 'SELECT', 'card_kind': 'KEEP'}),
    ]
    for name, options in scenarios:
        out = f'screenshot_{name}_clean.png'
        print(f'--> Capturing {name} -> {out}...')
        if not capture(output_name=out, **options):
            return False
    print("ALL SCREENSHOTS CAPTURED!\n")
    return True

def do_inspect():
    print("\n=== INSPECTING UI REGIONS & VISUAL QUALITY ===")
    from PIL import Image
    import numpy as np

    shot_path = SCRATCH / "screenshot_draft_clean.png"
    if not shot_path.exists():
        shot_path = SCRATCH / "screenshot_app.png"
    if not shot_path.exists():
        print("No screenshot found. Run --shots first.")
        return False

    img = Image.open(shot_path)
    w, h = img.size
    print(f"Analyzing {shot_path.name} ({w}x{h})...")

    out_dir = SCRATCH / "ui_inspect"
    out_dir.mkdir(exist_ok=True)

    regions = [
        ("01_top_bar.png", (0, 0, w, min(h, 56))),
        ("02_tool_rail.png", (0, 56, min(w, 108), max(56, h - 35))),
        ("03_viewbar.png", (108, 56, max(108, w - 280), min(h, 150))),
        ("04_canvas.png", (108, 150, max(108, w - 280), max(150, h - 35))),
        ("05_inspector.png", (max(0, w - 285), 56, w, max(56, h - 35))),
        ("06_status_bar.png", (0, max(0, h - 35), w, h)),
    ]

    for fname, box in regions:
        crop = img.crop(box)
        crop.save(out_dir / fname)
        arr = np.array(crop)
        mean_b = arr.mean()
        print(f"  {fname:<20} {crop.size[0]:>4}x{crop.size[1]:<4}  avg brightness: {mean_b:5.1f}")

    print(f"Inspection crops saved to: {out_dir}\n")
    return True

def main(argv=None):
    parser = argparse.ArgumentParser(description="Devil Designer Dev Tool")
    parser.add_argument("--quick", action="store_true", help="Run fast headless unit tests only (~0.1s)")
    parser.add_argument("--arrangement-performance", choices=("baseline", "fixed", "current"), help="Measure orbit FPS, CPU, GPU snapshot and arrangement display cost")
    parser.add_argument('--action-performance', choices=('baseline', 'fixed', 'current'), help='Profile action latency on a rigged six-panel fixture')
    parser.add_argument("--test", action="store_true", help="Run all unit, background, and GUI tests")
    parser.add_argument("--build", action="store_true", help="Build, validate, and sync")
    parser.add_argument("--shots", action="store_true", help="Capture all screenshots")
    parser.add_argument("--stage", type=str, help="Capture screenshot for a single stage (e.g. DRAFT, SEW, ARRANGE, SIMULATE)")
    parser.add_argument("--inspect", action="store_true", help="Slice and inspect UI regions")
    parser.add_argument("--all", action="store_true", help="Test, build, sync, screenshot, and inspect")
    parser.add_argument("--clean", action="store_true", help="Delete disposable scratch artifacts without touching dist or source")
    parser.add_argument("--keep-scratch", action="store_true", help="Keep artifacts after success for manual inspection")
    
    args = parser.parse_args(argv)
    if args.clean and args.keep_scratch:
        parser.error('--clean and --keep-scratch cannot be combined')
    if not any([args.quick, args.test, args.build, args.shots, args.stage, args.inspect, args.all, args.clean, args.arrangement_performance, args.action_performance]):
        parser.print_help()
        return 0
        
    operations = [
        (args.action_performance, lambda: do_action_performance(args.action_performance)),
        (args.arrangement_performance, lambda: do_arrangement_performance(args.arrangement_performance)),
        (args.quick, do_quick_tests),
        (args.test or args.all, do_tests),
        (args.build or args.all, do_build),
        (args.stage, lambda: do_stage_screenshot(args.stage)),
        (args.shots or args.all, do_screenshots),
        (args.inspect or args.all, do_inspect),
    ]
    if any(enabled for enabled, operation in operations):
        prepare_scratch()
    for enabled, operation in operations:
        if enabled and not operation():
            print('Task failed. Diagnostic artifacts remain in scratch; use --clean when finished.')
            return 1
    if not args.keep_scratch:
        try:
            removed = clean_scratch()
        except (OSError, ValueError) as error:
            print(f'Scratch cleanup failed: {error}')
            return 1
        print(f'Scratch removed ({removed} temporary files). Installable archives remain in dist.')
            
    print("Dev tasks completed successfully!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
