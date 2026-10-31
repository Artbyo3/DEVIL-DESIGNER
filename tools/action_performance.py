import cProfile
import hashlib
import json
from pathlib import Path
import pstats
import statistics
import sys
import time
import traceback
from types import SimpleNamespace

import bpy
from mathutils import Quaternion

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.workspace import prepare_scratch
import devil_designer
from devil_designer import arrangement, arrangement_controls, editor, garment, live_panels
from devil_designer.core import Document, Session, arrangement_record


def geometry():
    result = {}
    for panel in garment.generated(bpy.context.scene, 'panel'):
        payload = dict(vertices=[list(vertex.co) for vertex in panel.data.vertices],
                       matrix=[list(row) for row in panel.matrix_world],
                       faces=[list(face.vertices) for face in panel.data.polygons])
        result[panel['dd_pattern_id']] = hashlib.sha256(json.dumps(payload).encode()).hexdigest()
    return result


def fixture():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    parts = []
    for location, scale in (((0, 0, 1.15), (.26, .15, .4)), ((0, 0, 1.7), (.12, .12, .16)),
                            ((-.42, 0, 1.38), (.27, .08, .08)), ((.42, 0, 1.38), (.27, .08, .08)),
                            ((-.13, 0, .45), (.105, .11, .45)), ((.13, 0, .45), (.105, .11, .45))):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=96, ring_count=64, location=location)
        part = bpy.context.object
        part.scale = scale
        parts.append(part)
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    avatar = bpy.context.object
    avatar.name = 'Action performance avatar'
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    rig_data = bpy.data.armatures.new('Action rig')
    rig = bpy.data.objects.new('Action rig', rig_data)
    bpy.context.scene.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    bone = rig_data.edit_bones.new('Body')
    bone.head = (0, 0, 0)
    bone.tail = (0, 0, 1.8)
    bpy.ops.object.mode_set(mode='OBJECT')
    group = avatar.vertex_groups.new(name='Body')
    group.add(list(range(len(avatar.data.vertices))), 1, 'REPLACE')
    modifier = avatar.modifiers.new('Rigged avatar', 'ARMATURE')
    modifier.object = rig
    scene = bpy.context.scene
    scene.dd_avatar = avatar
    scene.dd_spacing = .035
    arrangement.ensure_volumes(bpy.context)
    arrangement.edit_point(bpy.context, 'chest', '', action='ADD', angle=.7, height=.6)
    session = Session()
    for index in range(6):
        left = index * .3
        session.add([(left, 0), (left + .25, 0), (left + .25, .4), (left, .4)])
        if index % 2 == 0:
            session.document.patterns[-1].arrangement = arrangement_record('chest', 'front', False, version=2)
    patterns = session.document.patterns
    session.sew_chains([session.document.edge(patterns[0].id, 1)], [session.document.edge(patterns[1].id, 3)])
    session.sew_chains([session.document.edge(patterns[2].id, 1)], [session.document.edge(patterns[3].id, 3)])
    for pattern in patterns:
        session.selected = pattern.id
        session.add_anchor((pattern.points[0][0] + .1, .1))
    for index in range(24):
        session.commit(lambda: setattr(patterns[-1], 'name', 'Panel ' + str(index)))
    scene.dd_document = session.document.dumps()
    live_panels.sync(bpy.context)
    session.document.uv_layout = garment.document(scene).uv_layout
    scene.dd_document = session.document.dumps()
    return session, avatar


def profile_rows(profiler):
    result = []
    for (filename, line, name), (primitive, calls, own, cumulative, callers) in pstats.Stats(profiler).stats.items():
        if filename.startswith(str(ROOT)) or 'update' in name or 'depsgraph' in name:
            result.append(dict(file=Path(filename).name, line=line, name=name, calls=calls,
                               own_ms=own * 1000, total_ms=cumulative * 1000))
    return sorted(result, key=lambda row: row['total_ms'], reverse=True)


def perform(active, target, action, region):
    motion = []
    started = time.perf_counter()
    if action == 'add_pin':
        active.session.add_anchor((target.points[0][0] + .12, .2))
        active.persist()
    elif action == 'remove_pin':
        anchor = next(anchor for anchor in active.session.document.anchors if anchor.pattern == target.id)
        active.session.commit(lambda: active.session.document.anchors.remove(anchor))
        active.persist()
    elif action in ('add_point', 'remove_point'):
        status = bpy.ops.devil_designer.arrangement_edit(volume='chest', point='custom_1',
            action='ADD' if action == 'add_point' else 'DELETE', angle=.4, height=.6)
        if status != {'FINISHED'}:
            raise RuntimeError(str(status))
    elif action == 'duplicate':
        active.session.duplicate()
        active.persist()
    elif action == 'move':
        active.session.move_selection(.02, .01)
        active.persist()
    else:
        center = tuple(sum(point[axis] for point in target.points) / len(target.points) for axis in (0, 1))
        active.gesture = dict(mode='MOVE', start=center, ref_pos=center, points=list(target.points))
        active.preview = list(target.points)
        for frame in range(60):
            remaining = started + frame / 30 - time.perf_counter()
            if remaining > 0:
                time.sleep(remaining)
            pointer = active.view.screen((center[0] + .02 * (frame + 1) / 60, center[1] + .01), active.canvas_layout.canvas)
            active.pointer = pointer
            event = SimpleNamespace(type='MOUSEMOVE', value='NOTHING', mouse_x=pointer[0] + region.x,
                                    mouse_y=pointer[1] + region.y, ctrl=False, shift=False, alt=False)
            tick = time.perf_counter()
            active.handle_event(bpy.context, event)
            bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
            motion.append((time.perf_counter() - tick) * 1000)
        release_start = time.perf_counter()
        event.type = 'LEFTMOUSE'
        event.value = 'RELEASE'
        active.handle_event(bpy.context, event)
        release_ms = (time.perf_counter() - release_start) * 1000
    return (time.perf_counter() - started) * 1000, motion, release_ms if motion else 0


def measure(active, target, action, region, profiled):
    before = geometry()
    rebuilt = []
    original_mesh = garment.fabric_mesh
    def mesh_probe(document, pattern, *args, **kwargs):
        rebuilt.append(pattern.id)
        return original_mesh(document, pattern, *args, **kwargs)
    garment.fabric_mesh = mesh_probe
    updates = []
    evaluations = []
    original_build = garment.build_panels
    class LayerProbe:
        def __getattr__(self, name):
            return getattr(bpy.context.view_layer, name)
        def update(self):
            started = time.perf_counter()
            bpy.context.view_layer.update()
            updates.append((time.perf_counter() - started) * 1000)
    class ContextProbe:
        view_layer = LayerProbe()
        def __getattr__(self, name):
            return getattr(bpy.context, name)
        def evaluated_depsgraph_get(self):
            started = time.perf_counter()
            graph = bpy.context.evaluated_depsgraph_get()
            evaluations.append((time.perf_counter() - started) * 1000)
            return graph
    def build_probe(context):
        return original_build(ContextProbe())
    garment.build_panels = build_probe
    profiler = cProfile.Profile()
    try:
        if profiled:
            profiler.enable()
        action_ms, motion, release_ms = perform(active, target, action, region)
        update_start = time.perf_counter()
        bpy.context.view_layer.update()
        update_ms = (time.perf_counter() - update_start) * 1000
        redraw_start = time.perf_counter()
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
        redraw_ms = (time.perf_counter() - redraw_start) * 1000
        timer_start = time.perf_counter()
        pointer = active.pointer
        timer = SimpleNamespace(type='TIMER', value='NOTHING', mouse_x=pointer[0] + region.x,
                                mouse_y=pointer[1] + region.y, ctrl=False, shift=False, alt=False)
        for tick in range(10):
            active.handle_event(bpy.context, timer)
        timer_ms = (time.perf_counter() - timer_start) * 1000
    finally:
        profiler.disable()
        garment.fabric_mesh = original_mesh
        garment.build_panels = original_build
    after = geometry()
    reference_equal = None
    if hasattr(live_panels, 'wrapped_positions'):
        cached = live_panels.wrapped_positions
        live_panels.wrapped_positions = cached.__wrapped__
        try:
            garment.build_panels(bpy.context, force_rebuild=True)
            reference_equal = after == geometry()
            if not reference_equal:
                raise AssertionError('Cached panels differ from the uncached reference.')
        finally:
            live_panels.wrapped_positions = cached
    return dict(profiled=profiled, action_ms=action_ms, update_ms=update_ms, redraw_ms=redraw_ms,
                reference_equal=reference_equal,
                release_ms=release_ms, timer_ms=timer_ms,
                build_updates_ms=sum(updates), build_updates_count=len(updates),
                evaluation_get_ms=sum(evaluations), before=list(before.values()), after=list(after.values()),
                rebuilt=rebuilt, unrelated_rebuilt=sum(identity != target.id for identity in rebuilt),
                unchanged=[identity for identity in before if before[identity] == after.get(identity)],
                motion_mean_ms=statistics.mean(motion) if motion else 0,
                motion_max_ms=max(motion, default=0), profile=profile_rows(profiler) if profiled else [])


def run():
    output = prepare_scratch()
    label = sys.argv[-1] if '--' in sys.argv else 'baseline'
    result = dict(label=label, records=[], source={path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in sorted((ROOT / 'devil_designer').glob('*.py'))})
    try:
        devil_designer.register()
        area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
        region = next(region for region in area.regions if region.type == 'WINDOW')
        with bpy.context.temp_override(area=area, region=region, region_data=area.spaces.active.region_3d):
            session, avatar = fixture()
            base = session.document.dumps()
            undo = list(session.undo_stack)
            volumes = avatar['dd_arrangement_volumes']
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            active = editor._active
            active.reveal_3d()
            view = area.spaces.active.region_3d
            view.view_location = (0, 0, .9)
            view.view_distance = 3.7
            view.view_rotation = Quaternion((1, 0, 0), 1.3)
            view.update()
            bpy.context.scene.dd_reference_visible = True
            if not arrangement_controls.projected_points(bpy.context):
                raise AssertionError(str(dict(region_data=str(bpy.context.region_data),
                    panel=str(active.canvas_layout.panel), world=len(arrangement.world_points(bpy.context)))))
            active.snap = False
            draw_times = []
            original_draw = arrangement_controls.draw_points
            bpy.types.SpaceView3D.draw_handler_remove(arrangement_controls._draw_handle, 'WINDOW')
            def timed_draw():
                started = time.perf_counter()
                original_draw()
                draw_times.append((time.perf_counter() - started) * 1000)
            arrangement_controls._draw_handle = bpy.types.SpaceView3D.draw_handler_add(timed_draw, (), 'WINDOW', 'POST_PIXEL')
            result.update(avatar_vertices=len(avatar.data.vertices), bones=len(avatar.modifiers[0].object.data.bones),
                          panels=6, seams=2, pins=6, undo_depth=len(undo), blender=bpy.app.version_string)
            for visible in (False, True):
                for arranged in (False, True):
                    for action in ('add_pin', 'remove_pin', 'add_point', 'remove_point', 'duplicate', 'drag', 'move'):
                        record = dict(visible=visible, arranged=arranged, action=action, runs=[])
                        for profiled in (False, False, True):
                            avatar['dd_arrangement_volumes'] = volumes
                            active.session = Session(Document.loads(base))
                            active.session.undo_stack = list(undo)
                            target = active.session.document.patterns[0 if arranged else 1]
                            active.session.select_piece(target.id)
                            scene = bpy.context.scene
                            scene.dd_document = base
                            scene.dd_reference_visible = visible
                            active._stored = base
                            garment.build_panels(bpy.context)
                            active.refresh_controls()
                            for iteration in range(3):
                                bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                            sample = measure(active, target, action, region, profiled)
                            record['runs'].append(sample)
                            print('ACTION', visible, arranged, action, profiled, round(sample['action_ms'], 2), flush=True)
                        result['records'].append(record)
                        (output / f'action-performance-{label}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            result['idle'] = []
            for visible in (False, True):
                scene.dd_reference_visible = visible
                for iteration in range(12):
                    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                frames = []
                draw_times.clear()
                point_count = len(arrangement_controls._projection_cache[1]) if visible and arrangement_controls._projection_cache else 0
                if visible and not point_count:
                    raise AssertionError('Visible guide benchmark has no visible points.')
                for iteration in range(120):
                    started = time.perf_counter()
                    bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
                    frames.append((time.perf_counter() - started) * 1000)
                result['idle'].append(dict(visible=visible, fps=1000 / statistics.mean(frames),
                                           point_count=point_count, cached_draw_ms=statistics.mean(draw_times)))
            result['complete'] = True
    except Exception:
        result['error'] = traceback.format_exc()
        traceback.print_exc()
    (output / f'action-performance-{label}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    bpy.ops.wm.quit_blender()


bpy.app.timers.register(run, first_interval=2)
