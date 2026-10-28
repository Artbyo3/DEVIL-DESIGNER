import inspect
import json
import math
import runpy
from dataclasses import replace
from pathlib import Path

import bpy

from devil_designer import garment, seam_shrink
from devil_designer.core import Session
from devil_designer.density import boundary_plan
from tools.check_comments import check_source


def run(check):
    root = Path(__file__).resolve().parents[1]
    helpers = runpy.run_path(str(root / "tests" / "blender_seam_shrink_prototype.py"))
    scene = bpy.context.scene
    garment.reset(bpy.context)
    scene.dd_quality = 12
    scene.dd_spacing = .03
    scene.dd_frames = 120
    session = Session()
    session.add([(0, 0), (.2, 0), (.2, .2), (0, .2)])
    session.add([(.3, 0), (.5, 0), (.5, .2), (.3, .2)])
    first, second = session.document.patterns
    session.sew(session.document.edge(first.id, 1), session.document.edge(second.id, 3))
    scene.dd_document = session.document.dumps()
    garment.build_panels(bpy.context)
    source = inspect.getsource(garment.compile_garment)
    hook = "    if any(seam.shrink for seam in doc.seams):\n        seam_shrink.apply(doc,obj,cloth,maps,plan)\n"
    scoped = "(.001 if any(seam.shrink for seam in doc.seams) else .003)/metres_per_unit(scene)"
    if source.count(hook) != 1 or source.count(scoped) != 1:
        raise AssertionError("Approved hook or collision scope changed.")
    baseline_source = source.replace(hook, "").replace(scoped, ".003/metres_per_unit(scene)").replace("def compile_garment(", "def baseline_compile(", 1)
    check_source(baseline_source, "baseline_compile.py")
    namespace = dict(garment.__dict__)
    exec(compile(baseline_source, "<pre-shrink-baseline>", "exec"), namespace)
    baseline = namespace["baseline_compile"](bpy.context)
    original = helpers["compiled_snapshot"](baseline)
    baseline_frames = [helpers["evaluate"](baseline, frame) for frame in range(1, 122)]
    garment.reset(bpy.context)
    candidate = garment.compile_garment(bpy.context)
    snapshot = helpers["compiled_snapshot"](candidate)
    components = {key: original[key] == snapshot[key] for key in original}
    errors = []
    for frame, expected in enumerate(baseline_frames, 1):
        actual = helpers["evaluate"](candidate, frame)
        errors.append(max(math.dist(first, second) for first, second in zip(actual, expected)))
    check(all(components.values()), "production Shrink zero preserves all ten compiled snapshot components exactly")
    check(max(errors) <= 1e-6, "production Shrink zero matches baseline in every evaluated frame within 1e-6")
    check(candidate.vertex_groups.get("DD Seam Shrink") is None, "production zero bypasses the Shrink group hook")
    report = dict(zero_components=components, zero_frame_errors=errors, zero_maximum=max(errors), trials=[])
    for partial, chained in ((False, False), (True, False), (False, True)):
        for reverse in (False, True):
            for shrink in (0, 10, 20, 30):
                garment.reset(bpy.context)
                current = Session()
                current.add([(0, 0), (.2, 0), (.2, .2), (0, .2)])
                current.add([(.3, 0), (.5, 0), (.5, .2), (.3, .2)])
                first, second = current.document.patterns
                first_edges, second_edges = current.document.edges(first.id), current.document.edges(second.id)
                if partial:
                    sides = [replace(first_edges[1], t0=.2, t1=.8)], [replace(second_edges[3], t0=.1, t1=.9)]
                elif chained:
                    sides = first_edges[:2], second_edges[2:]
                else:
                    sides = [first_edges[1]], [second_edges[3]]
                current.sew_chains(*sides, reverse=reverse)
                current.set_seam_shrink(current.document.seams[0].id, shrink)
                scene.dd_document = current.document.dumps()
                obj = garment.compile_garment(bpy.context)
                cloth = next(modifier for modifier in obj.modifiers if modifier.type == "CLOTH")
                document = garment.document(scene)
                maps = {}
                offset = 0
                for panel in garment.generated(scene, "panel"):
                    maps[panel["dd_pattern_id"]] = {key: [(fraction, vertex + offset) for fraction, vertex in values] for key, values in json.loads(panel["dd_edge_samples"]).items()}
                    offset += len(panel.data.vertices)
                plan = boundary_plan(document, scene.dd_spacing)
                expected = seam_shrink.boundary_weights(document.seams, maps, plan)
                group = obj.vertex_groups.get("DD Seam Shrink")
                actual = {vertex.index: item.weight for vertex in obj.data.vertices for item in vertex.groups if group and item.group == group.index}
                check(set(actual) == set(expected) and all(abs(actual[index] - weight) <= 1e-7 for index, weight in expected.items()),
                      f"compiled {shrink}% both-side membership: partial={partial}, chained={chained}, reverse={reverse}")
                distance = (.001 if shrink else .003) / garment.metres_per_unit(scene)
                check(abs(cloth.collision_settings.self_distance_min - distance) <= 1e-7 and cloth.settings.sewing_force_max == 50, "collision scope follows garment Shrink without altering sewing force")
                check(bool(cloth.settings.vertex_group_shrink) == bool(shrink), "only nonzero garments enable native shrink")
                report["trials"].append(dict(shrink=shrink, partial=partial, chained=chained, reverse=reverse, vertices=len(expected)))
    expected = scene.dd_document
    filename = root / "scratch" / "seam-shrink-persistence.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(filename))
    bpy.ops.wm.open_mainfile(filepath=str(filename))
    check(bpy.context.scene.dd_document == expected and garment.document(bpy.context.scene).seams[0].shrink == 30, "nonzero Shrink survives native blend save and reopen")
    saved = garment.generated(bpy.context.scene, "simulation")[0]
    check(saved.vertex_groups.get("DD Seam Shrink") is not None, "Shrink group survives native blend save and reopen")
    scene = bpy.context.scene
    garment.reset(bpy.context)
    scene.unit_settings.scale_length = .01
    scaled = garment.compile_garment(bpy.context)
    cloth = next(modifier for modifier in scaled.modifiers if modifier.type == "CLOTH")
    check(abs(cloth.collision_settings.self_distance_min - .1) < 1e-7, "scoped collision remains one physical millimetre with scaled scene units")
    (root / "scratch" / "seam-shrink-production-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
