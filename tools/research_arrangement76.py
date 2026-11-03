import ast
import cProfile
import hashlib
import io
import json
import math
import os
from pathlib import Path
import pstats
import statistics
import sys
import time
import tokenize
import bpy
from mathutils.bvhtree import BVHTree

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import devil_designer
from devil_designer import arrangement, garment
from devil_designer.core import Session, arrangement_record
from devil_designer.ellipse_volumes import directional_radius, section_at_height
from tools.workspace import prepare_scratch

output = prepare_scratch()
devil_designer.register()
scene = bpy.context.scene
scene.dd_spacing = .015
result = json.loads((output / 'issue76-evidence.json').read_text(encoding='utf-8')) if '--wrap-only' in sys.argv else dict(blender=bpy.app.version_string, processors=os.cpu_count(), timing=[], cases=[])
result['production_sha256'] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                             for path in sorted((ROOT / 'devil_designer').rglob('*.py'))}
for segments, rings in (() if '--wrap-only' in sys.argv else ((24, 16), (48, 32), (96, 64))):
    scene.dd_avatar = None
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    parts = []
    for position, scale in (((0, 0, 1.15), (.26, .15, .4)), ((0, 0, 1.7), (.12, .12, .16)),
                            ((-.42, 0, 1.38), (.27, .08, .08)), ((.42, 0, 1.38), (.27, .08, .08)),
                            ((-.13, 0, .45), (.105, .11, .45)), ((.13, 0, .45), (.105, .11, .45))):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, location=position)
        body_part = bpy.context.object
        body_part.scale = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        parts.append(body_part)
    bpy.ops.object.select_all(action='DESELECT')
    for body_part in parts:
        body_part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    avatar = bpy.context.object
    avatar.data.calc_loop_triangles()
    fresh, cached = [], []
    for repeat in range(5):
        scene.dd_avatar = None
        if 'dd_arrangement_volumes' in avatar:
            del avatar['dd_arrangement_volumes']
        started = time.perf_counter()
        scene.dd_avatar = avatar
        fresh.append(time.perf_counter() - started)
        assert len(json.loads(avatar['dd_arrangement_volumes'])['volumes']) == 12
        scene.dd_avatar = None
        started = time.perf_counter()
        scene.dd_avatar = avatar
        cached.append(time.perf_counter() - started)
    profiler = cProfile.Profile()
    profiler.runcall(arrangement.ensure_volumes, bpy.context, True)
    profile_text = io.StringIO()
    pstats.Stats(profiler, stream=profile_text).sort_stats('cumulative').print_stats(16)
    result['timing'].append(dict(vertices=len(avatar.data.vertices), triangles=len(avatar.data.loop_triangles),
                                 fresh_seconds=fresh, cached_seconds=cached, median_fresh_seconds=statistics.median(fresh),
                                 median_cached_seconds=statistics.median(cached), profile=profile_text.getvalue()))
    (output / 'issue76-evidence.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('TIMING', len(avatar.data.loop_triangles), statistics.median(fresh), flush=True)
scene.dd_avatar = None
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
body_vertices, body_faces = [], []
heights = sorted(set([index * 1.8 / 180 for index in range(181)] + [1.174, 1.18, 1.186]))
for height in heights:
    bulge = max(0, 1 - abs(height - 1.18) / .012)
    for segment in range(96):
        angle = math.tau * segment / 96
        body_vertices.append((.23 * math.sin(angle), -(.14 + .085 * bulge) * math.cos(angle), height))
for level in range(len(heights) - 1):
    for segment in range(96):
        following = (segment + 1) % 96
        body_faces.append((level * 96 + segment, level * 96 + following,
                           (level + 1) * 96 + following, (level + 1) * 96 + segment))
body_faces.extend((tuple(reversed(range(96))), tuple((len(heights) - 1) * 96 + segment for segment in range(96))))
body_mesh = bpy.data.meshes.new('Issue76WaistBulgeMesh')
body_mesh.from_pydata(body_vertices, [], body_faces)
avatar = bpy.data.objects.new('Issue76SyntheticUnsampledTorsoBulge', body_mesh)
scene.collection.objects.link(avatar)
bpy.context.view_layer.update()
scene.dd_avatar = avatar
body_mesh.calc_loop_triangles()
body_triangles = [tuple(triangle.vertices) for triangle in body_mesh.loop_triangles]
body_tree = BVHTree.FromPolygons(body_vertices, body_triangles, all_triangles=True)
control_vertices = [(.23 * math.sin(math.tau * segment / 96), -.14 * math.cos(math.tau * segment / 96), height)
                    for height in heights for segment in range(96)]
control_tree = BVHTree.FromPolygons(control_vertices, body_triangles, all_triangles=True)
result['cases'] = []
for label, outline in (('rectangle', [(-.24, -.28), (.24, -.28), (.24, .28), (-.24, .28)]),
                       ('concave_long_tab', [(-.24, -.28), (-.08, -.28), (-.08, -.08), (.24, -.08), (.24, .28), (-.24, .28)])):
    session = Session()
    session.add(outline)
    pattern = session.document.patterns[0]
    pattern.name = label
    pattern.arrangement = arrangement_record('waist', 'front', version=2)
    scene.dd_document = session.document.dumps()
    started = time.perf_counter()
    panel = garment.build_panels(bpy.context, force_rebuild=True)[0]
    build_seconds = time.perf_counter() - started
    world_vertices = [panel.matrix_world @ vertex.co for vertex in panel.data.vertices]
    panel.data.calc_loop_triangles()
    triangles = [tuple(triangle.vertices) for triangle in panel.data.loop_triangles]
    signed_gaps = []
    for vertex in world_vertices:
        location, normal, face_index, distance = body_tree.find_nearest(vertex)
        assert location is not None
        signed_gaps.append((vertex - location).dot(normal))
    overlaps = body_tree.overlap(BVHTree.FromPolygons(world_vertices, triangles, all_triangles=True))
    control_overlaps = control_tree.overlap(BVHTree.FromPolygons(world_vertices, triangles, all_triangles=True))
    resolved = arrangement.resolve_point(bpy.context, 'waist', 'front', 2)
    section = section_at_height(resolved['stack'], 1.18, resolved['up'])
    result['cases'].append(dict(label=label, outline=outline, vertices=len(world_vertices), triangles=len(triangles),
                                build_seconds=build_seconds, inside_vertices=sum(gap < -1e-6 for gap in signed_gaps),
                                deepest_penetration_m=max(0, -min(signed_gaps)),
                                intersecting_panel_triangles=len({pair[1] for pair in overlaps}),
                                control_intersecting_triangles=len({pair[1] for pair in control_overlaps}),
                                fitted_front_radius_at_bulge_m=directional_radius(section, (0, -1, 0)),
                                actual_body_front_radius_at_bulge_m=.225,
                                arrangement_message=scene.get('dd_arrangement_message', ''),
                                resolved=resolved))
    print('CASE', label, result['cases'][-1]['inside_vertices'], flush=True)
bpy.ops.wm.save_as_mainfile(filepath=str(output / 'issue76-wrap-repro.blend'))
source = Path(__file__).read_text(encoding='utf-8')
assert not any(token.type == tokenize.COMMENT for token in tokenize.generate_tokens(io.StringIO(source).readline))
assert not any(isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
               and isinstance(node.value.value, str) for node in ast.walk(ast.parse(source)))
(output / 'issue76-evidence.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
