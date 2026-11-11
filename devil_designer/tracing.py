import json
import math
from pathlib import Path


PROPERTIES = (
    'dd_trace_path', 'dd_trace_width', 'dd_trace_x', 'dd_trace_y',
    'dd_trace_opacity', 'dd_trace_visible', 'dd_trace_length', 'dd_trace_error',
    'dd_trace_rotation', 'dd_trace_flip_x', 'dd_trace_flip_y', 'dd_trace_locked', 'dd_trace_stack',
)
ENTRY_FIELDS = {'path': '', 'width': 1.0, 'x': 0.0, 'y': 0.0, 'opacity': .35, 'visible': True,
                'rotation': 0.0, 'flip_x': False, 'flip_y': False, 'locked': False}
REFERENCE_GAP = .05
_classes = []
_images = {}


def active_entry(scene):
    return {field: getattr(scene, 'dd_trace_' + field, default) for field, default in ENTRY_FIELDS.items()}


def apply_entry(scene, entry):
    for field, default in ENTRY_FIELDS.items():
        setattr(scene, 'dd_trace_' + field, type(default)(entry.get(field, default)))


def valid_entry(entry):
    if not isinstance(entry, dict) or not isinstance(entry.get('path'), str) or not entry['path']:
        return False
    for field, default in ENTRY_FIELDS.items():
        value = entry.get(field, default)
        if isinstance(default, bool):
            if type(value) is not bool:
                return False
        elif isinstance(default, float):
            if type(value) not in (int, float) or not math.isfinite(value):
                return False
    return entry.get('width', 1.0) > 0


def stack(scene):
    try:
        entries = json.loads(getattr(scene, 'dd_trace_stack', '') or '[]')
    except ValueError:
        return []
    if not isinstance(entries, list):
        return []
    return [dict(ENTRY_FIELDS, **entry) for entry in entries if valid_entry(entry)]


def write_stack(scene, entries):
    scene.dd_trace_stack = json.dumps(entries)


def reference_count(scene):
    return (1 if scene.dd_trace_path else 0) + len(stack(scene))


def add_reference(scene, path):
    entries = stack(scene)
    entry = dict(ENTRY_FIELDS, path=path)
    if scene.dd_trace_path:
        current = active_entry(scene)
        entries.append(current)
        entry.update(width=current['width'], y=current['y'], opacity=current['opacity'],
                     x=max(item['x'] + item['width'] for item in entries) + REFERENCE_GAP)
    write_stack(scene, entries)
    apply_entry(scene, entry)
    scene.dd_trace_error = ''


def cycle_reference(scene):
    entries = stack(scene)
    if not entries:
        return False
    current = active_entry(scene)
    write_stack(scene, entries[1:] + ([current] if current['path'] else []))
    apply_entry(scene, entries[0])
    scene.dd_trace_error = ''
    return True


def remove_reference(scene):
    entries = stack(scene)
    if entries:
        write_stack(scene, entries[1:])
        apply_entry(scene, entries[0])
    else:
        scene.dd_trace_path = ''
    scene.dd_trace_error = ''


def calibrated_width(width, first, second, measured_meters):
    values = (width, measured_meters, *first, *second)
    if len(first) != 2 or len(second) != 2 or not all(math.isfinite(value) for value in values):
        raise ValueError('Use two finite points on the image and a valid measurement.')
    if width <= 0 or measured_meters <= 0:
        raise ValueError('Image width and measured distance must be greater than zero.')
    distance = math.dist(first, second)
    if distance <= 1e-9:
        raise ValueError('Pick two different points on the reference image.')
    result = width * (measured_meters / distance)
    if not math.isfinite(result) or result < 0.000001:
        raise ValueError('This measurement is too large or too small. Choose another distance.')
    return result


def image_corners(width, image_size, position, rotation=0.0):
    pixel_width, pixel_height = image_size
    origin_x, origin_y = position
    if not all(math.isfinite(value) for value in (width, pixel_width, pixel_height, origin_x, origin_y, rotation)):
        raise ValueError('The reference image size or position is invalid.')
    if width <= 0 or pixel_width <= 0 or pixel_height <= 0:
        raise ValueError('Choose an image with a valid width and height.')
    height = width * pixel_height / pixel_width
    corners = (
        (origin_x, origin_y), (origin_x + width, origin_y),
        (origin_x + width, origin_y + height), (origin_x, origin_y + height),
    )
    if not rotation:
        return corners
    center_x, center_y = origin_x + width / 2, origin_y + height / 2
    cosine, sine = math.cos(math.radians(rotation)), math.sin(math.radians(rotation))
    return tuple((center_x + (x - center_x) * cosine - (y - center_y) * sine,
                  center_y + (x - center_x) * sine + (y - center_y) * cosine) for x, y in corners)


def scaled_about_center(width, image_size, position, factor):
    if not math.isfinite(factor) or factor <= 0:
        raise ValueError('Drag the corner away from the image center.')
    height = width * image_size[1] / image_size[0]
    center_x, center_y = position[0] + width / 2, position[1] + height / 2
    scaled = max(width * factor, 0.000001)
    return scaled, (center_x - scaled / 2, center_y - scaled * image_size[1] / image_size[0] / 2)


def turned(rotation, center, start, now, step=0.0):
    angle = rotation + math.degrees(math.atan2(now[1] - center[1], now[0] - center[0])
                                    - math.atan2(start[1] - center[1], start[0] - center[0]))
    if step:
        angle = round(angle / step) * step
    return (angle + 180.0) % 360.0 - 180.0


def inside(corners, point):
    signs = [(bx - ax) * (point[1] - ay) - (by - ay) * (point[0] - ax) >= 0
             for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1])]
    return all(signs) or not any(signs)


def calibrate(scene, first, second):
    width = calibrated_width(scene.dd_trace_width, first, second, scene.dd_trace_length)
    factor = width / scene.dd_trace_width
    origin_x = first[0] + (scene.dd_trace_x - first[0]) * factor
    origin_y = first[1] + (scene.dd_trace_y - first[1]) * factor
    if not all(math.isfinite(value) for value in (origin_x, origin_y)):
        raise ValueError('This measurement is too large. Choose another distance.')
    scene.dd_trace_width = width
    scene.dd_trace_x = origin_x
    scene.dd_trace_y = origin_y
    scene.dd_trace_error = ''
    return width


def load_image(filepath, retry=False):
    import bpy

    if not filepath:
        raise ValueError('Choose a reference image first.')
    resolved = bpy.path.abspath(filepath)
    cached = _images.get(resolved)
    if cached is not None and not retry:
        image, error = cached
        if error:
            raise ValueError(error)
        try:
            if image.size[0] > 0 and image.size[1] > 0:
                return image
        except ReferenceError:
            pass
    try:
        if not Path(resolved).is_file():
            raise ValueError('Reference image not found. Choose the file again with Load image.')
        image = bpy.data.images.load(resolved, check_existing=True)
        if image.source != 'FILE' or image.size[0] <= 0 or image.size[1] <= 0:
            raise ValueError('This file is not a usable still image. Choose a PNG or JPEG image.')
    except (OSError, RuntimeError, ValueError):
        error = (
            'Reference image not found. Choose the file again with Load image.'
            if not Path(resolved).is_file()
            else 'Could not open this image. Choose a readable PNG or JPEG file.'
        )
        _images[resolved] = (None, error)
        raise ValueError(error) from None
    _images[resolved] = (image, '')
    return image


def entry_corners(entry):
    image = load_image(entry['path'])
    return image, image_corners(entry['width'], image.size[:], (entry['x'], entry['y']), entry['rotation'])


def reference_corners(scene):
    if not scene.dd_trace_path:
        return ()
    try:
        corners = entry_corners(active_entry(scene))[1]
    except (ValueError, ReferenceError) as error:
        scene.dd_trace_error = str(error)
        return ()
    scene.dd_trace_error = ''
    return corners


def all_reference_corners(scene):
    points = list(reference_corners(scene)) if scene.dd_trace_visible else []
    for entry in stack(scene):
        if entry['visible']:
            try:
                points += entry_corners(entry)[1]
            except (ValueError, ReferenceError):
                continue
    return points


def draw_entry(ed, renderer, entry):
    import gpu
    from gpu_extras.batch import batch_for_shader

    image, corners = entry_corners(entry)
    points = [ed.view.screen(point, ed.canvas_layout.canvas) for point in corners]
    shader = getattr(renderer, '_trace_shader', None)
    if shader is None:
        shader = gpu.shader.from_builtin('IMAGE_COLOR')
        renderer._trace_shader = shader
    texture = gpu.texture.from_image(image)
    coordinates = [((1 - u) if entry['flip_x'] else u, (1 - v) if entry['flip_y'] else v)
                   for u, v in ((0, 0), (1, 0), (1, 1), (0, 1))]
    batch = batch_for_shader(shader, 'TRIS', {'pos': points, 'texCoord': coordinates}, indices=[(0, 1, 2), (0, 2, 3)])
    blend = gpu.state.blend_get()
    try:
        gpu.state.blend_set('ALPHA')
        shader.bind()
        shader.uniform_sampler('image', texture)
        shader.uniform_float('color', (1, 1, 1, entry['opacity']))
        batch.draw(shader)
    finally:
        gpu.state.blend_set(blend)


def draw_reference(ed, renderer):
    scene = ed._scene
    missing = []
    for entry in stack(scene):
        if entry['visible'] and entry['opacity'] > 0:
            try:
                draw_entry(ed, renderer, entry)
            except (ValueError, RuntimeError, ReferenceError):
                missing.append(Path(entry['path']).name)
    shown = False
    active_error = ''
    if scene.dd_trace_visible and scene.dd_trace_opacity > 0 and scene.dd_trace_path:
        try:
            draw_entry(ed, renderer, active_entry(scene))
            shown = True
        except (ValueError, RuntimeError, ReferenceError) as error:
            active_error = str(error) if isinstance(error, ValueError) else 'Could not display the reference image. Try Load image again.'
    notes = [active_error] if active_error else []
    if missing:
        notes.append('Reference image not found: ' + ', '.join(missing) + '. Use Next image, then Replace image.')
    scene.dd_trace_error = ' '.join(notes)
    return shown


def _make_operator(bpy):
    class DD_OT_load_trace_image(bpy.types.Operator):
        bl_idname = 'devil.load_trace_image'
        bl_label = 'Load reference image'
        bl_description = 'Place a still image behind the pattern canvas for tracing'
        bl_options = {'REGISTER', 'UNDO'}

        filepath: bpy.props.StringProperty(name='Image', subtype='FILE_PATH')
        add: bpy.props.BoolProperty(name='Add as another image', default=False, options={'HIDDEN'})
        filter_glob: bpy.props.StringProperty(default='*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.tif;*.tiff;*.tga;*.exr', options={'HIDDEN'})

        def invoke(self, context, event):
            self.filepath = '' if self.add else context.scene.dd_trace_path
            context.window_manager.fileselect_add(self)
            return {'RUNNING_MODAL'}

        def execute(self, context):
            scene = context.scene
            try:
                load_image(self.filepath, retry=True)
            except ValueError as error:
                scene.dd_trace_error = str(error)
                self.report({'ERROR'}, str(error))
                return {'CANCELLED'}
            if self.add:
                add_reference(scene, bpy.path.abspath(self.filepath))
            else:
                scene.dd_trace_path = bpy.path.abspath(self.filepath)
            scene.dd_trace_visible = True
            scene.dd_trace_error = ''
            _redraw(scene, context)
            self.report({'INFO'}, 'Reference image loaded. Set its width or calibrate a known distance.')
            return {'FINISHED'}

    return DD_OT_load_trace_image


def _redraw(scene, context):
    if context is not None and context.screen is not None:
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def register():
    import bpy

    if _classes:
        return
    scene = bpy.types.Scene
    scene.dd_trace_path = bpy.props.StringProperty(name='Reference image', subtype='FILE_PATH', update=_redraw)
    scene.dd_trace_width = bpy.props.FloatProperty(name='Image width', subtype='DISTANCE', unit='LENGTH', default=1.0, min=0.000001, update=_redraw)
    scene.dd_trace_length = bpy.props.FloatProperty(name='Measured distance', subtype='DISTANCE', unit='LENGTH', default=0.1, min=0.000001, update=_redraw)
    scene.dd_trace_x = bpy.props.FloatProperty(name='Image X', subtype='DISTANCE', unit='LENGTH', update=_redraw)
    scene.dd_trace_y = bpy.props.FloatProperty(name='Image Y', subtype='DISTANCE', unit='LENGTH', update=_redraw)
    scene.dd_trace_opacity = bpy.props.FloatProperty(name='Image opacity', default=0.35, min=0.0, max=1.0, subtype='FACTOR', update=_redraw)
    scene.dd_trace_visible = bpy.props.BoolProperty(name='Show reference image', default=True, update=_redraw)
    scene.dd_trace_error = bpy.props.StringProperty(name='Reference image message', options={'SKIP_SAVE'})
    scene.dd_trace_rotation = bpy.props.FloatProperty(name='Image rotation', default=0.0, min=-180.0, max=180.0, update=_redraw)
    scene.dd_trace_flip_x = bpy.props.BoolProperty(name='Mirror image horizontally', default=False, update=_redraw)
    scene.dd_trace_flip_y = bpy.props.BoolProperty(name='Mirror image vertically', default=False, update=_redraw)
    scene.dd_trace_locked = bpy.props.BoolProperty(name='Lock reference image', default=False, update=_redraw)
    scene.dd_trace_stack = bpy.props.StringProperty(name='Other reference images', default='[]', update=_redraw)
    operator = _make_operator(bpy)
    bpy.utils.register_class(operator)
    _classes.append(operator)


def unregister():
    import bpy

    for operator in reversed(_classes):
        bpy.utils.unregister_class(operator)
    _classes.clear()
    for name in PROPERTIES:
        if hasattr(bpy.types.Scene, name):
            delattr(bpy.types.Scene, name)
    _images.clear()
