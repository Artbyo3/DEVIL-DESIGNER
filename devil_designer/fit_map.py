import math


NEUTRAL = .03
SATURATION = .15


def vertex_ratios(rest, current, edges):
    if len(rest) != len(current):
        raise ValueError('Fit map needs matching flat and simulated vertices.')
    rest_totals = [0.0] * len(rest)
    current_totals = [0.0] * len(rest)
    for start, end in edges:
        rest_length = math.dist(rest[start], rest[end])
        if rest_length <= 1e-12:
            continue
        current_length = math.dist(current[start], current[end])
        for index in (start, end):
            rest_totals[index] += rest_length
            current_totals[index] += current_length
    return [current_length / rest_length if rest_length else 1.0
            for rest_length, current_length in zip(rest_totals, current_totals)]


def ratio_color(ratio):
    deformation = abs(ratio - 1.0)
    strength = 0.0 if deformation <= NEUTRAL + 1e-12 else 1.0 if deformation >= SATURATION - 1e-12 else (deformation - NEUTRAL) / (SATURATION - NEUTRAL)
    return (1.0, 1.0 - strength, 1.0 - strength, 1.0) if ratio > 1.0 else (1.0 - strength, 1.0 - strength, 1.0, 1.0)


def surface_edges(faces):
    return sorted({tuple(sorted((start, face[(index + 1) % len(face)])))
                   for face in faces for index, start in enumerate(face)})
