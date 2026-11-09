import os
import bpy

ASSET_FILE = 'geometry_nodes_dynamics_assets.blend'
STOCK_GROUPS = ('XPBD Simulation', 'XPBD Solver', 'Gravity', 'Collider', 'Set Friction', 'Set Geometry Tags',
                'Set Geo Updater - Deform Only')
GROUP_VERSION = 3
STOCK_PREFIX = 'DD Stock '
CLOTH_GROUP = 'DD XPBD Cloth'
SOLVER_GROUP = 'DD XPBD Solver'
SIMULATION_GROUP = 'DD XPBD Simulation'
CONTACT_GROUP = 'DD Self Contact'
GEOMETRY_PATH = 'Cloth/Geometry'
SHELL_FRICTION = .5


class Graph:
    def __init__(self, tree):
        self.tree = tree

    def wire(self, target, value):
        if isinstance(value, bpy.types.NodeSocket):
            self.tree.links.new(value, target)
        elif value is not None:
            target.default_value = value

    def node(self, kind, *values, settings=None, **named):
        node = self.tree.nodes.new(kind)
        for key, value in (settings or {}).items():
            setattr(node, key, value)
        for index, value in enumerate(values):
            self.wire(node.inputs[index], value)
        for key, value in named.items():
            self.wire(node.inputs[key.replace('_', ' ')], value)
        return node

    def math(self, operation, *values):
        return self.node('ShaderNodeMath', *values, settings={'operation': operation}).outputs[0]

    def vector(self, operation, *values):
        node = self.node('ShaderNodeVectorMath', *values, settings={'operation': operation})
        return node.outputs['Value' if operation in {'LENGTH', 'DOT_PRODUCT', 'DISTANCE'} else 'Vector']

    def scale(self, vector, factor):
        node = self.tree.nodes.new('ShaderNodeVectorMath')
        node.operation = 'SCALE'
        self.wire(node.inputs[0], vector)
        self.wire(node.inputs['Scale'], factor)
        return node.outputs['Vector']

    def compare(self, operation, first, second, data_type='FLOAT'):
        node = self.tree.nodes.new('FunctionNodeCompare')
        node.data_type = data_type
        node.operation = operation
        self.wire(node.inputs['A'], first)
        self.wire(node.inputs['B'], second)
        return node.outputs['Result']

    def logic(self, operation, *values):
        return self.node('FunctionNodeBooleanMath', *values, settings={'operation': operation}).outputs[0]

    def switch(self, input_type, condition, when_false, when_true):
        node = self.tree.nodes.new('GeometryNodeSwitch')
        node.input_type = input_type
        self.wire(node.inputs['Switch'], condition)
        self.wire(node.inputs['False'], when_false)
        self.wire(node.inputs['True'], when_true)
        return node.outputs[0]

    def attribute(self, name, data_type='FLOAT'):
        return self.node('GeometryNodeInputNamedAttribute', settings={'data_type': data_type}, Name=name).outputs['Attribute']

    def bundle(self, items):
        node = self.tree.nodes.new('NodeCombineBundle')
        for name, socket_type, value in items:
            node.bundle_items.new(socket_type, name)
            self.wire(node.inputs[name], value)
        return node.outputs['Bundle']

    def group(self, tree, **named):
        node = self.tree.nodes.new('GeometryNodeGroup')
        node.node_tree = tree
        for key, value in named.items():
            self.wire(node.inputs[key.replace('_', ' ')], value)
        return node


def stock_group(name):
    return bpy.data.node_groups[STOCK_PREFIX + name]


def load_stock_groups():
    missing = [name for name in STOCK_GROUPS if STOCK_PREFIX + name not in bpy.data.node_groups]
    if not missing:
        return
    path = os.path.join(bpy.utils.resource_path('LOCAL'), 'datafiles', 'assets', 'nodes', ASSET_FILE)
    if not os.path.exists(path):
        raise ValueError('This Blender build has no XPBD dynamics assets. Devil Designer needs Blender 5.2 or newer.')
    with bpy.data.libraries.load(path, link=False) as (source, target):
        available = [name for name in missing if name in source.node_groups]
        target.node_groups = available
    for name, group in zip(available, target.node_groups):
        if group is not None:
            group.name = STOCK_PREFIX + name
    absent = [name for name in missing if STOCK_PREFIX + name not in bpy.data.node_groups]
    if absent:
        raise ValueError('The XPBD dynamics assets are incomplete: ' + ', '.join(absent))


def socket(tree, name, in_out, socket_type, default=None):
    item = tree.interface.new_socket(name, in_out=in_out, socket_type=socket_type)
    if socket_type in {'NodeSocketFloat', 'NodeSocketInt', 'NodeSocketVector'}:
        item.structure_type = 'SINGLE'
    if default is not None:
        item.default_value = default
    return item


def surface_sample(graph, geometry, value, data_type, probe):
    node = graph.node('GeometryNodeSampleNearestSurface', settings={'data_type': data_type})
    graph.wire(node.inputs['Mesh'], geometry)
    graph.wire(node.inputs['Value'], value)
    graph.wire(node.inputs['Sample Position'], probe)
    return node.outputs['Value']


def build_contact_group():
    tree = bpy.data.node_groups.new(CONTACT_GROUP, 'GeometryNodeTree')
    socket(tree, 'Geometry', 'INPUT', 'NodeSocketGeometry')
    socket(tree, 'Body', 'INPUT', 'NodeSocketGeometry')
    socket(tree, 'Geometry', 'OUTPUT', 'NodeSocketGeometry')
    graph = Graph(tree)
    source = tree.nodes.new('NodeGroupInput')
    sink = tree.nodes.new('NodeGroupOutput')
    geometry = source.outputs['Geometry']
    position = graph.node('GeometryNodeInputPosition').outputs[0]
    normal = graph.node('GeometryNodeInputNormal').outputs['Normal']
    velocity = graph.attribute('velocity', 'FLOAT_VECTOR')

    margin = graph.attribute('dd_body_margin')
    grip = graph.attribute('dd_body_grip')
    surface = surface_sample(graph, source.outputs['Body'], position, 'FLOAT_VECTOR', position)
    outward = graph.vector('NORMALIZE', surface_sample(graph, source.outputs['Body'], normal, 'FLOAT_VECTOR', position))
    away = graph.vector('SUBTRACT', position, surface)
    height = graph.vector('DOT_PRODUCT', away, outward)
    reach = graph.vector('LENGTH', away)
    aligned = graph.compare('GREATER_THAN', graph.math('ABSOLUTE', height), graph.math('MULTIPLY', reach, .6))
    close = graph.compare('LESS_THAN', reach, margin)
    touching = graph.logic('AND', graph.compare('LESS_THAN', height, margin), graph.logic('OR', aligned, close))
    step = graph.math('MINIMUM', graph.math('SUBTRACT', margin, height), graph.attribute('dd_body_step'))
    lift = graph.scale(outward, step)
    speed = graph.vector('DOT_PRODUCT', velocity, outward)
    sliding = graph.vector('SUBTRACT', velocity, graph.scale(outward, speed))
    slowed = graph.vector('ADD', graph.scale(sliding, graph.math('SUBTRACT', 1.0, grip)),
                          graph.scale(outward, graph.math('MAXIMUM', speed, 0.0)))
    lifted = graph.node('GeometryNodeSetPosition', geometry, Selection=touching, Offset=lift).outputs[0]
    stored = graph.node('GeometryNodeStoreNamedAttribute', lifted, settings={'data_type': 'FLOAT_VECTOR', 'domain': 'POINT'},
                        Selection=touching, Name='velocity')
    graph.wire(stored.inputs['Value'], slowed)
    frame_number = graph.node('GeometryNodeInputSceneTime').outputs['Frame']
    odd = graph.compare('GREATER_THAN', graph.math('FLOORED_MODULO', frame_number, 2.0), .5)
    body_stage = graph.switch('GEOMETRY', odd, geometry, stored.outputs[0])

    rest = graph.attribute('dd_rest_position', 'FLOAT_VECTOR')
    thickness = graph.attribute('dd_self_thickness')
    weight = graph.attribute('dd_contact_weight')
    span = graph.math('MULTIPLY', thickness, 3.0)
    frame = graph.math('MULTIPLY', graph.attribute('dd_frame_time'), 2.0)
    total = (0.0, 0.0, 0.0)
    braking = (0.0, 0.0, 0.0)
    for side in (1.0, -1.0):
        toward = graph.scale(normal, side)
        probe = graph.vector('ADD', position, graph.scale(toward, span))
        hit = surface_sample(graph, geometry, position, 'FLOAT_VECTOR', probe)
        hit_rest = surface_sample(graph, geometry, rest, 'FLOAT_VECTOR', probe)
        hit_weight = surface_sample(graph, geometry, weight, 'FLOAT', probe)
        hit_velocity = surface_sample(graph, geometry, velocity, 'FLOAT_VECTOR', probe)
        gap = graph.vector('DOT_PRODUCT', graph.vector('SUBTRACT', hit, position), toward)
        foreign = graph.compare('GREATER_THAN', graph.vector('DISTANCE', hit_rest, rest), graph.math('MULTIPLY', thickness, 4.0))
        near = graph.compare('LESS_THAN', graph.vector('DISTANCE', hit, probe), graph.math('MULTIPLY', span, .97))
        facing = graph.logic('AND', graph.logic('AND', foreign, near), graph.compare('GREATER_THAN', hit_weight, .5))
        inside = graph.compare('LESS_THAN', gap, thickness)
        depth = graph.math('MULTIPLY', graph.math('SUBTRACT', thickness, gap), .5)
        push = graph.scale(toward, graph.math('MULTIPLY', depth, -1.0))
        total = graph.vector('ADD', total, graph.switch('VECTOR', graph.logic('AND', facing, inside), (0.0, 0.0, 0.0), push))
        closing = graph.vector('DOT_PRODUCT', graph.vector('SUBTRACT', velocity, hit_velocity), toward)
        allowed = graph.math('DIVIDE', graph.math('MAXIMUM', graph.math('SUBTRACT', gap, thickness), 0.0), frame)
        excess = graph.math('MAXIMUM', graph.math('SUBTRACT', closing, allowed), 0.0)
        brake = graph.scale(toward, graph.math('MULTIPLY', excess, -.5))
        braking = graph.vector('ADD', braking, graph.switch('VECTOR', facing, (0.0, 0.0, 0.0), brake))
    moved = graph.node('GeometryNodeSetPosition', geometry, Offset=graph.scale(total, weight)).outputs[0]
    slowed_cloth = graph.node('GeometryNodeStoreNamedAttribute', moved, settings={'data_type': 'FLOAT_VECTOR', 'domain': 'POINT'}, Name='velocity')
    graph.wire(slowed_cloth.inputs['Value'], graph.vector('ADD', velocity, graph.scale(braking, weight)))
    moved = graph.switch('GEOMETRY', odd, slowed_cloth.outputs[0], body_stage)

    partner = graph.attribute('dd_partner', 'INT')
    across = graph.node('GeometryNodeFieldAtIndex', settings={'data_type': 'FLOAT_VECTOR', 'domain': 'POINT'})
    graph.wire(across.inputs['Index'], partner)
    graph.wire(across.inputs['Value'], position)
    gap = graph.vector('SUBTRACT', across.outputs[0], position)
    free = graph.logic('NOT', graph.attribute('dd_pinned', 'BOOLEAN'))
    joined = graph.logic('AND', graph.logic('AND', graph.compare('GREATER_EQUAL', partner, 0, 'INT'), free),
                         graph.compare('LESS_THAN', graph.vector('LENGTH', gap), graph.attribute('dd_weld_reach')))
    welded = graph.node('GeometryNodeSetPosition', moved, Selection=joined, Offset=graph.scale(gap, .25)).outputs[0]

    pinned = graph.attribute('dd_pinned', 'BOOLEAN')
    placed = graph.node('GeometryNodeSetPosition', welded, Selection=pinned, Position=graph.attribute('dd_pin_goal', 'FLOAT_VECTOR')).outputs[0]
    still = graph.node('GeometryNodeStoreNamedAttribute', placed, settings={'data_type': 'FLOAT_VECTOR', 'domain': 'POINT'},
                       Selection=pinned, Name='velocity')
    tree.links.new(still.outputs[0], sink.inputs['Geometry'])
    return tree


def build_solver_group(contact):
    tree = stock_group('XPBD Solver').copy()
    tree.name = SOLVER_GROUP
    socket(tree, 'Inner Substeps', 'INPUT', 'NodeSocketInt', 4)
    socket(tree, 'Body', 'INPUT', 'NodeSocketGeometry')
    nodes = tree.nodes
    nodes['Switch'].inputs['Switch'].default_value = True
    step = nodes['XPBD Solver Test Wrapper.001']
    finish = nodes['Repeat Output']
    graph = Graph(tree)
    source = tree.nodes.new('NodeGroupInput')
    tree.links.new(source.outputs['Inner Substeps'], step.inputs['Substeps'])
    fetched = graph.node('NodeGetBundleItem', settings={'socket_type': 'GEOMETRY'}, Path=GEOMETRY_PATH)
    tree.links.new(step.outputs['World'], fetched.inputs['Bundle'])
    solved = graph.group(contact)
    tree.links.new(fetched.outputs['Item'], solved.inputs['Geometry'])
    tree.links.new(source.outputs['Body'], solved.inputs['Body'])
    stored = graph.node('NodeStoreBundleItem', settings={'socket_type': 'GEOMETRY'}, Path=GEOMETRY_PATH)
    tree.links.new(step.outputs['World'], stored.inputs['Bundle'])
    tree.links.new(solved.outputs['Geometry'], stored.inputs['Item'])
    tree.links.new(stored.outputs['Bundle'], finish.inputs['World'])
    return tree


def build_simulation_group(solver):
    tree = stock_group('XPBD Simulation').copy()
    tree.name = SIMULATION_GROUP
    socket(tree, 'Inner Substeps', 'INPUT', 'NodeSocketInt', 4)
    socket(tree, 'Body', 'INPUT', 'NodeSocketGeometry')
    node = tree.nodes['XPBD Solver']
    node.node_tree = solver
    source = tree.nodes.new('NodeGroupInput')
    tree.links.new(source.outputs['Inner Substeps'], node.inputs['Inner Substeps'])
    tree.links.new(source.outputs['Body'], node.inputs['Body'])
    return tree


def build_cloth_group(simulation):
    tree = bpy.data.node_groups.new(CLOTH_GROUP, 'GeometryNodeTree')
    tree['dd_group_version'] = GROUP_VERSION
    tree.is_modifier = True
    socket(tree, 'Geometry', 'INPUT', 'NodeSocketGeometry')
    socket(tree, 'Body', 'INPUT', 'NodeSocketObject')
    socket(tree, 'Body Shell', 'INPUT', 'NodeSocketObject')
    socket(tree, 'Grab Handle', 'INPUT', 'NodeSocketObject')
    socket(tree, 'Grab Index', 'INPUT', 'NodeSocketInt', -1)
    socket(tree, 'Grab Radius', 'INPUT', 'NodeSocketFloat', .05)
    socket(tree, 'Grab Stride', 'INPUT', 'NodeSocketFloat', .015)
    socket(tree, 'Grab Reach', 'INPUT', 'NodeSocketFloat', .12)
    socket(tree, 'Contact Passes', 'INPUT', 'NodeSocketInt', 1)
    socket(tree, 'Inner Substeps', 'INPUT', 'NodeSocketInt', 12)
    socket(tree, 'Iterations', 'INPUT', 'NodeSocketInt', 2)
    socket(tree, 'Seam Seconds', 'INPUT', 'NodeSocketFloat', .8)
    socket(tree, 'Gravity', 'INPUT', 'NodeSocketVector', (0.0, 0.0, -9.81))
    socket(tree, 'Damping', 'INPUT', 'NodeSocketFloat', 1.0)
    socket(tree, 'Geometry', 'OUTPUT', 'NodeSocketGeometry')
    graph = Graph(tree)
    source = tree.nodes.new('NodeGroupInput')
    sink = tree.nodes.new('NodeGroupOutput')
    out = source.outputs
    position = graph.node('GeometryNodeInputPosition').outputs[0]
    rest = graph.attribute('dd_rest_position', 'FLOAT_VECTOR')

    seconds = graph.node('GeometryNodeInputSceneTime').outputs['Seconds']
    start = graph.attribute('dd_seam_start')
    goal = graph.attribute('rest_length')
    elapsed = graph.math('SUBTRACT', seconds, graph.attribute('dd_time_zero'))
    progress = graph.math('DIVIDE', elapsed, graph.math('MAXIMUM', out['Seam Seconds'], .001))
    closing = graph.node('ShaderNodeMix', settings={'data_type': 'FLOAT', 'clamp_factor': True})
    graph.wire(closing.inputs['Factor'], progress)
    graph.wire(closing.inputs['A'], start)
    graph.wire(closing.inputs['B'], goal)
    seam = graph.attribute('dd_seam', 'BOOLEAN')
    length = graph.switch('FLOAT', seam, goal, closing.outputs['Result'])

    edge = graph.bundle((('Type', 'STRING', 'Blender.Constraint.EdgeLength'), ('filter', 'STRING', ''),
                         ('rest_length', 'FLOAT', length), ('compliance', 'FLOAT', graph.attribute('dd_edge_compliance')),
                         ('error_threshold', 'FLOAT', .001)))
    bend = graph.bundle((('Type', 'STRING', 'Blender.Constraint.CrossEdgeLength'), ('filter', 'STRING', ''),
                         ('rest_position', 'VECTOR', graph.attribute('dd_bend_rest', 'FLOAT_VECTOR')), ('compliance', 'FLOAT', graph.attribute('dd_bend_compliance')),
                         ('error_threshold', 'FLOAT', .001)))

    body = graph.node('GeometryNodeObjectInfo', out['Body'], settings={'transform_space': 'RELATIVE'}).outputs['Geometry']
    parts = graph.node('ShaderNodeSeparateXYZ', graph.attribute('dd_tack_vertices', 'FLOAT_VECTOR')).outputs
    shares = graph.node('ShaderNodeSeparateXYZ', graph.attribute('dd_tack_weights', 'FLOAT_VECTOR')).outputs
    target = (0.0, 0.0, 0.0)
    for index in range(3):
        sample = graph.node('GeometryNodeSampleIndex', settings={'data_type': 'FLOAT_VECTOR', 'domain': 'POINT'})
        graph.wire(sample.inputs['Geometry'], body)
        graph.wire(sample.inputs['Value'], position)
        graph.wire(sample.inputs['Index'], parts[index])
        target = graph.vector('ADD', target, graph.scale(sample.outputs['Value'], shares[index]))
    base = graph.attribute('dd_pin_target', 'FLOAT_VECTOR')
    settle = graph.node('ShaderNodeMix', settings={'data_type': 'VECTOR', 'clamp_factor': True})
    graph.wire(settle.inputs['Factor'], progress)
    graph.wire(settle.inputs[4], base)
    graph.wire(settle.inputs[5], target)
    anchor = graph.switch('VECTOR', graph.attribute('dd_tacked', 'BOOLEAN'), base, settle.outputs[1])

    goal = graph.node('GeometryNodeStoreNamedAttribute', out['Geometry'], settings={'data_type': 'FLOAT_VECTOR', 'domain': 'POINT'}, Name='dd_pin_goal')
    graph.wire(goal.inputs['Value'], anchor)
    tagged = graph.group(stock_group('Set Geometry Tags'), Geometry=goal.outputs[0], Tags='').outputs[0]
    gripping = graph.group(stock_group('Set Friction'), Geometry=tagged, Static=SHELL_FRICTION, Dynamic=SHELL_FRICTION).outputs[0]
    updated = graph.group(stock_group('Set Geo Updater - Deform Only'), Geometry=gripping, Extra_Sim_Attributes='').outputs[0]

    handle = graph.node('GeometryNodeObjectInfo', out['Grab Handle'], settings={'transform_space': 'RELATIVE'}).outputs['Location']
    grabbed = graph.node('GeometryNodeFieldAtIndex', settings={'data_type': 'FLOAT_VECTOR', 'domain': 'POINT'})
    graph.wire(grabbed.inputs['Index'], out['Grab Index'])
    graph.wire(grabbed.inputs['Value'], position)
    grabbed_rest = graph.node('GeometryNodeFieldAtIndex', settings={'data_type': 'FLOAT_VECTOR', 'domain': 'POINT'})
    graph.wire(grabbed_rest.inputs['Index'], out['Grab Index'])
    graph.wire(grabbed_rest.inputs['Value'], rest)
    distance = graph.vector('DISTANCE', rest, grabbed_rest.outputs[0])
    falloff = graph.math('SUBTRACT', 1.0, graph.math('DIVIDE', distance, graph.math('MAXIMUM', out['Grab Radius'], .001)))
    share = graph.math('MAXIMUM', falloff, 0.0)
    smooth = graph.math('MULTIPLY', share, share)
    reach = graph.vector('SUBTRACT', handle, grabbed.outputs[0])
    distance_to_hand = graph.vector('LENGTH', reach)
    grip = graph.node('ShaderNodeClamp', graph.math('SUBTRACT', 1.0, graph.math('DIVIDE', distance_to_hand, graph.math('MAXIMUM', out['Grab Reach'], .001))), 0.0, 1.0).outputs[0]
    stride = graph.math('MULTIPLY', graph.math('MINIMUM', distance_to_hand, out['Grab Stride']), grip)
    pull = graph.scale(graph.vector('NORMALIZE', reach), graph.math('MULTIPLY', stride, smooth))
    held = graph.logic('AND', graph.compare('GREATER_EQUAL', out['Grab Index'], 0, 'INT'), graph.compare('GREATER_THAN', smooth, .001))
    pinned = graph.attribute('dd_pinned', 'BOOLEAN')
    pins = graph.bundle((('Type', 'STRING', 'Blender.Constraint.PinPosition'), ('filter', 'STRING', ''),
                         ('selection', 'BOOLEAN', graph.logic('OR', pinned, held)),
                         ('position', 'VECTOR', graph.switch('VECTOR', held, anchor, graph.vector('ADD', position, pull))),
                         ('compliance', 'FLOAT', graph.switch('FLOAT', held, graph.attribute('dd_pin_compliance'), 0.0)),
                         ('error_threshold', 'FLOAT', .001), ('lambda_attribute', 'STRING', '')))

    settling = graph.math('SUBTRACT', progress, 1.0)
    ramp = graph.node('ShaderNodeClamp', settling, 0.0, 1.0).outputs[0]
    gravity = graph.group(stock_group('Gravity'), Gravity=graph.scale(out['Gravity'], ramp)).outputs[0]
    damping = graph.bundle((('Type', 'STRING', 'Blender.Damping'), ('filter', 'STRING', ''),
                            ('linear_damping', 'FLOAT', out['Damping']), ('angular_damping', 'FLOAT', 1.0)))
    shell = graph.node('GeometryNodeObjectInfo', out['Body Shell'], settings={'transform_space': 'RELATIVE'}).outputs['Geometry']
    collider = graph.group(stock_group('Collider'), Geometry=shell, Friction=SHELL_FRICTION).outputs['Collider']
    cloth = graph.bundle((('Geometry', 'GEOMETRY', updated), ('Edge Length', 'BUNDLE', edge), ('Cross Edge Length', 'BUNDLE', bend),
                          ('Pin Positions', 'BUNDLE', pins), ('Gravity', 'BUNDLE', gravity), ('Damping', 'BUNDLE', damping),
                          ('Shell', 'BUNDLE', collider)))
    world = graph.bundle((('Cloth', 'BUNDLE', cloth),))

    solved = graph.group(simulation, World=world, Substeps=out['Contact Passes'], Inner_Substeps=out['Inner Substeps'], Body=body,
                         Constraint_Steps=out['Iterations'], Time_Scale=1.0, Solver_Output_Path='SolverData')
    result = graph.node('NodeGetBundleItem', settings={'socket_type': 'GEOMETRY'}, Path=GEOMETRY_PATH)
    tree.links.new(solved.outputs['World'], result.inputs['Bundle'])
    tree.links.new(result.outputs['Item'], sink.inputs['Geometry'])
    return tree


def cloth_group():
    tree = bpy.data.node_groups.get(CLOTH_GROUP)
    if tree is not None and tree.get('dd_group_version') == GROUP_VERSION:
        return tree
    for name in (CLOTH_GROUP, SIMULATION_GROUP, SOLVER_GROUP, CONTACT_GROUP):
        stale = bpy.data.node_groups.get(name)
        if stale is not None:
            bpy.data.node_groups.remove(stale)
    load_stock_groups()
    return build_cloth_group(build_simulation_group(build_solver_group(build_contact_group())))


def input_identifier(tree, name):
    return next(item.identifier for item in tree.interface.items_tree
                if item.item_type == 'SOCKET' and item.in_out == 'INPUT' and item.name == name)
