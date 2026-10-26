"""Constrained fabric meshing with holes, internal paths, and chain correspondence."""
import math
from .core import area,contains,validate_polygon
from . import curves
MAX_VERTICES=50000

class SamplingPlan(dict):
    def __init__(self):
        super().__init__();self.samples={};self.seam_pairs=[];self.outputs={}


def edge_counts(document,spacing):
    if not math.isfinite(spacing) or not .003<=spacing<=.2:raise ValueError('Mesh spacing must be between 3 mm and 20 cm.')
    plan=SamplingPlan()
    for p in document.patterns:
        for path,_,_,_ in p.loops():
            for edge in document.edges(p.id,path):
                n=max(1,math.ceil(document.edge_length(edge)/spacing))
                values={i/n for i in range(n+1)}
                a,b=document.edge_vertices(edge)
                if a.outgoing is not None or b.incoming is not None:
                    _,cumulative=curves.arc_table(document.edge_curve(edge))
                    values.update(v/max(1e-12,cumulative[-1]) for v in cumulative)
                plan.samples[edge]=values
    for seam in document.seams:
        sides=[seam.side(i) for i in (0,1)]
        lengths=[document.chain_length(side) for side in sides]
        n=max(1,math.ceil(max(lengths)/spacing));ratios={i/n for i in range(n+1)}
        for side_index,side in enumerate(sides):
            prefix=0
            for edge in side:
                segment_length=document.edge_length(edge)
                low,high=sorted((edge.t0,edge.t1))
                for fraction in list(plan.samples[edge.full()]):
                    if low-1e-9<=fraction<=high+1e-9:
                        ratio=(prefix+abs(fraction-edge.t0)/abs(edge.t1-edge.t0)*segment_length)/lengths[side_index]
                        ratios.add(1-ratio if side_index==1 and seam.reverse else ratio)
                prefix+=segment_length
        pairs=[]
        for ratio in sorted(max(0,min(1,v)) for v in ratios):
            a=document.chain_position(sides[0],ratio)
            b=document.chain_position(sides[1],1-ratio if seam.reverse else ratio)
            for edge,fraction in (a,b):plan.samples[edge].add(max(0,min(1,fraction)))
            pairs.append((a,b))
        plan.seam_pairs.append((seam.id,pairs))
    for edge,values in plan.samples.items():
        values=sorted(values)
        unique=[]
        for v in values:
            if not unique or abs(v-unique[-1])>1e-8:unique.append(v)
        plan.samples[edge]=unique;plan[edge]=len(unique)-1
    return plan


def distance_to_segment(p,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1]
    t=max(0,min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/max(1e-20,dx*dx+dy*dy)))
    return math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy)


def fabric_mesh(document,pattern,spacing,counts):
    from mathutils import Vector
    from mathutils.geometry import delaunay_2d_cdt
    points=pattern.outline();validate_polygon(points)
    holes=[path.outline() for path in pattern.paths if path.role=='HOLE']
    def on_fabric(point):return contains(point,points) and not any(contains(point,hole) for hole in holes)
    verts=[];constraints=[];boundaries={};sample_info={};outer=[];slits=[]
    for path,_,closed,role in pattern.loops():
        ring_start=len(verts);path_indices=[];path_edges=document.edges(pattern.id,path)
        for edge in path_edges:
            fractions=counts.samples[edge] if hasattr(counts,'samples') else [i/counts[edge] for i in range(counts[edge]+1)]
            start=len(verts)
            verts.extend(document.edge_point(edge,f) for f in fractions[:-1])
            indices=list(range(start,len(verts)+1))
            boundaries[edge.start]=indices
            sample_info[edge.start]=[[f,i] for f,i in zip(fractions,indices)]
            path_indices.extend(indices[:-1])
        if not path_edges:continue
        last=path_edges[-1]
        if closed:
            boundaries[last.start][-1]=ring_start;sample_info[last.start][-1][1]=ring_start
        else:
            verts.append(document.edge_point(last,1));path_indices.append(len(verts)-1)
        constraints.extend(zip(path_indices,path_indices[1:]))
        if closed:constraints.append((path_indices[-1],path_indices[0]))
        if path=='OUTER':outer=path_indices
        if role=='SLIT':slits.append(path_indices)
    anchor_inputs={}
    for anchor in document.anchors:
        if anchor.pattern==pattern.id:
            anchor_inputs[anchor.id]=len(verts);verts.append((anchor.x,anchor.y))
    if len(verts)>MAX_VERTICES:raise ValueError('Boundary too dense. Increase mesh spacing.')
    minx,maxx=min(p[0] for p in points),max(p[0] for p in points)
    miny,maxy=min(p[1] for p in points),max(p[1] for p in points)
    rows=math.ceil((maxy-miny)/(spacing*math.sqrt(3)/2));cols=math.ceil((maxx-minx)/spacing)
    if rows*cols+len(verts)>MAX_VERTICES:raise ValueError('Pattern exceeds 50,000 candidate points. Increase mesh spacing.')
    constraint_points=[(verts[a],verts[b]) for a,b in constraints]
    for row in range(1,rows):
        y=miny+row*spacing*math.sqrt(3)/2
        for col in range(cols+1):
            p=(minx+(col+.5*(row%2))*spacing,y)
            if on_fabric(p) and min(distance_to_segment(p,a,b) for a,b in constraint_points)>spacing*.28:verts.append(p)
    if area([verts[i] for i in outer])<0:outer.reverse()
    out,_,faces,origins,_,_=delaunay_2d_cdt([Vector(v) for v in verts],list(constraints),[outer],1,1e-7,True)
    coords=[(float(v.x),float(v.y)) for v in out]
    faces=[tuple(f) for f in faces if on_fabric(tuple(sum(coords[i][a] for i in f)/len(f) for a in (0,1)))]
    if not faces:raise ValueError('This pattern has no meshable fabric area.')
    mapping={source:i for i,orig in enumerate(origins) for source in orig}
    boundary={key:[mapping[i] for i in values] for key,values in boundaries.items()}
    if hasattr(counts,'outputs'):
        counts.outputs[pattern.id]=dict(samples={key:[[fraction,mapping[index]] for fraction,index in values] for key,values in sample_info.items()},
            anchors={key:mapping[index] for key,index in anchor_inputs.items()},slits=[[mapping[i] for i in chain] for chain in slits],coords=coords)
    return coords,faces,boundary
