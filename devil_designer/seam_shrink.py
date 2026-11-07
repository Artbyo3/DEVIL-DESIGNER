def boundary_weights(seams, maps, plan):
    shrinks = {seam.id: seam.shrink for seam in seams}
    sides = {seam.id: seam.ease_side for seam in seams}
    weights = {}
    for identity, pairs in plan.seam_pairs:
        weight = shrinks[identity] / 100
        if not weight:
            continue
        for pair in pairs:
            for position, (edge, fraction) in enumerate(pair):
                if sides[identity] and position != sides[identity] - 1:
                    continue
                sample, vertex = min(maps[edge.pattern][edge.start], key=lambda item: abs(item[0] - fraction))
                if abs(sample - fraction) > 1e-6:
                    raise ValueError("Sewing samples changed. Rebuild the panels.")
                weights[vertex] = max(weights.get(vertex, 0), weight)
    return weights
