import json
from .core import Document
from .presets import resolve_preset


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
    import bpy
    indices = piece_indices(simulation)
    cloth = next(modifier for modifier in simulation.modifiers if modifier.type == 'CLOTH')
    frozen = {index for pattern in document.patterns if pattern.frozen and not pattern.deactivated for index in indices[pattern.id]}
    if frozen:
        cloth.collision_settings.use_self_collision = True
        held = frozen | {index for pair in json.loads(simulation['dd_sewing_pairs']) if any(index in frozen for index in pair) for index in pair}
        group = simulation.vertex_groups.get('DD Pins') or simulation.vertex_groups.new(name='DD Pins')
        group.add(sorted(held), 1, 'REPLACE')
        cloth.settings.vertex_group_mass = group.name
        exact_hold(simulation, held)
        for modifier in list(simulation.modifiers):
            if modifier.type != 'HOOK' or not held.intersection(modifier.vertex_indices):
                continue
            target = modifier.object
            simulation.modifiers.remove(modifier)
            if target and target.get('dd_kind') == 'anchor':
                bpy.data.objects.remove(target, do_unlink=True)
    active = [pattern for pattern in document.patterns if not pattern.deactivated]
    if not any(pattern.strengthened for pattern in active):
        return
    for key, group_name, properties in [('structural', 'DD Structural', ('tension', 'compression')),
                                        ('shear', 'DD Shear', ('shear',)), ('bending', 'DD Bending', ('bending',))]:
        values = [resolve_preset(pattern.preset, getattr(document, 'custom_presets', None))[key] * (MULTIPLIER if pattern.strengthened else 1) for pattern in active]
        low, high = min(values), max(values)
        for name in properties:
            setattr(cloth.settings, name + '_stiffness', low)
            setattr(cloth.settings, name + '_stiffness_max', high)
        group = simulation.vertex_groups[group_name]
        for pattern, value in zip(active, values):
            group.add(indices[pattern.id], (value - low) / (high - low) if high > low else 1, 'REPLACE')


def compile_run(context, document):
    import bpy
    from . import garment, layering, ui
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
    garment.ensure_collision(scene)
    layering.prepare_colliders(context)
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
            if obj.get('dd_kind') not in {'panel', 'simulation', 'anchor'} or obj.get('dd_owner') != garment.OWNER:
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
            apply_states(document, simulation)
            simulation['dd_run_rest'] = json.dumps(rest, separators=(',', ':'))
            simulation['dd_state_run'] = True
            simulation['dd_signature'] = marker
            anchors = garment.generated(temporary, 'anchor')
            garment.remove_objects(run_panels)
        garment.stop(context)
        garment.remove_objects(garment.generated(scene, 'anchor'))
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
        configure_collisions(context, document, simulation)
        context.view_layer.update()
        return simulation
    finally:
        if not transferred:
            garment.remove_objects(garment.generated(temporary, 'panel') + garment.generated(temporary, 'simulation') + garment.generated(temporary, 'anchor'))
        bpy.data.scenes.remove(temporary)
        if owned_collection is not None and owned_collection.users == 0:
            bpy.data.collections.remove(owned_collection)


def configure_collisions(context, document, simulation):
    import bpy
    from . import garment
    inactive = {pattern.id for pattern in document.patterns if pattern.deactivated}
    target = bpy.data.collections.new('DD State Colliders')
    target['dd_layering_owner'] = garment.OWNER
    target.use_fake_user = True
    for obj in context.scene.objects:
        if obj.get('dd_pattern_id') in inactive or obj.get('dd_kind') == 'final' and not obj.get('dd_wear_over', True):
            continue
        if obj == context.scene.dd_avatar or any(modifier.type == 'COLLISION' for modifier in obj.modifiers):
            target.objects.link(obj)
    cloth = next(modifier for modifier in simulation.modifiers if modifier.type == 'CLOTH')
    cloth.collision_settings.collection = target
    referenced = {modifier.collision_settings.collection for obj in bpy.data.objects for modifier in obj.modifiers if modifier.type == 'CLOTH'}
    for collection in list(bpy.data.collections):
        if collection != target and collection.get('dd_layering_owner') == garment.OWNER and collection not in referenced and collection.users == int(collection.use_fake_user):
            bpy.data.collections.remove(collection)


def exact_hold(simulation, held):
    import bpy
    positions = simulation.data.attributes.get('dd_frozen_position') or simulation.data.attributes.new(name='dd_frozen_position', type='FLOAT_VECTOR', domain='POINT')
    selection = simulation.data.attributes.get('dd_frozen_held') or simulation.data.attributes.new(name='dd_frozen_held', type='BOOLEAN', domain='POINT')
    for vertex, position, selected in zip(simulation.data.vertices, positions.data, selection.data):
        position.vector = vertex.co
        selected.value = vertex.index in held
    group = next((group for group in bpy.data.node_groups if group.get('dd_state_freeze')), None)
    if group is None:
        group = bpy.data.node_groups.new('DD Exact Frozen Hold', 'GeometryNodeTree')
        group['dd_state_freeze'] = True
        group.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        group.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
        source = group.nodes.new('NodeGroupInput')
        output = group.nodes.new('NodeGroupOutput')
        position = group.nodes.new('GeometryNodeInputNamedAttribute')
        position.data_type = 'FLOAT_VECTOR'
        position.inputs['Name'].default_value = 'dd_frozen_position'
        mask = group.nodes.new('GeometryNodeInputNamedAttribute')
        mask.data_type = 'BOOLEAN'
        mask.inputs['Name'].default_value = 'dd_frozen_held'
        fixed = group.nodes.new('GeometryNodeSetPosition')
        group.links.new(source.outputs['Geometry'], fixed.inputs['Geometry'])
        group.links.new(position.outputs['Attribute'], fixed.inputs['Position'])
        group.links.new(mask.outputs['Attribute'], fixed.inputs['Selection'])
        previous = fixed
        for name in ('dd_frozen_position', 'dd_frozen_held'):
            remove = group.nodes.new('GeometryNodeRemoveAttribute')
            remove.inputs['Name'].default_value = name
            group.links.new(previous.outputs['Geometry'], remove.inputs['Geometry'])
            previous = remove
        group.links.new(previous.outputs['Geometry'], output.inputs['Geometry'])
    modifier = simulation.modifiers.get('DD Exact Frozen Hold') or simulation.modifiers.new('DD Exact Frozen Hold', 'NODES')
    modifier.node_group = group


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
