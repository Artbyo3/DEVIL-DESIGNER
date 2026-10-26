"""Constrained Delaunay fabric meshes and matching seam sampling.

The 2D boundary is preserved, including concavities. Interior points use a
staggered grid, avoiding long fan triangles. Only Blender's mathutils is needed.
"""
import math
from .core import area, contains, validate_polygon

MAX_VERTICES = 50000


def edge_counts(document, spacing):
    if not math.isfinite(spacing) or spacing < .003 or spacing > .2:
        raise ValueError("Mesh spacing must be between 3 mm and 20 cm.")
    counts = {}
    for p in document.patterns:
        for i in range(len(p.vertices)):
            edge = document.edge(p.id,i)
            counts[edge] = max(1,math.ceil(math.dist(*document.edge_points(edge))/spacing))
    for seam in document.seams:
        count = max(counts[seam.a],counts[seam.b])
        counts[seam.a] = counts[seam.b] = count
    return counts


def distance_to_segment(p,a,b):
    dx,dy = b[0]-a[0],b[1]-a[1]
    t = max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy)))
    return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)


def fabric_mesh(document, pattern, spacing, counts):
    from mathutils import Vector
    from mathutils.geometry import delaunay_2d_cdt
    points = pattern.points
    validate_polygon(points)
    verts, boundaries = [],{}
    for i in range(len(points)):
        edge = document.edge(pattern.id,i)
        a,b = document.edge_points(edge)
        count = counts[edge]
        start = len(verts)
        verts.extend([(a[0]+(b[0]-a[0])*j/count,a[1]+(b[1]-a[1])*j/count) for j in range(count)])
        boundaries[edge.start] = list(range(start,start+count+1))
    n = len(verts)
    if n > MAX_VERTICES:
        raise ValueError("Boundary too dense. Increase mesh spacing.")
    boundaries[pattern.vertices[-1].id][-1] = 0
    constraints = [(i,(i+1)%n) for i in range(n)]
    minx,maxx = min(p[0] for p in points),max(p[0] for p in points)
    miny,maxy = min(p[1] for p in points),max(p[1] for p in points)
    rows = math.ceil((maxy-miny)/(spacing*math.sqrt(3)/2))
    cols = math.ceil((maxx-minx)/spacing)
    if rows*cols+n > MAX_VERTICES:
        raise ValueError("Pattern mesh exceeds 50,000 candidate points. Increase spacing.")
    edges = list(zip(points,points[1:]+points[:1]))
    for row in range(1,rows):
        y = miny+row*spacing*math.sqrt(3)/2
        for col in range(cols+1):
            p = (minx+(col+.5*(row%2))*spacing,y)
            if contains(p,points) and min(distance_to_segment(p,a,b) for a,b in edges)>spacing*.28:
                verts.append(p)
    ring = list(range(n))
    if area(points)<0:
        ring.reverse()
    result = delaunay_2d_cdt([Vector(v) for v in verts],constraints,[ring],1,1e-7,True)
    out,_,faces,origins,_,_ = result
    if not faces:
        raise ValueError("This pattern could not be meshed.")
    mapping = {source:i for i,orig in enumerate(origins) for source in orig}
    boundary = {key:[mapping[i] for i in indices] for key,indices in boundaries.items()}
    return [(float(v.x),float(v.y)) for v in out],[tuple(f) for f in faces],boundary
