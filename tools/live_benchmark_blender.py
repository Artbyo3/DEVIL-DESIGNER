import json
import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np

ARGUMENTS = json.loads(sys.argv[sys.argv.index('--') + 1]) if '--' in sys.argv else {}
ROOT = Path(ARGUMENTS.get('root', Path(__file__).resolve().parents[1]))
OUTPUT = Path(ARGUMENTS.get('output', ROOT / 'scratch' / 'live_benchmark.json'))
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
import devil_designer
from devil_designer import garment, xpbd, xpbd_live
from devil_designer.core import Session

BODIES = {'dense': (256, 138), 'light': (24, 16)}
TORSO_RADII = (.16, .13, .6)
TORSO_CENTER = 1.0
TUBE_SIZE = 6
PANEL_WIDTH = .2
LAYER_GROWTH = .03
PANEL_HEIGHT = .65
PANEL_BOTTOM = .65
WARMUP_FRAMES = int(ARGUMENTS.get('warmup', 20))
MEASURED_FRAMES = int(ARGUMENTS.get('frames', 60))
VARIANTS = ARGUMENTS.get('variants', ['full'])
PANEL_COUNTS = ARGUMENTS.get('panels', [3, 10, 20, 30])
BODY = ARGUMENTS.get('body', 'dense')
VIEWPORT = bool(ARGUMENTS.get('viewport', False))


def torso(kind):
    segments, rings = BODIES[kind]
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments, ring_count=rings, radius=1.0, location=(0, 0, TORSO_CENTER))
    body = bpy.context.object
    body.name = 'Benchmark torso ' + kind
    body.scale = TORSO_RADII
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    body.data.calc_loop_triangles()
    return body


def far_triangle():
    mesh = bpy.data.meshes.new('Benchmark far triangle')
    mesh.from_pydata([(0, 0, -100), (.01, 0, -100), (0, .01, -100)], [], [(0, 1, 2)])
    far = bpy.data.objects.new('Benchmark far triangle', mesh)
    bpy.context.scene.collection.objects.link(far)
    far.hide_set(True)
    return far


def layout(count):
    slots = []
    for index in range(count):
        tube, side = divmod(index, TUBE_SIZE)
        width = PANEL_WIDTH + tube * LAYER_GROWTH
        slots.append((tube, side, width))
    return slots


def garment_scene(scene, count):
    session = Session()
    slots = layout(count)
    for _, _, width in slots:
        session.add([(-width / 2, 0), (width / 2, 0), (width / 2, PANEL_HEIGHT), (-width / 2, PANEL_HEIGHT)])
        session.document.patterns[-1].placement_mode = 'LEGACY'
    patterns = session.document.patterns
    for first in range(0, count, TUBE_SIZE):
        members = list(range(first, min(first + TUBE_SIZE, count)))
        pairs = list(zip(members, members[1:])) + ([(members[-1], members[0])] if len(members) == TUBE_SIZE else [])
        for left, right in pairs:
            session.sew_chains([session.document.edge(patterns[left].id, 1)], [session.document.edge(patterns[right].id, 3)])
    scene.dd_document = session.document.dumps()
    panels = garment.build_panels(bpy.context)
    by_id = {panel['dd_pattern_id']: panel for panel in panels}
    for pattern, (tube, side, width) in zip(patterns, slots):
        panel = by_id[pattern.id]
        apothem = width * math.sqrt(3) / 2
        angle = 2 * math.pi * side / TUBE_SIZE
        panel.location = (apothem * math.cos(angle), apothem * math.sin(angle), PANEL_BOTTOM)
        panel.rotation_euler = (math.pi / 2, 0, angle + math.pi / 2)
    bpy.context.view_layer.update()
    return session.document


def clear_scene():
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in list(bpy.data.meshes):
        bpy.data.meshes.remove(mesh)


class HandlerClock:
    def __init__(self):
        self.spent = 0.0
        self.wrapped = []

    def wrap(self, callback):
        clock = self

        def timed(*arguments):
            started = time.perf_counter()
            try:
                return callback(*arguments)
            finally:
                clock.spent += time.perf_counter() - started
        timed._persistent = True
        return timed

    def install(self):
        for name in ('frame_change_pre', 'frame_change_post', 'depsgraph_update_pre', 'depsgraph_update_post'):
            handlers = getattr(bpy.app.handlers, name)
            originals = list(handlers)
            handlers.clear()
            for callback in originals:
                handlers.append(self.wrap(callback))
            self.wrapped.append((handlers, originals))

    def time_editor(self, owner):
        clock = self
        drawing, handling = owner.draw_overlay, owner.modal

        def draw_overlay(instance):
            started = time.perf_counter()
            try:
                return drawing(instance)
            finally:
                clock.spent += time.perf_counter() - started

        def modal(instance, context, event):
            started = time.perf_counter()
            try:
                return handling(instance, context, event)
            finally:
                clock.spent += time.perf_counter() - started
        owner.draw_overlay, owner.modal = draw_overlay, modal

    def take(self):
        spent, self.spent = self.spent, 0.0
        return spent * 1000.0


def statistics(values):
    ordered = np.sort(np.asarray(values, dtype=float))
    if not len(ordered):
        return dict(median=None, p95=None, mean=None)
    return dict(median=float(np.median(ordered)), p95=float(np.percentile(ordered, 95)), mean=float(ordered.mean()))


def quality(simulation):
    coordinates = xpbd_live.evaluated_points(bpy.context, simulation).astype(np.float64)
    pairs = np.array(json.loads(simulation['dd_sewing_pairs']), dtype=np.int64).reshape(-1, 2)
    gaps = np.linalg.norm(coordinates[pairs[:, 0]] - coordinates[pairs[:, 1]], axis=1) if len(pairs) else np.zeros(1)
    mesh = simulation.data
    edges = np.empty(len(mesh.edges) * 2, dtype=np.int32)
    mesh.edges.foreach_get('vertices', edges)
    edges = edges.reshape(-1, 2)
    loose = np.array([edge.is_loose for edge in mesh.edges], dtype=bool)
    linked = np.zeros(len(mesh.edges), dtype=bool)
    mesh.attributes['dd_bend_link'].data.foreach_get('value', linked)
    rest = np.empty(len(mesh.edges), dtype=np.float32)
    mesh.attributes['rest_length'].data.foreach_get('value', rest)
    chosen = ~loose & ~linked & (rest > 1e-6)
    ratios = np.linalg.norm(coordinates[edges[chosen, 0]] - coordinates[edges[chosen, 1]], axis=1) / rest[chosen]
    return dict(seam_gap_max_mm=float(gaps.max() * 1000), seam_gap_p99_mm=float(np.percentile(gaps, 99) * 1000),
                stretch_p99=float(np.percentile(ratios, 99)), lowest_z=float(coordinates[:, 2].min()),
                finite=bool(np.isfinite(coordinates).all()))


def apply_variant(simulation, variant, body, shell, far):
    xpbd.set_input(simulation, 'Body', far if variant in {'no_surface', 'no_collision'} else body)
    xpbd.set_input(simulation, 'Body Shell', None if variant in {'no_shell', 'no_collision'} else shell)
    simulation.update_tag()


def compiled(scene, count, kind):
    clear_scene()
    scene.frame_set(scene.frame_start)
    body = torso(kind)
    scene.dd_avatar = body
    garment_scene(scene, count)
    started = time.perf_counter()
    simulation = garment.compile_garment(bpy.context)
    compile_ms = (time.perf_counter() - started) * 1000.0
    body_input = xpbd.input_slot(simulation, 'Body').value
    shell_input = xpbd.input_slot(simulation, 'Body Shell').value
    return simulation, body, body_input, shell_input, compile_ms


def headless_variant(scene, simulation, clock):
    scene.frame_set(scene.frame_start)
    for _ in range(WARMUP_FRAMES):
        scene.frame_set(scene.frame_current + 1)
    frames, python = [], []
    clock.take()
    for _ in range(MEASURED_FRAMES):
        started = time.perf_counter()
        scene.frame_set(scene.frame_current + 1)
        frames.append((time.perf_counter() - started) * 1000.0)
        python.append(clock.take())
    return dict(frame_ms=statistics(frames), python_ms=statistics(python), samples=frames, **quality(simulation))


def describe(simulation, body, shell, count, kind, compile_ms):
    shell.data.calc_loop_triangles()
    return dict(panels=count, body=kind, body_triangles=len(body.data.loop_triangles), shell_triangles=len(shell.data.loop_triangles),
                cloth_vertices=len(simulation.data.vertices), sewing_pairs=len(json.loads(simulation['dd_sewing_pairs'])),
                substeps=xpbd.input_slot(simulation, 'Inner Substeps').value, compile_ms=compile_ms)


def run_headless():
    devil_designer.register()
    scene = bpy.context.scene
    scene.dd_spacing = .02
    scene.dd_pin_top = True
    clock = HandlerClock()
    clock.install()
    records = []
    for count in PANEL_COUNTS:
        simulation, body, collider, shell, compile_ms = compiled(scene, count, BODY)
        far = far_triangle()
        record = describe(simulation, body, shell, count, BODY, compile_ms)
        for variant in VARIANTS:
            apply_variant(simulation, variant, collider, shell, far)
            record[variant] = headless_variant(scene, simulation, clock)
            print('LIVE_BENCH', count, BODY, variant, json.dumps(record[variant]['frame_ms']), flush=True)
        apply_variant(simulation, 'full', collider, shell, far)
        records.append(record)
    finish(dict(mode='headless', records=records, blender=bpy.app.version_string))
    devil_designer.unregister()


def finish(result):
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=1), encoding='utf-8')
    print('LIVE_BENCH_DONE', OUTPUT, flush=True)


class ViewportRun:
    def __init__(self):
        self.scene = bpy.context.scene
        self.clock = HandlerClock()
        self.queue = list(PANEL_COUNTS)
        self.records = []
        self.state = None

    def view3d(self):
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    return window, area
        return None, None

    def start(self):
        from devil_designer import editor
        self.clock.time_editor(editor.DD_OT_pattern_editor)
        devil_designer.register()
        self.scene.dd_spacing = .02
        self.scene.dd_pin_top = True
        self.clock.install()
        bpy.app.handlers.frame_change_pre.append(self.frame_started)
        window, area = self.view3d()
        self.draw_handle = bpy.types.SpaceView3D.draw_handler_add(self.drawn, (), 'WINDOW', 'POST_PIXEL')
        for space in area.spaces:
            if space.type == 'VIEW_3D':
                space.shading.type = 'SOLID'
                space.region_3d.view_location = (0, 0, 1.0)
                space.region_3d.view_distance = 3.0
        self.next_case()
        return None

    def next_case(self):
        if not self.queue:
            bpy.types.SpaceView3D.draw_handler_remove(self.draw_handle, 'WINDOW')
            finish(dict(mode='viewport', records=self.records, blender=bpy.app.version_string))
            bpy.ops.wm.quit_blender()
            return None
        count = self.queue.pop(0)
        simulation, body, collider, shell, compile_ms = compiled(self.scene, count, BODY)
        self.simulation = simulation
        self.record = describe(simulation, body, shell, count, BODY, compile_ms)
        self.started, self.drawn_at, self.python = {}, {}, {}
        self.scene.frame_set(self.scene.frame_start)
        self.last_frame = self.scene.frame_start + WARMUP_FRAMES + MEASURED_FRAMES
        self.state = 'playing'
        window, area = self.view3d()
        with bpy.context.temp_override(window=window, area=area, region=next(region for region in area.regions if region.type == 'WINDOW'), screen=window.screen):
            bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
            bpy.ops.screen.animation_play()
        return .25

    def frame_started(self, scene, *_):
        if self.state == 'playing':
            self.started[scene.frame_current] = time.perf_counter()
            self.python[scene.frame_current] = self.clock.take()

    def drawn(self):
        if self.state == 'playing':
            frame = self.scene.frame_current
            self.drawn_at.setdefault(frame, time.perf_counter())

    def tick(self):
        if self.state != 'playing':
            return .25
        if self.scene.frame_current < self.last_frame:
            return .1
        window, area = self.view3d()
        with bpy.context.temp_override(window=window, area=area):
            bpy.ops.screen.animation_cancel(restore_frame=False)
        from devil_designer import editor
        if editor._active is not None:
            editor._active.cleanup()
        self.state = None
        first = self.scene.frame_start + WARMUP_FRAMES
        frames = range(first, self.last_frame)
        work = [(self.drawn_at[frame] - self.started[frame]) * 1000.0 for frame in frames if frame in self.drawn_at and frame in self.started]
        interval = [(self.started[frame + 1] - self.started[frame]) * 1000.0 for frame in frames if frame in self.started and frame + 1 in self.started]
        python = [self.python[frame + 1] for frame in frames if frame + 1 in self.python]
        self.record['full'] = dict(frame_ms=statistics(work), interval_ms=statistics(interval), python_ms=statistics(python),
                                   samples=work, frames_seen=len(work), **quality(self.simulation))
        print('LIVE_BENCH viewport', self.record['panels'], BODY, json.dumps(self.record['full']['frame_ms']), flush=True)
        self.records.append(self.record)
        return self.next_case()


def run_viewport():
    run = ViewportRun()
    bpy.app.timers.register(run.start, first_interval=1.0)
    bpy.app.timers.register(run.tick, first_interval=2.0)


if VIEWPORT:
    run_viewport()
else:
    run_headless()
