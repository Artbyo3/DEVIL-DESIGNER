"""Unified fast development tool for Devil Designer.

Usage:
  python tools/dev.py --test            # Run all unit, background, and GUI tests (~22s)
  python tools/dev.py --quick           # Run fast headless unit tests only (~0.1s)
  python tools/dev.py --build           # Build zip, validate with Blender, sync to user extensions (~0.7s)
  python tools/dev.py --shots           # Capture clean screenshots of all 4 stages + full mode (~12s)
  python tools/dev.py --stage STAGE     # Capture clean screenshot for a single stage (e.g. DRAFT, SEW)
  python tools/dev.py --inspect         # Crop and validate UI regions (contrast, margins, buttons)
  python tools/dev.py --all             # Test, build, sync, screenshot, and inspect in one command!
"""
import os
import sys
import time
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
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
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    dt = time.time() - t0
    if res.returncode != 0:
        print(f"FAILED in {dt:.2f}s:")
        print(res.stdout)
        print(res.stderr)
        return False
    print(f"    OK ({dt:.2f}s)")
    return True

def do_quick_tests():
    print("\n=== RUNNING FAST HEADLESS UNIT TESTS ===")
    return run_cmd([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"],
                   desc="Headless Unit Tests (56 tests)")

def do_tests():
    print("\n=== RUNNING ALL TEST SUITES ===")
    
    # 1. Headless unit tests
    if not do_quick_tests():
        return False

    # 2. Background Blender tests
    for t in ["blender_smoke.py", "blender_garment.py", "blender_advanced.py", "blender_silhouette.py"]:
        if not run_cmd([BLENDER_PATH, "--background", "--factory-startup", "--python", f"tests/{t}"],
                       desc=f"Blender Background: {t}"):
            return False

    # 3. In-engine GUI tests
    for t in ["gui_preview", "gui_silhouette", "gui_design"]:
        if not run_cmd([BLENDER_PATH, "--factory-startup", "--python", "tools/run_blender_gui.py", "--", t],
                       desc=f"In-Engine GUI: {t}"):
            return False

    print("ALL TESTS PASSED!\n")
    return True

def do_build():
    print("\n=== BUILDING & VALIDATING EXTENSION ===")
    
    # 1. Build zip
    if not run_cmd([sys.executable, "tools/build.py"], desc="Package extension zip"):
        return False
        
    zip_path = ROOT / "build" / "devil_designer-0.5.0.zip"
    
    # 2. Validate extension
    if not run_cmd([BLENDER_PATH, "--background", "--factory-startup", "--command", "extension", "validate", str(zip_path)],
                   desc="Validate extension package"):
        return False
        
    # 3. Sync to user extensions
    import shutil
    user_ext = Path(os.path.expandvars(r"%APPDATA%\Blender Foundation\Blender\5.2\extensions\user_default\devil_designer"))
    if user_ext.exists():
        shutil.copytree(ROOT / "devil_designer", user_ext, dirs_exist_ok=True)
        print(f"    Synced to {user_ext}")
    else:
        print(f"    (User extensions folder not found, skipping sync)")
        
    print("BUILD & VALIDATION COMPLETE!\n")
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
    stages = ["DRAFT", "SEW", "ARRANGE", "SIMULATE"]
    for s in stages:
        out = f"screenshot_{s.lower()}_clean.png"
        print(f"--> Capturing stage {s} -> {out}...")
        capture(stage=s, output_name=out, full_mode=False)
        
    print(f"--> Capturing full expanded mode -> screenshot_expanded_clean.png...")
    capture(stage="DRAFT", output_name="screenshot_expanded_clean.png", full_mode=True)
    print("ALL SCREENSHOTS CAPTURED!\n")
    return True

def do_inspect():
    print("\n=== INSPECTING UI REGIONS & VISUAL QUALITY ===")
    from PIL import Image
    import numpy as np

    shot_path = ROOT / "build" / "screenshot_draft_clean.png"
    if not shot_path.exists():
        shot_path = ROOT / "build" / "screenshot_app.png"
    if not shot_path.exists():
        print("No screenshot found. Run --shots first.")
        return False

    img = Image.open(shot_path)
    w, h = img.size
    print(f"Analyzing {shot_path.name} ({w}x{h})...")

    out_dir = ROOT / "build" / "ui_inspect"
    out_dir.mkdir(exist_ok=True)

    regions = [
        ("01_top_bar.png", (0, 0, w, min(h, 56))),
        ("02_tool_rail.png", (0, 56, min(w, 65), max(56, h - 35))),
        ("03_viewbar.png", (65, 56, max(65, w - 280), min(h, 140))),
        ("04_canvas.png", (65, 140, max(65, w - 280), max(140, h - 35))),
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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Devil Designer Dev Tool")
    parser.add_argument("--quick", action="store_true", help="Run fast headless unit tests only (~0.1s)")
    parser.add_argument("--test", action="store_true", help="Run all unit, background, and GUI tests")
    parser.add_argument("--build", action="store_true", help="Build, validate, and sync")
    parser.add_argument("--shots", action="store_true", help="Capture all screenshots")
    parser.add_argument("--stage", type=str, help="Capture screenshot for a single stage (e.g. DRAFT, SEW, ARRANGE, SIMULATE)")
    parser.add_argument("--inspect", action="store_true", help="Slice and inspect UI regions")
    parser.add_argument("--all", action="store_true", help="Test, build, sync, screenshot, and inspect")
    
    args = parser.parse_args()
    if not any([args.quick, args.test, args.build, args.shots, args.stage, args.inspect, args.all]):
        parser.print_help()
        sys.exit(0)
        
    if args.quick:
        if not do_quick_tests():
            sys.exit(1)
    if args.test or args.all:
        if not do_tests():
            sys.exit(1)
    if args.build or args.all:
        if not do_build():
            sys.exit(1)
    if args.stage:
        if not do_stage_screenshot(args.stage):
            sys.exit(1)
    if args.shots or args.all:
        if not do_screenshots():
            sys.exit(1)
    if args.inspect or args.all:
        if not do_inspect():
            sys.exit(1)
            
    print("Dev tasks completed successfully!")
