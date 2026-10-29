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
        vertices, triangles, axes = arrangement._volume_mesh(context, avatar)
        low, extent = arrangement._volume_bounds(vertices)
        normalized = [tuple((point[axis]-low[axis])/extent[2] for axis in range(3)) for point in vertices]
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
                samples.append(dict(volume=volume['id'], sample=index, circle_mean_mm=sum(circle)/len(circle),
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
        assert mixed.find(first_id).arrangement['version'] == 2
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
    assert sum(len(body['samples']) for body in results) == 42
    (prepare_scratch()/'arrangement-ellipse-production.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    print('PASS: production ellipses, 42 fits, two bodies, zero tall/bodice intersections, flat/spiral/G-R/UV/no-armature/transform checks',flush=True)


if __name__ == '__main__':
    run_checks()
