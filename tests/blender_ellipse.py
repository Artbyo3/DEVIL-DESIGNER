import json
import math
from pathlib import Path
import runpy
import sys
from unittest.mock import patch

import bpy
from mathutils import Euler, Matrix, Vector
from mathutils.bvhtree import BVHTree


ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
import devil_designer
from devil_designer import arrangement, garment, live_panels
from devil_designer.core import Document, Session, arrangement_record
from devil_designer.ellipse_volumes import directional_radius, section_at_height, wrap_positions
from tools.workspace import prepare_scratch


def run_checks():
    if not hasattr(bpy.context.scene, 'dd_avatar'):
        devil_designer.register()
    helpers = runpy.run_path(str(ROOT / 'tests' / 'blender_arrangement_ellipse_prototype.py'), run_name='ellipse_helpers')
    context = bpy.context
    scene = context.scene
    scene.dd_clearance = .03
    scene.dd_spacing = .02
    scene.unit_settings.scale_length = 1
    results = []

    def panel(width, height, version=2, flat=False):
        session = Session()
        session.add([(-width/2, -height/2), (width/2, -height/2), (width/2, height/2), (-width/2, height/2)])
        session.document.patterns[0].arrangement = arrangement_record('chest', 'front', flat, version=version)
        scene.dd_document = session.document.dumps()
        with patch.object(arrangement, '_volume_mesh', side_effect=AssertionError('No build-time mesh read')), patch.object(
                arrangement, '_volume_sections', side_effect=AssertionError('No build-time slicing')):
            return garment.build_panels(context)[0]

    def positions(obj):
        return [tuple(obj.matrix_world @ vertex.co) for vertex in obj.data.vertices]

    for scale, location in (((.25,.15,.5), (0,0,1.2)), ((.4,.2,.75), (2,0,1.8))):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=12, location=location)
        avatar = context.object
        avatar.scale = scale
        bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
        scene.dd_avatar = avatar
        context.view_layer.update()
        setup = arrangement.ensure_volumes(context, force=True)
        world_points = arrangement.world_points(context)
        vertices, triangles, axes, fingerprint = arrangement._volume_mesh(context, avatar)
        assert setup['fingerprint'] == fingerprint
        low, extent = arrangement._array_bounds(vertices)
        normalized = [tuple((point[axis]-low[axis])/extent[2] for axis in range(3)) for point in vertices.tolist()]
        triangles = triangles.tolist()
        samples = []
        for volume in setup['volumes']:
            if volume['id'] not in ('chest','waist','hip'):
                continue
            for index, sample in enumerate(volume['samples']):
                center = tuple(sample['center'][axis]*extent[axis]/extent[2] for axis in range(3))
                loops = arrangement._volume_sections(normalized, triangles, (0,0,1), center[2])
                loop = min(loops, key=lambda points: math.dist(arrangement._volume_center(points), center))
                fitted = helpers['fitted_section'](loop, center)
                assert max(abs(first-second)*extent[2]*1000 for first,second in zip(fitted, sample['radii'])) <= 1e-6
                points = helpers['uniform_loop'](loop, center)
                circle = [abs(math.dist(point,center)-sample['radius'])*extent[2]*1000 for point in points]
                ellipse = [helpers['ellipse_gap'](point,center,tuple(sample['radii']))*extent[2]*1000 for point in points]
                assert sum(ellipse) < sum(circle) and max(ellipse) < max(circle)
                samples.append(dict(volume=volume['id'], sample=index, adaptive=sample.get('adaptive', False), circle_mean_mm=sum(circle)/len(circle),
                                    circle_max_mm=max(circle), ellipse_mean_mm=sum(ellipse)/len(ellipse), ellipse_max_mm=max(ellipse)))
        evaluated = avatar.evaluated_get(context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            tree = BVHTree.FromPolygons([evaluated.matrix_world @ vertex.co for vertex in mesh.vertices],
                                        [tuple(face.vertices) for face in mesh.loop_triangles], all_triangles=True)
        finally:
            evaluated.to_mesh_clear()
        legacy = json.loads(json.dumps(setup))
        legacy['version'] = 1
        for volume in legacy['volumes']:
            for sample in volume['samples']:
                del sample['radii'], sample['basis']
        avatar['dd_arrangement_volumes'] = json.dumps(legacy)
        session = Session()
        for unused in range(2):
            session.add([(-.2,-.225),(.2,-.225),(.2,.225),(-.2,.225)])
            session.document.patterns[-1].arrangement = arrangement_record('chest','front')
        scene.dd_document = session.document.dumps()
        stored = avatar['dd_arrangement_volumes']
        old_panels = garment.build_panels(context)
        before_migration = {obj['dd_pattern_id']: positions(obj) for obj in old_panels}
        assert avatar['dd_arrangement_volumes'] == stored
        first_id, second_id = [pattern.id for pattern in session.document.patterns]
        live_panels.arrange_piece(context,first_id,'chest','front')
        mixed = garment.document(scene)
        assert mixed.find(first_id).arrangement['version'] == 3
        assert mixed.find(second_id).arrangement['version'] == 1
        mixed_positions = {obj['dd_pattern_id']: positions(obj) for obj in garment.generated(scene,'panel')}
        assert mixed_positions[second_id] == before_migration[second_id]
        assert mixed_positions[first_id] != before_migration[first_id]
        arrangement.ensure_volumes(context,force=True)
        regenerated = {obj['dd_pattern_id']: positions(obj) for obj in garment.build_panels(context)}
        assert regenerated[second_id] != before_migration[second_id]
        counts = []
        bare_geometry = []
        for width, height in ((.4,.45), (extent[0]*1.2, extent[2]*.8)):
            avatar['dd_arrangement_volumes'] = json.dumps(legacy)
            before = panel(width,height,version=1)
            circle_anchor_gap = tree.find_nearest(before.matrix_world.translation)[3] * 1000
            before.data.calc_loop_triangles()
            baseline = helpers['intersection_counts'](positions(before), [tuple(face.vertices) for face in before.data.loop_triangles], tree)
            arrangement.upgrade_volumes(context)
            after = panel(width,height)
            ellipse_anchor_gap = tree.find_nearest(after.matrix_world.translation)[3] * 1000
            assert ellipse_anchor_gap < circle_anchor_gap
            after.data.calc_loop_triangles()
            actual = helpers['intersection_counts'](positions(after), [tuple(face.vertices) for face in after.data.loop_triangles], tree)
            for key in ('triangle_pairs','panel_triangles','inside_vertices'):
                assert actual[key] == baseline[key] == 0, (scale,key,baseline,actual)
            counts.append(dict(circle=baseline, ellipse=actual, circle_anchor_gap_mm=circle_anchor_gap,
                               ellipse_anchor_gap_mm=ellipse_anchor_gap))
            bare_geometry.append(positions(after))
        avatar['dd_arrangement_volumes'] = json.dumps(setup)
        flat = panel(.4,.45,flat=True)
        assert max(abs(vertex.co.z) for vertex in flat.data.vertices) < 1e-8
        source_uv = [tuple(item.uv) for item in flat.data.uv_layers.active.data]
        document = garment.document(scene)
        source_outline = document.patterns[0].points
        wrapped = panel(.4,.45)
        assert [tuple(item.uv) for item in wrapped.data.uv_layers.active.data] == source_uv
        assert garment.document(scene).patterns[0].points == source_outline
        delta = Matrix.Translation(Vector((.01,.02,.03))) @ Euler((.1,-.2,.3),'XYZ').to_matrix().to_4x4()
        base = Matrix(json.loads(wrapped['dd_arrangement_base']))
        wrapped.matrix_world = base @ delta
        expected = positions(wrapped)
        captured = live_panels.capture(context)
        record = captured.patterns[0].arrangement
        assert record['version'] == 2
        assert Document.loads(captured.dumps()).patterns[0].arrangement == record
        rebuilt = garment.build_panels(context)[0]
        assert max(math.dist(first,second) for first,second in zip(positions(rebuilt),expected)) < 2e-6
        resolved = arrangement.resolve_point(context,'chest','front',version=2)
        section = section_at_height(resolved['stack'],resolved['height'],resolved['up'])
        curve = []
        for index in range(4097):
            angle = math.tau*index/4096
            direction = (math.sin(angle),-math.cos(angle),0)
            radius = directional_radius(section,direction)+resolved['clearance']
            curve.append(tuple(value*radius for value in direction))
        circumference = sum(math.dist(first,second) for first,second in zip(curve,curve[1:]))
        turns = wrap_positions([(index*circumference,0,0) for index in range(3)],resolved,circumference*2.5,0,.001)
        radii = [math.dist(position,section['center']) for position in turns]
        assert all(abs(second-first-.03)<2e-6 for first,second in zip(radii,radii[1:]))
        wide = panel(circumference*2.5,.1)
        assert all(math.isfinite(value) for vertex in wide.data.vertices for value in vertex.co)
        bpy.ops.object.armature_add(location=location)
        modifier = avatar.modifiers.new(name='Equivalence only',type='ARMATURE')
        modifier.object = context.object
        context.view_layer.update()
        rigged = arrangement.ensure_volumes(context,force=True)
        assert rigged == setup, [(key,str(setup[key])[:300],str(rigged[key])[:300]) for key in setup if setup[key] != rigged[key]]
        assert arrangement.world_points(context) == world_points
        for index,(width,height) in enumerate(((.4,.45),(extent[0]*1.2,extent[2]*.8))):
            assert positions(panel(width,height)) == bare_geometry[index]
        avatar.modifiers.remove(modifier)
        avatar.rotation_euler = (.3,-.4,.7)
        avatar.scale = (1.3,.9,1.1)
        context.view_layer.update()
        transformed = arrangement.resolve_point(context,'chest','front',version=2)
        assert abs(sum(first*second for first,second in zip(transformed['normal'],transformed['up']))) < 1e-6
        assert all(math.isfinite(value) for point in positions(panel(.4,.45)) for value in point)
        results.append(dict(scale=scale,samples=samples,panels=counts,no_armature_equivalent=True,flat=True,spiral=True,deltas=True))
    assert sum(not sample['adaptive'] for body in results for sample in body['samples']) == 42
    (prepare_scratch()/'arrangement-ellipse-production.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print('PASS: production ellipses, 42 fits, two bodies, zero tall/bodice intersections, flat/spiral/G-R/UV/no-armature/transform checks',flush=True)


def bulge_body(name, protrusion=True):
    heights = sorted(set([index * 1.8 / 180 for index in range(181)] + [1.174, 1.18, 1.186]))
    vertices, faces = [], []
    for height in heights:
        bulge = max(0, 1 - abs(height - 1.18) / .012) if protrusion else 0
        for segment in range(96):
            angle = math.tau * segment / 96
            vertices.append((.23 * math.sin(angle), -(.14 + .085 * bulge) * math.cos(angle), height))
    for level in range(len(heights) - 1):
        for segment in range(96):
            following = (segment + 1) % 96
            faces.append((level * 96 + segment, level * 96 + following, (level + 1) * 96 + following, (level + 1) * 96 + segment))
    faces.extend((tuple(reversed(range(96))), tuple((len(heights) - 1) * 96 + segment for segment in range(96))))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    avatar = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(avatar)
    bpy.context.view_layer.update()
    return avatar


def sphere_body(segments, rings, arm_gap=None):
    parts = []
    arm_x = .42 if arm_gap is None else .26 + arm_gap + .08
    for position, scale in (((0, 0, 1.15), (.26, .15, .4)), ((0, 0, 1.7), (.12, .12, .16)),
                            ((-arm_x, 0, 1.38), (.27 if arm_gap is None else .08, .08, .08 if arm_gap is None else .3)),
                            ((arm_x, 0, 1.38), (.27 if arm_gap is None else .08, .08, .08 if arm_gap is None else .3)),
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
    return bpy.context.object


def body_tree(avatar):
    mesh = avatar.data
    mesh.calc_loop_triangles()
    return BVHTree.FromPolygons([avatar.matrix_world @ vertex.co for vertex in mesh.vertices],
                                [tuple(triangle.vertices) for triangle in mesh.loop_triangles], all_triangles=True)


def panel_metrics(panel, tree, clearance):
    world = [panel.matrix_world @ vertex.co for vertex in panel.data.vertices]
    panel.data.calc_loop_triangles()
    triangles = [tuple(triangle.vertices) for triangle in panel.data.loop_triangles]
    rest = [tuple(item.vector)[:2] for item in panel.data.attributes['dd_rest'].data]
    centroids = [(world[a] + world[b] + world[c]) / 3 for a, b, c in triangles]
    gaps = []
    for sample in world + centroids:
        location, normal, _, distance = tree.find_nearest(sample)
        gaps.append(-distance if (sample - location).dot(normal) < 0 and live_panels.enclosed(tree, sample) else distance)
    panel_tree = BVHTree.FromPolygons(world, triangles, all_triangles=True)
    ratios = sorted((world[a] - world[b]).length / math.dist(rest[a], rest[b])
                    for a, b in (tuple(edge.vertices) for edge in panel.data.edges) if math.dist(rest[a], rest[b]) > 1e-9)
    excess = sorted(gap - clearance for gap in gaps[:len(world)])
    def percentile(values, fraction):
        return values[min(len(values) - 1, int(fraction * (len(values) - 1)))]
    return dict(vertices=len(world), triangles=len(triangles),
                inside=sum(gap < -1e-6 for gap in gaps), intersecting=len({pair[1] for pair in tree.overlap(panel_tree)}),
                self_intersections=sum(1 for first, second in panel_tree.overlap(panel_tree) if not set(triangles[first]) & set(triangles[second])),
                separation_mm=dict(minimum=min(gaps) * 1000, vertex_minimum=min(gaps[:len(world)]) * 1000,
                                   face_minimum=min(gaps[len(world):]) * 1000 if centroids else None,
                                   median=sorted(gaps)[len(gaps) // 2] * 1000),
                excess_mm=dict(p50=percentile(excess, .5) * 1000, p95=percentile(excess, .95) * 1000, maximum=excess[-1] * 1000),
                stretch=dict(minimum=ratios[0], median=percentile(ratios, .5), p95=percentile(ratios, .95), maximum=ratios[-1]),
                degenerate_faces=sum(1 for polygon in panel.data.polygons if polygon.area < 1e-12))


def arrange_document(outlines, records, spacing=.015):
    session = Session()
    for name, outline in outlines:
        session.add(outline)
        session.document.patterns[-1].name = name
    for pattern, record in zip(session.document.patterns, records):
        pattern.arrangement = record
    bpy.context.scene.dd_spacing = spacing
    bpy.context.scene.dd_document = session.document.dumps()
    return garment.build_panels(bpy.context, force_rebuild=True)


def run_issue76_checks():
    context = bpy.context
    scene = context.scene
    scene.dd_clearance = .03
    scene.unit_settings.scale_length = 1
    evidence = dict(blender=bpy.app.version_string, cases=[], difficult=[], continuity=[], selection=[])
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    avatar = bulge_body('Issue76Bulge')
    scene.dd_avatar = avatar
    setup = arrangement.ensure_volumes(context)
    torso = [sample for volume in setup['volumes'] if volume['id'] in ('chest', 'waist') for sample in volume['samples']]
    measured = [abs(sample['center'][2] * 1.8 - 1.18) for sample in torso if sample.get('adaptive')]
    assert measured and min(measured) < .003, measured
    evidence['adaptive_sample_offset_mm'] = min(measured) * 1000
    tree = body_tree(avatar)
    outlines = (('rectangle', [(-.24, -.28), (.24, -.28), (.24, .28), (-.24, .28)]),
                ('concave_long_tab', [(-.24, -.28), (-.08, -.28), (-.08, -.08), (.24, -.08), (.24, .28), (-.24, .28)]))
    for name, outline in outlines:
        panel = arrange_document([(name, outline)], [arrangement_record('waist', 'front', version=3)])[0]
        rest_before = [tuple(item.vector) for item in panel.data.attributes['dd_rest'].data]
        flat_faces = [tuple(polygon.vertices) for polygon in panel.data.polygons]
        metrics = panel_metrics(panel, tree, .03)
        assert metrics['inside'] == 0 and metrics['intersecting'] == 0 and metrics['self_intersections'] == 0, metrics
        assert metrics['separation_mm']['minimum'] >= 29, metrics
        assert metrics['excess_mm']['p95'] <= 15, metrics
        assert .85 <= metrics['stretch']['minimum'] and metrics['stretch']['maximum'] <= 1.15 and metrics['degenerate_faces'] == 0, metrics
        assert not scene.get('dd_arrangement_message', ''), scene['dd_arrangement_message']
        legacy = arrange_document([(name, outline)], [arrangement_record('waist', 'front', version=2)])[0]
        assert [tuple(item.vector) for item in legacy.data.attributes['dd_rest'].data] == rest_before
        assert [tuple(polygon.vertices) for polygon in legacy.data.polygons] == flat_faces
        evidence['cases'].append(dict(label=name, version=3, **metrics, legacy_v2=panel_metrics(legacy, tree, .03)))
    control = bulge_body('Issue76Control', protrusion=False)
    scene.dd_avatar = control
    control_panel = arrange_document([outlines[0]], [arrangement_record('waist', 'front', version=3)])[0]
    control_metrics = panel_metrics(control_panel, body_tree(control), .03)
    assert control_metrics['stretch']['maximum'] < 1.001 and control_metrics['excess_mm']['p95'] < 2, control_metrics
    evidence['control'] = control_metrics
    session_record = arrangement_record('waist', 'front', version=3)
    for overwrap, direction in ((False, 1), (True, 1), (True, -1)):
        session_record = dict(session_record, overwrap=overwrap, direction=direction)
        wide = arrange_document([('wide', [(-.9, -.05), (.9, -.05), (.9, .05), (-.9, .05)])], [session_record], .03)[0]
        message = scene.get('dd_arrangement_message', '')
        if not overwrap:
            assert 'Allow overwrap' in message and not garment.document(scene).patterns[0].arrangement['flat'], message
        else:
            assert not message and all(math.isfinite(value) for vertex in wide.data.vertices for value in vertex.co), message
            metrics = panel_metrics(wide, body_tree(control), .03)
            assert metrics['inside'] == 0 and metrics['intersecting'] == 0, metrics
            evidence['difficult'].append(dict(label='overwrap', direction=direction, **metrics))
    scene.dd_avatar = None
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    figure = sphere_body(32, 24)
    scene.dd_avatar = figure
    figure_tree = body_tree(figure)
    for label, outline, volume, point in (('tapered_sleeve', [(-.12, -.1), (.12, -.1), (.08, .1), (-.08, .1)], 'left_upper_arm', 'front'),
                                          ('notched_panel', [(-.2, -.2), (.2, -.2), (.2, .2), (.05, .2), (.05, 0), (-.05, 0), (-.05, .2), (-.2, .2)], 'chest', 'front'),
                                          ('long_bodice', [(-.18, -.35), (.22, -.35), (.18, .3), (-.2, .3)], 'waist', 'front_side')):
        panel = arrange_document([(label, outline)], [arrangement_record(volume, point, version=3)], .02)[0]
        metrics = panel_metrics(panel, figure_tree, .03)
        message = scene.get('dd_arrangement_message', '')
        assert not garment.document(scene).patterns[0].arrangement['flat']
        assert (metrics['inside'] == 0 and metrics['intersecting'] == 0) or 'could not keep' in message, (label, metrics, message)
        evidence['difficult'].append(dict(label=label, warning=message, **metrics))
    hood = arrange_document([('hood_left', [(-.12, -.15), (.12, -.15), (.1, .15), (-.1, .15)]),
                             ('hood_right', [(-.12, -.15), (.12, -.15), (.1, .15), (-.1, .15)])],
                            [arrangement_record('neck', 'side', version=3), arrangement_record('neck', 'opposite_side', version=3)], .02)
    message = scene.get('dd_arrangement_message', '')
    for panel in hood:
        metrics = panel_metrics(panel, figure_tree, .03)
        assert (metrics['inside'] == 0 and metrics['intersecting'] == 0) or 'could not keep' in message, (metrics, message)
        evidence['difficult'].append(dict(label='hood_' + panel.name, warning=message, **metrics))
    flat = arrange_document([('flat', [(-.15, -.15), (.15, -.15), (.15, .15), (-.15, .15)])], [arrangement_record('chest', 'front', True, version=3)], .02)[0]
    assert max(abs(vertex.co.z) for vertex in flat.data.vertices) < 1e-6
    scene.dd_avatar = None
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for gap in (.015, .06):
        close = sphere_body(32, 24, arm_gap=gap)
        scene.dd_avatar = close
        close_setup = arrangement.ensure_volumes(context)
        width = close.dimensions.x
        for identity in ('chest', 'waist'):
            volume = next(item for item in close_setup['volumes'] if item['id'] == identity)
            centers = [(sample['center'][0] - .5) * width for sample in volume['samples']]
            sides = [sample['radii'][0] for sample in volume['samples']]
            assert max(abs(value) for value in centers) < .01, (gap, identity, centers)
            assert all(abs(second - first) / first < .35 for first, second in zip(sides, sides[1:])), (gap, identity, sides)
            evidence['continuity'].append(dict(arm_gap_m=gap, volume=identity, center_offsets_mm=[value * 1000 for value in centers],
                                               side_radii=sides, samples=len(sides)))
        scene.dd_avatar = None
        bpy.data.objects.remove(close, do_unlink=True)
    deforming = bulge_body('Issue76Deforming', protrusion=False)
    scene.dd_avatar = deforming
    arrangement.ensure_volumes(context)
    arrangement.edit_point(context, 'waist', 'front', angle=.3, height=.4)
    signature = live_panels.avatar_signature(context)
    bounds = [tuple(corner) for corner in deforming.evaluated_get(context.evaluated_depsgraph_get()).bound_box]
    deforming.shape_key_add(name='Basis')
    key = deforming.shape_key_add(name='Inhale')
    for index, vertex in enumerate(deforming.data.vertices):
        if 1.0 < vertex.co.z < 1.2 and vertex.co.y < 0:
            key.data[index].co = Vector((vertex.co.x * .9, vertex.co.y * .9, vertex.co.z))
    key.value = 1
    context.view_layer.update()
    assert [tuple(corner) for corner in deforming.evaluated_get(context.evaluated_depsgraph_get()).bound_box] == bounds
    assert arrangement.stale_fit(context), 'same-bounds deformation invalidates the fit'
    job = arrangement.start_fit(context, keep=True)
    refreshed = arrangement.finish_fit(job)
    point = arrangement._volume_find(refreshed, 'waist', 'front')[1]
    assert (point['angle'], point['height']) == (.3, .4) and not arrangement.stale_fit(context)
    assert live_panels.avatar_signature(context) != signature
    evidence['same_bounds_refit'] = dict(kept_point=True, signature_changed=True)
    other = bulge_body('Issue76Other', protrusion=False)
    stored = deforming['dd_arrangement_volumes']
    stale = arrangement.start_fit(context, keep=True)
    scene.dd_avatar = other
    assert stale.state == 'cancelled' and deforming['dd_arrangement_volumes'] == stored
    arrangement.finish_fit(arrangement.pending_job(context))
    assert 'dd_arrangement_volumes' in other and deforming['dd_arrangement_volumes'] == stored
    other['dd_arrangement_volumes'] = '{'
    failing = arrangement.start_fit(context, keep=True)
    try:
        arrangement.finish_fit(failing)
        raise AssertionError('Interrupted refit replaced invalid JSON')
    except ValueError:
        pass
    assert other['dd_arrangement_volumes'] == '{'
    evidence['stale_and_failed_jobs'] = dict(stale_cancelled=True, invalid_setup_preserved=True)
    scene.dd_avatar = None
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    import time
    for segments, rings in ((48, 32), (96, 64)):
        body = sphere_body(segments, rings)
        body.data.calc_loop_triangles()
        runs = []
        for repeat in range(5):
            scene.dd_avatar = None
            if 'dd_arrangement_volumes' in body:
                del body['dd_arrangement_volumes']
            started = time.perf_counter()
            scene.dd_avatar = body
            callback = time.perf_counter() - started
            job = arrangement.pending_job(context)
            assert job is not None and 'dd_arrangement_volumes' not in body, (scene.get('dd_arrangement_message'), list(body.keys()))
            first = time.perf_counter()
            while job.state == 'pending':
                arrangement._advance(job, time.perf_counter() + arrangement.SLICE_SECONDS)
            completion = time.perf_counter() - first + callback
            assert job.state == 'ready' and len(json.loads(body['dd_arrangement_volumes'])['volumes']) == 12
            runs.append(dict(callback_ms=callback * 1000, completion_s=completion, slices=len(job.slices),
                             longest_step_ms=max(job.slices) * 1000, errors=0))
        scene.dd_avatar = None
        started = time.perf_counter()
        scene.dd_avatar = body
        cached = time.perf_counter() - started
        evidence['selection'].append(dict(triangles=len(body.data.loop_triangles), runs=runs, cached_callback_ms=cached * 1000))
        bpy.data.objects.remove(body, do_unlink=True)
    for record in evidence['selection']:
        assert all(run['callback_ms'] < 50 for run in record['runs']), record
        assert record['cached_callback_ms'] < 50, record
    (prepare_scratch() / 'issue76-acceptance.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print('PASS: issue 76 body-checked wrap, difficult shapes, continuity, refit and selection evidence', flush=True)


if __name__ == '__main__':
    run_checks()
    run_issue76_checks()
