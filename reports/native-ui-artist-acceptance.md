# Native minimal UI artist acceptance

## Accepted outcome

Make the minimal interface feel native to Blender while preserving the brand palette, saved garment compatibility, and protected garment math.

On November 1, 2026, the artist reported PASSED, with the qualification "not perfect but it passes". The follow-up instruction explicitly states "This is artist acceptance: ship it" and authorizes committing the UI work, pushing it, opening a PR, and merging to master once checks pass.

This acceptance does not authorize a release, version bump, docs-site changes, or protected garment-math changes.

## Accepted artifact identity

- Installable artifact: `devil_designer-0.11.0.zip`.
- Tested ZIP SHA-256: `2b55be79c0f825d2c5e6030e69a9b6f3b5e037ac4ec1eea986de74a120895d9f`.
- Tested packaged-source fingerprint: `cf7d449c5402679e3b418f7726a0529a638019c3c05f1aed41560e14474890bb`.
- Fingerprint algorithm: SHA-256 over sorted archive-relative paths, NUL, and each file's SHA-256 digest.
- The tested source was the dirty working tree based on `f034912a258e426636174596f15655c832adf6d3`, not a previously committed application tree.
- Verification at acceptance: all 11 real-Blender background suites, all 10 GUI suites with 912 checks, Blender package validation, and the packaged-module import gate pass. The independent compact-card review reports 1,080 layout cases with zero failures.

## Shipping boundary

Commit the accepted UI, its library-presentation dependencies, stock icon assets and provenance, generator, and relevant verification tests. Preserve unrelated local reports and prototypes.

Do not include any `docs-site/` changes or README/SPEC edits. The accepted ZIP contains a pre-existing icon README edit; leave that local edit outside the shipping commit. A rebuilt shipping package may therefore differ in `assets/icons/README.md` only as documentation, and in `assets/icons/sources.json` only through Git's configured LF normalization. Verify all other packaged bytes are identical and that icon provenance JSON is otherwise unchanged. These non-behavioral differences do not invalidate artist acceptance.

Require fresh verification on the committed source before merge, green remote checks, independent real-Blender verification, package/source equality, post-merge verification, and the repository's safe branch/worktree cleanup audit. If any executable behavior changes, preserve this acceptance record and request only the affected artist checks instead of silently applying acceptance to different behavior.
