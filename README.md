<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs-site/docs/assets/readme-logo-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="docs-site/docs/assets/readme-logo-light.svg">
    <img alt="Devil Designer logo" src="docs-site/docs/assets/readme-logo-dark.svg" width="140">
  </picture>
</p>

# Devil Designer

A movable 2D clothing-pattern editor and cloth authoring tool for Blender.

## Documentation

Full documentation, user guides, pattern drafting manuals, and simulation references are hosted at:

**https://artbyo3.github.io/DEVIL-DESIGNER/**

## Installation

Download `devil_designer-0.11.0.zip` from [Releases](https://github.com/Artbyo3/DEVIL-DESIGNER/releases) or build it locally with `python tools/build.py`, then install in Blender via **Edit > Preferences > Add-ons > Install from Disk...**.

For full setup details, requirements, and upgrading instructions, see the [Installation Guide](https://artbyo3.github.io/DEVIL-DESIGNER/install/).

## Fold lines and pleats

Draw a straight internal path from one boundary of a pattern piece to the other.
Right-click its edge and choose **Fold or pleat**. Choose Mountain, Valley, Knife,
or Box; pleats offer 1, 2, and 4 cm fold-pair spacing. Arrows and labels show the
direction before simulation. Right-click a fold again to reverse the whole pleat,
choose 60, 120, or 150 degrees, or remove its fold settings while keeping the paths.

Continue through Sew, Arrange, Simulate, and Keep as usual. Fold settings belong
to the pattern and survive the garment library, saved files, and undo. This first
version supports parallel, straight, boundary-to-boundary folds on each piece;
curved, partial, crossing, and hole-crossing folds are not supported. Folded pieces
use flat placement at arrangement points rather than automatic body wrapping.

Fold-containing garments use **1 mm self-collision for every piece in that
simulation**, including pieces without folds. Garments without folds retain the
existing 3 mm setting unless seam shrink already requires 1 mm. Smaller collision
clearance can allow closer layers; inspect the whole garment, not just its pleats.
Classic cloth can relax folds under load; material, mesh density, attachment, and
simulation duration still matter. No alternative cloth solver is used.

Darts have no new depth cap or altered algorithm. Regression fixtures exercise
49.9 cm darts in a 50 cm panel. Keep the apex inside valid fabric, and do not pin
both dart-mouth endpoints apart when testing closure.

## Links

- [Documentation](https://artbyo3.github.io/DEVIL-DESIGNER/)
- [Releases](https://github.com/Artbyo3/DEVIL-DESIGNER/releases)
- [Issues](https://github.com/Artbyo3/DEVIL-DESIGNER/issues)
- License: [GPL-3.0-or-later](LICENSE)
