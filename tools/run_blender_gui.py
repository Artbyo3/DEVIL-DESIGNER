"""Helper to run a GUI test inside Blender, wait for completion, and quit."""
import sys
import os
import json
import time
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

test_name = sys.argv[-1] if len(sys.argv) > 1 and not sys.argv[-1].startswith('-') else "gui_preview"
report_file = ROOT / "build" / f"{test_name.replace('gui_', '').replace('.py', '')}-report.json"
if "preview" in test_name:
    report_file = ROOT / "build" / "gui-report.json"
elif "silhouette" in test_name:
    report_file = ROOT / "build" / "silhouette-gui-report.json"
elif "design" in test_name:
    report_file = ROOT / "build" / "design-gui-report.json"

if report_file.exists():
    try:
        report_file.unlink()
    except Exception:
        pass

target_file = ROOT / "tests" / (test_name if test_name.endswith(".py") else f"{test_name}.py")
print(f"Loading test: {target_file}")
print(f"Expecting report: {report_file}")

with open(target_file, "r", encoding="utf-8") as f:
    code = compile(f.read(), str(target_file), "exec")
    exec(code, {"__name__": "__main__", "__file__": str(target_file)})

start_time = time.time()

def watchdog():
    if report_file.exists():
        time.sleep(0.5)
        try:
            data = json.loads(report_file.read_text(encoding="utf-8"))
            if "error" in data:
                print("GUI TEST FAILED:")
                print(data["error"])
            else:
                print(f"GUI TEST PASSED ({len(data.get('passed', []))} checks)")
        except Exception as e:
            print("Error reading report:", e)
        bpy.ops.wm.quit_blender()
        return None
    if time.time() - start_time > 20:
        print("GUI TEST TIMED OUT waiting for report")
        bpy.ops.wm.quit_blender()
        return None
    return 0.5

bpy.app.timers.register(watchdog, first_interval=1.0)
