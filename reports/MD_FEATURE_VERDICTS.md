# Marvelous feature verdicts

Row-by-row ruling on `reports/md-feature-matrix-2026-11-03.md` in the main checkout, judged for fitted VRChat and game clothing made inside Blender. Have and Partial are from reading this code, not from retesting each row.

230 rows: 7 Added, 76 Have, 12 Partial, 51 Blender, 5 Later, 79 Reject.

## Corrections to the source report

- Row 2D CAD Pattern Import / Export cites `ExportDXF` in the API. The raw `list.html`, `changelog.html` and `optiontype.html` on developer.marvelousdesigner.com contain the string DXF zero times, checked on 2026-11-06. The same row in the export module list is also unsupported. The File menu entry it names could not be checked, because the support site blocks automated reads.
- The API does have `ExportPatternCPX`, a binary format with no public spec, and `ExportPatternJSON`, which is deprecated in 2026.1 and always returns false. Neither gives a usable migration path.

## Changes to the feature matrix

- Add row: Math in number fields, Yes.
- Add row: Convert to hole, Yes, shown as Cut out hole.
- Change row: Import OBJ as garment, dropped again by the artist on 2026-11-07.
- Change row: Global search, from Blender to Dropped, because F3 does not reach the custom editor tools.

## 1. 2D Pattern Drafting and Editing

| Feature | Verdict | Reason |
| --- | --- | --- |
| Transform Pattern | Have | Transform frame |
| Preserve 3D Garment Shape on 2D Scaling | Have | Keep 3D shape when scaling |
| Edit Pattern | Have | Select tool |
| Transform Point/Segment | Have | Transform frame on points |
| Polygon Lasso Selection | Have | Lasso in the Select flyout |
| Invert Selection (2D) | Have | Ctrl I |
| Edit Curvature | Have | Bend |
| Edit Curve Point | Have | Curve points |
| Convert to Curve Point / Convert to Segment Point | Have | C key |
| Smooth Curve | Have | Round corner in the point menu |
| Optimize Curve Points | Reject | Only pays off on dense imported outlines, which we do not import |
| Add Point/Split Line | Have | Double-click or Q; Split into 3 or 4 equal parts, or every 2 or 5 cm |
| Add Point to Intersection | Reject | Rare; a point can be placed by hand with snapping |
| Delete All Overlapping Points | Reject | Validation already refuses coincident points |
| Polygon | Have | Draw flyout |
| Rectangle | Have | Draw flyout, click for exact size |
| Ellipse | Have | Draw flyout, click for exact size |
| Spiral | Reject | Stays dropped; a long gathered strip covers ruffles |
| Create / Edit AI Bezier Curve | Have | Polygon tool |
| Pattern Drafter (Beta) & AI Pattern Drafter (Beta) | Reject | AI and beta; starters already size from the avatar |
| Trace | Have | Trace as piece |
| Offset Pattern Outline | Have | Offset outline |
| Slash & Spread | Have | Slash and spread |
| Fullness (Point) & Fullness (Line) | Reject | Slash and spread does the same job |
| Walk Pattern | Reject | Physical production, not game clothing |
| Merge & Merge Symmetric Patterns | Have | Merge pieces |
| Change Length | Have | Exact length; no start or end anchor |
| Match Up & Match 2D Pattern Measurements | Reject | Exact length plus the new field math covers it |
| Clone Pattern (With/Without Sewing), Copy, Paste & Mirror Paste | Have | Duplicate, Mirror |
| Layer Clone (Over / Under) | Have | Piece > Clone |
| Linked Editing (Symmetric Pattern & Instance Pattern) | Have | Linked twin |
| Unfold & Unfold Symmetric Editing (with Sewing) | Have | Unfold |
| Symmetry Sync for Half-Symmetric Patterns | Reject | Needs a change to protected meshing |
| Align & Distribute | Reject | Canvas tidying, more menu rows than it earns |
| Order, Rotate & Flip Horizontally/Vertically | Have | Flip and transform; draw order not needed |
| Notch & Edit Notch | Reject | Physical production, not game clothing |
| Seam Allowance | Reject | Physical production, not game clothing |
| Lock Pattern / Lock All Pattern Outlines | Reject | Blender H and undo cover the risk |
| Baselines (Convert to Baseline, Unlock All Baselines) | Reject | Reference lines are not needed in a game workflow |
| Grainline (Edit Texture (2D), Show Grainline) | Reject | Fabric has no direction in the solver yet |
| Pattern Annotation & Edit Annotation | Reject | Blender annotate exists |
| Create / Show 2D Measurements | Reject | Lengths overlay covers the common case |
| Real-Time Arithmetic Input Updates in Ghost and Numeric Fields | Added | Blender fields do this, so a custom field that refuses it feels broken |

## 2. Internal Lines, Darts and Pleats

| Feature | Verdict | Reason |
| --- | --- | --- |
| Internal Polygon/Line | Partial | Works, still hard to use, #84 |
| Internal Rectangle | Have | Internal flyout |
| Internal Ellipse | Have | Internal flyout |
| Offset as Internal Line & Offset as Internal Line along Curve | Have | Offset copy on internal lines |
| Add Perpendicular Internal Line | Reject | Rare; snapping covers it |
| Group Internal Lines and Shapes | Reject | Few internal lines per piece in game clothing |
| Unlink Internal Line Symmetry | Reject | Too niche |
| Convert to Hole / Convert to Internal Shape | Added | Already worked but hidden behind Cut along path; the row now reads Cut out hole |
| Clone as Pattern / Clone as Internal Shape | Have | Trace as piece; Clone as internal stays dropped |
| Extend/Trim & Add Point to Pattern Outline / Internal Line | Partial | Lines snap to the outline; no trim tool, part of #84 |
| Divide Internal Lines / Divide Internal Point | Reject | Too niche |
| Cut & Cut & Sew | Have | Cut, Cut and sew |
| Dart (Internal Diamond Dart) | Have | Dart |
| Segment Darts (Add Dart, Edit Dart, Rotate Dart, Shape Dart) | Later | Real pattern tool but the diamond dart covers fit; revisit if artists ask |
| Pleats (Pleat Creation Tool) | Have | Fold menu |
| Pleats Fold | Have | Knife, Box, Accordion |
| Pleats Sewing | Have | Fold menu |
| Fold Arrangement | Later | Already Not yet; collars and cuffs, needs a 3D fold gizmo |
| Fold Angle, Fold Strength & Fold Rendering | Partial | Preset angles only |
| Internal Line Variable Fold Angle | Reject | Build on real fold angles first; preset folds do not need it |

## 3. Sewing

| Feature | Verdict | Reason |
| --- | --- | --- |
| Segment Sewing (2D) | Have | Sew tool |
| 1:N Segment Sewing (2D) & M:N Segment Sewing (2D) | Have | Sew flyout |
| Free Sewing (2D) | Have | Sew flyout |
| 1:N Free Sewing (2D) & M:N Free Sewing (2D) | Have | Sew flyout |
| 3D Segment Sewing & 3D M:N Segment Sewing | Have | 3D sewing |
| 3D Free Sewing & 3D M:N Free Sewing | Have | 3D sewing |
| Auto Sewing | Have | Auto sew, a guess |
| Edit Sewing (2D & 3D) | Have | Drag seam ends |
| Reverse Sewing | Have | Seam menu |
| Activate / Deactivate Sewing Lines | Added | Seam menu, Sewing On/Off; kept in the pattern |
| Check Sewing Length | Have | Pass and Gather warnings |
| [Beta] Seamline Ripping Tool (Seamline Rip & Edit Rip Tool) | Reject | Tearing cloth is not a VRChat clothing need |
| Seamline Property (Line Type: Turned / Flat, Sewing Line Angle, Fold Strength, Tension, Sublayer, 3D Seamline) | Reject | Per-seam construction detail the solver cannot express today |
| Weld Turned Seamlines & Seamline Sync during Export | Have | Keep welds seams; no turned seams exist here |
| Tack & Tack on Avatar | Have | Pin flyout |
| Line Tack on Garment & Line Tack on Avatar | Reject | Stays dropped; Pin Edge and tacks cover it |
| Edit Tack, Edit Line Tack & Copy/Paste/Mirror Paste Tack | Reject | Stays dropped |
| Standalone Shirring Tool | Reject | CLO only; Elastic plus M:N covers gathers |

## 4. 3D Arrangement, Avatar and Pose

| Feature | Verdict | Reason |
| --- | --- | --- |
| Select/Move (3D) & 3D Gizmo (Screen, World, Local, Unified, Divided) | Blender | Blender G and R |
| Arrange Pattern with Arrangement Points | Have | Arrangement points |
| Add / Edit Arrangement Points & Bounding Volumes | Have | Edit bounding volumes |
| Reset 2D Arrangement (All / Selected) | Have | Reset to layout |
| Reset 3D Arrangement (All / Selected) | Have | Reset drape |
| Re-drape 3D Arrangement | Have | Drape carries across edits |
| Symmetrical 3D State (Copy Symmetric Arrangement) | Reject | Linked twin covers the 2D side; rarely needed in 3D |
| Flip Normal | Blender | Blender flip normals after Keep |
| Align Collision Direction with Render Direction | Reject | No single-sided collision setting in our solver |
| Freeze / Unfreeze | Have | Freeze |
| Strengthen / Unstrengthen | Have | Strengthen |
| Solidify | Reject | Stays dropped; Freeze and Strengthen cover it |
| Deactivate (Pattern & Sewing) & Deactivate (Pattern Only) | Have | Deactivate |
| Hide / Show 3D Pattern & Isolate Selection | Blender | Blender H and local view |
| Pattern Archive | Reject | Deactivate covers it |
| Avatar Editor (Unified Tabs) | Reject | Blender is the avatar editor |
| Show Avatar Joints (Shift+X), FK Joint Gizmo & IK Joint Mapping / IK Mode | Blender | Blender armature posing |
| AI Pose Generator (Beta) | Reject | AI pose, and Blender posing already exists |
| Blend Shape Avatar & Blend Shape Animation | Blender | Blender shape keys, then drape on that pose |
| Change Pose by OBJ / AVT Morphing (Load as Morph Target) | Blender | Blender shape keys |
| Auto Convert to Avatar | Reject | Marvelous skeleton only |
| Soft Body Simulation for Avatars (CPU & GPU) | Reject | Stays dropped; large solver work for a small visual gain |
| Avatar Surface & Collision Properties (Skin Offset, Friction, Smooth Avatar, Show Wireframe) | Have | Skin offset and Friction (Slippery, Normal, Grippy); smoothing is Blender |
| Avatar & 3D Garment Measure Tools | Blender | Blender Measure tool |
| 3D Pen (Avatar) & Edit 3D Pen (Avatar) | Partial | Draw on avatar, curved areas approximate |
| 3D Pencil (Avatar) & Symmetry Side Lock | Reject | Blender grease pencil can sketch guides |
| 3D Pen (Garment) & Edit 3D Pen (Garment) | Have | On garment |
| Flatten & Flattening as Straight Line | Partial | Flattens, curved areas approximate |

## 5. Simulation and Live Interaction Tools (Including Exhaustive Pinching & Pinning Family)

| Feature | Verdict | Reason |
| --- | --- | --- |
| Simulate (Normal / CPU) & Complete (Nonlinear) Simulation | Have | Simulate; solver presets are fixed by design |
| GPU Simulation (Windows CUDA & macOS Metal) | Have | Geometry Nodes solver, one PC tested, #118 |
| Simulation Properties (Time Step, Number of Simulation, CG Finish/Iteration, Gravity, Air Damping, Collision) | Partial | Quality chips and gravity from the scene; no raw solver panel, on purpose |
| Use Layer (Layer & Sublayer) | Have | Wear over layering; no per-piece layer number |
| Wind Controller (Planar / Spherical) | Reject | Stays dropped; static clothing |
| [Pinching Family 1] Select/Move Hand Tool (Single-Point Live Drag) | Have | Grab |
| [Pinching Family 2] Quick Pinching | Have | Grab radius |
| [Pinching Family 3] Advanced Pinching with Soft Selection | Reject | Grab radius covers the common need |
| [Pinching Family 4] Brush Pinching | Added | Pinch paints along a drag |
| [Pinching Family 5] Pinching Simulation Override & Rest Shape Update | Reject | Tuning on top of a feature we only have partly |
| [Pinching Family 6] Sculpt Tool — Pinch Brush (plus Grab, Standard, Smooth, Inflate, Flatten, Mask) | Blender | Blender Sculpt mode, after Keep |
| [Pinning Family 7] Quick Single-Point Pin (W + Click) | Have | Pin tool |
| [Pinning Family 8] Pin (Box) | Have | Pin flyout, Box |
| [Pinning Family 9] Pin (Lasso) | Later | Box covers most; add if artists ask |
| [Pinning Family 10] Pin (Brush) / Select Mesh (Brush / Box / Lasso) | Reject | Grab radius and Pin Box cover it |
| [Pinning Family 11] Pin Entire Segment / Pattern & Add/Subtract Modifiers | Have | Pin flyout, Edge |
| [Pinning Family 12] Pin Group Selection, Gizmo Manipulation & Keyframing | Have | Grab Pin mode moves pins; keyframes are not needed |
| [Pinning Family 13] Attach Pin to Avatar / Detach Pin from Avatar | Have | Tack to body |
| [Pinning Family 14] Duplicate Pins to Symmetric Pattern | Reject | Too niche; pinning twice is quick |
| [Pinning Family 15] Delete Selected Pin / Delete All Pins | Have | Remove pin |
| Garment Fit Maps (Stress Map, Strain Map, Fit Map, Show Pressure Points) | Have | Fit map; stress and pressure stay out |

## 6. Fabric and Material Properties

| Feature | Verdict | Reason |
| --- | --- | --- |
| Fabric Physical Property Presets & Open/Save Fabric (.zfab / .psp) | Have | Six presets, saved custom fabric |
| Stretch-Weft, Stretch-Warp & Shear | Added | Weft stretch and Bias stiffness as ratios of the warp stretch |
| Bending-Weft, Bending-Warp & Bending-Bias | Partial | Bending only; no directional split |
| Buckling Ratio & Buckling Stiffness (Weft / Warp / Bias) | Later | Stays Later |
| Internal Damping, Weight (gsm) & Friction Coefficient | Partial | Mass and body friction; damping not exposed |
| Particle Distance | Have | Coarse to Ultra |
| Add'l Thickness - Collision & Add'l Thickness - Rendering | Partial | Skin offset and Keep thickness |
| Add Pattern Thickness, Curved Side Geometry & Mesh Style (Triangle, Quad (Optimized), Quad (Grid)) | Partial | Solidify and Faces: Quads on Keep (mostly quads); a clean quad grid is #54 |
| Express Air Pressure (Pressure) | Partial | Puff, approximate |
| Material Shader Types (Fabric_Matte, Shiny, Silk/Satin, Velvet, Leather, Metal, Plastic, Transparent, Iridescent, Fur (Render), Fur_Strand, Toon) | Blender | Blender shaders |
| PBR Texture Maps (Base Color, Normal, Displacement, Opacity, Roughness, Metalness, SSS, Anisotropy) | Blender | Blender materials |
| Import All PBR Maps Once | Blender | Blender Node Wrangler |
| Open Selected Material from ZFAB & Swap Front/Back Material | Blender | Blender materials |
| PBR Map Generator, AI Texture Generator & AI Graphic Generator | Reject | AI and texture generation; out of scope |
| Substance (.sbsar) Procedural Materials | Blender | Blender and Substance |

## 7. Trims, Notions and Hardware

| Feature | Verdict | Reason |
| --- | --- | --- |
| Zipper (Create Zippers) | Reject | Model it as a mesh in Blender |
| Edit Zipper | Reject | Model it as a mesh in Blender |
| Zipper End Extension | Reject | Model it as a mesh in Blender |
| Register Custom OBJ to Zipper Component (Teeth, Slider, Puller, Stopper) | Reject | Model it as a mesh in Blender |
| Zipper Style (.zps), Tape, Slider & Stopper Properties | Reject | Model it as a mesh in Blender |
| Lacing Tool | Reject | Stays dropped; model it as a mesh in blender |
| Edit Lacing Tool | Reject | Stays dropped |
| Button (Create Button) & Buttonhole (Create Buttonhole) | Reject | Model it as a mesh in Blender |
| Select/Move Button & Fasten Button | Reject | Model it as a mesh in Blender |
| Button Style Property Editor & Register Custom OBJ as Button | Reject | Model it as a mesh in Blender |
| Piping & Edit Piping | Reject | Model it as a mesh in Blender |
| Binding & Select Binding | Reject | A strip sewn to the edge does this |
| Trims / OBJ Trim (.trm) & GPU-Accelerated Trim Simulation | Blender | Blender parenting |
| Convert Patterns to Trims and Accessories & Register Rigged Accessories (.zacs) | Reject | Kept mesh already is a normal Blender object |
| Topstitch (Segment, Free, Seamline, Edit Topstitch & Topstitch Style) | Blender | Texture work |
| Puckering (Segment, Free, Seamline, Edit Puckering & Puckering Style) | Blender | Texture work |
| Elastic & Seam Taping | Have | Elastic; seam taping is production |
| Bond & Skive | Reject | Strengthen covers stiffness |

## 8. Grading and Sizing

| Feature | Verdict | Reason |
| --- | --- | --- |
| Auto Fitting | Partial | Proportional refit, not a true fit |
| Pattern Drafter: Match to Avatar Size & Points of Measure (POM) | Reject | Starters already size from the avatar |
| Shrink Pattern (Shrinkage Weft / Shrinkage Warp) | Added | Fabric Shrink lengthwise and widthwise, up to 30% |
| Steam (Partial Shrinkage Brush) & Steam Eraser Brush | Added | Steam paints along a drag; Clear exists |
| Avatar Size Editor & Scale Avatars | Blender | Blender scale |
| Pattern Grading (Size Group, Offset Grading, Grading Rules, Graphic Grading, Auto Grading) | Reject | CLO only and production |
| Standalone POM (Point of Measure) Tech-Pack Tab | Reject | CLO only and production |

## 9. UV and Texture Work

| Feature | Verdict | Reason |
| --- | --- | --- |
| [Mode] UV Editor | Blender | Blender UV Editor |
| Reset to 2D Arrangement & Fit All UV (to 0–1) | Have | UVs come from the pattern |
| UDIM Multi-Tile Support & Move UV with Value | Blender | Blender UDIM |
| Automatic UV Packing (UV Packing) | Blender | Blender Pack Islands |
| Select All with Same Property in UV Editor | Blender | Blender select similar |
| Bake Textures | Blender | Blender Bake |
| Unified UV Coordinates (Unified Map) | Have | UVs from pattern |
| Garment OBJ UV Preservation | Reject | Dropped with Import OBJ |
| Avatar UV Display | Blender | Blender UV Editor |
| Edit Texture (2D & 3D) | Blender | Blender UV and materials |
| Graphic (2D Pattern / 3D Pattern) & Transform Graphic | Blender | Blender and Substance |
| Lock Graphics (Lock Placement) | Reject | No graphics here |
| Graphic On/Off Toggle | Reject | No graphics here |
| Maintain Graphics & Seam Lines on Fur (Fur Trimmer) | Reject | No fur here |
| Standalone Colorway Editor / Colorway Mode | Reject | CLO only |

## 10. Rendering, Animation and Export (Including Retopology & EveryWear)

| Feature | Verdict | Reason |
| --- | --- | --- |
| 3D Garment & Avatar Surface Rendering Styles | Blender | Blender viewport shading |
| Schematic Render (Alt+0) & Local Schematic Scale for Topstitch | Reject | Tech-sheet output |
| Toon Shader / Express Cartoon (MToon) | Blender | Blender shaders; VRM has its own add-on |
| Render Mode (CPU / NVIDIA GPU / Apple Metal Path Tracer) | Blender | Blender Cycles |
| Render Lighting (Dome, Rectangle, Sphere, Spot, Directional) & Shadow Catcher | Blender | Blender lights |
| Viewport Camera, Depth of Field & Custom View (5, 2, 8, 4, 6, 0) | Blender | Blender cameras |
| 3D Snapshot, 2D Snapshot, Turntable Images & Turntable Video | Blender | Blender render and screenshot |
| [Mode] Animation (Timeline, Record, Play, Scene Time Warp, Play Region, Timeline Marker) | Blender | Blender timeline |
| Keyframe Animation, Hierarchical Animation Layers & Bake Keyframes | Blender | Blender keyframes |
| Auto Convert to Motion | Blender | Blender retargeting |
| [Mode] Retopology (Create Patch, Create Topology, Edit Topology, Symmetry, Ghost, Subdivide, Remeshing) | Blender | Blender retopology |
| EveryWear (Beta) — Real-Time Game Garment Optimization & Auto-Rigging Suite | Later | Parked by the artist: rigging, LOD and baking stay in Blender |

## 11. Import / Export Formats

| Feature | Verdict | Reason |
| --- | --- | --- |
| Native Project & Garment Formats (.zprj, .zpac, .gar, .pos, .mtn, .avt, .avs, .zfab, .psp, .trm, .zacs, .zps, .sst, .pkr) | Have | Blender file and library file |
| 3D File (OBJ) Import / Export (.obj) — Avatar, Garment, Trim & Morph Target | Reject | Dropped by the artist for now; Blender imports and exports OBJ meshes |
| 3D File (FBX) Import / Export (.fbx) | Blender | Blender FBX |
| 3D File (Alembic) Import / Export (.abc — Ogawa & HDF5) | Blender | Blender Alembic |
| 3D File (USD) Import / Export (.usd, .usda, .usdc, .usdz) & USD Layering | Blender | Blender USD |
| glTF 2.0 (.gltf / .glb) Import / Export | Blender | Blender glTF |
| VRM File (.vrm) Import / Export | Blender | VRM add-on for Blender |
| MetaHuman DNA Importer (.dna) | Reject | MetaHuman is not our audience |
| Point Cache Animation Import / Export (.mc, .mcx, .pc2, .mdd) | Blender | Blender cache tools |
| 2D CAD Pattern Import / Export (.dxf ASTM/AAMA, .ai, .pdf) | Reject | Report row not confirmed; DXF appears nowhere in the API docs it cites, see below |
| Legacy 3D Formats: COLLADA (.dae), Modo (.lxo) & 3ds Max (.3ds) | Blender | Blender import |
| Import and Export Presets & Unreal Engine LiveSync (CLO/MD LiveSync) | Reject | Stays dropped |

## 12. API, Scripting and Automation

| Feature | Verdict | Reason |
| --- | --- | --- |
| Python Editor & Interactive Console (Python Script) | Blender | Blender Python |
| Plug-in Management (Configure Plug-ins) | Blender | Blender add-ons |
| PySide6 GUI API (QtWidgets, QtCore, QtGui, Non-Modal Dialogs & Background Task Runner) | Blender | Blender Python UI |
| import_api Module (ImportFile, ImportZprj, ImportAvatar, ImportPose, ImportOBJ, ImportFBX, ImportUSD, ImportAlembic, ImportVRM, ImportGarment, ImportSubstanceFile) | Blender | Blender Python |
| export_api Module (ExportZPrj, ExportZPac, ExportOBJ, ExportFBX, ExportUSD, ExportGLTF, ExportGLB, ExportAlembic, ExportVRM, ExportVertexCache, ExportDXF, ExportSnapshot3D, ExportTurntableImages, ExportAnimationVideo, ExportRenderingImage) | Blender | Blender Python |
| pattern_api Module (2D Drafting, Editing, Sewing, Pleats, Symmetry, Archive & UV Space Packing) | Reject | Project Python API is not a current need |
| fabric_api Module (Fabrics, PBR Maps, Substance Presets & Physical Properties) | Reject | Project Python API is not a current need |
| utility_api Module (Simulation, Wind, Animation Recording, Camera, Schematic Render, Auto Fitting & History) | Reject | Project Python API is not a current need |
| ApiTypes Module (Structured Option Objects) | Reject | Project Python API is not a current need |
| Silent Install (No-GUI Command-Line Installation) | Reject | Extensions platform handles install |

## 13. UI and Workflow Features

| Feature | Verdict | Reason |
| --- | --- | --- |
| Global Search | Reject | Corrected from Blender; F3 does not reach our custom tools, and nine tools do not need search |
| Customize Toolbar | Reject | No user layout editor; the dock grows when a tool needs a slot |
| Custom UI Layout & Split Window View | Blender | Blender workspaces |
| Workspace Mode Selector (Simulation, Animation, Modular, UV Editor, Retopology, Render) | Blender | Blender workspaces |
| [Mode] Modular & Modular Library | Reject | Stays dropped; starters and library cover it |
| Tab-Formatted Object Browser & Scene Browser | Reject | Right-click menus replace it |
| Property Editor & History Window | Reject | Right-click menus replace it; undo exists |
| New Library Window (Assets, CONNECT, CLO-SET) & Set Download Folder Path for CONNECT | Have | Garment library |
| User Settings / Preferences, View Controls & Shortcuts | Blender | Blender preferences |
| Set Default Files | Blender | Blender startup file |
| 3D Garment Information Metadata | Have | Library names and tags |
