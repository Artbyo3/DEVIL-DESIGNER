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
    point_type: str = 'CORNER'

def compute_auto_handles(nodes,idx,closed):
    v=nodes[idx]
    if not closed and (idx==0 or idx==len(nodes)-1):
        return None,None
    count=len(nodes)
    if count<2:
        return None,None
    before=nodes[idx-1] if (closed or idx>0) else nodes[0]
    after=nodes[(idx+1)%count] if closed else nodes[min(count-1,idx+1)]
    dx=after.x-before.x
    dy=after.y-before.y
    length=math.hypot(dx,dy)
    if length<1e-10:
        return None,None
    tangent=(dx/length,dy/length)
    d_before=math.hypot(v.x-before.x,v.y-before.y)
    d_after=math.hypot(v.x-after.x,v.y-after.y)
    incoming=(-tangent[0]*d_before/3,-tangent[1]*d_before/3) if (closed or idx>0) else None
    outgoing=(tangent[0]*d_after/3,tangent[1]*d_after/3) if (closed or idx<count-1) else None
    return incoming,outgoing

def update_auto_handles(nodes,closed):
    for i,v in enumerate(nodes):
        if getattr(v,'point_type','CORNER')=='AUTO':
            v.incoming,v.outgoing=compute_auto_handles(nodes,i,closed)

def align_smooth_handles(v):
    if v.outgoing is not None and v.incoming is not None:
        l_out=math.hypot(*v.outgoing)
        l_in=math.hypot(*v.incoming)
        if l_out>1e-10:
            u=(v.outgoing[0]/l_out,v.outgoing[1]/l_out)
            v.incoming=(-u[0]*l_in,-u[1]*l_in)
        elif l_in>1e-10:
            u=(-v.incoming[0]/l_in,-v.incoming[1]/l_in)
            v.outgoing=(u[0]*l_out,u[1]*l_out)
    elif v.outgoing is not None:
        v.incoming=(-v.outgoing[0],-v.outgoing[1])
    elif v.incoming is not None:
        v.outgoing=(-v.incoming[0],-v.incoming[1])

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
    mesh_density: str = 'AUTO'
    fabric_override: bool = False
    placement_mode: str = 'LAYOUT'
    arrangement: dict = None
    panel_origin: dict = None

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
    update_auto_handles(vertices,closed)
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
    shrink: int = 0

    def side(self,index): return list((self.chain_a or (self.a,)) if index==0 else (self.chain_b or (self.b,)))

@dataclass
class Anchor:
    pattern: str
    x: float
    y: float
    kind: str = 'PIN'
    target: tuple = None
    id: str = field(default_factory=uid)
    binding: dict = None


def vertex_data(v):
    return dict(x=float(v.x),y=float(v.y),id=v.id,incoming=v.incoming,outgoing=v.outgoing,point_type=getattr(v,'point_type','CORNER'))


def read_vertex(v):
    handles=[]
    for key in ('incoming','outgoing'):
        value=v.get(key)
        if value is not None:
            if len(value)!=2 or any(not math.isfinite(float(n)) for n in value): raise ValueError('Invalid Bezier handle.')
            value=tuple(float(n) for n in value)
        handles.append(value)
    ptype=v.get('point_type')
    if ptype is None:
        ptype='SMOOTH' if (handles[0] is not None or handles[1] is not None) else 'CORNER'
    elif ptype not in ('CORNER','SMOOTH','AUTO'):
        raise ValueError('Unknown point type.')
    return Vertex(float(v['x']),float(v['y']),v['id'],handles[0],handles[1],point_type=ptype)


def arrangement_record(volume,point,flat=False):
    return dict(version=1,volume=volume,point=point,flat=flat,translation=[0.0]*3,rotation=[0.0]*3)


def validate_arrangement(record):
    if not isinstance(record,dict) or set(record)!={'version','volume','point','flat','translation','rotation'}:
        raise ValueError('Invalid arrangement record.')
    if type(record['version']) is not int or record['version']!=1 or type(record['flat']) is not bool:
        raise ValueError('Unsupported arrangement record.')
    for key in ('volume','point'):
        if not isinstance(record[key],str) or not record[key].strip():raise ValueError('Arrangement IDs must be nonempty.')
    for key in ('translation','rotation'):
        if not isinstance(record[key],(list,tuple)) or len(record[key])!=3 or any(
                type(value) not in (int,float) or not math.isfinite(value) for value in record[key]):
            raise ValueError('Arrangement deltas must contain three finite numbers.')


class Document:
    def __init__(self,patterns=None,seams=None,anchors=None,uv_layout=None,preset='COTTON',linked_pairs=None):
        self.patterns=patterns or []
        self.seams=seams or []
        self.anchors=anchors or []
        self.uv_layout=uv_layout
        self.preset=preset
        self.linked_pairs=linked_pairs or []

    def dumps(self):
        return json.dumps(dict(version=4,preset=getattr(self,'preset','COTTON'),patterns=[dict(id=p.id,name=p.name,\
            vertices=[vertex_data(v) for v in p.vertices],paths=[dict(id=q.id,name=q.name,closed=q.closed,role=q.role,\
            vertices=[vertex_data(v) for v in q.vertices]) for q in p.paths],preset=p.preset,wrap_radius=p.wrap_radius,\
            features=p.features,mesh_density=p.mesh_density,fabric_override=getattr(p,'fabric_override',False),placement_mode=p.placement_mode,arrangement=p.arrangement,panel_origin=p.panel_origin) for p in self.patterns],seams=[dict(id=s.id,a=vars(s.a),b=vars(s.b),reverse=s.reverse,\
            chain_a=[vars(e) for e in s.side(0)],chain_b=[vars(e) for e in s.side(1)],**({"shrink":s.shrink} if s.shrink else {})) for s in self.seams],\
            anchors=[vars(a) for a in self.anchors],uv_layout=self.uv_layout,**({'linked_pairs':self.linked_pairs} if self.linked_pairs else {})),separators=(',',':'),allow_nan=False)

    @classmethod
    def loads(cls,value):
        if not value: return cls()
        try:
            data=json.loads(value)
            if data['version'] not in (1,2,3,4): raise ValueError('Unsupported pattern document version.')
            doc_preset=data.get('preset','COTTON')
            patterns=[]
            for item in data['patterns']:
                p=Pattern(item['name'],[read_vertex(v) for v in item['vertices']],item['id'])
                p.paths=[Path(q['name'],[read_vertex(v) for v in q['vertices']],q['closed'],q['role'],q['id']) for q in item.get('paths',[])]
                p.preset=item.get('preset','COTTON'); p.wrap_radius=float(item.get('wrap_radius',0)); p.features=item.get('features',[])
                p.mesh_density=item.get('mesh_density','AUTO')
                p.placement_mode=item.get('placement_mode','LAYOUT') if data['version']>=4 else 'LEGACY'
                p.arrangement=item.get('arrangement') if data['version']>=4 else None
                p.panel_origin=item.get('panel_origin') if data['version']>=4 else None
                if 'fabric_override' in item:
                    p.fabric_override=bool(item['fabric_override'])
                else:
                    p.fabric_override=bool(item.get('preset') is not None and item.get('preset')!=doc_preset)
                patterns.append(p)
            document=cls(patterns,uv_layout=data.get('uv_layout'),preset=doc_preset)
            document.linked_pairs=data.get('linked_pairs',[])
            if data['version']>=2:
                for item in data['seams']:
                    document.seams.append(Seam(EdgeRef(**item['a']),EdgeRef(**item['b']),item['reverse'],item['id'],
                        tuple(EdgeRef(**e) for e in item.get('chain_a',[])),tuple(EdgeRef(**e) for e in item.get('chain_b',[])),item.get('shrink',0)))
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
        from .linked_editing import validate_pairs
        validate_pairs(self)
        ids=set()
        def identity(value):
            if not isinstance(value,str) or not value or value in ids: raise ValueError('Pattern, path, point, and feature IDs must be unique.')
            ids.add(value)
        for p in self.patterns:
            identity(p.id)
            if not isinstance(p.name,str) or not p.name.strip(): raise ValueError('Pattern names must contain text.')
            if p.preset not in {'COTTON','LINEN','SILK','DENIM','KNIT','LEATHER'}: raise ValueError('Unknown cloth preset.')
            if p.mesh_density not in ('AUTO','COARSE','STANDARD','FINE'): raise ValueError('Unknown mesh density.')
            if p.placement_mode not in ('LAYOUT','LEGACY'):raise ValueError('Unknown panel placement mode.')
            if p.arrangement is not None:validate_arrangement(p.arrangement)
            if p.panel_origin is not None:
                origin=p.panel_origin
                if not isinstance(origin,dict) or set(origin)!={'source','bounds'} or not isinstance(origin['source'],str) or not origin['source']:
                    raise ValueError('Invalid cut panel origin.')
                if not isinstance(origin['bounds'],(list,tuple)) or len(origin['bounds'])!=4 or any(type(value) not in (int,float) or not math.isfinite(value) for value in origin['bounds']):
                    raise ValueError('Cut panel bounds must contain four finite numbers.')
                if origin['bounds'][0]>=origin['bounds'][2] or origin['bounds'][1]>=origin['bounds'][3]:raise ValueError('Cut panel bounds must have positive size.')
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
        for seam in self.seams:
            identity(seam.id)
            if type(seam.shrink) is not int or seam.shrink not in (0,10,20,30):
                raise ValueError("Seam Shrink must be 0, 10, 20 or 30 percent.")
        for anchor in self.anchors:
            identity(anchor.id)
            p=self.find(anchor.pattern)
            if p is None or not p.contains((anchor.x,anchor.y)): raise ValueError('Pins and tacks must lie on fabric.')
            if anchor.kind not in {'PIN','TACK'}: raise ValueError('Unknown anchor type.')
            if anchor.target is not None and (len(anchor.target)!=3 or any(not math.isfinite(v) for v in anchor.target)):
                raise ValueError('Invalid tack target.')
            if anchor.binding is not None:
                from .tack_binding import validate_binding
                validate_binding(anchor.binding)
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
            v.point_type='CORNER'
        else:
            a.outgoing=curves.sub(left[1],left[0]); b.incoming=curves.sub(right[2],right[3])
            v.point_type='SMOOTH'
        nodes.insert(nodes.index(a)+1,v)
        update_auto_handles(nodes,edge.path=='OUTER' or p.path(edge.path).closed)
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
        from .linked_editing import split_partner
        split_partner(self,edge,fraction,v)
        return v


from .construction import ConstructionMixin

def pattern_touches_box(pattern,x0,y0,x1,y1):
    center=((x0+x1)/2,(y0+y1)/2)
    if pattern.contains(center):return True
    corners=[(x0,y0),(x1,y0),(x1,y1),(x0,y1)]
    if any(pattern.contains(c) for c in corners):return True
    outline=pattern.outline()
    poly_edges=list(zip(outline,outline[1:]+outline[:1]))
    box_edges=list(zip(corners,corners[1:]+corners[:1]))
    for a,b in poly_edges:
        for c,d in box_edges:
            if intersects(a,b,c,d):return True
    return False

class Session(ConstructionMixin):
    def __init__(self,document=None):
        self.document=document or Document()
        self._selected=self._corner=None
        self.path='OUTER'
        self.segment=None
        self.point_selection=[]
        self.selected_patterns=set()
        self.selected_points=set()
        self._undo_selections=[]
        self._redo_selections=[]
        self.undo_stack,self.redo_stack=[],[]
        self.last_repairs=0

    @property
    def selected(self):
        return self._selected

    @selected.setter
    def selected(self,value):
        self._selected=value
        if value is None:
            self.selected_patterns.clear()
        elif value:
            if not self.selected_patterns or (len(self.selected_patterns)==1 and not self.selected_points):
                self.selected_patterns={value}

    @property
    def corner(self):
        return self._corner

    @corner.setter
    def corner(self,value):
        self._corner=value
        if value is None:
            if len(self.selected_points)<=1:self.selected_points.clear()
        else:
            if self._selected and len(self.selected_points)<=1:
                self.selected_points={(self._selected,self.path,value)}

    def get_selection_state(self):
        return dict(patterns=set(self.selected_patterns),points=set(self.selected_points),
                    selected=self._selected,corner=self._corner,path=self.path,
                    segment=self.segment,point_selection=list(self.point_selection))

    def set_selection_state(self,state):
        if not isinstance(state,dict):return
        self.selected_patterns={pid for pid in state.get('patterns',()) if self.document.find(pid)}
        self.selected_points=set()
        for pid,path_id,idx in state.get('points',()):
            p=self.document.find(pid)
            if p:
                try:
                    if idx<len(p.path(path_id).vertices):
                        self.selected_points.add((pid,path_id,idx))
                except (ValueError,KeyError,IndexError):pass
        self._selected=state.get('selected')
        if self._selected and not self.document.find(self._selected):
            self._selected=next(iter(self.selected_patterns),None) if self.selected_patterns else None
        self._corner=state.get('corner')
        self.path=state.get('path','OUTER')
        self.segment=state.get('segment')
        self.point_selection=list(state.get('point_selection',[]))
        self.sync_from_multi()

    def sync_from_multi(self):
        if self.selected_patterns and not self.selected_points:
            if self._selected not in self.selected_patterns:
                self._selected=next(iter(self.selected_patterns),None)
            self._corner=None;self.point_selection=[]
        elif self.selected_points:
            first=next(iter(self.selected_points))
            self._selected,self.path=first[0],first[1]
            self.point_selection=[idx for (pid,path,idx) in self.selected_points if pid==self._selected and path==self.path]
            self._corner=first[2] if len(self.selected_points)==1 else None

    def clear_selection(self):
        self.selected_patterns.clear()
        self.selected_points.clear()
        self._selected=self._corner=self.segment=None
        self.path='OUTER';self.point_selection=[]

    def select_all(self):
        self.clear_selection()
        for p in self.document.patterns:self.selected_patterns.add(p.id)
        if self.document.patterns:self._selected=self.document.patterns[0].id

    def select_piece(self,pattern_id,toggle=False):
        if not toggle:
            self.selected_patterns={pattern_id}
            self.selected_points.clear()
            self._selected=pattern_id;self.path='OUTER'
            self._corner=None;self.point_selection=[]
            if self.segment and self.segment.pattern!=pattern_id:self.segment=None
        else:
            if pattern_id in self.selected_patterns:
                self.selected_patterns.remove(pattern_id)
                if self._selected==pattern_id:
                    self._selected=next(iter(self.selected_patterns),None) if self.selected_patterns else None
            else:
                self.selected_patterns.add(pattern_id)
                self._selected=pattern_id
        self.sync_from_multi()

    def select_point(self,pattern_id,path_id,point_index,toggle=False):
        key=(pattern_id,path_id,point_index)
        if not toggle:
            self.clear_selection()
            self.selected_points.add(key)
        else:
            if key in self.selected_points:self.selected_points.remove(key)
            else:self.selected_points.add(key)
        self.sync_from_multi()

    def is_multi_selected(self):
        return len(self.selected_patterns)+len(self.selected_points)>1

    def has_selection(self):
        return bool(self.selected_patterns or self.selected_points or self._selected)

    def selection_counts(self):
        n_p=len(self.selected_patterns) if self.selected_patterns else (1 if self._selected and not self.selected_points and self._corner is None else 0)
        n_pt=len(self.selected_points) if self.selected_points else (1 if self._corner is not None else 0)
        return n_p,n_pt

    def can_merge_selected_points(self):
        if len(self.selected_points)!=2:return False
        pts=list(self.selected_points)
        if pts[0][0]!=pts[1][0] or pts[0][1]!=pts[1][1]:return False
        p=self.document.find(pts[0][0])
        if not p:return False
        nodes=p.path(pts[0][1]).vertices
        a,b=sorted([pts[0][2],pts[1][2]])
        return b==a+1 or (a==0 and b==len(nodes)-1)

    def box_select(self,x0,y0,x1,y1,shift=False):
        min_x,max_x=min(x0,x1),max(x0,x1)
        min_y,max_y=min(y0,y1),max(y0,y1)
        pts_found=[]
        for p in self.document.patterns:
            for path,nodes,_,_ in p.loops():
                for idx,v in enumerate(nodes):
                    if min_x<=v.x<=max_x and min_y<=v.y<=max_y:
                        pts_found.append((p.id,path,idx))
        if pts_found:
            if not shift:self.clear_selection()
            for pt in pts_found:self.selected_points.add(pt)
            self.sync_from_multi()
            return 'POINTS',len(self.selected_points)
        touched=[]
        for p in self.document.patterns:
            if pattern_touches_box(p,min_x,min_y,max_x,max_y):
                touched.append(p.id)
        if touched:
            if not shift:self.clear_selection()
            for pid in touched:self.selected_patterns.add(pid)
            self.sync_from_multi()
            return 'PIECES',len(self.selected_patterns)
        if not shift:self.clear_selection()
        return 'NONE',0


    def commit(self,operation):
        from .linked_editing import synchronize
        before=self.document.dumps()
        before_sel=self.get_selection_state()
        old_seams={s.id for s in self.document.seams}
        self.last_repairs=0
        try:
            operation()
            synchronize(self.document,Document.loads(before),self.selected)
            self.document.prune_seams()
            self.document.validate()
            self.last_repairs=len(old_seams-{s.id for s in self.document.seams})
        except Exception:
            self.document=Document.loads(before)
            raise
        if self.document.dumps()!=before:
            self.undo_stack.append(before);self.undo_stack=self.undo_stack[-100:]
            self._undo_selections.append(before_sel);self._undo_selections=self._undo_selections[-100:]
            self.redo_stack.clear();self._redo_selections.clear();return True
        return False

    def set_mesh_density(self,name):
        if name not in ('AUTO','COARSE','STANDARD','FINE'):raise ValueError('Unknown mesh density.')
        if self._selected is None and not self.selected_patterns:raise ValueError('Select a pattern to change mesh density.')
        pats=[self.document.find(pid) for pid in self.selected_patterns if self.document.find(pid)]
        if not pats and self._selected:
            p=self.document.find(self._selected)
            if p:pats=[p]
        if not pats:raise ValueError('Select a pattern to change mesh density.')
        def op():
            for p in pats:p.mesh_density=name
        return self.commit(op)

    def set_document_preset(self,name):
        if name not in {'COTTON','LINEN','SILK','DENIM','KNIT','LEATHER'}: raise ValueError('Unknown cloth preset.')
        def op():
            self.document.preset=name
            for p in self.document.patterns:
                if not getattr(p,'fabric_override',False): p.preset=name
        return self.commit(op)

    def set_fabric_override(self,name):
        if self._selected is None and not self.selected_patterns:raise ValueError('Select a pattern to set fabric.')
        pats=[self.document.find(pid) for pid in self.selected_patterns if self.document.find(pid)]
        if not pats and self._selected:
            p=self.document.find(self._selected)
            if p:pats=[p]
        if not pats:raise ValueError('Select a pattern to set fabric.')
        if name in ('AUTO',None):
            def op():
                for p in pats:p.fabric_override=False;p.preset=getattr(self.document,'preset','COTTON')
            return self.commit(op)
        if name not in {'COTTON','LINEN','SILK','DENIM','KNIT','LEATHER'}: raise ValueError('Unknown cloth preset.')
        def op():
            for p in pats:p.fabric_override=True;p.preset=name
        return self.commit(op)

    def add(self,points):
        raw_pts=[(v.x,v.y) if isinstance(v,Vertex) else v for v in points]
        validate_polygon(raw_pts)
        names={p.name for p in self.document.patterns}; index=1
        while f'Pattern {index:02d}' in names: index+=1
        nodes=[v if isinstance(v,Vertex) else Vertex(*v) for v in points]
        update_auto_handles(nodes,True)
        p=Pattern(f'Pattern {index:02d}',nodes,preset=getattr(self.document,'preset','COTTON'))
        self.commit(lambda:self.document.patterns.append(p))
        self.clear_selection();self.selected_patterns.add(p.id)
        self._selected,self._corner,self.path=p.id,None,'OUTER'

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
        p=Pattern('Ellipse',nodes,preset=getattr(self.document,'preset','COTTON'))
        self.commit(lambda:self.document.patterns.append(p))
        self.clear_selection();self.selected_patterns.add(p.id)
        self._selected,self._corner,self.path=p.id,None,'OUTER'

    def add_path(self,points,closed=False):
        p=self.document.find(self._selected)
        if p is None: raise ValueError('Select a pattern for the internal shape.')
        nodes=[v if isinstance(v,Vertex) else Vertex(*v) for v in points]
        update_auto_handles(nodes,closed)
        path=Path('Internal '+str(len(p.paths)+1),nodes,closed)
        self.commit(lambda:p.paths.append(path)); self.path,self.corner=path.id,None
        return path

    def move(self,points):
        p=self.document.find(self._selected)
        if p is None: raise ValueError('Select a pattern to edit.')
        nodes=p.path(self.path).vertices
        if len(points)!=len(nodes): raise ValueError('The point count changed.')
        old=[(v.x,v.y) for v in nodes]
        def apply():
            for v,point in zip(nodes,points): v.x,v.y=point
            update_auto_handles(nodes,self.path=='OUTER' or p.path(self.path).closed)
            if self.path=='OUTER' and all(math.dist(curves.sub(q,pnt),curves.sub(points[0],old[0]))<1e-8 for pnt,q in zip(old,points)):
                dx,dy=curves.sub(points[0],old[0])
                for path in p.paths:
                    for v in path.vertices: v.x+=dx; v.y+=dy
                for anchor in self.document.anchors:
                    if anchor.pattern==p.id: anchor.x+=dx; anchor.y+=dy
        return self.commit(apply)

    def move_selection(self,dx,dy):
        if abs(dx)<1e-9 and abs(dy)<1e-9:return False
        pieces=set(self.selected_patterns)
        if not pieces and not self.selected_points and self._selected:
            if self._corner is None:pieces.add(self._selected)
        points=set(self.selected_points)
        if not pieces and not points and self._selected and self._corner is not None:
            points.add((self._selected,self.path,self._corner))
        if not pieces and not points:return False
        def apply():
            for pid in pieces:
                p=self.document.find(pid)
                if not p:continue
                for _,nodes,closed,_ in p.loops():
                    for v in nodes:v.x+=dx;v.y+=dy
                    update_auto_handles(nodes,closed)
                for anchor in self.document.anchors:
                    if anchor.pattern==p.id:anchor.x+=dx;anchor.y+=dy
            affected_paths=set()
            for pid,path_id,idx in points:
                if pid in pieces:continue
                p=self.document.find(pid)
                if not p:continue
                nodes=p.path(path_id).vertices
                if 0<=idx<len(nodes):
                    v=nodes[idx];v.x+=dx;v.y+=dy
                    affected_paths.add((pid,path_id))
            for pid,path_id in affected_paths:
                p=self.document.find(pid)
                if p:
                    update_auto_handles(p.path(path_id).vertices,path_id=='OUTER' or p.path(path_id).closed)
        return self.commit(apply)

    def flip_horizontal(self):
        pats=[self.document.find(pid) for pid in self.selected_patterns if self.document.find(pid)]
        if not pats and not self.selected_points and self._selected and self._corner is None:
            p=self.document.find(self._selected)
            if p:pats=[p]
        if pats:
            xs=[v.x for p in pats for _,nodes,_,_ in p.loops() for v in nodes]
            cx=(min(xs)+max(xs))/2
            pat_ids={p.id for p in pats}
            def op():
                for p in pats:
                    for _,nodes,_,_ in p.loops():
                        for v in nodes:
                            v.x=2*cx-v.x
                            if v.incoming is not None:v.incoming=(-v.incoming[0],v.incoming[1])
                            if v.outgoing is not None:v.outgoing=(-v.outgoing[0],v.outgoing[1])
                    for anchor in self.document.anchors:
                        if anchor.pattern==p.id:anchor.x=2*cx-anchor.x
                for seam in self.document.seams:
                    side_a={e.pattern for e in seam.side(0)}
                    side_b={e.pattern for e in seam.side(1)}
                    if side_a.issubset(pat_ids)!=side_b.issubset(pat_ids):
                        seam.reverse=not seam.reverse
            return self.commit(op)
        pts=set(self.selected_points)
        if not pts and self._selected and self._corner is not None:
            pts.add((self._selected,self.path,self._corner))
        if not pts:return False
        nodes_to_flip=[]
        for pid,path_id,idx in pts:
            p=self.document.find(pid)
            if p:
                nds=p.path(path_id).vertices
                if 0<=idx<len(nds):nodes_to_flip.append(nds[idx])
        if not nodes_to_flip:return False
        cx=(min(v.x for v in nodes_to_flip)+max(v.x for v in nodes_to_flip))/2
        def op_pts():
            for v in nodes_to_flip:
                v.x=2*cx-v.x
                if v.incoming is not None:v.incoming=(-v.incoming[0],v.incoming[1])
                if v.outgoing is not None:v.outgoing=(-v.outgoing[0],v.outgoing[1])
        return self.commit(op_pts)

    def flip_vertical(self):
        pats=[self.document.find(pid) for pid in self.selected_patterns if self.document.find(pid)]
        if not pats and not self.selected_points and self._selected and self._corner is None:
            p=self.document.find(self._selected)
            if p:pats=[p]
        if pats:
            ys=[v.y for p in pats for _,nodes,_,_ in p.loops() for v in nodes]
            cy=(min(ys)+max(ys))/2
            pat_ids={p.id for p in pats}
            def op():
                for p in pats:
                    for _,nodes,_,_ in p.loops():
                        for v in nodes:
                            v.y=2*cy-v.y
                            if v.incoming is not None:v.incoming=(v.incoming[0],-v.incoming[1])
                            if v.outgoing is not None:v.outgoing=(v.outgoing[0],-v.outgoing[1])
                    for anchor in self.document.anchors:
                        if anchor.pattern==p.id:anchor.y=2*cy-anchor.y
                for seam in self.document.seams:
                    side_a={e.pattern for e in seam.side(0)}
                    side_b={e.pattern for e in seam.side(1)}
                    if side_a.issubset(pat_ids)!=side_b.issubset(pat_ids):
                        seam.reverse=not seam.reverse
            return self.commit(op)
        pts=set(self.selected_points)
        if not pts and self._selected and self._corner is not None:
            pts.add((self._selected,self.path,self._corner))
        if not pts:return False
        nodes_to_flip=[]
        for pid,path_id,idx in pts:
            p=self.document.find(pid)
            if p:
                nds=p.path(path_id).vertices
                if 0<=idx<len(nds):nodes_to_flip.append(nds[idx])
        if not nodes_to_flip:return False
        cy=(min(v.y for v in nodes_to_flip)+max(v.y for v in nodes_to_flip))/2
        def op_pts():
            for v in nodes_to_flip:
                v.y=2*cy-v.y
                if v.incoming is not None:v.incoming=(v.incoming[0],-v.incoming[1])
                if v.outgoing is not None:v.outgoing=(v.outgoing[0],-v.outgoing[1])
        return self.commit(op_pts)

    def rotate(self,angle_degrees):
        rad=math.radians(angle_degrees)
        c=math.cos(rad);s=math.sin(rad)
        if abs(angle_degrees-90)<1e-6 or abs(angle_degrees+270)<1e-6:c,s=0.0,1.0
        elif abs(angle_degrees+90)<1e-6 or abs(angle_degrees-270)<1e-6:c,s=0.0,-1.0
        elif abs(abs(angle_degrees)-180)<1e-6:c,s=-1.0,0.0
        elif abs(angle_degrees)<1e-6:return False
        pats=[self.document.find(pid) for pid in self.selected_patterns if self.document.find(pid)]
        if not pats and not self.selected_points and self._selected and self._corner is None:
            p=self.document.find(self._selected)
            if p:pats=[p]
        if pats:
            xs=[v.x for p in pats for _,nodes,_,_ in p.loops() for v in nodes]
            ys=[v.y for p in pats for _,nodes,_,_ in p.loops() for v in nodes]
            cx=(min(xs)+max(xs))/2;cy=(min(ys)+max(ys))/2
            def op():
                for p in pats:
                    for _,nodes,_,_ in p.loops():
                        for v in nodes:
                            dx,dy=v.x-cx,v.y-cy
                            v.x=cx+c*dx-s*dy
                            v.y=cy+s*dx+c*dy
                            if v.incoming is not None:v.incoming=(c*v.incoming[0]-s*v.incoming[1],s*v.incoming[0]+c*v.incoming[1])
                            if v.outgoing is not None:v.outgoing=(c*v.outgoing[0]-s*v.outgoing[1],s*v.outgoing[0]+c*v.outgoing[1])
                    for anchor in self.document.anchors:
                        if anchor.pattern==p.id:
                            dx,dy=anchor.x-cx,anchor.y-cy
                            anchor.x=cx+c*dx-s*dy
                            anchor.y=cy+s*dx+c*dy
            return self.commit(op)
        pts=set(self.selected_points)
        if not pts and self._selected and self._corner is not None:
            pts.add((self._selected,self.path,self._corner))
        if not pts:return False
        nodes_to_rot=[]
        for pid,path_id,idx in pts:
            p=self.document.find(pid)
            if p:
                nds=p.path(path_id).vertices
                if 0<=idx<len(nds):nodes_to_rot.append(nds[idx])
        if not nodes_to_rot:return False
        cx=(min(v.x for v in nodes_to_rot)+max(v.x for v in nodes_to_rot))/2
        cy=(min(v.y for v in nodes_to_rot)+max(v.y for v in nodes_to_rot))/2
        def op_pts():
            for v in nodes_to_rot:
                dx,dy=v.x-cx,v.y-cy
                v.x=cx+c*dx-s*dy
                v.y=cy+s*dx+c*dy
                if v.incoming is not None:v.incoming=(c*v.incoming[0]-s*v.incoming[1],s*v.incoming[0]+c*v.incoming[1])
                if v.outgoing is not None:v.outgoing=(c*v.outgoing[0]-s*v.outgoing[1],s*v.outgoing[0]+c*v.outgoing[1])
        return self.commit(op_pts)

    def rotate_90(self,clockwise=True):
        return self.rotate(-90 if clockwise else 90)

    def duplicate(self):
        patterns_to_dup=[self.document.find(pid) for pid in self.selected_patterns if self.document.find(pid)]
        if not patterns_to_dup:
            p=self.document.find(self._selected)
            if p:patterns_to_dup=[p]
        if not patterns_to_dup:return False
        clones=[];pattern_map={};id_map={}
        for p in patterns_to_dup:
            new=clone_pattern(p,offset=(.03,-.03));new.name+=' copy'
            clones.append((p,new));pattern_map[p.id]=new.id
            id_map.update(getattr(new,'_id_map',{}))
        def remap(edge):
            target_pid=pattern_map.get(edge.pattern,edge.pattern)
            candidate=EdgeRef(target_pid,id_map.get(edge.start,edge.start),id_map.get(edge.end,edge.end),edge.t0,edge.t1,id_map.get(edge.path,edge.path))
            try:self.document.edge_vertices(candidate);return candidate
            except ValueError:
                opposite=EdgeRef(candidate.pattern,candidate.end,candidate.start,1-candidate.t0,1-candidate.t1,candidate.path)
                self.document.edge_vertices(opposite);return opposite
        def apply():
            for orig,new in clones:
                self.document.patterns.append(new)
                clone_relationships(self.document,orig,new)
            from .linked_editing import duplicate_pairs
            duplicate_pairs(self.document,pattern_map,id_map)
            dup_ids={orig.id for orig,_ in clones}
            if len(dup_ids)>1:
                for seam in list(self.document.seams):
                    sides_patterns={e.pattern for side in (seam.side(0),seam.side(1)) for e in side}
                    if len(sides_patterns)>1 and sides_patterns.issubset(dup_ids):
                        try:
                            a=[remap(e) for e in seam.side(0)];b=[remap(e) for e in seam.side(1)]
                            new_seam=Seam(a[0],b[0],seam.reverse,chain_a=tuple(a),chain_b=tuple(b),shrink=seam.shrink)
                            self.document.seams.append(new_seam)
                        except (ValueError,KeyError):continue
        result=self.commit(apply)
        if result:
            self.clear_selection()
            for _,new in clones:self.selected_patterns.add(new.id)
            self._selected=clones[0][1].id;self.path='OUTER';self._corner=None;self.point_selection=[]
        return result

    def delete(self):
        pts=list(self.selected_points)
        if not pts and self._selected and self._corner is not None:
            pts=[(self._selected,self.path,self._corner)]
        if pts:
            def apply_points():
                pts_by_path={}
                for pid,path_id,idx in pts:
                    pts_by_path.setdefault((pid,path_id),[]).append(idx)
                for (pid,path_id),indices in pts_by_path.items():
                    p=self.document.find(pid)
                    if p:
                        nodes=p.path(path_id).vertices
                        for idx in sorted(indices,reverse=True):
                            if 0<=idx<len(nodes):nodes.pop(idx)
            result=self.commit(apply_points)
            if result:
                self.selected_points.clear()
                self._corner=None
                self.point_selection=[]
            return result
        pat_ids=set(self.selected_patterns)
        if not pat_ids and self._selected:pat_ids={self._selected}
        if self.path!='OUTER' and len(pat_ids)==1:
            p=self.document.find(next(iter(pat_ids)))
            if p:
                path=p.path(self.path);result=self.commit(lambda:p.paths.remove(path));self.path='OUTER';return result
        if not pat_ids:return False
        def apply_pieces():
            for pid in pat_ids:
                p=self.document.find(pid)
                if p and p in self.document.patterns:self.document.patterns.remove(p)
        result=self.commit(apply_pieces)
        if result:self.clear_selection()
        return result

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

    def set_seam_shrink(self,identity,shrink):
        if type(shrink) is not int or shrink not in (0,10,20,30):
            raise ValueError("Seam Shrink must be 0, 10, 20 or 30 percent.")
        seam=next((seam for seam in self.document.seams if seam.id==identity),None)
        if seam is None:raise ValueError("That seam no longer exists.")
        return self.commit(lambda:setattr(seam,'shrink',shrink))

    def split_segment(self,edge,fraction=.5):
        if not .0001<fraction<.9999:raise ValueError('Split inside the segment, away from its endpoints.')
        return self.commit(lambda:self.document.split_edge(edge,fraction))

    def set_point_type(self,point_type,points=None):
        if point_type not in ('CORNER','SMOOTH','AUTO'):raise ValueError('Unknown point type.')
        if points is None:
            pts=list(self.selected_points)
            if not pts and self._selected and self._corner is not None:
                pts=[(self._selected,self.path,self._corner)]
        else:
            pts=list(points)
        if not pts:raise ValueError('Select a pattern point.')
        def apply():
            for pid,path_id,idx in pts:
                p=self.document.find(pid)
                if not p:continue
                nodes=p.path(path_id).vertices
                if not (0<=idx<len(nodes)):continue
                v=nodes[idx]
                closed=path_id=='OUTER' or p.path(path_id).closed
                v.point_type=point_type
                if point_type=='CORNER':
                    v.incoming=v.outgoing=None
                elif point_type=='SMOOTH':
                    if v.incoming is None and v.outgoing is None:
                        v.incoming,v.outgoing=compute_auto_handles(nodes,idx,closed)
                    else:
                        align_smooth_handles(v)
                elif point_type=='AUTO':
                    v.incoming,v.outgoing=compute_auto_handles(nodes,idx,closed)
            for pid,path_id,_ in pts:
                p=self.document.find(pid)
                if p:
                    update_auto_handles(p.path(path_id).vertices,path_id=='OUTER' or p.path(path_id).closed)
        return self.commit(apply)

    def cycle_point_type(self,index=None):
        pts=list(self.selected_points)
        if not pts and self._selected and (index is not None or self._corner is not None):
            pts=[(self._selected,self.path,self._corner if index is None else index)]
        if not pts:raise ValueError('Select a pattern point.')
        first_p=self.document.find(pts[0][0])
        if not first_p:raise ValueError('Select a pattern point.')
        first_nodes=first_p.path(pts[0][1]).vertices
        first_v=first_nodes[pts[0][2]]
        order=['CORNER','SMOOTH','AUTO']
        current=getattr(first_v,'point_type','CORNER')
        target=order[(order.index(current)+1)%len(order)]
        self.set_point_type(target,pts)
        return target

    def curve_point(self,index=None):
        return self.cycle_point_type(index=index)

    def set_handle(self,index,which,value,other_which=None,other_value=None,pattern_id=None,path_id=None):
        pid=pattern_id or self._selected
        path=path_id or self.path
        p=self.document.find(pid)
        if not p:raise ValueError('The pattern no longer exists.')
        v=p.path(path).vertices[index]
        def apply():
            setattr(v,which,tuple(value) if value is not None else None)
            if other_which and other_value is not None:
                setattr(v,other_which,tuple(other_value))
            elif other_which and other_value is None:
                setattr(v,other_which,None)
        return self.commit(apply)

    def set_length(self,edge,target):
        if not math.isfinite(target) or target<.0001:raise ValueError('Length must be at least 0.01 cm.')
        a,b=self.document.edge_vertices(edge);ratio=target/self.document.edge_length(edge)
        def apply():
            b.x,b.y=curves.add((a.x,a.y),curves.mul((b.x-a.x,b.y-a.y),ratio))
            if a.outgoing is not None:a.outgoing=curves.mul(a.outgoing,ratio)
            if b.incoming is not None:b.incoming=curves.mul(b.incoming,ratio)
        return self.commit(apply)

    def merge_points(self,indices=None):
        if (indices is None or len(indices)!=2) and len(self.selected_points)==2:
            pts=list(self.selected_points)
            if pts[0][0]==pts[1][0] and pts[0][1]==pts[1][1]:
                self._selected=pts[0][0];self.path=pts[0][1]
                indices=[pts[0][2],pts[1][2]]
        p=self.document.find(self._selected)
        if p is None:raise ValueError('Select a pattern point.')
        nodes=p.path(self.path).vertices
        if indices is None or len(indices)!=2:raise ValueError('Shift-click two adjacent points to merge.')
        a,b=sorted(indices)
        if b!=a+1 and (a,b)!=(0,len(nodes)-1):raise ValueError('Merge adjacent points.')
        def apply():
            nodes[a].x,nodes[a].y=curves.mix((nodes[a].x,nodes[a].y),(nodes[b].x,nodes[b].y),.5)
            nodes.pop(b)
        result=self.commit(apply);self.corner=a;self.point_selection=[];return result

    def offset(self,distance):
        p=self.document.find(self._selected)
        if p is None:raise ValueError('Select a pattern to offset.')
        if abs(distance)<1e-6:raise ValueError('Enter a nonzero outline offset.')
        new=Pattern(p.name+' offset',[Vertex(*q) for q in curves.offset_polygon(p.outline(),distance)],preset=p.preset,fabric_override=getattr(p,'fabric_override',False))
        for hole in p.paths:
            if hole.role=='HOLE':new.paths.append(Path(hole.name,[Vertex(*q) for q in curves.offset_polygon(hole.outline(),-distance)],True,'HOLE'))
        self.commit(lambda:self.document.patterns.append(new))
        self.clear_selection();self.selected_patterns.add(new.id)
        self.selected,self.path,self.corner=new.id,'OUTER',None

    def add_anchor(self,point,kind='PIN',target=None,binding=None):
        if not self._selected:raise ValueError('Select a pattern for the anchor.')
        anchor=Anchor(self._selected,*point,kind,target,binding=binding)
        self.commit(lambda:self.document.anchors.append(anchor));return anchor

    def history(self,redo=False):
        self.last_repairs=0
        source,target=(self.redo_stack,self.undo_stack) if redo else (self.undo_stack,self.redo_stack)
        sel_source,sel_target=(self._redo_selections,self._undo_selections) if redo else (self._undo_selections,self._redo_selections)
        if not source:return False
        target.append(self.document.dumps());sel_target.append(self.get_selection_state())
        self.document=Document.loads(source.pop())
        if sel_source:
            self.set_selection_state(sel_source.pop())
        else:
            self.corner=None;self.path='OUTER';self.segment=None;self.point_selection=[]
            if not self.document.find(self._selected):self._selected=None
            self.selected_patterns={self._selected} if self._selected else set()
            self.selected_points=set()
        return True


def clone_pattern(pattern,offset=(0,0),reflection=None):
    result=copy.deepcopy(pattern);result.id=uid();mapping={pattern.id:result.id}
    def convert(v,orig):
        old=v.id;v.id=uid();mapping[old]=v.id
        v.point_type=getattr(orig,'point_type','CORNER')
        p=(v.x,v.y)
        if reflection:
            p=curves.reflect(p,*reflection)
            if v.incoming is not None:v.incoming=curves.reflect(v.incoming,*reflection,vector=True)
            if v.outgoing is not None:v.outgoing=curves.reflect(v.outgoing,*reflection,vector=True)
        v.x,v.y=curves.add(p,offset)
    for v,orig in zip(result.vertices,pattern.vertices):convert(v,orig)
    for path,orig_path in zip(result.paths,pattern.paths):
        old=path.id;path.id=uid();mapping[old]=path.id
        for v,orig in zip(path.vertices,orig_path.vertices):convert(v,orig)
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
            new=Seam(a[0],b[0],seam.reverse,chain_a=tuple(a),chain_b=tuple(b),shrink=seam.shrink)
            document.seams.append(new);seam_map[seam.id]=new.id
    for feature in source.features:
        if feature.get('seam') and feature['seam'] not in seam_map:continue
        new=copy.deepcopy(feature);new['id']=uid()
        if new.get('seam'):new['seam']=seam_map[new['seam']]
        if new.get('apex'):new['apex']=mapping.get(new['apex'],new['apex'])
        target.features.append(new)
