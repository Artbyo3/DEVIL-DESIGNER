import math

GIRTH_BANDS = ('hip', 'waist', 'chest')
RATIO_RANGE = (.5, 2.0)


def _ratio(new, old):
    if not (math.isfinite(new) and math.isfinite(old)) or new <= 0 or old <= 0:
        raise ValueError('The avatar measurements are not usable for a refit.')
    return min(RATIO_RANGE[1], max(RATIO_RANGE[0], new / old))


def length_ratio(old, new):
    if not (math.isfinite(new['height']) and math.isfinite(old['height'])) or new['height'] <= 0 or old['height'] <= 0:
        raise ValueError('The avatar measurements are not usable for a refit.')
    ratio = new['height'] / old['height']
    if not RATIO_RANGE[0] <= ratio <= RATIO_RANGE[1]:
        raise ValueError('The new body is less than half or more than twice the height of the old one, so the garment kept its size.')
    return ratio


def girth_profile(old, new):
    span = old['high_z'] - old['low_z']
    if not math.isfinite(span) or span <= 0:
        raise ValueError('The avatar measurements are not usable for a refit.')
    if old['fallback'] or new['fallback']:
        along = length_ratio(old, new)
        return lambda fraction: along
    marks = sorted(((old[band + '_z'] - old['low_z']) / span, _ratio(new[band], old[band])) for band in GIRTH_BANDS)

    def girth(fraction):
        if fraction <= marks[0][0]:
            return marks[0][1]
        for (low, low_ratio), (high, high_ratio) in zip(marks, marks[1:]):
            if fraction <= high:
                return low_ratio + (high_ratio - low_ratio) * (fraction - low) / max(high - low, 1e-9)
        return marks[-1][1]
    return girth


def _warp(x, y, centre_x, centre_y, across, along):
    return centre_x + (x - centre_x) * across, centre_y + (y - centre_y) * along


def refit_document(document, spans, old, new):
    along = length_ratio(old, new)
    girth = girth_profile(old, new)
    chest = girth((old['chest_z'] - old['low_z']) / (old['high_z'] - old['low_z']))
    for pattern in document.patterns:
        xs = [vertex.x for vertex in pattern.vertices]
        ys = [vertex.y for vertex in pattern.vertices]
        centre_x, bottom, top = (min(xs) + max(xs)) / 2, min(ys), max(ys)
        centre_y = (bottom + top) / 2
        span = spans.get(pattern.id)

        def across(y, span=span, bottom=bottom, top=top):
            if span is None:
                return chest
            low, high, upright = span
            if not upright or top - bottom < 1e-9:
                return girth((low + high) / 2)
            return girth(low + (high - low) * (y - bottom) / (top - bottom))

        for _, nodes, _, _ in pattern.loops():
            for vertex in nodes:
                factor = across(vertex.y)
                vertex.x, vertex.y = _warp(vertex.x, vertex.y, centre_x, centre_y, factor, along)
                if vertex.incoming is not None:
                    vertex.incoming = (vertex.incoming[0] * factor, vertex.incoming[1] * along)
                if vertex.outgoing is not None:
                    vertex.outgoing = (vertex.outgoing[0] * factor, vertex.outgoing[1] * along)
        middle = across(centre_y)
        pattern.wrap_radius *= middle
        if pattern.panel_origin:
            left, low_y, right, high_y = pattern.panel_origin['bounds']
            left, low_y = _warp(left, low_y, centre_x, centre_y, middle, along)
            right, high_y = _warp(right, high_y, centre_x, centre_y, middle, along)
            pattern.panel_origin['bounds'] = [left, low_y, right, high_y]
        for anchor in document.anchors:
            if anchor.pattern == pattern.id:
                anchor.x, anchor.y = _warp(anchor.x, anchor.y, centre_x, centre_y, across(anchor.y), along)
        for record in document.steam:
            if record['pattern'] == pattern.id:
                factor = across(record['y'])
                x, y = _warp(record['x'], record['y'], centre_x, centre_y, factor, along)
                record.update(x=x, y=y, radius=record['radius'] * max(factor, along))
    return along, chest
