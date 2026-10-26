import math
import re
from dataclasses import dataclass


MODES = ('BODICE', 'SLEEVES', 'SKIRT')


@dataclass(frozen=True)
class Placement:
    pattern_id: str
    point: tuple
    normal: tuple


def layout_plan(pieces, body_bounds, mode):
    if mode not in MODES:
        raise ValueError('Choose BODICE, SLEEVES, or SKIRT.')
    pieces = tuple(pieces)
    if not pieces:
        raise ValueError('Draw at least one closed pattern first.')
    identities = set()
    for pattern_id, name in pieces:
        if not isinstance(pattern_id, str) or not pattern_id or pattern_id in identities:
            raise ValueError('Every piece needs a unique pattern ID.')
        if not isinstance(name, str) or not name.strip():
            raise ValueError('Every piece needs a name.')
        identities.add(pattern_id)
    if len(body_bounds) != 2 or any(len(corner) != 3 for corner in body_bounds):
        raise ValueError('Avatar bounds need two three-dimensional corners.')
    low, high = body_bounds
    if any(not math.isfinite(value) for corner in body_bounds for value in corner):
        raise ValueError('Avatar bounds must be finite.')
    extent = tuple(high[axis] - low[axis] for axis in range(3))
    if any(not math.isfinite(value) or value <= 0 for value in extent):
        raise ValueError('Avatar bounds must have positive width, depth, and height.')
    center = tuple(low[axis] + extent[axis] * .5 for axis in range(3))
    ordered = sorted(pieces, key=lambda piece: (piece[1].casefold(), piece[0]))
    result = []
    if mode == 'SKIRT':
        if len(pieces) < 2:
            raise ValueError('Skirt arrangement needs at least two panels.')
        for index, (pattern_id, name) in enumerate(ordered):
            angle = -math.pi / 2 + math.tau * index / len(ordered)
            horizontal, depth = math.cos(angle), math.sin(angle)
            normal = (horizontal * extent[1], depth * extent[0], 0)
            length = math.hypot(*normal)
            result.append(Placement(pattern_id,
                (center[0] + horizontal * extent[0] * .5,
                 center[1] + depth * extent[1] * .5, low[2] + extent[2] * .43),
                tuple(value / length for value in normal)))
        return tuple(result)
    labels = ('front', 'back') if mode == 'BODICE' else ('left', 'right')
    groups = {label: [] for label in labels}
    unlabeled = []
    for piece in ordered:
        tokens = set(re.findall(r'[a-z]+', piece[1].casefold()))
        matches = tokens.intersection(labels)
        if len(matches) > 1:
            raise ValueError(f'Conflicting {mode.lower()} labels: {", ".join(labels)}. Use at most one per piece.')
        if matches:
            groups[matches.pop()].append(piece)
        else:
            unlabeled.append(piece)
    for piece in unlabeled:
        label = min(labels, key=lambda candidate: len(groups[candidate]))
        groups[label].append(piece)
    for label in labels:
        group = sorted(groups[label], key=lambda piece: (piece[1].casefold(), piece[0]))
        for index, (pattern_id, name) in enumerate(group):
            offset = (index + .5) / len(group) - .5
            if mode == 'BODICE':
                side = -1 if label == 'front' else 1
                point = (center[0] + offset * extent[0] * .4,
                         low[1] if side < 0 else high[1], low[2] + extent[2] * .72)
                normal = (0, side, 0)
            else:
                side = 1 if label == 'left' else -1
                point = (center[0] + side * extent[0] * .36,
                         low[1], low[2] + extent[2] * (.78 + offset * .16))
                normal = (0, -1, 0)
            result.append(Placement(pattern_id, point, normal))
    return tuple(result)


def arrange(context, mode):
    from mathutils import Vector
    from . import garment, placement

    scene = context.scene
    avatar = scene.dd_avatar
    if avatar is None:
        raise ValueError('Choose your avatar body mesh first.')
    if (avatar.type != 'MESH' or avatar not in list(scene.objects)
            or avatar.get('dd_kind') in {'panel', 'simulation', 'final', 'anchor'}
            or not avatar.data.vertices):
        raise ValueError('Choose an avatar body mesh in the current scene.')
    document = garment.document(scene)
    document.validate()
    document.validate_seams()
    for value, label in ((scene.dd_spacing, 'Pattern spacing'),
                         (scene.unit_settings.scale_length, 'Scene unit scale')):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f'{label} must be positive and finite.')
    if not math.isfinite(scene.dd_clearance) or scene.dd_clearance < 0:
        raise ValueError('Body clearance must be nonnegative and finite.')
    plan = layout_plan(((piece.id, piece.name) for piece in document.patterns),
                       garment.bounds(avatar), mode)
    unit = garment.metres_per_unit(scene)
    gap = scene.dd_clearance / unit
    if not math.isfinite(gap) or any(not math.isfinite(coordinate + normal * gap)
            for target in plan for coordinate, normal in zip(target.point, target.normal)):
        raise ValueError('Arrangement coordinates must be finite.')
    panels = garment.generated(scene, 'panel')
    panel_ids = [panel.get('dd_pattern_id') for panel in panels]
    if len(set(panel_ids)) != len(panel_ids):
        raise ValueError('Generated panels have duplicate pattern IDs; rebuild them first.')
    serialized = document.dumps()
    if (set(panel_ids) != {target.pattern_id for target in plan}
            or any(panel.type != 'MESH' or not panel.data.vertices
                   or panel.get('dd_document') != serialized
                   or panel.get('dd_spacing') != scene.dd_spacing
                   or panel.get('dd_units') != unit for panel in panels)):
        panels = garment.build_panels(context)
    by_id = {panel.get('dd_pattern_id'): panel for panel in panels}
    if len(by_id) != len(plan) or set(by_id) != {target.pattern_id for target in plan}:
        raise ValueError('Generated panels do not match the arrangement pieces.')
    previous = [(panel, panel.matrix_world.copy()) for panel in panels]
    try:
        for target in plan:
            placement.place(context, target.pattern_id, Vector(target.point), Vector(target.normal))
    except Exception:
        for panel, matrix in previous:
            panel.matrix_world = matrix
        context.view_layer.update()
        raise
    return len(plan)
