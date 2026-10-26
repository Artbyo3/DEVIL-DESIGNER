# Sourced CC0 interface icons

These are existing third-party icons, not AI-generated or hand-drawn replacements.

- Kenney Game Icons and Game Icons Expansion: https://kenney.nl/assets/game-icons and https://kenney.nl/assets/game-icons-expansion
- Maki: https://github.com/mapbox/maki
- Temaki: https://github.com/rapideditor/temaki

All three collections dedicate their icon artwork under CC0 1.0. The original license documents are included alongside these assets. `sources.json` records the individual upstream files, checksums, pinned SVG revisions, and the reflected Redo variant.

`tools/prepare_icons.py` normalizes the supplied artwork into transparent 64-pixel images and quantized alpha spans in `geometry.json`. The spans are cached as native Blender UNIFORM_COLOR GPU batches. No SVG parser, image renderer, network request, Pillow, or resvg dependency is needed at runtime. Original SVG files are retained where applicable. Kenney raster originals are identified by their archive paths and SHA-256 hashes.

To regenerate, download the two named Kenney archives into `build`, install Pillow and resvg_py into the developer environment (`build/icon_vendor` is also supported), and run `python tools/prepare_icons.py`. Regeneration deliberately refreshes upstream SVG revisions; review the resulting provenance changes.
