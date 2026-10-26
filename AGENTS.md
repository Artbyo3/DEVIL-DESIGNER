# DEVIL DESIGNER — AGENT GUIDELINES

## STRICT CODEBASE RULE: NO CODE COMMENTS
- **Comments in the code are strictly forbidden.**
- Do not write any inline (`# ...`) or block comments in any code files (`.py`, `.js`, `.sh`, `.cmd`, `.ps1`).
- Write clean, self-documenting code with descriptive function, variable, and class names.
- If existing comments are encountered anywhere in the codebase, remove them.

---

## ARCHITECTURE & IMPLEMENTATION PRINCIPLES
1. **Garment & Simulation Math Integrity**:
   - Zero modifications to garment algorithms, physics equations, or simulation math in `core.py`, `garment.py`, `meshing.py`, `placement.py`.
2. **UI & Rendering Architecture**:
   - Blender native GPU rendering (`gpu.shader.from_builtin('UNIFORM_COLOR')`, `POLYLINE_UNIFORM_COLOR`).
   - Shared computed bounds for rendering and hit detection.
   - Minimalist Apple-inspired design language with cohesive tokens (`ui_system.py`).
3. **UX & Workflow Priority**:
   - Prioritize user flow and time-to-first-garment.
   - Maintain guided stage flow (`DRAFT` -> `SEW` -> `ARRANGE` -> `SIMULATE` -> `KEEP`).
   - Keep empty states actionable with one-click creation templates.
   - Provide real-time feedback during sewing and authoring to prevent user errors before they happen.

---

## DEVELOPER WORKFLOW SHORTCUTS
Run the unified developer runner from the repository root:
- `.\dev.cmd --quick`: Fast headless unit tests (56 tests in ~0.15s)
- `.\dev.cmd --test`: Complete verification across all 8 test suites (~21s)
- `.\dev.cmd --build`: Packages extension zip, validates package with Blender, and syncs to user addons (~0.7s)
- `.\dev.cmd --shots`: Clean, unobstructed in-engine stage screenshots (~14s)
- `.\dev.cmd --inspect`: Slices and validates UI contrast and layout bounds
- `.\dev.cmd --all`: Full end-to-end test, build, screenshot, and inspect pass

All test suites must pass 100% with no regressions on every change.
