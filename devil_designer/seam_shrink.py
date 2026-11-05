def boundary_weights(seams, maps, plan):
    shrinks = {seam.id: seam.shrink for seam in seams}
    weights = {}
    for identity, pairs in plan.seam_pairs:
        weight = shrinks[identity] / 100
        if not weight:
            continue
        for pair in pairs:
            for edge, fraction in pair:
                sample, vertex = min(maps[edge.pattern][edge.start], key=lambda item: abs(item[0] - fraction))
                if abs(sample - fraction) > 1e-6:
                    raise ValueError("Sewing samples changed. Rebuild the panels.")
                weights[vertex] = max(weights.get(vertex, 0), weight)
    return weights
