"""Split screenshot_app.png into sub-regions to inspect each UI component visually."""
import json
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
shot = ROOT / "build" / "screenshot_app.png"
if not shot.exists():
    print("screenshot_app.png not found")
    exit(1)

img = Image.open(shot)
w, h = img.size
print(f"Loaded screenshot: {w}x{h}")

out_dir = ROOT / "build" / "ui_inspect"
out_dir.mkdir(exist_ok=True)

# 1. Top Bar (top 56 px)
top_bar = img.crop((0, 0, w, min(h, 56)))
top_bar.save(out_dir / "01_top_bar.png")

# 2. Left Tool Rail (left 65 px, between header and footer)
rail = img.crop((0, 56, min(w, 65), max(56, h - 35)))
rail.save(out_dir / "02_tool_rail.png")

# 3. Viewbar & Workflow strip (top of canvas)
viewbar = img.crop((65, 56, max(65, w - 280), min(h, 140)))
viewbar.save(out_dir / "03_viewbar.png")

# 4. Canvas center (with patterns)
canvas = img.crop((65, 140, max(65, w - 280), max(140, h - 35)))
canvas.save(out_dir / "04_canvas.png")

# 5. Right Inspector
inspector = img.crop((max(0, w - 285), 56, w, max(56, h - 35)))
inspector.save(out_dir / "05_inspector.png")

# 6. Bottom Status Bar (bottom 35 px)
footer = img.crop((0, max(0, h - 35), w, h))
footer.save(out_dir / "06_status_bar.png")

print(f"Saved region crops to {out_dir}")
