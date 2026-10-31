# Installation & Setup

This guide walks you through building the add-on archive, installing it into Blender 5.2+, opening the editor, and validating the installation.

---

## Prerequisites

* **Blender Version:** Blender 5.2 LTS or later (tested on Blender 5.2.3 LTS).
* **Operating System:** Windows, Linux, or macOS supported by Blender 5.2+.
* **External Dependencies:** None. Devil Designer relies strictly on Blender's built-in Python 3 environment and native GPU drawing. No external network services or binary libraries are required.

---

## Building the Add-on Package

If you have cloned the repository source, you can build the production add-on ZIP package directly:

```bash
python tools/build.py
```

This generates the installable package at:

```
dist/devil_designer-0.10.0.zip
```

On Windows, the developer runner script can run tests and build the package in one step:

```cmd
.\dev.cmd --test --build
```

The runner automatically cleans up the disposable `scratch/` workspace while preserving the final archive in `dist/`.

---

## Installing into Blender

Follow these steps to install the add-on in Blender:

1. Open Blender.
2. Go to **Edit > Preferences** from the top menu.
3. Select the **Add-ons** tab on the left.
4. Click the **v** (menu / arrow) icon in the top-right corner of the Add-ons dialog and choose **Install from Disk...**.
5. Browse to `dist/devil_designer-0.10.0.zip` and click **Install from Disk**.
6. Locate **Devil Designer** in the add-on list and check its box to enable it.

!!! warning "Upgrading from an earlier version"
    If you are upgrading from a previous release of Devil Designer:
    
    1. Uncheck the previous version in **Preferences > Add-ons**.
    2. Restart Blender completely to flush any cached Python modules from memory.
    3. Install and enable **Devil Designer v0.10.0**.

---

## Launching the Editor

Once enabled, you can open Devil Designer from any 3D Viewport:

* **Keyboard Shortcut:** Press <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>D</kbd>.
* **Search:** Press <kbd>F3</kbd>, type `Devil Designer`, and press <kbd>Enter</kbd>.
* **Viewport Menu:** Click **View > Devil Designer** in the 3D Viewport header.

### Workspace Layout

The editor opens as an immersive, non-intrusive workspace:

* **100% Full-Screen Canvas:** A clean 2D workspace dedicated to pattern drafting, cutting, and sewing.
* **8-Tool Left Dock:** Quick access to Select (`V`), Polygon (`P`), Rectangle (`R`), Ellipse (`E`), Internal Line (`I`), Cut Knife (`N`), Sew (`J`), and Pin/Tack (`K`/`T`).
* **Micro-Indicators:** Persistent status toggles in the corner for Snapping (`[S]`), Body Guide (`[H]`), Segment Lengths (`[L]`), and Fit Map (`[F]`).
* **Contextual Right-Click Menus:** Right-clicking any element (a piece, point, edge, internal path, seam badge, anchor, or empty canvas) opens a compact, focused card right at your cursor.
* **Revealed 3D Viewport:** When 3D placement, sewing, or drape inspection is active, the 3D viewport is revealed alongside the canvas. Click **Full canvas** to return to the dedicated 2D view.
* **Interface Icons:** Public interface icons are sourced CC0 artwork from Kenney, Maki, and Temaki. Provenance and original licenses ship in `devil_designer/assets/icons`. The Blender renderer caches native GPU geometry with zero extra runtime dependencies.

### Exiting the Editor

* Press <kbd>Escape</kbd> when idle. Escape prioritizes active operations: it first cancels pending drafting or dragging gestures, then dismisses any open contextual menu, and finally exits the editor.
* Click the **Close** button in the header.
* Press <kbd>Ctrl</kbd> + <kbd>Alt</kbd> + <kbd>D</kbd> again.

---

## Verifying the Installation

To verify that the add-on passes all unit, integration, and publication tests:

```bash
# Fast headless unit tests
python -m unittest discover -s tests -p "test_*.py" -v

# Headless Blender integration test suites
blender --background --factory-startup --python-exit-code 1 --python tests/blender_smoke.py
blender --background --factory-startup --python-exit-code 1 --python tests/blender_garment.py
blender --background --factory-startup --python-exit-code 1 --python tests/blender_advanced.py
blender --background --factory-startup --python-exit-code 1 --python tests/blender_silhouette.py
blender --background --factory-startup --python-exit-code 1 --python tests/blender_density.py
blender --background --factory-startup --python-exit-code 1 --python tests/blender_arrangement.py
blender --background --factory-startup --python-exit-code 1 --python tests/blender_tack_binding.py
blender --background --factory-startup --python-exit-code 1 --python tests/blender_tracing.py
blender --background --factory-startup --python-exit-code 1 --python tests/blender_layering.py
blender --background --factory-startup --python-exit-code 1 --python tests/blender_piece_states.py
blender --background --factory-startup --python-exit-code 1 --python tests/blender_sewing_preview.py

# In-engine interactive GUI test suites
blender --factory-startup --python tests/gui_preview.py
blender --factory-startup --python tests/gui_design.py
blender --factory-startup --python tests/gui_silhouette.py

# Package build and extension validation
python tools/build.py
blender --background --factory-startup --command extension validate dist/devil_designer-0.10.0.zip

# Public publication and privacy audit
python tools/check_public.py
```

The publication audit checks source, archives, and reachable Git history to ensure no private account names, absolute machine paths, or unapproved commit identities are included. The product specification (`SPEC.md` in the repository root) records intended scope and implementation coverage.

---

## Developer Workspace & Scratch Discipline

When developing or contributing to Devil Designer:

* **`dist/`:** Holds the installable extension ZIP (`devil_designer-0.10.0.zip`) and is never auto-deleted.
* **`scratch/`:** Everything disposable belongs in the ignored `scratch/` directory: test scenes, backups, benchmark reports, screenshots, generated scripts, preview logs, icon downloads, temporary dependencies, and test garment libraries. Never place source files, required artwork, licenses, or user projects in scratch.

Use the developer runner script (`dev.cmd` on Windows or `tools/dev.py`) so child processes run cleanly without generating bytecode caches:

```cmd
# Run all test suites and package the extension
.\dev.cmd --test --build

# Run visual audits, retaining generated screenshots in scratch
.\dev.cmd --shots --keep-scratch
.\dev.cmd --inspect --keep-scratch

# Clean the disposable scratch workspace
.\dev.cmd --clean
```

The `--clean` command only deletes `scratch/`; it never deletes `dist/`, source files, or user projects. It refuses linked directories and reports locked files rather than force-closing Blender or discarding work. Close disposable preview windows before cleaning. Standalone test, screenshot, and icon utilities also write to `scratch/`; run `--clean` when finished.
