import importlib
import json
import math
import sys
import traceback
from pathlib import Path
from types import SimpleNamespace
import bpy
from bpy_extras import view3d_utils
from mathutils import Quaternion, Vector

SETTINGS = json.loads(sys.argv[sys.argv.index('--') + 1])
OUTPUT = Path(SETTINGS['output'])
PACKAGE = SETTINGS['package']
bpy.context.preferences.view.show_splash = False
records = {}
errors = {}


def module(name):
    return importlib.import_module(PACKAGE + '.' + name)


def capsule(radius, start, end):
    start, end = Vector(start), Vector(end)
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=radius, depth=(end - start).length, location=(start + end) / 2)
    part = bpy.context.object
    part.rotation_mode = 'QUATERNION'
    part.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(end - start)
    return part


def ellipsoid(radii, location):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1, location=location)
    part = bpy.context.object
    part.scale = radii
    return part


def mannequin(name, scale=1.0):
    bpy.ops.object.select_all(action='DESELECT')
    parts = [ellipsoid((.15, .11, .30), (0, 0, 1.18)), ellipsoid((.17, .12, .16), (0, 0, .92)),
             ellipsoid((.09, .1, .12), (0, 0, 1.62)), capsule(.05, (0, 0, 1.40), (0, 0, 1.55)),
             capsule(.075, (.09, 0, .90), (.09, 0, .05)), capsule(.075, (-.09, 0, .90), (-.09, 0, .05)),
             capsule(.045, (.17, 0, 1.40), (.40, 0, 1.00)), capsule(.045, (-.17, 0, 1.40), (-.40, 0, 1.00)),
             ellipsoid((.18, .08, .06), (0, 0, 1.40))]
    for part in parts:
        part.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    body = bpy.context.object
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    remesh = body.modifiers.new('Skin', 'REMESH')
    remesh.mode = 'VOXEL'
    remesh.voxel_size = .012
    bpy.ops.object.modifier_apply(modifier=remesh.name)
    bpy.ops.object.shade_smooth()
    body.name = name
    body.scale = (scale, scale, scale)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return body


def surface(body, x, z):
    hit, location, _, _ = body.ray_cast(Vector((x, -2, z)), Vector((0, 1, 0)))
    return body.matrix_world @ location if hit else Vector((x, -.12, z))


def view_area():
    area = next(area for area in bpy.context.screen.areas if area.type == 'VIEW_3D')
    return area, next(region for region in area.regions if region.type == 'WINDOW')


def editor():
    return module('editor')._active


def event(kind, point, value='PRESS', **modifiers):
    _, region = view_area()
    data = dict(type=kind, value=value, mouse_x=point[0] + region.x, mouse_y=point[1] + region.y, ctrl=False, shift=False, alt=False, unicode='')
    data.update(modifiers)
    return SimpleNamespace(**data)


def click(point):
    active = editor()
    active.handle_event(bpy.context, event('LEFTMOUSE', point))
    active.handle_event(bpy.context, event('LEFTMOUSE', point, 'RELEASE'))


def window_rect(rect):
    _, region = view_area()
    return [region.x + rect.x, region.y + rect.y, rect.w, rect.h]


def union(*rects):
    left = min(rect[0] for rect in rects)
    bottom = min(rect[1] for rect in rects)
    right = max(rect[0] + rect[2] for rect in rects)
    top = max(rect[1] + rect[3] for rect in rects)
    return [left, bottom, right - left, top - bottom]


def around(point, reach):
    _, region = view_area()
    return [region.x + point[0] - reach, region.y + point[1] - reach, 2 * reach, 2 * reach]


def whole():
    _, region = view_area()
    return [region.x, region.y, region.width, region.height]


def piece_rect(pattern):
    active = editor()
    canvas = active.canvas_layout.canvas
    outline = pattern.outline()
    points = [active.view.screen(point, canvas) for point in outline]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    _, region = view_area()
    return [region.x + min(xs), region.y + min(ys), max(xs) - min(xs), max(ys) - min(ys)]


def card_rect():
    card = editor().minimal_card()
    return window_rect(card[0]) if card else whole()


def fresh(session):
    active = editor()
    active.cancel_gesture()
    active.card_kind = None
    active.seam_selected = None
    active.pending_edge = None
    active.pending_tack = None
    active.session = session
    active.persist()
    active.choose_tool('SELECT')
    if not active.full:
        active.restore_canvas()
    active.canvas_layout = active.make_layout()
    active.fit()
    active.pointer = (-100000, -100000)
    active.message = ''


def redraw():
    for area in bpy.context.screen.areas:
        area.tag_redraw()


def capture(name, focus, aspect):
    redraw()
    records[name] = dict(focus=[float(value) for value in focus], aspect=aspect)
    bpy.ops.screen.screenshot(filepath=str(OUTPUT / (name + '.png')))


def plan():
    core = module('core')
    garment = module('garment')
    library = module('library')
    scene = bpy.context.scene
    for obj in list(scene.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    area, region = view_area()
    space = area.spaces.active
    space.show_region_ui = False
    space.shading.type = 'SOLID'
    space.overlay.show_floor = True
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.screen.screen_full_area(use_hide_panels=False)
    area, region = view_area()
    area.ui_type = 'PREFERENCES'
    bpy.context.preferences.active_section = 'ADDONS'
    bpy.context.window_manager.addon_search = 'Devil'
    yield 1.5
    preferences = next(item for item in bpy.context.screen.areas if item.type == 'PREFERENCES')
    top = preferences.y + preferences.height
    capture('shot-install-enable-addon', [preferences.x, top - 420, 560, 420], '4:3')
    preferences.ui_type = 'VIEW_3D'
    yield .5
    area, region = view_area()
    area.spaces.active.show_region_ui = False
    body = mannequin('Mannequin')
    scene.dd_avatar = body
    scene.dd_spacing = .02
    scene.dd_library_dir = SETTINGS['library']
    with bpy.context.temp_override(area=area, region=region):
        bpy.ops.devil_designer.pattern_editor('INVOKE_DEFAULT')
    active = editor()
    active.pointer = (-100000, -100000)
    yield 1.5
    capture('shot-install-editor-view', whole(), '16:9')
    scene.dd_reference_visible = False
    yield .3

    session = core.Session()
    session.add([(0, 0), (.3, 0), (.34, .22), (.3, .46), (0, .46)])
    fresh(session)
    pattern = active.session.document.patterns[0]
    active.session.select_point(pattern.id, 'OUTER', 2, toggle=False)
    active.sync_selection()
    active.perform_action('CURVE')
    active.canvas_layout = active.make_layout()
    canvas = active.canvas_layout.canvas
    vertex = active.session.document.patterns[0].vertices[2]
    spot = active.view.screen((vertex.x, vertex.y), canvas)
    active.pointer = spot
    active.show_card('POINT', spot)
    active.pointer = (-100000, -100000)
    yield .8
    capture('shot-draft-bezier-editing', union(card_rect(), around(spot, 90)), '4:3')
    yield .3

    session = core.Session()
    session.add([(0, 0), (.25, 0), (.28, .42), (0, .5)])
    fresh(session)
    pattern = active.session.document.patterns[0]
    active.session.select_edge(active.session.document.edge(pattern.id, 3))
    active.sync_selection()
    active.perform_action('MIRROR_SEW')
    active.card_kind = None
    active.fit()
    yield .8
    capture('shot-draft-mirror-with-seam', whole(), '16:9')
    yield .3

    folding = module('folding')
    session = core.Session()
    session.add([(0, 0), (.5, 0), (.5, .4), (0, .4)])
    session.add_path([(.15, 0), (.15, .4)])
    folding.author_fold(session, 'MOUNTAIN')
    session.add_path([(.35, 0), (.35, .4)])
    folding.author_fold(session, 'VALLEY')
    fresh(session)
    active.session.selected = active.session.document.patterns[0].id
    active.sync_selection()
    yield .8
    capture('shot-draft-fold-pleats', piece_rect(active.session.document.patterns[0]), '4:3')
    yield .3

    image = bpy.data.images.new('Reference sketch', width=96, height=128)
    pixels = []
    for row in range(128):
        for column in range(96):
            inside = 18 < column < 78 and 10 < row < 110 and abs(column - 48) < 30 - max(0, row - 90) * .2
            pixels.extend((.86, .82, .74, 1) if not inside else (.32, .46, .62, 1))
    image.pixels = pixels
    image.filepath_raw = str(OUTPUT / 'reference-sketch.png')
    image.file_format = 'PNG'
    image.save()
    scene.dd_trace_path = image.filepath_raw
    scene.dd_trace_width = .6
    scene.dd_trace_x = 0
    scene.dd_trace_y = 0
    scene.dd_trace_opacity = .7
    session = core.Session()
    session.add([(-.2, -.35), (.2, -.35), (.2, .3), (-.2, .3)])
    fresh(session)
    active.session.selected = None
    active.sync_selection()
    active.fit()
    active.canvas_layout = active.make_layout()
    corners = module('tracing').entry_corners(module('tracing').active_entry(scene))[1]
    screen = [active.view.screen(point, active.canvas_layout.canvas) for point in corners]
    xs = [point[0] for point in screen]
    ys = [point[1] for point in screen]
    active.show_card('TRACE_CALIBRATION', (max(xs) + 12, max(ys)))
    yield .8
    capture('shot-draft-trace-reference', union([region.x + min(xs), region.y + min(ys), max(xs) - min(xs), max(ys) - min(ys)], card_rect()), '4:3')
    active.card_kind = None
    scene.dd_trace_path = ''
    yield .3

    session = core.Session()
    session.add([(0, 0), (.3, 0), (.32, .3), (.2, .46), (0, .46)])
    fresh(session)
    active.session.selected = active.session.document.patterns[0].id
    active.sync_selection()
    active.minimal_action('CLONE_LINKED')
    active.card_kind = None
    active.fit()
    yield .8
    capture('shot-quickstart-mirrored-twin', whole(), '16:9')
    yield .3

    session = core.Session()
    session.add([(0, 0), (.3, 0), (.3, .4), (0, .4)])
    session.add([(.45, 0), (.75, 0), (.75, .43), (.45, .43)])
    first, second = session.document.patterns
    session.sew(session.document.edge(first.id, 1), session.document.edge(second.id, 3))
    session.sew(session.document.edge(first.id, 2), session.document.edge(second.id, 2))
    fresh(session)
    active.choose_tool('SEW')
    yield .8
    capture('shot-quickstart-seam-mismatch', whole(), '16:9')
    active.choose_tool('SELECT')
    seams = active.session.document.seams
    active.seam_selected = seams[0].id
    yield .3
    badge = next(rect for rect, identity, _ in active.seam_badges() if identity == seams[0].id)
    active.show_card('SEAM', (badge.x + badge.w + 6, badge.y + badge.h))
    yield .8
    capture('shot-sew-mismatch-warning', card_rect(), '4:3')
    active.card_kind = None
    active.seam_selected = None
    yield .3

    session = core.Session()
    session.add([(0, 0), (.3, 0), (.3, .4), (0, .4)])
    session.add([(.45, 0), (.75, 0), (.75, .4), (.45, .4)])
    first, second = session.document.patterns
    fresh(session)
    active.choose_tool('SEW')
    active.pending_edge = active.session.document.edge(first.id, 1)
    yield .8
    canvas = active.canvas_layout.canvas
    middle = active.view.screen((.375, .2), canvas)
    capture('shot-sew-segment-selection', around(middle, 330), '4:3')
    active.pending_edge = None
    active.session.sew(active.session.document.edge(first.id, 1), active.session.document.edge(second.id, 3))
    active.persist()
    active.choose_tool('SEW')
    yield .3
    seam = active.session.document.seams[0]
    active.seam_selected = seam.id
    badge = next(rect for rect, identity, _ in active.seam_badges() if identity == seam.id)
    active.show_card('SEAM', (badge.x + badge.w + 6, badge.y + badge.h))
    yield .8
    capture('shot-sew-direction-reversal', union(card_rect(), around((badge.x + badge.w / 2, badge.y + badge.h / 2), 70)), '4:3')
    active.card_kind = None
    active.seam_selected = None
    yield .3

    fresh(core.Session())
    active.perform_action('STARTER_TEE')
    active.card_kind = None
    active.reveal_3d()
    view = area.spaces.active.region_3d
    view.view_rotation = Quaternion((1, 0, 0), math.pi / 2) @ Quaternion((0, 1, 0), -.35)
    view.view_location = Vector((.55, 0, 1.15))
    view.view_distance = 2.6
    view.view_perspective = 'PERSP'
    view.update()
    scene.dd_reference_visible = True
    scene.dd_points_visible = True
    active.fit()
    patterns = active.session.document.patterns
    active.session.selected = patterns[0].id
    active.sync_selection()
    yield 1.5
    capture('shot-arrange-wrap-points', whole(), '16:9')
    yield .3

    scene.dd_points_visible = False
    active.choose_tool('TACK')
    vertex = patterns[0].vertices[0]
    corner = active.view.screen((vertex.x, vertex.y), active.canvas_layout.canvas)
    click(corner)
    spot = surface(body, -.08, 1.05)
    target = view3d_utils.location_3d_to_region_2d(region, view, spot)
    if target is not None and active.pending_tack is not None:
        click(target)
    active.choose_tool('SELECT')
    yield 1.0
    anchors = active.session.document.anchors
    tacked = [anchor for anchor in anchors if anchor.kind == 'TACK']
    records['tack-count'] = dict(focus=[0, 0, 0, 0], aspect='none', count=len(tacked))
    active.restore_canvas()
    scene.dd_reference_visible = False
    active.session.selected = None
    active.sync_selection()
    active.fit()
    active.canvas_layout = active.make_layout()
    active.message = ''
    yield .8
    marker = active.view.screen((tacked[0].x, tacked[0].y), active.canvas_layout.canvas) if tacked else None
    focus = around(marker, 200) if marker is not None else whole()
    capture('shot-arrange-avatar-tacks', focus, '4:3')
    if tacked:
        active.session.commit(lambda: active.session.document.anchors.clear())
        active.persist()
    yield .3

    fresh(core.Session())
    active.perform_action('STARTER_TANK')
    active.card_kind = None
    active.reveal_3d()
    view.view_rotation = Quaternion((1, 0, 0), math.pi / 2) @ Quaternion((0, 1, 0), -.35)
    view.view_location = Vector((.55, 0, 1.1))
    view.view_distance = 2.4
    view.update()
    yield .5
    active.perform_action('SIMULATE')
    yield 9.0
    active.perform_action('SIMULATE')
    yield 1.0
    active.pointer = (-100000, -100000)
    capture('dd-overview', whole(), '16:9')
    yield .3
    active.fit_overlay.toggle()
    yield 1.0
    capture('shot-simulate-fit-map', whole(), '16:9')
    active.fit_overlay.toggle()
    yield .3
    active.canvas_layout = active.make_layout()
    button = active.canvas_layout.buttons['KEEP_OPTIONS'][0]
    active.show_card('KEEP', (button.x, button.y + button.h))
    yield .8
    capture('shot-simulate-keep-mesh', union(card_rect(), window_rect(active.canvas_layout.buttons['KEEP'][0])), '4:3')
    active.card_kind = None
    active.perform_action('KEEP')
    yield 2.0
    kept = garment.generated(scene, 'final')
    records['kept'] = dict(focus=[0, 0, 0, 0], aspect='none', count=len(kept), message=active.message)
    if kept:
        for obj in bpy.context.view_layer.objects:
            obj.select_set(False)
        kept[0].select_set(True)
        bpy.context.view_layer.objects.active = kept[0]
        kept[0].name = 'Tank'
    active.pointer = (-100000, -100000)
    yield 1.0
    capture('shot-quickstart-mesh-keep', whole(), '16:9')
    yield .3
    active.canvas_layout = active.make_layout()
    if 'SIMULATE_OPTIONS' in active.canvas_layout.buttons:
        button = active.canvas_layout.buttons['SIMULATE_OPTIONS'][0]
        active.show_card('SIMULATE', (button.x, button.y + 45 * active.canvas_layout.scale))
        rows = active.card_rows('SIMULATE')[1]
        if any(row[0] == 'WEAR_OVER_0' and row[2] == 'Off' for row in rows):
            active.minimal_action('WEAR_OVER_0')
            active.show_card('SIMULATE', (button.x, button.y + 45 * active.canvas_layout.scale))
        yield .8
        capture('shot-simulate-layer-settings', union(card_rect(), window_rect(active.canvas_layout.buttons['SIMULATE'][0])), '4:3')
        active.card_kind = None
    yield .3

    library.save(bpy.context, 'Summer tank', ['Top'])
    fresh(core.Session())
    active.perform_action('STARTER_TEE')
    active.card_kind = None
    library.save(bpy.context, 'Everyday tee', ['Top'])
    active.restore_canvas()
    active.show_card('LIBRARY')
    active.refresh_library()
    yield 1.5
    capture('shot-library-save-garment', whole(), '16:9')
    active.card_kind = None
    yield .3

    for obj in list(scene.objects):
        if obj.get('dd_kind') in {'final', 'simulation', 'panel', 'anchor'}:
            bpy.data.objects.remove(obj, do_unlink=True)
    body.hide_set(True)
    smaller = mannequin('Second avatar', .86)
    scene.dd_avatar = smaller
    fresh(core.Session())
    entries = library.entries(scene)
    index = next((position for position, path in enumerate(entries) if 'Everyday' in Path(path).name or 'everyday' in Path(path).name.lower()), 0)
    scene.dd_library_selected = index
    library.load(bpy.context, index)
    active.reconcile_generated_document()
    active.reveal_3d()
    view.view_location = Vector((.5, 0, 1.0))
    view.view_distance = 2.4
    view.update()
    yield 2.0
    capture('shot-library-load-avatar', whole(), '16:9')


def drive():
    try:
        delay = next(steps)
        return delay
    except StopIteration:
        finish()
        return None
    except Exception:
        errors['plan'] = traceback.format_exc()
        traceback.print_exc()
        finish()
        return None


def finish():
    (OUTPUT / 'records.json').write_text(json.dumps(dict(records=records, errors=errors, window=[bpy.context.window.width, bpy.context.window.height]), indent=1), encoding='utf-8')
    bpy.ops.wm.quit_blender()


steps = plan()
bpy.app.timers.register(drive, first_interval=2.0)
