"""Pattern geometry, storage, and history. Coordinates are always metres.

Drafts and drag previews only enter the document after a valid completed edit.
This module has no Blender dependency.
"""
from dataclasses import dataclass, field
import json
import math
import uuid

EPS = 1e-10

def uid():
    return uuid.uuid4().hex

def cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])

def area(points):
    return sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points, points[1:]+points[:1])) / 2

def on_segment(p, a, b):
    return (abs(cross(a,b,p)) <= EPS and
            min(a[0],b[0])-EPS <= p[0] <= max(a[0],b[0])+EPS and
            min(a[1],b[1])-EPS <= p[1] <= max(a[1],b[1])+EPS)

def intersects(a, b, c, d):
    x,y,z,w = cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
    if ((x > EPS and y < -EPS or x < -EPS and y > EPS) and
            (z > EPS and w < -EPS or z < -EPS and w > EPS)):
        return True
    return any((on_segment(c,a,b),on_segment(d,a,b),on_segment(a,c,d),on_segment(b,c,d)))

def validate_polygon(points):
    if len(points) < 3:
        raise ValueError("A pattern needs at least three corners.")
    if any(not math.isfinite(v) or abs(v) > 10000 for p in points for v in p):
        raise ValueError("Coordinates must be finite and within 10 km.")
    n = len(points)
    for i in range(n):
        a,b,c = points[i-1],points[i],points[(i+1)%n]
        if math.dist(b,c) < 1e-6:
            raise ValueError("Two neighbouring corners are too close.")
        if abs(cross(a,b,c)) <= EPS and (on_segment(c,a,b) or on_segment(a,b,c)):
            raise ValueError("An edge doubles back on itself.")
        for j in range(i+1,n):
            if j == i+1 or (i == 0 and j == n-1):
                continue
            if intersects(points[i],points[(i+1)%n],points[j],points[(j+1)%n]):
                raise ValueError("Pattern edges cannot cross or touch each other.")
    if abs(area(points)) < 1e-8:
        raise ValueError("This pattern has no usable area.")

def contains(point, points):
    inside = False
    x,y = point
    for a,b in zip(points,points[1:]+points[:1]):
        if on_segment(point,a,b):
            return True
        if (a[1]>y) != (b[1]>y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            inside = not inside
    return inside

def triangulate(points):
    """Ear clipping handles concave patterns, collinear corners, either winding."""
    validate_polygon(points)
    indices = list(range(len(points)))
    if area(points) < 0:
        indices.reverse()
    while len(indices) > 3:
        flat = next((k for k in range(len(indices)) if abs(cross(
            points[indices[k-1]],points[indices[k]],points[indices[(k+1)%len(indices)]])) <= EPS),None)
        if flat is None:
            break
        indices.pop(flat)
    triangles = []
    while len(indices) > 3:
        for k,b in enumerate(indices):
            a,c = indices[k-1],indices[(k+1)%len(indices)]
            if cross(points[a],points[b],points[c]) <= EPS:
                continue
            if any(cross(points[a],points[b],points[p]) >= -EPS and
                   cross(points[b],points[c],points[p]) >= -EPS and
                   cross(points[c],points[a],points[p]) >= -EPS
                   for p in indices if p not in (a,b,c)):
                continue
            triangles.append((a,b,c))
            indices.pop(k)
            break
        else:
            raise ValueError("Cannot fill this pattern; check its corners.")
    triangles.append(tuple(indices))
    return triangles

from . import curves
import copy

@dataclass
class Vertex:
    x: float
    y: float
    id: str = field(default_factory=uid)
    incoming: tuple = None
    outgoing: tuple = None

@dataclass
class Path:
    name: str
    vertices: list
    closed: bool = False
    role: str = 'INTERNAL'
    id: str = field(default_factory=uid)

    @property
    def points(self): return [(v.x,v.y) for v in self.vertices]

    def outline(self): return sample_path(self.vertices,self.closed)

@dataclass
class Pattern:
    name: str
    vertices: list
    id: str = field(default_factory=uid)
    paths: list = field(default_factory=list)
    preset: str = 'COTTON'
    wrap_radius: float = 0.0
    features: list = field(default_factory=list)

    @property
    def points(self): return [(v.x,v.y) for v in self.vertices]

    def outline(self): return sample_path(self.vertices,True)

    def path(self,identity='OUTER'):
        if identity=='OUTER': return self
        result=next((p for p in self.paths if p.id==identity),None)
        if result is None: raise ValueError('The internal path no longer exists.')
        return result

    def loops(self):
        return [('OUTER',self.vertices,True,'OUTER')]+[(p.id,p.vertices,p.closed,p.role) for p in self.paths]

    def contains(self,point):
        return contains(point,self.outline()) and not any(contains(point,p.outline()) for p in self.paths if p.role=='HOLE')


def sample_path(vertices,closed):
    result=[]
    count=len(vertices) if closed else len(vertices)-1
    for i in range(count):
        a,b=vertices[i],vertices[(i+1)%len(vertices)]
        result.extend(point for _,point in curves.table(curves.controls(a,b))[:-1])
    if not closed and vertices: result.append((vertices[-1].x,vertices[-1].y))
    return result

@dataclass(frozen=True)
class EdgeRef:
    pattern: str
    start: str
    end: str
    t0: float = 0.0
    t1: float = 1.0
    path: str = 'OUTER'

    def full(self): return EdgeRef(self.pattern,self.start,self.end,path=self.path)

@dataclass
class Seam:
    a: EdgeRef
    b: EdgeRef
    reverse: bool = True
    id: str = field(default_factory=uid)
    chain_a: tuple = ()
    chain_b: tuple = ()

    def side(self,index): return list((self.chain_a or (self.a,)) if index==0 else (self.chain_b or (self.b,)))

@dataclass
class Anchor:
    pattern: str
    x: float
    y: float
    kind: str = 'PIN'
    target: tuple = None
    id: str = field(default_factory=uid)


def vertex_data(v):
    return dict(x=float(v.x),y=float(v.y),id=v.id,incoming=v.incoming,outgoing=v.outgoing)


def read_vertex(v):
    handles=[]
    for key in ('incoming','outgoing'):
        value=v.get(key)
        if value is not None:
            if len(value)!=2 or any(not math.isfinite(float(n)) for n in value): raise ValueError('Invalid Bezier handle.')
            value=tuple(float(n) for n in value)
        handles.append(value)
    return Vertex(float(v['x']),float(v['y']),v['id'],*handles)


class Document:
    def __init__(self,patterns=None,seams=None,anchors=None,uv_layout=None):
        self.patterns=patterns or []
        self.seams=seams or []
        self.anchors=anchors or []
        self.uv_layout=uv_layout

    def dumps(self):
        return json.dumps(dict(version=3,patterns=[dict(id=p.id,name=p.name,
            vertices=[vertex_data(v) for v in p.vertices],paths=[dict(id=q.id,name=q.name,closed=q.closed,role=q.role,
            vertices=[vertex_data(v) for v in q.vertices]) for q in p.paths],preset=p.preset,wrap_radius=p.wrap_radius,
            features=p.features) for p in self.patterns],seams=[dict(id=s.id,a=vars(s.a),b=vars(s.b),reverse=s.reverse,
            chain_a=[vars(e) for e in s.side(0)],chain_b=[vars(e) for e in s.side(1)]) for s in self.seams],
            anchors=[vars(a) for a in self.anchors],uv_layout=self.uv_layout),separators=(',',':'),allow_nan=False)

    @classmethod
    def loads(cls,value):
        if not value: return cls()
        try:
            data=json.loads(value)
            if data['version'] not in (1,2,3): raise ValueError('Unsupported pattern document version.')
            patterns=[]
            for item in data['patterns']:
                p=Pattern(item['name'],[read_vertex(v) for v in item['vertices']],item['id'])
                p.paths=[Path(q['name'],[read_vertex(v) for v in q['vertices']],q['closed'],q['role'],q['id']) for q in item.get('paths',[])]
                p.preset=item.get('preset','COTTON'); p.wrap_radius=float(item.get('wrap_radius',0)); p.features=item.get('features',[])
                patterns.append(p)
            document=cls(patterns,uv_layout=data.get('uv_layout'))
            if data['version']>=2:
                for item in data['seams']:
                    document.seams.append(Seam(EdgeRef(**item['a']),EdgeRef(**item['b']),item['reverse'],item['id'],
                        tuple(EdgeRef(**e) for e in item.get('chain_a',[])),tuple(EdgeRef(**e) for e in item.get('chain_b',[]))))
            document.anchors=[Anchor(**a) for a in data.get('anchors',[])]
            if data['version']<3 and patterns:
                points=[point for p in patterns for point in p.points]
                lo=[min(p[a] for p in points) for a in (0,1)]
                extent=max(max(p[0] for p in points)-lo[0],max(p[1] for p in points)-lo[1],.001)
                document.uv_layout=dict(origin=lo,scale=extent)
            document.validate()
            return document
        except (KeyError,TypeError,json.JSONDecodeError,OverflowError,AttributeError) as exc:
            raise ValueError('Cannot read the saved pattern document.') from exc

    def find(self,identity): return next((p for p in self.patterns if p.id==identity),None)

    def edge(self,pattern,index,path='OUTER'):
        p=self.find(pattern)
        if p is None: raise ValueError('The pattern no longer exists.')
        nodes=p.path(path).vertices
        closed=path=='OUTER' or p.path(path).closed
        if index<0 or index>=len(nodes)-(0 if closed else 1): raise ValueError('Choose a valid segment.')
        return EdgeRef(p.id,nodes[index].id,nodes[(index+1)%len(nodes)].id,path=path)

    def edges(self,pattern,path='OUTER'):
        p=self.find(pattern); q=p.path(path)
        return [self.edge(pattern,i,path) for i in range(len(q.vertices)-(0 if path=='OUTER' or q.closed else 1))]

    def edge_vertices(self,edge):
        p=self.find(edge.pattern)
        if p:
            nodes=p.path(edge.path).vertices
            closed=edge.path=='OUTER' or p.path(edge.path).closed
            for i in range(len(nodes)-(0 if closed else 1)):
                if nodes[i].id==edge.start and nodes[(i+1)%len(nodes)].id==edge.end: return nodes[i],nodes[(i+1)%len(nodes)]
        raise ValueError('A referenced segment was removed. Pair the replacement again.')

    def edge_curve(self,edge): return curves.controls(*self.edge_vertices(edge))
    def edge_point(self,edge,fraction): return curves.at_length(self.edge_curve(edge),fraction)
    def edge_points(self,edge): return self.edge_point(edge,edge.t0),self.edge_point(edge,edge.t1)
    def edge_length(self,edge): return curves.length(self.edge_curve(edge))*abs(edge.t1-edge.t0)

    def chain_length(self,chain): return sum(self.edge_length(e) for e in chain)

    def chain_position(self,chain,fraction):
        total=self.chain_length(chain)
        target=max(0,min(1,fraction))*total
        for i,edge in enumerate(chain):
            length=self.edge_length(edge)
            if target<=length+1e-10 or i==len(chain)-1:
                t=max(0,min(1,target/max(1e-15,length)))
                return edge.full(),edge.t0+(edge.t1-edge.t0)*t
            target-=length
        raise ValueError('A sewing side needs at least one segment.')

    def seam_stats(self,seam):
        a,b=self.chain_length(seam.side(0)),self.chain_length(seam.side(1))
        return a,b,abs(a-b),100*abs(a-b)/max(a,b,1e-12)

    def validate_seams(self):
        used={}
        for seam in self.seams:
            self.edge_vertices(seam.a);self.edge_vertices(seam.b)
            if seam.chain_a and seam.a!=seam.chain_a[0] or seam.chain_b and seam.b!=seam.chain_b[0]:
                raise ValueError('Sewing aliases do not match their edge chains.')
            if not isinstance(seam.reverse,bool): raise ValueError('Invalid sewing direction.')
            for side in (seam.side(0),seam.side(1)):
                if not side: raise ValueError('A sewing side is empty.')
                for edge in side:
                    self.edge_vertices(edge)
                    if not all(math.isfinite(t) and 0<=t<=1 for t in (edge.t0,edge.t1)) or abs(edge.t1-edge.t0)<1e-8:
                        raise ValueError('Sewing ranges need distinct positions between 0 and 100 percent.')
                    lo,hi=sorted((edge.t0,edge.t1))
                    key=edge.full()
                    if any(min(hi,b)-max(lo,a)>1e-7 for a,b in used.get(key,[])):
                        raise ValueError('These sewing ranges overlap an existing pair.')
                    used.setdefault(key,[]).append((lo,hi))

    def validate(self):
        ids=set()
        def identity(value):
            if not isinstance(value,str) or not value or value in ids: raise ValueError('Pattern, path, point, and feature IDs must be unique.')
            ids.add(value)
        for p in self.patterns:
            identity(p.id)
            if not isinstance(p.name,str) or not p.name.strip(): raise ValueError('Pattern names must contain text.')
            if p.preset not in {'COTTON','LINEN','SILK','DENIM','KNIT'}: raise ValueError('Unknown cloth preset.')
            if not math.isfinite(p.wrap_radius) or p.wrap_radius<0: raise ValueError('Invalid wrap radius.')
            for v in p.vertices: identity(v.id)
            outer=p.outline();validate_polygon(outer)
            holes=[]
            for path in p.paths:
                identity(path.id)
                if path.role not in {'INTERNAL','HOLE','SLIT'}: raise ValueError('Unknown internal path role.')
                for v in path.vertices: identity(v.id)
                points=path.outline()
                if path.closed:
                    validate_polygon(points)
                elif len(points)<2 or any(math.dist(a,b)<1e-8 for a,b in zip(points,points[1:])):
                    raise ValueError('An internal line needs distinct points.')
                if any(not contains(point,outer) for point in points): raise ValueError('Internal paths must stay inside their pattern.')
                path_edges=list(zip(points,points[1:]+(points[:1] if path.closed else [])))
                for a,b in path_edges:
                    for c,d in zip(outer,outer[1:]+outer[:1]):
                        if cross(a,b,c)*cross(a,b,d)<-EPS and cross(c,d,a)*cross(c,d,b)<-EPS:
                            raise ValueError('An internal path crosses outside its pattern boundary.')
                if path.role=='HOLE':
                    if any(on_segment(point,a,b) for point in points for a,b in zip(outer,outer[1:]+outer[:1])):
                        raise ValueError('A hole must lie strictly inside the pattern.')
                    if not path.closed: raise ValueError('A hole must be closed.')
                    for other in holes:
                        if any(contains(point,other) for point in points) or any(contains(point,points) for point in other):
                            raise ValueError('Holes cannot overlap.')
                    holes.append(points)
            for path in p.paths:
                if path.role!='HOLE' and any(contains(point,hole) and not any(on_segment(point,a,b) for a,b in zip(hole,hole[1:]+hole[:1])) for point in path.outline() for hole in holes):
                    raise ValueError('Internal paths cannot pass through a hole.')
        for seam in self.seams: identity(seam.id)
        for anchor in self.anchors:
            identity(anchor.id)
            p=self.find(anchor.pattern)
            if p is None or not p.contains((anchor.x,anchor.y)): raise ValueError('Pins and tacks must lie on fabric.')
            if anchor.kind not in {'PIN','TACK'}: raise ValueError('Unknown anchor type.')
            if anchor.target is not None and (len(anchor.target)!=3 or any(not math.isfinite(v) for v in anchor.target)):
                raise ValueError('Invalid tack target.')
        self.validate_seams()
        if self.uv_layout is not None:
            scale=self.uv_layout['scale']; origin=self.uv_layout['origin']
            if not math.isfinite(scale) or scale<=0 or len(origin)!=2 or any(not math.isfinite(v) for v in origin):
                raise ValueError('Invalid UV layout transform.')

    def prune_seams(self):
        valid=[]
        for seam in self.seams:
            try:
                for side in (seam.side(0),seam.side(1)):
                    for e in side: self.edge_vertices(e)
                valid.append(seam)
            except ValueError: pass
        self.seams=valid
        self.anchors=[a for a in self.anchors if self.find(a.pattern)]

    def split_edge(self,edge,fraction=.5):
        a,b=self.edge_vertices(edge)
        p=self.find(edge.pattern); nodes=p.path(edge.path).vertices
        control=self.edge_curve(edge); t=curves.parameter(control,fraction)
        left,right=curves.split(control,t)
        v=Vertex(*left[3],incoming=curves.sub(left[2],left[3]),outgoing=curves.sub(right[1],right[0]))
        if a.outgoing is None and b.incoming is None:
            v.incoming=v.outgoing=None
        else:
            a.outgoing=curves.sub(left[1],left[0]); b.incoming=curves.sub(right[2],right[3])
        nodes.insert(nodes.index(a)+1,v)
        def remap(span):
            if span.full()!=edge.full(): return [span]
            lo,hi=sorted((span.t0,span.t1)); result=[]
            if lo<fraction-1e-10:
                result.append(EdgeRef(edge.pattern,a.id,v.id,lo/fraction,min(hi,fraction)/fraction,edge.path))
            if hi>fraction+1e-10:
                result.append(EdgeRef(edge.pattern,v.id,b.id,max(0,(lo-fraction)/(1-fraction)),(hi-fraction)/(1-fraction),edge.path))
            if span.t0>span.t1:
                result=[EdgeRef(e.pattern,e.start,e.end,e.t1,e.t0,e.path) for e in reversed(result)]
            return result
        for seam in self.seams:
            sides=[[new for old in seam.side(i) for new in remap(old)] for i in (0,1)]
            seam.chain_a,seam.chain_b=tuple(sides[0]),tuple(sides[1]); seam.a,seam.b=sides[0][0],sides[1][0]
        return v


from .construction import ConstructionMixin

class Session(ConstructionMixin):
    def __init__(self,document=None):
        self.document=document or Document()
        self.selected=self.corner=None
        self.path='OUTER'
        self.segment=None
        self.point_selection=[]
        self.undo_stack,self.redo_stack=[],[]
        self.last_repairs=0

    def commit(self,operation):
        before=self.document.dumps()
        old_seams={s.id for s in self.document.seams}
        self.last_repairs=0
        try:
            operation()
            self.document.prune_seams()
            self.document.validate()
            self.last_repairs=len(old_seams-{s.id for s in self.document.seams})
        except Exception:
            self.document=Document.loads(before)
            raise
        if self.document.dumps()!=before:
            self.undo_stack.append(before); self.undo_stack=self.undo_stack[-100:]; self.redo_stack.clear(); return True
        return False

    def add(self,points):
        validate_polygon(points)
        names={p.name for p in self.document.patterns}; index=1
        while f'Pattern {index:02d}' in names: index+=1
        p=Pattern(f'Pattern {index:02d}',[Vertex(*point) for point in points])
        self.commit(lambda:self.document.patterns.append(p))
        self.selected,self.corner,self.path=p.id,None,'OUTER'

    def add_ellipse(self,a,b,internal=False):
        cx,cy=(a[0]+b[0])/2,(a[1]+b[1])/2
        rx,ry=abs(b[0]-a[0])/2,abs(b[1]-a[1])/2
        if min(rx,ry)<.0005: raise ValueError('Ellipse dimensions must exceed 1 mm.')
        k=.5522847498307936
        nodes=[Vertex(cx+rx,cy,incoming=(0,-k*ry),outgoing=(0,k*ry)),
               Vertex(cx,cy+ry,incoming=(k*rx,0),outgoing=(-k*rx,0)),
               Vertex(cx-rx,cy,incoming=(0,k*ry),outgoing=(0,-k*ry)),
               Vertex(cx,cy-ry,incoming=(-k*rx,0),outgoing=(k*rx,0))]
        if internal: return self.add_path(nodes,True)
        p=Pattern('Ellipse',nodes)
        self.commit(lambda:self.document.patterns.append(p)); self.selected,self.corner,self.path=p.id,None,'OUTER'

    def add_path(self,points,closed=False):
        p=self.document.find(self.selected)
        if p is None: raise ValueError('Select a pattern for the internal shape.')
        nodes=[v if isinstance(v,Vertex) else Vertex(*v) for v in points]
        path=Path('Internal '+str(len(p.paths)+1),nodes,closed)
        self.commit(lambda:p.paths.append(path)); self.path,self.corner=path.id,None
        return path

    def move(self,points):
        p=self.document.find(self.selected)
        if p is None: raise ValueError('Select a pattern to edit.')
        nodes=p.path(self.path).vertices
        if len(points)!=len(nodes): raise ValueError('The point count changed.')
        old=[(v.x,v.y) for v in nodes]
        def apply():
            for v,point in zip(nodes,points): v.x,v.y=point
            if self.path=='OUTER' and all(math.dist(curves.sub(q,pnt),curves.sub(points[0],old[0]))<1e-8 for pnt,q in zip(old,points)):
                dx,dy=curves.sub(points[0],old[0])
                for path in p.paths:
                    for v in path.vertices: v.x+=dx; v.y+=dy
                for anchor in self.document.anchors:
                    if anchor.pattern==p.id: anchor.x+=dx; anchor.y+=dy
        return self.commit(apply)

    def duplicate(self):
        p=self.document.find(self.selected)
        if p is None:return False
        new=clone_pattern(p,offset=(.03,-.03));new.name+=' copy'
        def apply():
            self.document.patterns.append(new)
            clone_relationships(self.document,p,new)
        self.commit(apply);self.selected,self.corner,self.path=new.id,None,'OUTER';return True

    def delete(self):
        p=self.document.find(self.selected)
        if p is None:return False
        if self.corner is not None:
            nodes=p.path(self.path).vertices; index=self.corner
            result=self.commit(lambda:nodes.pop(index));self.corner=None;return result
        if self.path!='OUTER':
            path=p.path(self.path); result=self.commit(lambda:p.paths.remove(path));self.path='OUTER';return result
        result=self.commit(lambda:self.document.patterns.remove(p));self.selected=None;return result

    def sew(self,a,b): return self.sew_chains([a],[b])

    def sew_chains(self,a,b,reverse=True):
        for e in a+b: self.document.edge_vertices(e)
        seam=Seam(a[0],b[0],reverse,chain_a=tuple(a),chain_b=tuple(b))
        return self.commit(lambda:self.document.seams.append(seam))

    def remove_seam(self,identity):
        seam=next((s for s in self.document.seams if s.id==identity),None)
        if seam is None:raise ValueError('That seam no longer exists.')
        result=self.commit(lambda:self.document.seams.remove(seam));self.last_repairs=0;return result

    def reverse_seam(self,identity):
        seam=next((s for s in self.document.seams if s.id==identity),None)
        if seam is None:raise ValueError('That seam no longer exists.')
        return self.commit(lambda:setattr(seam,'reverse',not seam.reverse))

    def split_segment(self,edge,fraction=.5):
        if not .0001<fraction<.9999:raise ValueError('Split inside the segment, away from its endpoints.')
        return self.commit(lambda:self.document.split_edge(edge,fraction))

    def curve_point(self,index=None):
        p=self.document.find(self.selected)
        if p is None:raise ValueError('Select a pattern point.')
        nodes=p.path(self.path).vertices;index=self.corner if index is None else index
        if index is None:raise ValueError('Select a pattern point.')
        def apply():
            v=nodes[index]
            if v.incoming is not None or v.outgoing is not None:v.incoming=v.outgoing=None;return
            closed=self.path=='OUTER' or p.path(self.path).closed
            before,after=(nodes[index-1],nodes[(index+1)%len(nodes)]) if closed else (nodes[max(0,index-1)],nodes[min(len(nodes)-1,index+1)])
            direction=(after.x-before.x,after.y-before.y);length=math.hypot(*direction)
            if length<1e-10:raise ValueError('Cannot create a tangent at this point.')
            tangent=curves.mul(direction,1/length)
            v.incoming=curves.mul(tangent,-math.dist((v.x,v.y),(before.x,before.y))/3)
            v.outgoing=curves.mul(tangent,math.dist((v.x,v.y),(after.x,after.y))/3)
            if not closed and index==0:v.incoming=None
            if not closed and index==len(nodes)-1:v.outgoing=None
        return self.commit(apply)

    def set_handle(self,index,which,value):
        p=self.document.find(self.selected);v=p.path(self.path).vertices[index]
        return self.commit(lambda:setattr(v,which,tuple(value)))

    def set_length(self,edge,target):
        if not math.isfinite(target) or target<.0001:raise ValueError('Length must be at least 0.01 cm.')
        a,b=self.document.edge_vertices(edge);ratio=target/self.document.edge_length(edge)
        def apply():
            b.x,b.y=curves.add((a.x,a.y),curves.mul((b.x-a.x,b.y-a.y),ratio))
            if a.outgoing is not None:a.outgoing=curves.mul(a.outgoing,ratio)
            if b.incoming is not None:b.incoming=curves.mul(b.incoming,ratio)
        return self.commit(apply)

    def merge_points(self,indices):
        p=self.document.find(self.selected);nodes=p.path(self.path).vertices
        if len(indices)!=2:raise ValueError('Shift-click two adjacent points to merge.')
        a,b=sorted(indices)
        if b!=a+1 and (a,b)!=(0,len(nodes)-1):raise ValueError('Merge adjacent points.')
        def apply():
            nodes[a].x,nodes[a].y=curves.mix((nodes[a].x,nodes[a].y),(nodes[b].x,nodes[b].y),.5)
            nodes.pop(b)
        result=self.commit(apply);self.corner=a;self.point_selection=[];return result

    def offset(self,distance):
        p=self.document.find(self.selected)
        if p is None:raise ValueError('Select a pattern to offset.')
        if abs(distance)<1e-6:raise ValueError('Enter a nonzero outline offset.')
        new=Pattern(p.name+' offset',[Vertex(*q) for q in curves.offset_polygon(p.outline(),distance)],preset=p.preset)
        for hole in p.paths:
            if hole.role=='HOLE':new.paths.append(Path(hole.name,[Vertex(*q) for q in curves.offset_polygon(hole.outline(),-distance)],True,'HOLE'))
        self.commit(lambda:self.document.patterns.append(new));self.selected,self.path,self.corner=new.id,'OUTER',None

    def add_anchor(self,point,kind='PIN',target=None):
        if not self.selected:raise ValueError('Select a pattern for the anchor.')
        anchor=Anchor(self.selected,*point,kind,target)
        self.commit(lambda:self.document.anchors.append(anchor));return anchor

    def history(self,redo=False):
        self.last_repairs=0
        source,target=(self.redo_stack,self.undo_stack) if redo else (self.undo_stack,self.redo_stack)
        if not source:return False
        target.append(self.document.dumps());self.document=Document.loads(source.pop());self.corner=None;self.path='OUTER';self.segment=None;self.point_selection=[]
        if not self.document.find(self.selected):self.selected=None
        return True


def clone_pattern(pattern,offset=(0,0),reflection=None):
    result=copy.deepcopy(pattern);result.id=uid();mapping={pattern.id:result.id}
    def convert(v):
        old=v.id;v.id=uid();mapping[old]=v.id
        p=(v.x,v.y)
        if reflection:
            p=curves.reflect(p,*reflection)
            if v.incoming is not None:v.incoming=curves.reflect(v.incoming,*reflection,vector=True)
            if v.outgoing is not None:v.outgoing=curves.reflect(v.outgoing,*reflection,vector=True)
        v.x,v.y=curves.add(p,offset)
    for v in result.vertices:convert(v)
    for path in result.paths:
        old=path.id;path.id=uid();mapping[old]=path.id
        for v in path.vertices:convert(v)
    result.features=[]
    result._id_map=mapping
    return result


def clone_relationships(document,source,target,reverse_outer=False):
    mapping=getattr(target,'_id_map',{})
    seam_map={}
    def remap(edge):
        candidate=EdgeRef(target.id,mapping[edge.start],mapping[edge.end],edge.t0,edge.t1,mapping.get(edge.path,edge.path))
        try:document.edge_vertices(candidate);return candidate
        except ValueError:
            opposite=EdgeRef(candidate.pattern,candidate.end,candidate.start,1-candidate.t0,1-candidate.t1,candidate.path)
            document.edge_vertices(opposite);return opposite
    for seam in list(document.seams):
        if all(e.pattern==source.id for side in (seam.side(0),seam.side(1)) for e in side):
            try:a,b=[remap(e) for e in seam.side(0)],[remap(e) for e in seam.side(1)]
            except (ValueError,KeyError):continue
            new=Seam(a[0],b[0],seam.reverse,chain_a=tuple(a),chain_b=tuple(b))
            document.seams.append(new);seam_map[seam.id]=new.id
    for feature in source.features:
        if feature.get('seam') and feature['seam'] not in seam_map:continue
        new=copy.deepcopy(feature);new['id']=uid()
        if new.get('seam'):new['seam']=seam_map[new['seam']]
        if new.get('apex'):new['apex']=mapping.get(new['apex'],new['apex'])
        target.features.append(new)
