from .core import Session, EdgeRef,arrangement_record


def make_edge(doc, pattern_id, index, rev=False):
    e = doc.edge(pattern_id, index)
    if rev:
        return EdgeRef(e.pattern, e.start, e.end, 1.0, 0.0, e.path)
    return e


def create_tee_starter(measurements, fabric='COTTON'):
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
    neck_w = 0.09
    armhole_drop = 0.22
    sleeve_ext = 0.14
    waist_y = m.get('waist_y', 0.62 * (m['height'] / 100 if 'height' in m else 1.70))
    base_y = max(0.0, waist_y - 0.15)

    front_pts = [
        (-half_waist, base_y),
        (half_waist, base_y),
        (half_chest, base_y + torso_h - armhole_drop),
        (half_sh + sleeve_ext, base_y + torso_h - armhole_drop * 0.4),
        (half_sh + sleeve_ext, base_y + torso_h - 0.04),
        (half_sh, base_y + torso_h - 0.02),
        (neck_w, base_y + torso_h),
        (0.0, base_y + torso_h - 0.08),
        (-neck_w, base_y + torso_h),
        (-half_sh, base_y + torso_h - 0.02),
        (-(half_sh + sleeve_ext), base_y + torso_h - 0.04),
        (-(half_sh + sleeve_ext), base_y + torso_h - armhole_drop * 0.4),
        (-half_chest, base_y + torso_h - armhole_drop),
    ]

    back_offset = 0.85
    back_pts = [(x + back_offset, y) for x, y in front_pts]
    back_pts[7] = (back_offset, base_y + torso_h - 0.02)

    s = Session()
    s.add(front_pts)
    s.document.patterns[-1].name = 'Tee front'
    s.document.patterns[-1].preset = fabric

    s.add(back_pts)
    s.document.patterns[-1].name = 'Tee back'
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
        pattern.arrangement=arrangement_record('chest',point)
    return s.document


def create_tank_starter(measurements, fabric='COTTON'):
    m = measurements or {
        'chest': 96.0,
        'waist': 80.0,
        'hip': 96.0,
        'torso_length': 40.0,
        'shoulder_width': 44.0,
    }
    half_chest = (m['chest'] / 2 + 4.0) / 200
    half_waist = (m['waist'] / 2 + 4.0) / 200
    torso_h = max(0.40, (m['torso_length'] + 12.0) / 100)
    half_sh = max(half_chest * 0.80, (m['shoulder_width'] + 2.0) / 400)
    neck_w = 0.10
    armhole_drop = 0.24
    waist_y = m.get('waist_y', 0.62 * (m['height'] / 100 if 'height' in m else 1.70))
    base_y = max(0.0, waist_y - 0.15)

    front_pts = [
        (-half_waist, base_y),
        (half_waist, base_y),
        (half_chest, base_y + torso_h - armhole_drop),
        (half_sh * 0.75, base_y + torso_h - 0.02),
        (neck_w + 0.03, base_y + torso_h),
        (0.0, base_y + torso_h - 0.12),
        (-(neck_w + 0.03), base_y + torso_h),
        (-half_sh * 0.75, base_y + torso_h - 0.02),
        (-half_chest, base_y + torso_h - armhole_drop),
    ]

    back_offset = 0.85
    back_pts = [(x + back_offset, y) for x, y in front_pts]
    back_pts[5] = (back_offset, base_y + torso_h - 0.03)

    s = Session()
    s.add(front_pts)
    s.document.patterns[-1].name = 'Tank front'
    s.document.patterns[-1].preset = fabric

    s.add(back_pts)
    s.document.patterns[-1].name = 'Tank back'
    s.document.patterns[-1].preset = fabric

    f_id = s.document.patterns[0].id
    b_id = s.document.patterns[1].id

    s.sew_chains([make_edge(s.document, f_id, 1)], [make_edge(s.document, b_id, 8)], reverse=True)
    s.sew_chains([make_edge(s.document, f_id, 8, rev=True)], [make_edge(s.document, b_id, 1)], reverse=False)
    s.sew_chains([make_edge(s.document, f_id, 3)], [make_edge(s.document, b_id, 6)], reverse=True)
    s.sew_chains([make_edge(s.document, f_id, 6, rev=True)], [make_edge(s.document, b_id, 3)], reverse=False)

    for pattern,point in zip(s.document.patterns,('front','back')):
        pattern.arrangement=arrangement_record('chest',point)
    return s.document


def create_skirt_starter(measurements, fabric='COTTON'):
    m = measurements or {
        'waist': 80.0,
        'hip': 96.0,
    }
    half_waist = (m['waist'] / 2 + 4.0) / 200
    half_hip = (m['hip'] / 2 + 12.0) / 200
    skirt_len = 0.48
    waist_y = m.get('waist_y', 0.62 * (m['height'] / 100 if 'height' in m else 1.70))
    base_y = max(0.0, waist_y - skirt_len)

    front_pts = [
        (-half_hip, base_y),
        (half_hip, base_y),
        (half_waist, base_y + skirt_len),
        (-half_waist, base_y + skirt_len),
    ]

    back_offset = 0.85
    back_pts = [(x + back_offset, y) for x, y in front_pts]

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
        pattern.arrangement=arrangement_record('waist',point)
    return s.document


STARTER_GENERATORS = {
    'STARTER_TEE': ('Tee', create_tee_starter, 'BODICE'),
    'STARTER_TANK': ('Tank', create_tank_starter, 'BODICE'),
    'STARTER_SKIRT': ('Skirt', create_skirt_starter, 'SKIRT'),
}
