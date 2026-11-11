import math

from . import curves

POINT = 'POINT'
MIDPOINT = 'MIDPOINT'
INTERSECTION = 'INTERSECTION'
EDGE = 'EDGE'
RANK = {POINT: 0, INTERSECTION: 1, MIDPOINT: 2}
LABELS = {POINT: 'Point', MIDPOINT: 'Midpoint', INTERSECTION: 'Intersection', EDGE: 'Edge'}
SNAP_PIXELS = 10
EDGE_END_MARGIN = .01
ON_EDGE_SHARE = .05


def nearest_on_line(line, point):
    best = (float('inf'), line[0])
    for first, second in zip(line, line[1:]):
        across = (second[0] - first[0], second[1] - first[1])
        squared = across[0] * across[0] + across[1] * across[1]
        share = max(0.0, min(1.0, ((point[0] - first[0]) * across[0] + (point[1] - first[1]) * across[1]) / squared)) if squared else 0.0
        spot = (first[0] + across[0] * share, first[1] + across[1] * share)
        distance = math.dist(spot, point)
        if distance < best[0]:
            best = (distance, spot)
    return best


def segments_near(line, point, reach):
    return [(first, second) for first, second in zip(line, line[1:])
            if min(first[0], second[0]) - reach <= point[0] <= max(first[0], second[0]) + reach
            and min(first[1], second[1]) - reach <= point[1] <= max(first[1], second[1]) + reach]


def crossing(first, second):
    (ax, ay), (bx, by) = first
    (cx, cy), (dx, dy) = second
    denominator = (bx - ax) * (dy - cy) - (by - ay) * (dx - cx)
    if abs(denominator) < 1e-14:
        return None
    along = ((cx - ax) * (dy - cy) - (cy - ay) * (dx - cx)) / denominator
    other = ((cx - ax) * (by - ay) - (cy - ay) * (bx - ax)) / denominator
    if not (-1e-9 <= along <= 1 + 1e-9 and -1e-9 <= other <= 1 + 1e-9):
        return None
    return ax + (bx - ax) * along, ay + (by - ay) * along


class Targets:
    def __init__(self, document, moving=frozenset()):
        self.points = []
        self.edges = []
        for pattern in document.patterns:
            for path, nodes, _, _ in pattern.loops():
                self.points.extend((node.x, node.y, POINT) for node in nodes if node.id not in moving)
                for edge in document.edges(pattern.id, path):
                    if edge.start in moving or edge.end in moving:
                        continue
                    control = document.edge_curve(edge)
                    line = [point for _, point in curves.table(control)]
                    middle = curves.at_length(control, .5)
                    self.points.append((middle[0], middle[1], MIDPOINT))
                    across = [point[0] for point in line]
                    up = [point[1] for point in line]
                    self.edges.append(((min(across), min(up), max(across), max(up)), line))

    def snap(self, point, reach):
        found = []
        for x, y, kind in self.points:
            distance = math.hypot(x - point[0], y - point[1])
            if distance <= reach:
                found.append((round(distance, 6), RANK[kind], (x, y), kind))
        near = []
        for (left, low, right, high), line in self.edges:
            if left - reach <= point[0] <= right + reach and low - reach <= point[1] <= high + reach:
                distance, spot = nearest_on_line(line, point)
                if distance <= reach:
                    near.append((distance, spot, segments_near(line, point, reach)))
        for index, (_, _, first_line) in enumerate(near):
            for _, _, second_line in near[index + 1:]:
                for first in first_line:
                    for second in second_line:
                        spot = crossing(first, second)
                        if spot is not None and math.dist(spot, point) <= reach:
                            found.append((round(math.dist(spot, point), 6), RANK[INTERSECTION], spot, INTERSECTION))
        if found:
            _, _, spot, kind = min(found, key=lambda item: item[:2])
            return spot, kind
        if near:
            return min(near, key=lambda item: item[0])[1], EDGE
        return None


def fabric_spot(pattern, candidates):
    return next((spot for spot in candidates if spot is not None and pattern.contains(spot)), None)


def edge_fraction(control, spot, reach):
    fraction, distance = curves.closest_fraction(control, spot)
    if distance <= reach * ON_EDGE_SHARE and EDGE_END_MARGIN < fraction < 1 - EDGE_END_MARGIN:
        return fraction
    return None
