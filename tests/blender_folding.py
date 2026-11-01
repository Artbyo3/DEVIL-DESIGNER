import json
import math
import statistics
from pathlib import Path
import bpy
from devil_designer import garment, library
from devil_designer.core import Document, Session
from devil_designer.folding import author_fold, fold_records


def _crease_faces(panel, pattern):
    rest = [tuple(item.vector) for item in panel.data.attributes['dd_rest'].data]
    adjacent = {}
    for face in panel.data.polygons:
        indices = tuple(face.vertices)
        for left, right in zip(indices, indices[1:] + indices[:1]):
            adjacent.setdefault(tuple(sorted((left, right))), []).append(indices)
    result = []
    for path, _ in fold_records(pattern):
        start, end = path.points[0], path.points[-1]
        direction = (end[0]-start[0], end[1]-start[1])
        pairs = []
        for edge, faces in adjacent.items():
            if len(faces) == 2 and all(abs(direction[0]*(rest[index][1]-start[1])-direction[1]*(rest[index][0]-start[0])) < 1e-7 for index in edge):
                pairs.append(faces)
        result.append(pairs)
    return result


def _angles(mesh, creases, signed=False):
    def normal(face):
        start, middle, end = (mesh.vertices[index].co for index in face[:3])
        return (middle-start).cross(end-start).normalized()
    def angle(left, right):
        first, second = normal(left), normal(right)
        cosine = max(-1, min(1, first.dot(second)))
        if not signed:
            return math.degrees(math.acos(cosine))
        shared = set(left).intersection(right)
        start, end = next((start,end) for start,end in zip(left,left[1:]+left[:1]) if start in shared and end in shared)
        axis = (mesh.vertices[end].co-mesh.vertices[start].co).normalized()
        return math.degrees(math.atan2(axis.dot(first.cross(second)), cosine))
    return [statistics.median(angle(left, right) for left, right in pairs) for pairs in creases]


def run(check):
    root = Path(__file__).resolve().parents[1]
    scene = bpy.context.scene
    garment.stop(bpy.context)
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.mesh.primitive_cube_add(size=.02, location=(-.5, 0, -.5))
    scene.dd_avatar = bpy.context.object
    scene.unit_settings.scale_length = 1
    scene.dd_spacing = .015
    scene.dd_quality = 12
    scene.dd_frames = 125
    scene.dd_pin_top = True
    scene.dd_self_collision = True
    scene.dd_thickness = 0
    scene.dd_library_dir = str(root / 'scratch' / 'fold-library')
    report = dict(blender=bpy.app.version_string, mocked=False, folds=[], darts=[])
    for style in ('MOUNTAIN', 'VALLEY', 'KNIFE', 'BOX'):
        garment.reset(bpy.context)
        garment.remove_objects(garment.generated(scene, 'final'))
        session = Session()
        session.add([(0, 0), (.4, 0), (.4, .5), (0, .5)])
        session.add_path([(.2, 0), (.2, .5)])
        author_fold(session, style)
        scene.dd_document = session.document.dumps()
        panel = garment.build_panels(bpy.context)[0]
        pattern = garment.document(scene).patterns[0]
        creases = _crease_faces(panel, pattern)
        check(all(creases), style + ' has actual constrained interior crease edges')
        initial = _angles(panel.data, creases)
        initial_signed = _angles(panel.data, creases, signed=True)
        check(all(abs(angle-150) < .1 for angle in initial), style + ' starts with requested signed fold geometry')
        expected_uv = [tuple(item.uv) for item in panel.data.uv_layers.active.data]
        library.save(bpy.context, 'Fold ' + style)
        loaded = library.load(bpy.context, scene.dd_library_selected)
        check(len(fold_records(loaded.patterns[0])) == len(creases), style + ' survives the real garment library')
        panel = garment.generated(scene, 'panel')[0]
        check([tuple(item.uv) for item in panel.data.uv_layers.active.data] == expected_uv, style + ' library preserves flat UVs')
        simulation = garment.compile_garment(bpy.context)
        check(any(modifier.type == 'CLOTH' for modifier in simulation.modifiers), style + ' uses Blender classic cloth')
        cloth = next(modifier for modifier in simulation.modifiers if modifier.type == 'CLOTH')
        check(abs(cloth.collision_settings.self_distance_min-.001) < 1e-8, style + ' production compile uses the approved 1 mm collision distance')
        for frame in range(scene.frame_start, scene.frame_start+121):
            scene.frame_set(frame)
            evaluated = simulation.evaluated_get(bpy.context.evaluated_depsgraph_get())
            check(all(math.isfinite(value) and abs(value) < 10 for vertex in evaluated.data.vertices for value in vertex.co), style + ' finite cloth frame ' + str(frame))
        final = _angles(evaluated.data, creases)
        final_signed = _angles(evaluated.data, creases, signed=True)
        check(all(before*after > 0 for before,after in zip(initial_signed,final_signed)), style + ' preserves mountain and valley direction after draping')
        record = dict(style=style, frame=scene.frame_current, initial_angles=initial, final_angles=final, vertices=len(evaluated.data.vertices))
        report['folds'].append(record)
        (root / 'scratch' / 'fold-physics-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        check(all(angle >= 105 for angle in final), style + ' retains at least 105 degrees after 120 simulated frames')
        check('FINISHED' in bpy.ops.devil_designer.keep_drape(), style + ' Keep operator finalizes actual draped mesh')
        kept = garment.generated(scene, 'final')[-1]
        check(len(kept.data.polygons) > 0 and kept.data.uv_layers.active is not None, style + ' Keep preserves fabric faces and UVs')
    expected_folds = scene.dd_document
    filename = root / 'scratch' / 'fold-native-persistence.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(filename))
    bpy.ops.wm.open_mainfile(filepath=str(filename))
    scene = bpy.context.scene
    check(scene.dd_document == expected_folds and len(fold_records(garment.document(scene).patterns[0])) == 4, 'box fold features and references survive actual native blend save and reload')
    for depth in (.4, .49, .499):
        garment.reset(bpy.context)
        garment.remove_objects(garment.generated(scene, 'final'))
        scene.dd_pin_top = False
        session = Session()
        session.add([(0, 0), (.4, 0), (.4, .5), (0, .5)])
        session.dart(session.document.edge(session.selected, 2), .3, .7, (.2, .5-depth))
        scene.dd_document = session.document.dumps()
        garment.build_panels(bpy.context)
        simulation = garment.compile_garment(bpy.context)
        for frame in range(scene.frame_start, scene.frame_start+31):
            scene.frame_set(frame)
            evaluated = simulation.evaluated_get(bpy.context.evaluated_depsgraph_get())
        pairs = json.loads(simulation['dd_sewing_pairs'])
        maximum = max((evaluated.data.vertices[left].co-evaluated.data.vertices[right].co).length for left, right in pairs)
        report['darts'].append(dict(depth_m=depth, max_sewing_gap_m=maximum))
        check(maximum < .003, 'deep dart ' + str(depth) + ' closes to less than 3 mm with classic cloth')
        check('FINISHED' in bpy.ops.devil_designer.keep_drape(), 'deep dart ' + str(depth) + ' finalizes through Keep operator')
    expected = scene.dd_document
    filename = root / 'scratch' / 'deep-dart-persistence.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(filename))
    bpy.ops.wm.open_mainfile(filepath=str(filename))
    check(Document.loads(bpy.context.scene.dd_document).dumps() == Document.loads(expected).dumps(), 'construction data survives native blend save and reload')
    (root / 'scratch' / 'fold-physics-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    from tests.blender_fold_garments import run as run_mixed_garments
    run_mixed_garments(check)
