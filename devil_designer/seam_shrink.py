CALIBRATED_WEIGHTS = {0: 0.0, 10: .1844, 20: .3587166666666667, 30: .5313}


def boundary_weights(seams, maps, plan):
    shrinks = {seam.id: seam.shrink for seam in seams}
    weights = {}
    for identity, pairs in plan.seam_pairs:
        weight = CALIBRATED_WEIGHTS[shrinks[identity]]
        if not weight:
            continue
        for pair in pairs:
            for edge, fraction in pair:
                sample, vertex = min(maps[edge.pattern][edge.start], key=lambda item: abs(item[0] - fraction))
                if abs(sample - fraction) > 1e-6:
                    raise ValueError("Sewing samples changed. Rebuild the panels.")
                weights[vertex] = max(weights.get(vertex, 0), weight)
    return weights


def apply(document, obj, cloth, maps, plan):
    weights = boundary_weights(document.seams, maps, plan)
    group = obj.vertex_groups.new(name="DD Seam Shrink")
    for vertex, weight in weights.items():
        group.add([vertex], weight, "REPLACE")
    cloth.settings.shrink_min = 0
    cloth.settings.shrink_max = .60
    cloth.settings.vertex_group_shrink = group.name
