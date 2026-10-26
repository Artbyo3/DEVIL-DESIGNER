import math
from pathlib import Path


PROPERTIES = (
    'dd_trace_path', 'dd_trace_width', 'dd_trace_x', 'dd_trace_y',
    'dd_trace_opacity', 'dd_trace_visible', 'dd_trace_length', 'dd_trace_error',
)
_classes = []
_images = {}


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


def image_corners(width, image_size, position):
    pixel_width, pixel_height = image_size
    origin_x, origin_y = position
    if not all(math.isfinite(value) for value in (width, pixel_width, pixel_height, origin_x, origin_y)):
        raise ValueError('The reference image size or position is invalid.')
    if width <= 0 or pixel_width <= 0 or pixel_height <= 0:
        raise ValueError('Choose an image with a valid width and height.')
    height = width * pixel_height / pixel_width
    return (
        (origin_x, origin_y), (origin_x + width, origin_y),
        (origin_x + width, origin_y + height), (origin_x, origin_y + height),
    )


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


def reference_corners(scene):
    if not scene.dd_trace_path:
        return ()
    try:
        image = load_image(scene.dd_trace_path)
        corners = image_corners(scene.dd_trace_width, image.size[:], (scene.dd_trace_x, scene.dd_trace_y))
    except (ValueError, ReferenceError) as error:
        scene.dd_trace_error = str(error)
        return ()
    scene.dd_trace_error = ''
    return corners


def draw_reference(ed, renderer):
    scene = ed._scene
    if not scene.dd_trace_visible or scene.dd_trace_opacity <= 0 or not scene.dd_trace_path:
        return False
    try:
        image = load_image(scene.dd_trace_path)
        corners = image_corners(scene.dd_trace_width, image.size[:], (scene.dd_trace_x, scene.dd_trace_y))
        points = [ed.view.screen(point, ed.canvas_layout.canvas) for point in corners]
        import gpu
        from gpu_extras.batch import batch_for_shader

        shader = getattr(renderer, '_trace_shader', None)
        if shader is None:
            shader = gpu.shader.from_builtin('IMAGE_COLOR')
            renderer._trace_shader = shader
        texture = gpu.texture.from_image(image)
        batch = batch_for_shader(
            shader, 'TRIS',
            {'pos': points, 'texCoord': [(0, 0), (1, 0), (1, 1), (0, 1)]},
            indices=[(0, 1, 2), (0, 2, 3)],
        )
        blend = gpu.state.blend_get()
        try:
            gpu.state.blend_set('ALPHA')
            shader.bind()
            shader.uniform_sampler('image', texture)
            shader.uniform_float('color', (1, 1, 1, scene.dd_trace_opacity))
            batch.draw(shader)
        finally:
            gpu.state.blend_set(blend)
    except (ValueError, RuntimeError, ReferenceError) as error:
        scene.dd_trace_error = str(error) if isinstance(error, ValueError) else 'Could not display the reference image. Try Load image again.'
        return False
    scene.dd_trace_error = ''
    return True


def _make_operator(bpy):
    class DD_OT_load_trace_image(bpy.types.Operator):
        bl_idname = 'devil.load_trace_image'
        bl_label = 'Load reference image'
        bl_description = 'Place a still image behind the pattern canvas for tracing'
        bl_options = {'REGISTER', 'UNDO'}

        filepath: bpy.props.StringProperty(name='Image', subtype='FILE_PATH')
        filter_glob: bpy.props.StringProperty(default='*.png;*.jpg;*.jpeg;*.webp;*.bmp;*.tif;*.tiff;*.tga;*.exr', options={'HIDDEN'})

        def invoke(self, context, event):
            self.filepath = context.scene.dd_trace_path
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
