import copy
import math
from .meshing import SamplingPlan,edge_counts


def effective_spacing(pattern,default_spacing):
    if not math.isfinite(default_spacing) or not .003<=default_spacing<=.2:
        raise ValueError('Mesh spacing must be between 3 mm and 20 cm.')
    if pattern.mesh_density not in ('AUTO','COARSE','STANDARD','FINE'):
        raise ValueError('Unknown mesh density.')
    multiplier={'AUTO':1.0,'COARSE':2.0,'STANDARD':1.0,'FINE':.5}[pattern.mesh_density]
    return max(.003,min(.2,default_spacing*multiplier))


def boundary_plan(document,default_spacing):
    if not document.patterns:
        return edge_counts(document,default_spacing)
    neighbours={pattern.id:set() for pattern in document.patterns}
    for seam in document.seams:
        identities={edge.pattern for side in (0,1) for edge in seam.side(side)}
        for identity in identities:
            neighbours[identity].update(identities)
    plan=SamplingPlan()
    visited=set()
    for pattern in document.patterns:
        if pattern.id in visited:
            continue
        component=set()
        pending=[pattern.id]
        while pending:
            identity=pending.pop()
            if identity in component:
                continue
            component.add(identity)
            pending.extend(neighbours[identity]-component)
        visited.update(component)
        subset=copy.copy(document)
        subset.patterns=[piece for piece in document.patterns if piece.id in component]
        subset.seams=[seam for seam in document.seams if seam.a.pattern in component]
        subset.anchors=[anchor for anchor in document.anchors if anchor.pattern in component]
        spacing=min(effective_spacing(piece,default_spacing) for piece in subset.patterns)
        shared=edge_counts(subset,spacing)
        plan.update(shared)
        plan.samples.update(shared.samples)
        plan.seam_pairs.extend(shared.seam_pairs)
        plan.outputs.update(shared.outputs)
    seam_order={seam.id:index for index,seam in enumerate(document.seams)}
    plan.seam_pairs.sort(key=lambda item:seam_order[item[0]])
    return plan
