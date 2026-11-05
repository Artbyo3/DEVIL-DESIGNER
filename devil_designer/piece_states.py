import json
from .core import Document


FLAGS = ('frozen', 'deactivated', 'strengthened')
MULTIPLIER = 4


def label(pattern):
    if pattern.deactivated:
        return 'Deactivated'
    return ' · '.join(text for enabled, text in ((pattern.frozen, 'Frozen'), (pattern.strengthened, 'Strengthened ×4')) if enabled)


def toggle(session, flag):
    from .linked_editing import pair_for
    if flag not in FLAGS:
        raise ValueError('Unknown piece simulation state.')
    pattern = session.document.find(session.selected)
    if pattern is None:
        raise ValueError('Select a piece first.')
    targets = [pattern]
    pair = pair_for(session.document, pattern.id)
    if pair and pair['enabled']:
        targets = [session.document.find(identity) for identity in pair['members']]
    enabled = not getattr(pattern, flag)
    return session.commit(lambda: [setattr(target, flag, enabled) for target in targets])


def without_states(document):
    data = json.loads(document.dumps())
    for pattern in data['patterns']:
        pattern.pop('simulation', None)
    return Document.loads(json.dumps(data))


def active_document(document):
    active = without_states(document)
    identities = {pattern.id for pattern in document.patterns if not pattern.deactivated}
    active.patterns = [pattern for pattern in active.patterns if pattern.id in identities]
    active.seams = [seam for seam in active.seams if all(edge.pattern in identities for side in (0, 1) for edge in seam.side(side))]
    active.anchors = [anchor for anchor in active.anchors if anchor.pattern in identities]
    active.linked_pairs = [pair for pair in active.linked_pairs if all(identity in identities for identity in pair['members'])]
    return active


def synchronize_metadata(context, document, panels):
    from . import garment
    serialized = document.dumps()
    if len(panels) != len(document.patterns) or not panels:
        return False
    expected = without_states(document).dumps()
    for panel in panels:
        stored = panel.get('dd_document')
        if not stored or panel.get('dd_spacing') != context.scene.dd_spacing or panel.get('dd_units') != garment.metres_per_unit(context.scene):
            return False
        if stored != serialized and without_states(Document.loads(stored)).dumps() != expected:
            return False
    for panel in panels:
        panel['dd_document'] = serialized
    return True


def required(document):
    return any(getattr(pattern, flag) for pattern in document.patterns for flag in FLAGS)


def piece_indices(obj):
    identities = json.loads(obj.get('dd_piece_ids', '[]'))
    return {identity: [vertex.index for vertex in obj.data.vertices if any(group.group == index for group in vertex.groups)]
            for index, identity in enumerate(identities)}


def snapshot(context, panels):
    from . import garment
    simulations = garment.generated(context.scene, 'simulation')
    if not simulations:
        return {}
    obj = simulations[0]
    evaluated = obj.evaluated_get(context.evaluated_depsgraph_get())
    stored = json.loads(obj['dd_run_rest']) if obj.get('dd_run_rest') else {}
    result = {}
    for identity, indices in piece_indices(obj).items():
        panel = next((item for item in panels if item.get('dd_pattern_id') == identity), None)
        rest = stored.get(identity)
        if rest is None and panel is not None:
            rest = [tuple(item.vector) for item in panel.data.attributes['dd_rest'].data]
        if rest is not None and len(rest) == len(indices):
            local = {index: offset for offset, index in enumerate(indices)}
            faces = [tuple(local[index] for index in face.vertices) for face in obj.data.polygons if all(index in local for index in face.vertices)]
            result[identity] = (rest, [tuple(obj.matrix_world @ evaluated.data.vertices[index].co) for index in indices], faces)
    return result


def transfer(rest, positions, faces, target):
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    from mathutils.geometry import barycentric_transform
    if len(rest) == len(target) and all(tuple(first) == tuple(second) for first, second in zip(rest, target)):
        return positions
    tree = BVHTree.FromPolygons([Vector(point) for point in rest], faces)
    mapped = []
    for point in target:
        location, normal, face_index, distance = tree.find_nearest(Vector(point))
        if location is None or distance > 1e-5:
            raise ValueError('Freeze cannot transfer this changed outline. Reset the drape before simulating.')
        face = faces[face_index]
        if len(face) != 3:
            raise ValueError('Freeze needs triangular source sampling. Reset the drape before simulating.')
        mapped.append(tuple(barycentric_transform(Vector(point), *(Vector(rest[index]) for index in face), *(Vector(positions[index]) for index in face))))
    return mapped


def apply_states(document, simulation):
    from . import xpbd
    indices = piece_indices(simulation)
    frozen = {index for pattern in document.patterns if pattern.frozen and not pattern.deactivated for index in indices[pattern.id]}
    if frozen:
        held = frozen | {index for pair in json.loads(simulation['dd_sewing_pairs']) if any(index in frozen for index in pair) for index in pair}
        xpbd.hold(simulation, held)
    for pattern in document.patterns:
        if pattern.strengthened and not pattern.deactivated:
            xpbd.strengthen(simulation, indices[pattern.id], MULTIPLIER)


def compile_run(context, document):
    import bpy
    from . import garment, ui, xpbd
    scene = context.scene
    active = active_document(document)
    if not active.patterns:
        raise ValueError('All pieces are deactivated. Activate at least one piece to simulate.')
    panels = garment.generated(scene, 'panel')
    compatible = synchronize_metadata(context, document, panels)
    poses = snapshot(context, panels) if compatible else {}
    if not compatible:
        panels = garment.build_panels(context)
        document = garment.document(scene)
        active = active_document(document)
    marker = garment.signature(scene, panels)
    old = garment.generated(scene, 'simulation')
    if old and old[0].get('dd_signature') == marker:
        return old[0]
    garment.require_body(scene)
    temporary = bpy.data.scenes.new('DD State Compile')
    owned_collection = None
    simulation = None
    transferred = False
    try:
        temporary.unit_settings.scale_length = scene.unit_settings.scale_length
        temporary.gravity = scene.gravity
        temporary.frame_start = scene.frame_start
        temporary.frame_end = scene.frame_end
        for key in ui.PROPERTIES:
            if key not in {'dd_document', 'dd_collection', 'dd_history'}:
                setattr(temporary, key, getattr(scene, key))
        temporary.dd_document = active.dumps()
        for obj in scene.objects:
            if obj.get('dd_kind') not in {'panel', 'simulation', 'anchor', 'collider'} or obj.get('dd_owner') != garment.OWNER:
                temporary.collection.objects.link(obj)
        with context.temp_override(scene=temporary, view_layer=temporary.view_layers[0]):
            run_panels = garment.build_panels(context)
            owned_collection = temporary.dd_collection
            rest = {}
            for panel in run_panels:
                identity = panel['dd_pattern_id']
                source = next(item for item in panels if item['dd_pattern_id'] == identity)
                source_rest = [tuple(item.vector) for item in source.data.attributes['dd_rest'].data]
                run_rest = [tuple(item.vector) for item in panel.data.attributes['dd_rest'].data]
                if source_rest == run_rest and [tuple(face.vertices) for face in source.data.polygons] == [tuple(face.vertices) for face in panel.data.polygons]:
                    for vertex, original in zip(panel.data.vertices, source.data.vertices):
                        vertex.co = original.co
                panel.matrix_world = source.matrix_world.copy()
                rest[identity] = run_rest
            context.view_layer.update()
            simulation = garment.compile_garment(context)
            if poses:
                for identity, indices in piece_indices(simulation).items():
                    if identity in poses:
                        coordinates = transfer(*poses[identity], rest[identity])
                        for index, point in zip(indices, coordinates):
                            simulation.data.vertices[index].co = point
                simulation.data.update()
                xpbd.restart_from_pose(simulation)
            apply_states(document, simulation)
            simulation['dd_run_rest'] = json.dumps(rest, separators=(',', ':'))
            simulation['dd_state_run'] = True
            simulation['dd_signature'] = marker
            anchors = garment.generated(temporary, 'anchor') + garment.generated(temporary, 'collider')
            garment.remove_objects(run_panels)
        garment.stop(context)
        garment.remove_objects(garment.generated(scene, 'anchor') + garment.generated(scene, 'collider'))
        garment.remove_objects(old)
        scene.frame_set(scene.frame_start)
        destination = garment.collection(scene)
        for obj in [simulation] + anchors:
            destination.objects.link(obj)
            owned_collection.objects.unlink(obj)
        transferred = True
        scene.frame_end = max(scene.frame_end, temporary.frame_end)
        update_display(context, document)
        for panel in panels:
            inactive = document.find(panel['dd_pattern_id']).deactivated
            panel.hide_set(not inactive)
            panel.hide_render = True
        for obj in context.selected_objects:
            obj.select_set(False)
        simulation.select_set(True)
        context.view_layer.objects.active = simulation
        simulation.data.update()
        simulation.update_tag()
        context.view_layer.update()
        scene.frame_set(scene.frame_start + 1)
        scene.frame_set(scene.frame_start)
        return simulation
    finally:
        if not transferred:
            garment.remove_objects(garment.generated(temporary, 'panel') + garment.generated(temporary, 'simulation') + garment.generated(temporary, 'anchor') + garment.generated(temporary, 'collider'))
        bpy.data.scenes.remove(temporary)
        if owned_collection is not None and owned_collection.users == 0:
            bpy.data.collections.remove(owned_collection)


def update_display(context, document):
    from . import garment
    for panel in garment.generated(context.scene, 'panel'):
        pattern = document.find(panel.get('dd_pattern_id'))
        if pattern is not None and pattern.deactivated:
            if 'dd_state_display' not in panel:
                panel['dd_state_display'] = panel.display_type
            panel.display_type = 'WIRE'
        elif 'dd_state_display' in panel:
            panel.display_type = panel['dd_state_display']
            del panel['dd_state_display']
