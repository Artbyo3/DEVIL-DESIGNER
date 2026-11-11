import math

from .core import Session, EdgeRef, Vertex, arrangement_record


ADULT_HEIGHT = 150.0
SKIRT_WAIST_EASE = 8.0
SKIRT_HIP_EASE = 8.0
SKIRT_HIP_DROP = 0.20
SKIRT_MIN_FLARE = 0.05
SKIRT_MAX_FLARE = 0.5
ARM_CLEARANCE = 0.01


def make_edge(doc, pattern_id, index, rev=False):
    e = doc.edge(pattern_id, index)
    if rev:
        return EdgeRef(e.pattern, e.start, e.end, 1.0, 0.0, e.path)
    return e


def create_tee_starter(measurements, fabric='COTTON', name='Tee', sleeve_scale=1.0):
    m = measurements or {
        'chest': 96.0,
        'waist': 80.0,
        'hip': 96.0,
        'torso_length': 40.0,
        'shoulder_width': 44.0,
        'arm_length': 36.0,
    }
    half_chest = (m['chest'] / 2 + 6.0) / 200
    half_waist = (m['waist'] / 2 + 6.0) / 200
    torso_h = max(0.40, (m['torso_length'] + 15.0) / 100)
    half_sh = max(half_chest * 0.95, (m['shoulder_width'] + 6.0) / 400)
    size = min(1.0, m.get('height', ADULT_HEIGHT) / ADULT_HEIGHT)
    neck_w = 0.09 * size
    armhole_drop = 0.22 * size
    sleeve_ext = 0.14 * size * sleeve_scale
    sleeve_opening = (0.10 if sleeve_scale == 1.0 else 0.17) * size
    waist_y = m.get('waist_y', 0.62 * (m['height'] / 100 if 'height' in m else 1.70))
    base_y = max(0.0, waist_y - 0.15)
    top = min(base_y + torso_h, m.get('neck_y', base_y + torso_h))
    sleeve_top = top - 0.04
    sleeve_bottom = sleeve_top - sleeve_opening
    armpit = top - armhole_drop
    if 'arm_top_y' in m:
        sleeve_top = min(top - 0.02, max(sleeve_top, m['arm_top_y'] + ARM_CLEARANCE))
        sleeve_bottom = min(sleeve_bottom, m['arm_bottom_y'] - ARM_CLEARANCE)
        armpit = min(armpit, sleeve_bottom)

    front_pts = [
        (-half_waist, base_y),
        (half_waist, base_y),
        (half_chest, armpit),
        (half_sh + sleeve_ext, sleeve_bottom),
        (half_sh + sleeve_ext, sleeve_top),
        (half_sh, top - 0.02),
        (neck_w, top),
        (0.0, top - 0.08),
        (-neck_w, top),
        (-half_sh, top - 0.02),
        (-(half_sh + sleeve_ext), sleeve_top),
        (-(half_sh + sleeve_ext), sleeve_bottom),
        (-half_chest, armpit),
    ]

    back_offset = 0.85
    back_pts = [(x + back_offset, y) for x, y in front_pts]
    back_pts[7] = (back_offset, top - 0.02)

    s = Session()
    s.add(front_pts)
    s.document.patterns[-1].name = name + ' front'
    s.document.patterns[-1].preset = fabric

    s.add(back_pts)
    s.document.patterns[-1].name = name + ' back'
    s.document.patterns[-1].preset = fabric

    f_id = s.document.patterns[0].id
    b_id = s.document.patterns[1].id

    s.sew_chains([make_edge(s.document, f_id, 1)], [make_edge(s.document, b_id, 12)], reverse=True)
    s.sew_chains([make_edge(s.document, f_id, 12, rev=True)], [make_edge(s.document, b_id, 1)], reverse=False)
    s.sew_chains([make_edge(s.document, f_id, 2)], [make_edge(s.document, b_id, 11)], reverse=True)
    s.sew_chains([make_edge(s.document, f_id, 11, rev=True)], [make_edge(s.document, b_id, 2)], reverse=False)
    s.sew_chains([make_edge(s.document, f_id, 4)], [make_edge(s.document, b_id, 9)], reverse=True)
    s.sew_chains([make_edge(s.document, f_id, 9, rev=True)], [make_edge(s.document, b_id, 4)], reverse=False)
    s.sew_chains([make_edge(s.document, f_id, 5)], [make_edge(s.document, b_id, 8)], reverse=True)
    s.sew_chains([make_edge(s.document, f_id, 8, rev=True)], [make_edge(s.document, b_id, 5)], reverse=False)

    for pattern,point in zip(s.document.patterns,('front','back')):
        pattern.arrangement=arrangement_record('chest',point,version=3)
    return s.document


def create_tank_starter(measurements, fabric='COTTON', name='Tank', extra_length=0.0, hem_flare=0.0):
    m = measurements or {
        'chest': 96.0,
        'waist': 80.0,
        'hip': 96.0,
        'torso_length': 40.0,
        'shoulder_width': 44.0,
    }
    half_chest = (m['chest'] / 2 + 4.0) / 200
    half_waist = (m['waist'] / 2 + 4.0) / 200
    torso_h = max(0.40, (m['torso_length'] + 12.0) / 100) + extra_length
    half_sh = max(half_chest * 0.80, (m['shoulder_width'] + 2.0) / 400)
    neck_edge = min(0.13, half_sh * 0.75 * 0.9)
    armhole_drop = 0.24
    waist_y = m.get('waist_y', 0.62 * (m['height'] / 100 if 'height' in m else 1.70))
    base_y = max(0.0, waist_y - 0.15 - extra_length)
    half_hem = half_waist + hem_flare

    front_pts = [
        (-half_hem, base_y),
        (half_hem, base_y),
        (half_chest, base_y + torso_h - armhole_drop),
        (half_sh * 0.75, base_y + torso_h - 0.02),
        (neck_edge, base_y + torso_h),
        (0.0, base_y + torso_h - 0.12),
        (-neck_edge, base_y + torso_h),
        (-half_sh * 0.75, base_y + torso_h - 0.02),
        (-half_chest, base_y + torso_h - armhole_drop),
    ]

    back_offset = 0.85
    back_pts = [(x + back_offset, y) for x, y in front_pts]
    back_pts[5] = (back_offset, base_y + torso_h - 0.03)

    s = Session()
    s.add(front_pts)
    s.document.patterns[-1].name = name + ' front'
    s.document.patterns[-1].preset = fabric

    s.add(back_pts)
    s.document.patterns[-1].name = name + ' back'
    s.document.patterns[-1].preset = fabric

    f_id = s.document.patterns[0].id
    b_id = s.document.patterns[1].id

    s.sew_chains([make_edge(s.document, f_id, 1)], [make_edge(s.document, b_id, 8)], reverse=True)
    s.sew_chains([make_edge(s.document, f_id, 8, rev=True)], [make_edge(s.document, b_id, 1)], reverse=False)
    s.sew_chains([make_edge(s.document, f_id, 3)], [make_edge(s.document, b_id, 6)], reverse=True)
    s.sew_chains([make_edge(s.document, f_id, 6, rev=True)], [make_edge(s.document, b_id, 3)], reverse=False)

    for pattern,point in zip(s.document.patterns,('front','back')):
        pattern.arrangement=arrangement_record('chest',point,version=3)
    return s.document


def skirt_arc(apex, radius, flare):
    reach = 4 / 3 * math.tan(flare / 2) * radius
    height = apex - radius * math.cos(flare)
    left = Vertex(-radius * math.sin(flare), height)
    right = Vertex(radius * math.sin(flare), height)
    return left, right, (reach * math.cos(flare), -reach * math.sin(flare)), (-reach * math.cos(flare), -reach * math.sin(flare))


def create_skirt_starter(measurements, fabric='COTTON'):
    m = measurements or {
        'waist': 80.0,
        'hip': 96.0,
    }
    size = min(1.0, m.get('height', ADULT_HEIGHT) / ADULT_HEIGHT)
    skirt_len = 0.48
    waist_y = m.get('waist_y', 0.62 * (m['height'] / 100 if 'height' in m else 1.70))
    hip_drop = waist_y - m['hip_y'] if 'hip_y' in m else SKIRT_HIP_DROP * size
    hip_drop = min(max(hip_drop, SKIRT_HIP_DROP * size / 2), skirt_len * .8)
    waist_arc = (m['waist'] + SKIRT_WAIST_EASE) / 400
    hip_arc = (max(m['hip'], m['waist']) + SKIRT_HIP_EASE) / 400
    flare = min(max((hip_arc - waist_arc) / hip_drop, SKIRT_MIN_FLARE), SKIRT_MAX_FLARE)
    waist_radius = waist_arc / flare
    apex = waist_y + waist_radius
    hem_left, hem_right, hem_left.outgoing, hem_right.incoming = skirt_arc(apex, waist_radius + skirt_len, flare)
    waist_left, waist_right, waist_left.incoming, waist_right.outgoing = skirt_arc(apex, waist_radius, flare)
    front_pts = [hem_left, hem_right, waist_right, waist_left]

    back_offset = max(0.85, 2 * hem_right.x + 0.05)
    back_pts = [Vertex(v.x + back_offset, v.y, incoming=v.incoming, outgoing=v.outgoing) for v in front_pts]

    s = Session()
    s.add(front_pts)
    s.document.patterns[-1].name = 'Skirt front'
    s.document.patterns[-1].preset = fabric

    s.add(back_pts)
    s.document.patterns[-1].name = 'Skirt back'
    s.document.patterns[-1].preset = fabric

    f_id = s.document.patterns[0].id
    b_id = s.document.patterns[1].id

    s.sew_chains([make_edge(s.document, f_id, 1)], [make_edge(s.document, b_id, 3)], reverse=True)
    s.sew_chains([make_edge(s.document, f_id, 3, rev=True)], [make_edge(s.document, b_id, 1)], reverse=False)

    for pattern,point in zip(s.document.patterns,('front','back')):
        pattern.arrangement=arrangement_record('waist',point,version=3)
    return s.document


def create_long_sleeve_starter(measurements, fabric='COTTON'):
    document = create_tee_starter(measurements, fabric, 'Long sleeve', 3.2)
    for pattern in document.patterns:
        pattern.arrangement['flat'] = True
    return document


def create_jacket_starter(measurements, fabric='COTTON'):
    document = create_long_sleeve_starter(measurements, fabric)
    front = document.patterns[0]
    top = max(y for _, y in front.points)
    bottom = min(y for _, y in front.points)
    session = Session(document)
    session.selected = front.id
    session.knife_cut([(0.0, top + .1), (0.0, bottom - .1)], False)
    for pattern in session.document.patterns:
        pattern.name = pattern.name.replace('Long sleeve', 'Jacket')
    return session.document


def create_hoodie_starter(measurements, fabric='COTTON'):
    document = create_long_sleeve_starter(measurements, fabric)
    session = Session(document)
    front, back = document.patterns
    for pattern in document.patterns:
        pattern.name = pattern.name.replace('Long sleeve', 'Hoodie')
    right_neck = [make_edge(document, back.id, 7), make_edge(document, front.id, 6)]
    left_neck = [make_edge(document, front.id, 7), make_edge(document, back.id, 6)]
    width = document.chain_length(right_neck)
    depth = .34
    base = max(y for _, y in front.points) + .08
    hoods = []
    for label, offset in (('Hood right', -.4), ('Hood left', .6)):
        session.add([(offset, base), (offset + width, base), (offset + width, base + depth), (offset, base + depth)])
        hood = document.patterns[-1]
        hood.name = label
        hood.preset = fabric
        hood.arrangement = arrangement_record('neck', 'opposite_side' if label == 'Hood right' else 'side', True, version=3)
        hoods.append(hood.id)
    right, left = hoods
    session.sew_chains(right_neck, [make_edge(document, right, 0)], reverse=False)
    session.sew_chains(left_neck, [make_edge(document, left, 0)], reverse=False)
    session.sew_chains([make_edge(document, right, 3)], [make_edge(document, left, 1)], reverse=True)
    session.sew_chains([make_edge(document, right, 2)], [make_edge(document, left, 2)], reverse=True)
    return document


def create_dress_starter(measurements, fabric='COTTON'):
    return create_tank_starter(measurements, fabric, 'Dress', .45, .10)


def create_pants_starter(measurements, fabric='COTTON'):
    m = measurements or {'hip': 96.0, 'inseam': 76.0}
    size = min(1.0, m.get('height', ADULT_HEIGHT) / ADULT_HEIGHT)
    quarter = (m['hip'] / 4 + 3.0) / 100
    waist_y = m.get('waist_y', 0.62 * (m['height'] / 100 if 'height' in m else 1.70))
    crotch_y = waist_y - .28 * size
    base_y = max(0.0, crotch_y - m.get('inseam', 76.0) / 100)
    leg_x = quarter * .55
    half_hem = .10 * size
    right = [(leg_x - half_hem, base_y), (leg_x + half_hem, base_y), (quarter, waist_y), (0.0, waist_y),
             (0.0, crotch_y + .05), (quarter * .15, crotch_y)]
    left = [(-x, y) for x, y in reversed(right)]
    back_offset = 0.85
    s = Session()
    pieces = []
    for label, points, offset in (('Pants front right', left, 0.0), ('Pants front left', right, 0.0),
                                  ('Pants back left', left, back_offset), ('Pants back right', right, back_offset)):
        s.add([(x + offset, y) for x, y in points])
        s.document.patterns[-1].name = label
        s.document.patterns[-1].preset = fabric
        pieces.append(s.document.patterns[-1].id)
    front_right, front_left, back_left, back_right = pieces
    for first, first_edge, second, second_edge in ((front_left, 1, back_left, 3), (front_left, 5, back_left, 5),
                                                   (front_right, 3, back_right, 1), (front_right, 5, back_right, 5),
                                                   (front_right, 1, front_left, 3), (front_right, 0, front_left, 4),
                                                   (back_left, 1, back_right, 3), (back_left, 0, back_right, 4)):
        s.sew_chains([make_edge(s.document, first, first_edge)], [make_edge(s.document, second, second_edge)], reverse=True)
    for identity, volume, point in ((front_right, 'right_thigh', 'front'), (front_left, 'left_thigh', 'front'),
                                    (back_left, 'left_thigh', 'back'), (back_right, 'right_thigh', 'back')):
        s.document.find(identity).arrangement = arrangement_record(volume, point, version=3)
    return s.document


STARTER_GENERATORS = {
    'STARTER_TEE': ('Tee', create_tee_starter, 'BODICE'),
    'STARTER_TANK': ('Tank', create_tank_starter, 'BODICE'),
    'STARTER_SKIRT': ('Skirt', create_skirt_starter, 'SKIRT'),
    'STARTER_LONG_SLEEVE': ('Long sleeve', create_long_sleeve_starter, 'BODICE'),
    'STARTER_DRESS': ('Dress', create_dress_starter, 'BODICE'),
    'STARTER_JACKET': ('Jacket', create_jacket_starter, 'BODICE'),
    'STARTER_HOODIE': ('Hoodie', create_hoodie_starter, 'BODICE'),
    'STARTER_PANTS': ('Pants', create_pants_starter, 'PANTS'),
}
