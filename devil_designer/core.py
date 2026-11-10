from dataclasses import dataclass, field
import json
import math
import uuid

from .presets import valid_fabric

EPS = 1e-10
MAX_SPLIT_PARTS = 200

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
    frozen: bool = False
    deactivated: bool = False
    strengthened: bool = False

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
    ease_side: int = 0
    active: bool = True

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


ARRANGEMENT_KEYS={'version','volume','point','flat','translation','rotation'}
ARRANGEMENT_OPTIONS={'clearance','direction','overwrap'}


def arrangement_record(volume,point,flat=False,*,version=1,clearance=None,direction=1,overwrap=False):
    record=dict(version=version,volume=volume,point=point,flat=flat,translation=[0.0]*3,rotation=[0.0]*3)
    if version==3:record.update(clearance=clearance,direction=direction,overwrap=overwrap)
    return record


def validate_arrangement(record):
    if not isinstance(record,dict) or set(record)!=ARRANGEMENT_KEYS|(ARRANGEMENT_OPTIONS if record.get('version')==3 else set()):
        raise ValueError('Invalid arrangement record.')
    if type(record['version']) is not int or record['version'] not in (1,2,3) or type(record['flat']) is not bool:
        raise ValueError('Unsupported arrangement record.')
    if record['version']==3 and (record['direction'] not in (1,-1) or type(record['direction']) is not int or type(record['overwrap']) is not bool
                                 or record['clearance'] is not None and (type(record['clearance']) not in (int,float) or not math.isfinite(record['clearance']) or not 0<record['clearance']<=.3)):
        raise ValueError('Invalid arrangement options.')
    for key in ('volume','point'):
        if not isinstance(record[key],str) or not record[key].strip():raise ValueError('Arrangement IDs must be nonempty.')
    for key in ('translation','rotation'):
        if not isinstance(record[key],(list,tuple)) or len(record[key])!=3 or any(
                type(value) not in (int,float) or not math.isfinite(value) for value in record[key]):
            raise ValueError('Arrangement deltas must contain three finite numbers.')


class Document:
    def __init__(self,patterns=None,seams=None,anchors=None,uv_layout=None,preset='COTTON',linked_pairs=None,custom_presets=None):
        self.patterns=patterns or []
        self.seams=seams or []
        self.anchors=anchors or []
        self.uv_layout=uv_layout
        self.preset=preset
        self.linked_pairs=linked_pairs or []
        self.custom_presets=custom_presets or {}
        self.elastics=[]
        self.elastics_dropped=0
        self.joins=[]
        self.steam=[]

    def dumps(self):
        return json.dumps(dict(version=4,preset=getattr(self,'preset','COTTON'),patterns=[dict(id=p.id,name=p.name,\
            vertices=[vertex_data(v) for v in p.vertices],paths=[dict(id=q.id,name=q.name,closed=q.closed,role=q.role,\
            vertices=[vertex_data(v) for v in q.vertices]) for q in p.paths],preset=p.preset,wrap_radius=p.wrap_radius,\
            features=p.features,mesh_density=p.mesh_density,fabric_override=getattr(p,'fabric_override',False),placement_mode=p.placement_mode,arrangement=p.arrangement,panel_origin=p.panel_origin,**({'simulation':{key:getattr(p,key) for key in ('frozen','deactivated','strengthened') if getattr(p,key)}} if p.frozen or p.deactivated or p.strengthened else {})) for p in self.patterns],seams=[dict(id=s.id,a=vars(s.a),b=vars(s.b),reverse=s.reverse,\
            chain_a=[vars(e) for e in s.side(0)],chain_b=[vars(e) for e in s.side(1)],**({"shrink":s.shrink} if s.shrink else {}),**({"ease_side":s.ease_side} if s.ease_side else {}),**({"active":False} if not s.active else {})) for s in self.seams],\
            anchors=[vars(a) for a in self.anchors],uv_layout=self.uv_layout,**({'linked_pairs':self.linked_pairs} if self.linked_pairs else {}),**({'custom_presets':self.custom_presets} if getattr(self,'custom_presets',None) else {}),**({'elastics':self.elastics} if self.elastics else {}),**({'joins':self.joins} if self.joins else {}),**({'steam':self.steam} if self.steam else {})),separators=(',',':'),allow_nan=False)

    @classmethod
    def loads(cls,value):
        if not value: return cls()
        try:
            data=json.loads(value)
            if data['version'] not in (1,2,3,4): raise ValueError('Unsupported pattern document version.')
            doc_preset=data.get('preset','COTTON')
            custom_presets=data.get('custom_presets',{})
            if not isinstance(custom_presets,dict):raise ValueError('Invalid custom presets.')
            custom_presets={cp_name:{key:val for key,val in cp_vals.items() if key!='shear'} if isinstance(cp_vals,dict) else cp_vals for cp_name,cp_vals in custom_presets.items()}
            for cp_name,cp_vals in custom_presets.items():
                if not isinstance(cp_name,str) or not cp_name.strip() or not valid_fabric(cp_vals):
                    raise ValueError('Invalid custom fabric preset.')
            patterns=[]
            for item in data['patterns']:
                p=Pattern(item['name'],[read_vertex(v) for v in item['vertices']],item['id'])
                p.paths=[Path(q['name'],[read_vertex(v) for v in q['vertices']],q['closed'],q['role'],q['id']) for q in item.get('paths',[])]
                p.preset=item.get('preset','COTTON'); p.wrap_radius=float(item.get('wrap_radius',0)); p.features=item.get('features',[])
                p.mesh_density=item.get('mesh_density','AUTO')
                p.placement_mode=item.get('placement_mode','LAYOUT') if data['version']>=4 else 'LEGACY'
                p.arrangement=item.get('arrangement') if data['version']>=4 else None
                p.panel_origin=item.get('panel_origin') if data['version']>=4 else None
                state=item.get('simulation',{})
                if not isinstance(state,dict) or set(state)-{'frozen','deactivated','strengthened'} or any(type(flag) is not bool for flag in state.values()):raise ValueError('Invalid piece simulation state.')
                for key,flag in state.items():setattr(p,key,flag)
                if 'fabric_override' in item:
                    p.fabric_override=bool(item['fabric_override'])
                else:
                    p.fabric_override=bool(item.get('preset') is not None and item.get('preset')!=doc_preset)
                patterns.append(p)
            document=cls(patterns,uv_layout=data.get('uv_layout'),preset=doc_preset,custom_presets=custom_presets)
            document.linked_pairs=data.get('linked_pairs',[])
            if data['version']>=2:
                for item in data['seams']:
                    document.seams.append(Seam(EdgeRef(**item['a']),EdgeRef(**item['b']),item['reverse'],item['id'],
                        tuple(EdgeRef(**e) for e in item.get('chain_a',[])),tuple(EdgeRef(**e) for e in item.get('chain_b',[])),item.get('shrink',0),ease_side=item.get('ease_side',0),active=item.get('active',True) is not False))
            document.anchors=[Anchor(**a) for a in data.get('anchors',[])]
            document.elastics=data.get('elastics',[])
            document.joins=data.get('joins',[])
            document.steam=data.get('steam',[])
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
        valid_presets={'COTTON','LINEN','SILK','DENIM','KNIT','LEATHER'}|set(getattr(self,'custom_presets',{}) or {})
        if getattr(self,'preset','COTTON') not in valid_presets: raise ValueError('Unknown cloth preset.')
        for p in self.patterns:
            identity(p.id)
            if not isinstance(p.name,str) or not p.name.strip(): raise ValueError('Pattern names must contain text.')
            if p.preset not in valid_presets: raise ValueError('Unknown cloth preset.')
            if p.mesh_density not in ('AUTO','COARSE','STANDARD','FINE','ULTRA'): raise ValueError('Unknown mesh density.')
            if any(type(getattr(p,key)) is not bool for key in ('frozen','deactivated','strengthened')):raise ValueError('Invalid piece simulation state.')
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
            if seam.ease_side not in (0,1,2):raise ValueError('Invalid seam ease side.')
        for anchor in self.anchors:
            identity(anchor.id)
            p=self.find(anchor.pattern)
            if p is None or not p.contains((anchor.x,anchor.y)): raise ValueError('Pins and tacks must lie on fabric.')
            if anchor.kind not in {'PIN','TACK','JOIN'}: raise ValueError('Unknown anchor type.')
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
        present={a.id for a in self.anchors}
        self.joins=[pair for pair in self.joins if all(identity in present for identity in pair)]
        joined={identity for pair in self.joins for identity in pair}
        self.anchors=[a for a in self.anchors if a.kind!='JOIN' or a.id in joined]
        def elastic_valid(record):
            try:self.edge_vertices(EdgeRef(record['pattern'],record['start'],record['end'],path=record['path']));return True
            except ValueError:return False
        kept=[record for record in self.elastics if elastic_valid(record)]
        self.elastics_dropped+=len(self.elastics)-len(kept)
        self.elastics=kept
        self.steam=[record for record in self.steam if self.find(record['pattern'])]

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
        elastics=[]
        for record in self.elastics:
            reference=EdgeRef(record['pattern'],record['start'],record['end'],path=record['path'])
            if reference==edge.full():
                elastics.extend(dict(record,start=start,end=end) for start,end in ((a.id,v.id),(v.id,b.id)))
            else:elastics.append(record)
        self.elastics=elastics
        from .linked_editing import split_partner
        split_partner(self,edge,fraction,v)
        return v


from .construction import ConstructionMixin

def pattern_enclosed_by_box(pattern,x0,y0,x1,y1):
    min_x,max_x=min(x0,x1),max(x0,x1)
    min_y,max_y=min(y0,y1),max(y0,y1)
    outline=pattern.outline()
    if not outline:return False
    return all(min_x<=pt[0]<=max_x and min_y<=pt[1]<=max_y for pt in outline)

def pattern_touches_box(pattern,x0,y0,x1,y1):
    min_x,max_x=min(x0,x1),max(x0,x1)
    min_y,max_y=min(y0,y1),max(y0,y1)
    center=((x0+x1)/2,(y0+y1)/2)
    if pattern.contains(center):return True
    corners=[(min_x,min_y),(max_x,min_y),(max_x,max_y),(min_x,max_y)]
    if any(pattern.contains(c) for c in corners):return True
    outline=pattern.outline()
    if any(min_x<=pt[0]<=max_x and min_y<=pt[1]<=max_y for pt in outline):return True
    poly_edges=list(zip(outline,outline[1:]+outline[:1]))
    box_edges=list(zip(corners,corners[1:]+corners[:1]))
    for a,b in poly_edges:
        for c,d in box_edges:
            if intersects(a,b,c,d):return True
    return False

def point_in_lasso(pt,poly):
    x,y=pt
    inside=False
    n=len(poly)
    for i in range(n):
        x1,y1=poly[i]
        x2,y2=poly[(i+1)%n]
        if ((y1>y)!=(y2>y)) and (x<(x2-x1)*(y-y1)/(y2-y1+1e-12)+x1):
            inside=not inside
    return inside

def pattern_in_lasso(pattern,poly,rule='ENCLOSE'):
    outline=pattern.outline()
    if not outline:return False
    if rule=='ENCLOSE':
        return all(point_in_lasso(pt,poly) for pt in outline)
    if any(point_in_lasso(pt,poly) for pt in outline):
        return True
    if any(pattern.contains(pt) for pt in poly):
        return True
    poly_edges=list(zip(outline,outline[1:]+outline[:1]))
    lasso_edges=list(zip(poly,poly[1:]+poly[:1]))
    for a,b in poly_edges:
        for c,d in lasso_edges:
            if intersects(a,b,c,d):return True
    return False

def edge_in_box(doc,edge,x0,y0,x1,y1,rule='ENCLOSE'):
    try:samples=[pt for _,pt in curves.table(doc.edge_curve(edge))]
    except Exception:return False
    if not samples:return False
    min_x,max_x=min(x0,x1),max(x0,x1)
    min_y,max_y=min(y0,y1),max(y0,y1)
    in_box=[min_x<=pt[0]<=max_x and min_y<=pt[1]<=max_y for pt in samples]
    if rule=='ENCLOSE':return all(in_box)
    if any(in_box):return True
    corners=[(min_x,min_y),(max_x,min_y),(max_x,max_y),(min_x,max_y)]
    box_edges=list(zip(corners,corners[1:]+corners[:1]))
    edge_segs=list(zip(samples,samples[1:]))
    for a,b in edge_segs:
        for c,d in box_edges:
            if intersects(a,b,c,d):return True
    return False

def edge_in_lasso(doc,edge,poly,rule='ENCLOSE'):
    try:samples=[pt for _,pt in curves.table(doc.edge_curve(edge))]
    except Exception:return False
    if not samples:return False
    in_lasso=[point_in_lasso(pt,poly) for pt in samples]
    if rule=='ENCLOSE':return all(in_lasso)
    if any(in_lasso):return True
    lasso_edges=list(zip(poly,poly[1:]+poly[:1]))
    edge_segs=list(zip(samples,samples[1:]))
    for a,b in edge_segs:
        for c,d in lasso_edges:
            if intersects(a,b,c,d):return True
    return False

def canonicalize_auto_handles(doc):
    for p in doc.patterns:
        for _,nodes,closed,_ in p.loops():
            update_auto_handles(nodes,closed)

def selected_edge_curves(doc,nodes):
    result=[]
    for p in doc.patterns:
        for path_id,vlist,closed,_ in p.loops():
            if all((p.id,path_id,i) in nodes for i in range(len(vlist))):continue
            count=len(vlist) if closed else len(vlist)-1
            for i in range(count):
                j=(i+1)%len(vlist)
                key_a=(p.id,path_id,i);key_b=(p.id,path_id,j)
                if key_a in nodes and key_b in nodes and 'AUTO' in (getattr(vlist[i],'point_type','CORNER'),getattr(vlist[j],'point_type','CORNER')):
                    result.append((key_a,key_b,curves.controls(vlist[i],vlist[j])))
    return result

CURVE_TOLERANCE=1e-6

class Session(ConstructionMixin):
    def __init__(self,document=None):
        self.document=document or Document()
        self._selected=self._corner=None
        self.path='OUTER'
        self.segment=None
        self.point_selection=[]
        self.selected_patterns=set()
        self.selected_points=set()
        self.selected_edges=set()
        self.selected_paths=set()
        self.acquisition_target='PIECES'
        self.active_entity=None
        self.placed_pivot=None
        self._undo_selections=[]
        self._redo_selections=[]
        self._committed_selection=None
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
            if self.active_entity and self.active_entity[0]=='PIECE':
                self.active_entity=None
        elif value:
            if not self.selected_patterns or (len(self.selected_patterns)==1 and not self.selected_points):
                self.selected_patterns={value}
                self.active_entity=('PIECE',value)

    @property
    def corner(self):
        return self._corner

    @corner.setter
    def corner(self,value):
        self._corner=value
        if value is None:
            if len(self.selected_points)<=1:
                self.selected_points.clear()
                if self.active_entity and self.active_entity[0]=='POINT':
                    self.active_entity=None
        else:
            if self._selected and len(self.selected_points)<=1:
                self.selected_points={(self._selected,self.path,value)}
                self.active_entity=('POINT',(self._selected,self.path,value))

    def get_selection_state(self):
        return dict(patterns=set(self.selected_patterns),points=set(self.selected_points),
                    edges=set(self.selected_edges),paths=set(self.selected_paths),
                    target=self.acquisition_target,active=self.active_entity,
                    placed_pivot=self.placed_pivot,selected=self._selected,
                    corner=self._corner,path=self.path,segment=self.segment,
                    point_selection=list(self.point_selection))

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
        self.selected_edges=set()
        for edge in state.get('edges',()):
            p=self.document.find(edge.pattern)
            if p:
                try:
                    vlist=p.path(edge.path).vertices
                    vids={v.id for v in vlist}
                    if edge.start in vids and edge.end in vids:
                        self.selected_edges.add(edge)
                except (ValueError,KeyError):pass
        self.selected_paths=set()
        for pid,path_id in state.get('paths',()):
            p=self.document.find(pid)
            if p:
                try:
                    p.path(path_id)
                    self.selected_paths.add((pid,path_id))
                except (ValueError,KeyError):pass
        self.acquisition_target=state.get('target','PIECES')
        self.active_entity=state.get('active')
        self.placed_pivot=state.get('placed_pivot')
        self._selected=state.get('selected')
        if self._selected and not self.document.find(self._selected):
            self._selected=None
        self._corner=state.get('corner')
        self.path=state.get('path','OUTER')
        self.segment=state.get('segment')
        self.point_selection=list(state.get('point_selection',[]))
        self.sync_from_multi()

    def sync_from_multi(self):
        if not self.has_selection():
            self._selected=None;self._corner=None;self.path='OUTER'
            self.segment=None;self.point_selection=[];self.active_entity=None
            return
        if self.active_entity is not None:
            kind,val=self.active_entity
            if kind=='PIECE' and val not in self.selected_patterns:self.active_entity=None
            elif kind=='POINT' and val not in self.selected_points:self.active_entity=None
            elif kind=='EDGE' and val not in self.selected_edges:self.active_entity=None
            elif kind=='PATH' and val not in self.selected_paths:self.active_entity=None
        if self.active_entity is not None:
            kind,val=self.active_entity
            if kind=='PIECE':
                self._selected=val;self.path='OUTER';self._corner=None
                self.segment=None;self.point_selection=[]
            elif kind=='POINT':
                pid,path_id,idx=val
                self._selected=pid;self.path=path_id;self._corner=idx
                self.segment=None
                self.point_selection=[i for (p,pth,i) in self.selected_points if p==pid and pth==path_id]
            elif kind=='EDGE':
                self._selected=val.pattern;self.path=val.path;self.segment=val
                self._corner=None;self.point_selection=[]
            elif kind=='PATH':
                pid,path_id=val
                self._selected=pid;self.path=path_id;self._corner=None
                self.segment=None;self.point_selection=[]

    def clear_selection(self):
        self.selected_patterns.clear()
        self.selected_points.clear()
        self.selected_edges.clear()
        self.selected_paths.clear()
        self.active_entity=None
        self._selected=self._corner=self.segment=None
        self.path='OUTER';self.point_selection=[]
        self.placed_pivot=None

    def select_all(self):
        self.clear_selection()
        if self.acquisition_target=='PIECES':
            for p in self.document.patterns:self.selected_patterns.add(p.id)
            if self.document.patterns:self.active_entity=('PIECE',self.document.patterns[0].id)
        elif self.acquisition_target=='POINTS':
            for p in self.document.patterns:
                for path,nodes,_,_ in p.loops():
                    for idx in range(len(nodes)):self.selected_points.add((p.id,path,idx))
            if self.selected_points:self.active_entity=('POINT',next(iter(self.selected_points)))
        elif self.acquisition_target=='EDGES':
            for p in self.document.patterns:
                for path,_,_,_ in p.loops():
                    for edge in self.document.edges(p.id,path):self.selected_edges.add(edge)
            if self.selected_edges:self.active_entity=('EDGE',next(iter(self.selected_edges)))
        elif self.acquisition_target=='PATHS':
            for p in self.document.patterns:
                for path in p.paths:self.selected_paths.add((p.id,path.id))
            if self.selected_paths:self.active_entity=('PATH',next(iter(self.selected_paths)))
        self.sync_from_multi()

    def select_piece(self,pattern_id,toggle=False):
        if not toggle:
            self.clear_selection()
            self.selected_patterns.add(pattern_id)
            self.active_entity=('PIECE',pattern_id)
        else:
            if pattern_id in self.selected_patterns:
                self.selected_patterns.remove(pattern_id)
                if self.active_entity==('PIECE',pattern_id):self.active_entity=None
            else:
                self.selected_patterns.add(pattern_id)
                self.active_entity=('PIECE',pattern_id)
        self.sync_from_multi()

    def select_point(self,pattern_id,path_id,point_index,toggle=False):
        key=(pattern_id,path_id,point_index)
        if not toggle:
            self.clear_selection()
            self.selected_points.add(key)
            self.active_entity=('POINT',key)
        else:
            if key in self.selected_points:
                self.selected_points.remove(key)
                if self.active_entity==('POINT',key):self.active_entity=None
            else:
                self.selected_points.add(key)
                self.active_entity=('POINT',key)
        self.sync_from_multi()

    def select_edge(self,edge_ref,toggle=False):
        if not toggle:
            self.clear_selection()
            self.selected_edges.add(edge_ref)
            self.active_entity=('EDGE',edge_ref)
        else:
            if edge_ref in self.selected_edges:
                self.selected_edges.remove(edge_ref)
                if self.active_entity==('EDGE',edge_ref):self.active_entity=None
            else:
                self.selected_edges.add(edge_ref)
                self.active_entity=('EDGE',edge_ref)
        self.sync_from_multi()

    def select_path(self,pattern_id,path_id,toggle=False):
        key=(pattern_id,path_id)
        if not toggle:
            self.clear_selection()
            self.selected_paths.add(key)
            self.active_entity=('PATH',key)
        else:
            if key in self.selected_paths:
                self.selected_paths.remove(key)
                if self.active_entity==('PATH',key):self.active_entity=None
            else:
                self.selected_paths.add(key)
                self.active_entity=('PATH',key)
        self.sync_from_multi()

    def invert_selection(self):
        target=self.acquisition_target
        if target=='PIECES':
            all_pids={p.id for p in self.document.patterns}
            self.selected_patterns=all_pids-self.selected_patterns
        elif target=='POINTS':
            all_pts={(p.id,path,idx) for p in self.document.patterns for path,nodes,_,_ in p.loops() for idx in range(len(nodes))}
            self.selected_points=all_pts-self.selected_points
        elif target=='EDGES':
            all_edges={e for p in self.document.patterns for path,_,_,_ in p.loops() for e in self.document.edges(p.id,path)}
            self.selected_edges=all_edges-self.selected_edges
        elif target=='PATHS':
            all_paths={(p.id,path.id) for p in self.document.patterns for path in p.paths}
            self.selected_paths=all_paths-self.selected_paths
        self.sync_from_multi()

    def select_connected(self,mode='PATH'):
        if mode=='PATH':
            if self.active_entity:
                kind,val=self.active_entity
                if kind=='POINT':
                    pid,path_id,_=val
                    p=self.document.find(pid)
                    if p:
                        for i in range(len(p.path(path_id).vertices)):
                            self.selected_points.add((pid,path_id,i))
                elif kind=='EDGE':
                    p=self.document.find(val.pattern)
                    if p:
                        for e in self.document.edges(val.pattern,val.path):
                            self.selected_edges.add(e)
                elif kind=='PATH':
                    self.selected_paths.add(val)
        elif mode=='SEWN':
            seeds=set(self.selected_patterns)
            if not seeds and self._selected:seeds.add(self._selected)
            connected=set(seeds)
            changed=True
            while changed:
                changed=False
                for seam in self.document.seams:
                    side_a={e.pattern for e in seam.side(0)}
                    side_b={e.pattern for e in seam.side(1)}
                    if connected.intersection(side_a) and not side_b.issubset(connected):
                        connected.update(side_b);changed=True
                    if connected.intersection(side_b) and not side_a.issubset(connected):
                        connected.update(side_a);changed=True
            self.selected_patterns.update(connected)
        self.sync_from_multi()

    def is_multi_selected(self):
        return len(self.selected_patterns)+len(self.selected_points)+len(self.selected_edges)+len(self.selected_paths)>1

    def has_selection(self):
        return bool(self.selected_patterns or self.selected_points or self.selected_edges or self.selected_paths)

    def selection_counts(self):
        return len(self.selected_patterns),len(self.selected_points)

    def can_merge_selected_points(self):
        if len(self.selected_points)!=2:return False
        pts=list(self.selected_points)
        if pts[0][0]!=pts[1][0] or pts[0][1]!=pts[1][1]:return False
        p=self.document.find(pts[0][0])
        if not p:return False
        nodes=p.path(pts[0][1]).vertices
        a,b=sorted([pts[0][2],pts[1][2]])
        return b==a+1 or (a==0 and b==len(nodes)-1)

    def box_select(self,x0,y0,x1,y1,mode=None,shift=False,alt=False):
        target=self.acquisition_target
        rule='ENCLOSE' if x1>=x0 else 'CROSSING'
        if mode is None:
            if alt:mode='SUBTRACT'
            elif shift:mode='ADD'
            else:mode='REPLACE'
        min_x,max_x=min(x0,x1),max(x0,x1)
        min_y,max_y=min(y0,y1),max(y0,y1)
        hits=set()
        if target=='PIECES':
            for p in self.document.patterns:
                matched=pattern_enclosed_by_box(p,min_x,min_y,max_x,max_y) if rule=='ENCLOSE' else pattern_touches_box(p,min_x,min_y,max_x,max_y)
                if matched:hits.add(p.id)
            if mode=='REPLACE':self.selected_patterns=hits
            elif mode=='ADD':self.selected_patterns.update(hits)
            elif mode=='SUBTRACT':self.selected_patterns.difference_update(hits)
            self.sync_from_multi()
            return 'PIECES',len(self.selected_patterns)
        elif target=='POINTS':
            for p in self.document.patterns:
                for path,nodes,_,_ in p.loops():
                    for idx,v in enumerate(nodes):
                        if min_x<=v.x<=max_x and min_y<=v.y<=max_y:
                            hits.add((p.id,path,idx))
            if mode=='REPLACE':self.selected_points=hits
            elif mode=='ADD':self.selected_points.update(hits)
            elif mode=='SUBTRACT':self.selected_points.difference_update(hits)
            self.sync_from_multi()
            return 'POINTS',len(self.selected_points)
        elif target=='EDGES':
            for p in self.document.patterns:
                for path,_,_,_ in p.loops():
                    for edge in self.document.edges(p.id,path):
                        if edge_in_box(self.document,edge,min_x,min_y,max_x,max_y,rule):
                            hits.add(edge)
            if mode=='REPLACE':self.selected_edges=hits
            elif mode=='ADD':self.selected_edges.update(hits)
            elif mode=='SUBTRACT':self.selected_edges.difference_update(hits)
            self.sync_from_multi()
            return 'EDGES',len(self.selected_edges)
        elif target=='PATHS':
            for p in self.document.patterns:
                for path in p.paths:
                    samples=path.outline()
                    in_box=[min_x<=pt[0]<=max_x and min_y<=pt[1]<=max_y for pt in samples]
                    matched=all(in_box) if rule=='ENCLOSE' else (any(in_box) or any(intersects(a,b,c,d) for a,b in zip(samples,samples[1:]) for c,d in zip([(min_x,min_y),(max_x,min_y),(max_x,max_y),(min_x,max_y)],[(max_x,min_y),(max_x,max_y),(min_x,max_y),(min_x,min_y)])))
                    if matched:hits.add((p.id,path.id))
            if mode=='REPLACE':self.selected_paths=hits
            elif mode=='ADD':self.selected_paths.update(hits)
            elif mode=='SUBTRACT':self.selected_paths.difference_update(hits)
            self.sync_from_multi()
            return 'PATHS',len(self.selected_paths)
        return target,0

    def lasso_select(self,points,mode=None,shift=False,alt=False,rule='ENCLOSE'):
        target=self.acquisition_target
        if mode is None:
            if alt:mode='SUBTRACT'
            elif shift:mode='ADD'
            else:mode='REPLACE'
        hits=set()
        poly=list(points)
        if len(poly)>=2 and poly[0]==poly[-1]:poly=poly[:-1]
        if len(poly)<3:return target,0
        if target=='PIECES':
            for p in self.document.patterns:
                if pattern_in_lasso(p,poly,rule):hits.add(p.id)
            if mode=='REPLACE':self.selected_patterns=hits
            elif mode=='ADD':self.selected_patterns.update(hits)
            elif mode=='SUBTRACT':self.selected_patterns.difference_update(hits)
            self.sync_from_multi()
            return 'PIECES',len(self.selected_patterns)
        elif target=='POINTS':
            for p in self.document.patterns:
                for path,nodes,_,_ in p.loops():
                    for idx,v in enumerate(nodes):
                        if point_in_lasso((v.x,v.y),poly):
                            hits.add((p.id,path,idx))
            if mode=='REPLACE':self.selected_points=hits
            elif mode=='ADD':self.selected_points.update(hits)
            elif mode=='SUBTRACT':self.selected_points.difference_update(hits)
            self.sync_from_multi()
            return 'POINTS',len(self.selected_points)
        elif target=='EDGES':
            for p in self.document.patterns:
                for path,_,_,_ in p.loops():
                    for edge in self.document.edges(p.id,path):
                        if edge_in_lasso(self.document,edge,poly,rule):
                            hits.add(edge)
            if mode=='REPLACE':self.selected_edges=hits
            elif mode=='ADD':self.selected_edges.update(hits)
            elif mode=='SUBTRACT':self.selected_edges.difference_update(hits)
            self.sync_from_multi()
            return 'EDGES',len(self.selected_edges)
        elif target=='PATHS':
            for p in self.document.patterns:
                for path in p.paths:
                    samples=path.outline()
                    in_poly=[point_in_lasso(pt,poly) for pt in samples]
                    matched=all(in_poly) if rule=='ENCLOSE' else (any(in_poly) or any(intersects(a,b,c,d) for a,b in zip(samples,samples[1:]) for c,d in zip(poly,poly[1:]+poly[:1])))
                    if matched:hits.add((p.id,path.id))
            if mode=='REPLACE':self.selected_paths=hits
            elif mode=='ADD':self.selected_paths.update(hits)
            elif mode=='SUBTRACT':self.selected_paths.difference_update(hits)
            self.sync_from_multi()
            return 'PATHS',len(self.selected_paths)
        return target,0


    def commit(self,operation):
        from .linked_editing import synchronize
        before=self.document.dumps()
        before_sel=self.get_selection_state()
        old_seams={s.id for s in self.document.seams}
        dropped_before=self.document.elastics_dropped
        self.last_repairs=0
        try:
            operation()
            synchronize(self.document,Document.loads(before),self.selected)
            self.document.prune_seams()
            self.document.validate()
            self.last_repairs=len(old_seams-{s.id for s in self.document.seams})+max(0,self.document.elastics_dropped-dropped_before)
        except Exception:
            self.document=Document.loads(before)
            raise
        if self.document.dumps()!=before:
            self.undo_stack.append(before);self.undo_stack=self.undo_stack[-100:]
            self._undo_selections.append(before_sel);self._undo_selections=self._undo_selections[-100:]
            self.redo_stack.clear();self._redo_selections.clear();return True
        return False

    def set_mesh_density(self,name):
        if name not in ('AUTO','COARSE','STANDARD','FINE','ULTRA'):raise ValueError('Unknown mesh density.')
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
        valid={'COTTON','LINEN','SILK','DENIM','KNIT','LEATHER'}|set(getattr(self.document,'custom_presets',{}) or {})
        if name not in valid: raise ValueError('Unknown cloth preset.')
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
        valid={'COTTON','LINEN','SILK','DENIM','KNIT','LEATHER'}|set(getattr(self.document,'custom_presets',{}) or {})
        if name not in valid: raise ValueError('Unknown cloth preset.')
        def op():
            for p in pats:p.fabric_override=True;p.preset=name
        return self.commit(op)

    def set_custom_preset(self,name,values):
        if not isinstance(name,str) or not name.strip() or not valid_fabric(values):
            raise ValueError('Invalid custom fabric preset.')
        def op():
            if not hasattr(self.document,'custom_presets') or self.document.custom_presets is None:
                self.document.custom_presets={}
            self.document.custom_presets[name]=dict(values)
        return self.commit(op)

    def delete_custom_preset(self,name):
        if not hasattr(self.document,'custom_presets') or name not in self.document.custom_presets:
            raise ValueError('Unknown custom preset.')
        def op():
            del self.document.custom_presets[name]
            if self.document.preset==name:
                self.document.preset='COTTON'
            for p in self.document.patterns:
                if p.preset==name:
                    p.preset=self.document.preset
                    p.fabric_override=False
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

    def resolve_selection(self,doc=None):
        doc=doc or self.document
        nodes={}
        whole_patterns=set(self.selected_patterns)
        for pid in self.selected_patterns:
            p=doc.find(pid)
            if not p:continue
            for path,vlist,_,_ in p.loops():
                for i,v in enumerate(vlist):
                    nodes[(pid,path,i)]=v
        for pid,path_id in self.selected_paths:
            p=doc.find(pid)
            if not p:continue
            try:
                q=p.path(path_id)
                for i,v in enumerate(q.vertices):
                    nodes[(pid,path_id,i)]=v
            except (ValueError,KeyError):pass
        for edge in self.selected_edges:
            p=doc.find(edge.pattern)
            if not p:continue
            try:
                vlist=p.path(edge.path).vertices
                i0=next((i for i,v in enumerate(vlist) if v.id==edge.start),None)
                i1=next((i for i,v in enumerate(vlist) if v.id==edge.end),None)
                if i0 is not None:nodes[(edge.pattern,edge.path,i0)]=vlist[i0]
                if i1 is not None:nodes[(edge.pattern,edge.path,i1)]=vlist[i1]
            except (ValueError,KeyError):pass
        for pid,path_id,idx in self.selected_points:
            p=doc.find(pid)
            if not p:continue
            try:
                vlist=p.path(path_id).vertices
                if 0<=idx<len(vlist):
                    nodes[(pid,path_id,idx)]=vlist[idx]
            except (ValueError,IndexError):pass
        if not nodes and self._selected:
            p=doc.find(self._selected)
            if p:
                if self._corner is not None:
                    try:
                        nodes[(self._selected,self.path,self._corner)]=p.path(self.path).vertices[self._corner]
                    except (ValueError,IndexError):pass
                elif self.segment:
                    try:
                        vlist=p.path(self.segment.path).vertices
                        i0=next((i for i,v in enumerate(vlist) if v.id==self.segment.start),None)
                        i1=next((i for i,v in enumerate(vlist) if v.id==self.segment.end),None)
                        if i0 is not None:nodes[(self.segment.pattern,self.segment.path,i0)]=vlist[i0]
                        if i1 is not None:nodes[(self.segment.pattern,self.segment.path,i1)]=vlist[i1]
                    except (ValueError,KeyError):pass
                else:
                    whole_patterns.add(p.id)
                    for path,vlist,_,_ in p.loops():
                        for i,v in enumerate(vlist):
                            nodes[(self._selected,path,i)]=v
        return nodes,whole_patterns

    def selection_center(self):
        bounds=self.selection_bounds()
        if bounds is None:return 0.0,0.0
        return (bounds[0]+bounds[2])/2,(bounds[1]+bounds[3])/2

    def selection_bounds(self):
        pts=[]
        doc=self.document
        for pid in self.selected_patterns:
            p=doc.find(pid)
            if p:
                for path,_,_,_ in p.loops():
                    for edge in doc.edges(p.id,path):
                        for _,pt in curves.table(doc.edge_curve(edge)):
                            pts.append(pt)
        for edge in self.selected_edges:
            if edge.pattern not in self.selected_patterns:
                try:
                    for _,pt in curves.table(doc.edge_curve(edge)):
                        pts.append(pt)
                except (ValueError,KeyError):pass
        for pid,path_id in self.selected_paths:
            if pid not in self.selected_patterns:
                p=doc.find(pid)
                if p:
                    try:
                        for edge in doc.edges(pid,path_id):
                            for _,pt in curves.table(doc.edge_curve(edge)):
                                pts.append(pt)
                    except (ValueError,KeyError):pass
        for pid,path_id,idx in self.selected_points:
            if pid not in self.selected_patterns and (pid,path_id) not in self.selected_paths:
                p=doc.find(pid)
                if p:
                    try:
                        v=p.path(path_id).vertices[idx]
                        pts.append((v.x,v.y))
                    except (ValueError,IndexError):pass
        if not pts and self._selected:
            p=doc.find(self._selected)
            if p:
                if self._corner is not None:
                    try:
                        v=p.path(self.path).vertices[self._corner]
                        pts.append((v.x,v.y))
                    except (ValueError,IndexError):pass
                elif self.segment:
                    try:
                        for _,pt in curves.table(doc.edge_curve(self.segment)):
                            pts.append(pt)
                    except (ValueError,KeyError):pass
                else:
                    for path,_,_,_ in p.loops():
                        for edge in doc.edges(p.id,path):
                            for _,pt in curves.table(doc.edge_curve(edge)):
                                pts.append(pt)
        if not pts:return None
        return min(p[0] for p in pts),min(p[1] for p in pts),max(p[0] for p in pts),max(p[1] for p in pts)

    def get_pivot(self):
        if self.placed_pivot is not None:return self.placed_pivot
        return self.selection_center()

    def set_pivot(self,x,y):
        self.placed_pivot=(float(x),float(y))

    def reset_pivot(self):
        self.placed_pivot=None

    def find_pivot_candidate(self,pointer_world,tolerance=0.02):
        candidates=[]
        sc=self.selection_center()
        d_sc=math.hypot(sc[0]-pointer_world[0],sc[1]-pointer_world[1])
        if d_sc<=tolerance:
            candidates.append((3,round(d_sc,6),999999,sc,'Selection center'))
        order=0
        for p in self.document.patterns:
            for path,nodes,_,_ in p.loops():
                for v in nodes:
                    d=math.hypot(v.x-pointer_world[0],v.y-pointer_world[1])
                    if d<=tolerance:
                        candidates.append((1,round(d,6),order,(v.x,v.y),f'Vertex ({v.x:.2f}, {v.y:.2f})'))
                    order+=1
                for edge in self.document.edges(p.id,path):
                    ctrl=self.document.edge_curve(edge)
                    mid=curves.at_length(ctrl,0.5)
                    mid=(round(mid[0],7),round(mid[1],7))
                    d=math.hypot(mid[0]-pointer_world[0],mid[1]-pointer_world[1])
                    if d<=tolerance:
                        candidates.append((2,round(d,6),order,mid,'Midpoint'))
                    order+=1
        if not candidates:
            return pointer_world,'Free'
        candidates.sort(key=lambda item:(item[1],item[0],item[2]))
        best=candidates[0]
        return best[3],best[4]

    def preflight_transform(self,candidate_doc,whole_patterns,nodes):
        try:
            candidate_doc.validate()
        except Exception as exc:
            return dict(status='BLOCK',reason='Invalid panel geometry: '+str(exc))
        from .linked_editing import synchronize
        try:
            synchronize(candidate_doc,self.document,self.selected)
        except Exception as exc:
            return dict(status='BLOCK',reason='Linked editing synchronization failed: '+str(exc))
        canonicalize_auto_handles(candidate_doc)
        source_doc=Document.loads(self.document.dumps())
        canonicalize_auto_handles(source_doc)
        for key,cand_v in nodes.items():
            pid,path_id,idx=key
            p=candidate_doc.find(pid)
            if not p:
                return dict(status='BLOCK',reason='Selected piece removed during synchronization.')
            try:
                v=p.path(path_id).vertices[idx]
                if abs(v.x-cand_v.x)>1e-6 or abs(v.y-cand_v.y)>1e-6:
                    return dict(status='BLOCK',reason='Linked editing conflict: synchronization overwrote explicitly selected geometry.')
            except (ValueError,IndexError):
                return dict(status='BLOCK',reason='Selected vertex missing during synchronization.')
        old_seams={s.id:s for s in self.document.seams}
        new_seams={s.id:s for s in candidate_doc.seams}
        if len(new_seams)<len(old_seams):
            return dict(status='BLOCK',reason='A seam would be pruned or invalidated.')
        warn_details=[]
        affected_seam_ids=[]
        affected_patterns=set()
        for sid,old_seam in old_seams.items():
            new_seam=new_seams.get(sid)
            if not new_seam:
                return dict(status='BLOCK',reason='A seam would be pruned or invalidated.')
            if old_seam.reverse!=new_seam.reverse or getattr(old_seam,'shrink',0)!=getattr(new_seam,'shrink',0):
                return dict(status='BLOCK',reason='A seam configuration was modified.')
            for side_idx in (0,1):
                old_chain=old_seam.side(side_idx);new_chain=new_seam.side(side_idx)
                if len(old_chain)!=len(new_chain):
                    return dict(status='BLOCK',reason='A seam chain was modified or reordered.')
                for e_old,e_new in zip(old_chain,new_chain):
                    if (e_old.pattern!=e_new.pattern or e_old.path!=e_new.path or
                        e_old.start!=e_new.start or e_old.end!=e_new.end or
                        abs(e_old.t0-e_new.t0)>1e-6 or abs(e_old.t1-e_new.t1)>1e-6):
                        return dict(status='BLOCK',reason='A seam reference or span was modified or reordered.')
            try:
                for side_idx in (0,1):
                    for e in new_seam.side(side_idx):
                        if candidate_doc.edge_length(e)<1e-5:
                            return dict(status='BLOCK',reason='Seam span length is near zero.')
                len0_before=sum(source_doc.edge_length(e) for e in old_seam.side(0))
                len1_before=sum(source_doc.edge_length(e) for e in old_seam.side(1))
                len0_after=sum(candidate_doc.edge_length(e) for e in new_seam.side(0))
                len1_after=sum(candidate_doc.edge_length(e) for e in new_seam.side(1))
            except Exception as exc:
                return dict(status='BLOCK',reason='Seam geometry evaluation failed: '+str(exc))
            tol0=max(0.0001,0.0001*len(old_seam.side(0)))
            tol1=max(0.0001,0.0001*len(old_seam.side(1)))
            r_min=(len0_before-tol0)/(len1_before+tol1)
            r_max=(len0_before+tol0)/(len1_before-tol1)
            r_after=len0_after/len1_after if len1_after>0 else 1.0
            seam_changed=(abs(len0_after-len0_before)>tol0 or abs(len1_after-len1_before)>tol1)
            ratio_changed=(r_after<r_min-1e-6 or r_after>r_max+1e-6)
            chain_break_changed=False
            for side_idx in (0,1):
                old_side=old_seam.side(side_idx);new_side=new_seam.side(side_idx)
                if len(old_side)>1:
                    old_tot=len0_before if side_idx==0 else len1_before
                    new_tot=len0_after if side_idx==0 else len1_after
                    cum_old=cum_new=0.0
                    for e_old,e_new in zip(old_side[:-1],new_side[:-1]):
                        cum_old+=source_doc.edge_length(e_old)
                        cum_new+=candidate_doc.edge_length(e_new)
                        if abs(cum_new/new_tot-cum_old/old_tot)>(0.0001/old_tot):
                            chain_break_changed=True;break
            if (seam_changed and ratio_changed) or chain_break_changed:
                diff_cm=abs(len0_after-len1_after)*100
                max_len=max(len0_after,len1_after)
                percent=(abs(len0_after-len1_after)/max_len*100) if max_len>0 else 0.0
                affected_seam_ids.append(sid)
                for e in old_seam.side(0)+old_seam.side(1):
                    p=candidate_doc.find(e.pattern)
                    if p:affected_patterns.add(p.name)
                warn_details.append(dict(seam_id=sid,len0_before=len0_before,len1_before=len1_before,
                                         len0_after=len0_after,len1_after=len1_after,diff_cm=diff_cm,
                                         percent=percent))
        if warn_details:
            first_warn=warn_details[0]
            can_include_sewn=(len(whole_patterns)>0 and len(whole_patterns)==len(self.selected_patterns) and not self.selected_points and not self.selected_edges and not self.selected_paths)
            return dict(status='WARN',diff_cm=first_warn['diff_cm'],percent=first_warn['percent'],
                        len0_after=first_warn['len0_after'],len1_after=first_warn['len1_after'],
                        len0_before=first_warn['len0_before'],len1_before=first_warn['len1_before'],
                        affected_count=len(affected_seam_ids),affected_pieces=list(affected_patterns),
                        can_include_sewn=can_include_sewn,details=warn_details)
        return dict(status='OK')

    def commit_candidate(self,candidate_doc,coalesce=False):
        before=self.document.dumps()
        before_sel=self.get_selection_state()
        for cand_p in candidate_doc.patterns:
            p=self.document.find(cand_p.id)
            if p:
                for cand_path,cand_nodes,_,_ in cand_p.loops():
                    try:
                        q=p.path(cand_path)
                        for v_orig,v_cand in zip(q.vertices,cand_nodes):
                            v_orig.x,v_orig.y=v_cand.x,v_cand.y
                            v_orig.incoming=v_cand.incoming
                            v_orig.outgoing=v_cand.outgoing
                            if hasattr(v_cand,'point_type'):v_orig.point_type=v_cand.point_type
                    except (ValueError,KeyError):pass
                p.features=list(cand_p.features)
        for cand_a in candidate_doc.anchors:
            a=next((anc for anc in self.document.anchors if anc.id==cand_a.id),None)
            if a:a.x,a.y=cand_a.x,cand_a.y
        self.document.seams=candidate_doc.seams
        self.document.linked_pairs=candidate_doc.linked_pairs
        self.document.prune_seams()
        self.document.validate()
        canonicalize_auto_handles(self.document)
        if self.document.dumps()!=before:
            if not coalesce:
                self.undo_stack.append(before);self.undo_stack=self.undo_stack[-100:]
                self._undo_selections.append(before_sel);self._undo_selections=self._undo_selections[-100:]
            self.redo_stack.clear();self._redo_selections.clear()
            self.remember_committed_selection()
            return True
        return False

    def remember_committed_selection(self):
        self._committed_selection=(self.document.dumps(),self.get_selection_state())

    def build_transform_candidate(self,op_kind,param,pivot=None):
        nodes,whole_patterns=self.resolve_selection()
        if not nodes:return None,{'status':'BLOCK','reason':'No selection'}
        pivot=pivot or self.get_pivot()
        px,py=pivot
        if op_kind=='SCALE' and (not isinstance(param,(int,float)) or not math.isfinite(param) or param<=0):
            return None,{'status':'BLOCK','reason':'Scale factor must be positive and finite.'}
        if op_kind=='MOVE':
            dx,dy=param
            def place(x,y):return x+dx,y+dy
            def turn(vector):return vector
        elif op_kind=='ROTATE':
            angle_degrees=param
            rad=math.radians(angle_degrees)
            c=math.cos(rad);s=math.sin(rad)
            if abs(angle_degrees-90)<1e-6 or abs(angle_degrees+270)<1e-6:c,s=0.0,1.0
            elif abs(angle_degrees+90)<1e-6 or abs(angle_degrees-270)<1e-6:c,s=0.0,-1.0
            elif abs(abs(angle_degrees)-180)<1e-6:c,s=-1.0,0.0
            def place(x,y):
                rx=x-px;ry=y-py
                return px+c*rx-s*ry,py+s*rx+c*ry
            def turn(vector):return (c*vector[0]-s*vector[1],s*vector[0]+c*vector[1])
        else:
            factor=param
            def place(x,y):return px+factor*(x-px),py+factor*(y-py)
            def turn(vector):return (factor*vector[0],factor*vector[1])
        cand_doc=Document.loads(self.document.dumps())
        canonicalize_auto_handles(cand_doc)
        cand_nodes,_=self.resolve_selection(cand_doc)
        selected_curves=selected_edge_curves(cand_doc,cand_nodes)
        for v in cand_nodes.values():
            v.x,v.y=place(v.x,v.y)
            if v.incoming is not None:v.incoming=turn(v.incoming)
            if v.outgoing is not None:v.outgoing=turn(v.outgoing)
        for pid in whole_patterns:
            for anchor in cand_doc.anchors:
                if anchor.pattern==pid:anchor.x,anchor.y=place(anchor.x,anchor.y)
        exact_handles={key:(v.incoming,v.outgoing) for key,v in cand_nodes.items()}
        canonicalize_auto_handles(cand_doc)
        deviation=0.0
        convert_keys=set()
        for key_a,key_b,source_control in selected_curves:
            target=tuple(place(*point) for point in source_control)
            produced=curves.controls(cand_nodes[key_a],cand_nodes[key_b])
            edge_deviation=max(math.dist(curves.evaluate(target,i/100),curves.evaluate(produced,i/100)) for i in range(101))
            if edge_deviation>CURVE_TOLERANCE:
                deviation=max(deviation,edge_deviation)
                convert_keys.update(key for key in (key_a,key_b) if getattr(cand_nodes[key],'point_type','CORNER')=='AUTO')
        exact_doc=None
        if convert_keys:
            exact_doc=Document.loads(cand_doc.dumps())
            exact_nodes,_=self.resolve_selection(exact_doc)
            for key in convert_keys:
                v=exact_nodes[key]
                v.point_type='SMOOTH'
                v.incoming,v.outgoing=exact_handles[key]
            canonicalize_auto_handles(exact_doc)
        pre=self.preflight_transform(cand_doc,whole_patterns,cand_nodes)
        if deviation>CURVE_TOLERANCE and pre['status']!='BLOCK':
            if pre['status']=='OK':pre=dict(status='WARN',can_include_sewn=False)
            pre.update(curve_deviation_mm=deviation*1000,auto_point_count=len(convert_keys),exact_candidate=exact_doc)
        return cand_doc,pre

    def move_selection(self,dx,dy,confirm=False,coalesce=False):
        if abs(dx)<1e-9 and abs(dy)<1e-9:return False
        cand_doc,pre=self.build_transform_candidate('MOVE',(dx,dy))
        if not cand_doc:return False
        if pre['status']=='BLOCK':
            raise ValueError(pre['reason'])
        if pre['status']=='WARN' and not confirm:
            return pre
        before_pivot=self.placed_pivot
        res=self.commit_candidate(cand_doc,coalesce=coalesce)
        if res and before_pivot is not None:
            self.placed_pivot=(round(before_pivot[0]+dx,7),round(before_pivot[1]+dy,7))
            self.remember_committed_selection()
        return res

    def align_pieces(self,mode):
        pats=[self.document.find(pid) for pid in sorted(self.selected_patterns) if self.document.find(pid)]
        if mode in ('DISTRIBUTE_X','DISTRIBUTE_Y'):
            if len(pats)<3:raise ValueError('Select three or more pieces to distribute.')
        elif len(pats)<2:raise ValueError('Select two or more pieces to align.')
        def bounds(pattern):
            points=[(v.x,v.y) for _,nodes,_,_ in pattern.loops() for v in nodes]
            return min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)
        boxes={p.id:bounds(p) for p in pats}
        left=min(b[0] for b in boxes.values());bottom=min(b[1] for b in boxes.values())
        right=max(b[2] for b in boxes.values());top=max(b[3] for b in boxes.values())
        shifts={}
        if mode=='DISTRIBUTE_X' or mode=='DISTRIBUTE_Y':
            axis=0 if mode=='DISTRIBUTE_X' else 1
            ordered=sorted(pats,key=lambda p:(boxes[p.id][axis]+boxes[p.id][axis+2])/2)
            span=(right-left) if axis==0 else (top-bottom)
            gap=(span-sum(boxes[p.id][axis+2]-boxes[p.id][axis] for p in ordered))/(len(ordered)-1)
            cursor=left if axis==0 else bottom
            for p in ordered:
                low,high=boxes[p.id][axis],boxes[p.id][axis+2]
                shifts[p.id]=((cursor-low,0.0) if axis==0 else (0.0,cursor-low))
                cursor+=high-low+gap
        else:
            for p in pats:
                x0,y0,x1,y1=boxes[p.id]
                shifts[p.id]={'LEFT':(left-x0,0.0),'CENTER':((left+right)/2-(x0+x1)/2,0.0),'RIGHT':(right-x1,0.0),
                              'TOP':(0.0,top-y1),'MIDDLE':(0.0,(bottom+top)/2-(y0+y1)/2),'BOTTOM':(0.0,bottom-y0)}[mode]
        if all(abs(dx)<1e-9 and abs(dy)<1e-9 for dx,dy in shifts.values()):return False
        def op():
            for p in pats:
                dx,dy=shifts[p.id]
                for _,nodes,_,_ in p.loops():
                    for v in nodes:v.x+=dx;v.y+=dy
                for anchor in self.document.anchors:
                    if anchor.pattern==p.id:anchor.x+=dx;anchor.y+=dy
        return self.commit(op)

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

    def rotate(self,angle_degrees,pivot=None,confirm=False):
        if abs(angle_degrees)<1e-9:return False
        cand_doc,pre=self.build_transform_candidate('ROTATE',angle_degrees,pivot=pivot)
        if not cand_doc:return False
        if pre['status']=='BLOCK':
            raise ValueError(pre['reason'])
        if pre['status']=='WARN' and not confirm:
            return pre
        return self.commit_candidate(cand_doc)

    def scale(self,factor,pivot=None,confirm=False):
        if not isinstance(factor,(int,float)) or not math.isfinite(factor) or factor<=0:
            raise ValueError('Scale factor must be positive and finite.')
        if abs(factor-1.0)<1e-9:return False
        cand_doc,pre=self.build_transform_candidate('SCALE',factor,pivot=pivot)
        if not cand_doc:return False
        if pre['status']=='BLOCK':
            raise ValueError(pre['reason'])
        if pre['status']=='WARN' and not confirm:
            return pre
        return self.commit_candidate(cand_doc)

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
                            new_seam=Seam(a[0],b[0],seam.reverse,chain_a=tuple(a),chain_b=tuple(b),shrink=seam.shrink,active=seam.active)
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
        def apply():
            from .linked_editing import mirror_seam
            self.document.seams.append(seam)
            twin=mirror_seam(self.document,seam)
            if twin is not None:
                self.document.seams.append(twin)
                try:self.document.validate_seams()
                except ValueError:self.document.seams.remove(twin)
        return self.commit(apply)

    def linked_seams(self,identity):
        from .linked_editing import seam_twin
        seam=next((s for s in self.document.seams if s.id==identity),None)
        if seam is None:raise ValueError('That seam no longer exists.')
        twin=seam_twin(self.document,seam)
        return seam,[item for item in (seam,twin) if item is not None]

    def set_linked_seam(self,identity,name,value):
        _,seams=self.linked_seams(identity)
        def apply():
            for item in seams:setattr(item,name,value)
        return self.commit(apply)

    def remove_seam(self,identity):
        _,seams=self.linked_seams(identity)
        def apply():
            for item in seams:
                if item in self.document.seams:self.document.seams.remove(item)
        result=self.commit(apply);self.last_repairs=0;return result

    def reverse_seam(self,identity):
        seam,_=self.linked_seams(identity)
        return self.set_linked_seam(identity,'reverse',not seam.reverse)

    def set_seam_shrink(self,identity,shrink):
        if type(shrink) is not int or shrink not in (0,10,20,30):
            raise ValueError("Seam Shrink must be 0, 10, 20 or 30 percent.")
        return self.set_linked_seam(identity,'shrink',shrink)

    def set_seam_active(self,identity,active):
        return self.set_linked_seam(identity,'active',bool(active))

    def split_segment(self,edge,fraction=.5):
        if not .0001<fraction<.9999:raise ValueError('Split inside the segment, away from its endpoints.')
        return self.commit(lambda:self.document.split_edge(edge,fraction))

    def split_segment_into(self,edge,parts):
        if type(parts) is not int or not 2<=parts<=MAX_SPLIT_PARTS:raise ValueError(f'Split into 2 to {MAX_SPLIT_PARTS} parts.')
        def apply():
            current=edge.full()
            _,end=self.document.edge_vertices(current)
            for remaining in range(parts,1,-1):
                point=self.document.split_edge(current,1/remaining)
                current=EdgeRef(edge.pattern,point.id,end.id,path=edge.path)
        return self.commit(apply)

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
        result=self.commit(apply);self.select_point(p.id,self.path,a);self.point_selection=[];return result

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

    def offset_path(self,distance):
        p=self.document.find(self._selected)
        if p is None or self.path=='OUTER':raise ValueError('Select an internal line to offset.')
        source=p.path(self.path);nodes=source.vertices;count=len(nodes);copies=[]
        for index,v in enumerate(nodes):
            before=nodes[(index-1)%count] if source.closed or index else v
            after=nodes[(index+1)%count] if source.closed or index<count-1 else v
            dx,dy=after.x-before.x,after.y-before.y;length=math.hypot(dx,dy)
            if length<1e-9:raise ValueError('This internal line is too short to offset.')
            copies.append(Vertex(v.x-dy/length*distance,v.y+dx/length*distance,incoming=v.incoming,outgoing=v.outgoing,point_type=getattr(v,'point_type','CORNER')))
        path=Path(source.name+' offset',copies,source.closed)
        self.commit(lambda:p.paths.append(path));self.path,self.corner=path.id,None
        return path

    def round_corner(self,radius):
        p=self.document.find(self._selected)
        if p is None or self.corner is None:raise ValueError('Select a corner to round.')
        nodes=p.path(self.path).vertices;v=nodes[self.corner];edges=self.document.edges(p.id,self.path)
        incoming=next((edge for edge in edges if edge.end==v.id),None);outgoing=next((edge for edge in edges if edge.start==v.id),None)
        if incoming is None or outgoing is None:raise ValueError('The end of an open line cannot be rounded.')
        before,after=self.document.edge_length(incoming),self.document.edge_length(outgoing)
        if radius*2>=min(before,after):raise ValueError('This corner is too close to the next point for that radius.')
        def apply():
            a=self.document.split_edge(incoming,1-radius/before);b=self.document.split_edge(outgoing,radius/after)
            nodes.remove(v)
            a.point_type=b.point_type='CORNER'
            a.outgoing=((v.x-a.x)*.55,(v.y-a.y)*.55);b.incoming=((v.x-b.x)*.55,(v.y-b.y)*.55)
        result=self.commit(apply);self.corner=None;self.point_selection=[];return result

    def layer_clone(self,over=True):
        p=self.document.find(self._selected)
        if p is None:raise ValueError('Select a piece to layer.')
        layer=clone_pattern(p,offset=(.03,-.03));layer.name=p.name+' layer'
        def apply():
            self.document.patterns.append(layer)
            sewn={edge.full() for seam in self.document.seams for side in (seam.side(0),seam.side(1)) for edge in side}
            for first,second in zip(self.document.edges(p.id),self.document.edges(layer.id)):
                if first not in sewn:self.document.seams.append(Seam(first,second,False))
            record=p.arrangement
            if record and record.get('version')==3 and not record['flat']:
                (layer if over else p).arrangement=dict(record,clearance=(record['clearance'] or 0.0)+.005)
        result=self.commit(apply)
        self.clear_selection();self.selected_patterns.add(layer.id)
        self.selected,self.path,self.corner=layer.id,'OUTER',None
        return result

    def set_seam_end(self,identity,side,last,fraction):
        from .linked_editing import follow_seam_range
        seam,seams=self.linked_seams(identity)
        twin=seams[1] if len(seams)>1 else None
        chain=seam.side(side);index=-1 if last else 0;edge=chain[index]
        moved=EdgeRef(edge.pattern,edge.start,edge.end,edge.t0 if last else fraction,fraction if last else edge.t1,edge.path)
        if abs(moved.t1-moved.t0)<.005:raise ValueError('A sewn range needs some length.')
        chain[index]=moved
        def apply():
            if side:seam.chain_b=tuple(chain);seam.b=chain[0]
            else:seam.chain_a=tuple(chain);seam.a=chain[0]
            follow_seam_range(self.document,seam,twin)
        return self.commit(apply)

    def set_seam_length(self,identity,side,target):
        seam=next((s for s in self.document.seams if s.id==identity),None)
        if seam is None:raise ValueError('That seam no longer exists.')
        chain=seam.side(side);edge=chain[-1];full=self.document.edge_length(edge.full())
        span=(target-self.document.chain_length(chain[:-1]))/full
        direction=1 if edge.t1>=edge.t0 else -1
        fraction=edge.t0+span*direction
        if span<=0 or not 0<=fraction<=1:raise ValueError('That length does not fit on this edge.')
        return self.set_seam_end(identity,side,True,fraction)

    def set_seam_ease(self,identity,side):
        return self.set_linked_seam(identity,'ease_side',side)

    def set_elastic(self,edge,shrink):
        def apply():
            self.document.elastics=[record for record in self.document.elastics if (record['pattern'],record['start'],record['end'])!=(edge.pattern,edge.start,edge.end)]
            if shrink:self.document.elastics.append(dict(pattern=edge.pattern,start=edge.start,end=edge.end,path=edge.path,shrink=shrink))
        return self.commit(apply)

    def add_steam(self,records):
        return self.commit(lambda:self.document.steam.extend(records))

    def clear_steam(self,identity):
        def apply():
            self.document.steam=[record for record in self.document.steam if record['pattern']!=identity]
        return self.commit(apply)

    def slash_spread(self,degrees):
        p=self.document.find(self._selected)
        if p is None or self.path=='OUTER':raise ValueError('Select an internal line that reaches the outline at both ends.')
        path=p.path(self.path)
        if path.closed:raise ValueError('Use an open internal line.')
        points=path.points[0],path.points[-1]
        def locate(point):
            for edge in self.document.edges(p.id):
                fraction,distance=curves.closest_fraction(self.document.edge_curve(edge),point)
                if distance<1e-4:
                    a,b=self.document.edge_vertices(edge)
                    if fraction<1e-4:return a
                    if fraction>1-1e-4:return b
                    return self.document.split_edge(edge,fraction)
            raise ValueError('Extend the line to the outline at both ends.')
        turn=-math.radians(degrees);cos,sin=math.cos(turn),math.sin(turn)
        def apply():
            hinge=locate(points[0]);tip=locate(points[1])
            nodes=p.vertices;start=nodes.index(hinge);order=nodes[start:]+nodes[:start];end=order.index(tip)
            copy_tip=Vertex(tip.x,tip.y)
            spin=lambda v:None if v is None else (v[0]*cos-v[1]*sin,v[0]*sin+v[1]*cos)
            centre=(hinge.x,hinge.y)
            for v in (*order[1:end],copy_tip):
                dx,dy=v.x-centre[0],v.y-centre[1]
                v.x,v.y=centre[0]+dx*cos-dy*sin,centre[1]+dx*sin+dy*cos
                v.incoming=spin(v.incoming);v.outgoing=spin(v.outgoing)
            p.vertices=[hinge,*order[1:end],copy_tip,tip,*order[end+1:]]
            p.paths.remove(path)
        result=self.commit(apply);self.path,self.corner='OUTER',None;return result

    def add_join(self,first,second):
        a,b=Anchor(first[0],first[1],first[2],'JOIN'),Anchor(second[0],second[1],second[2],'JOIN')
        def apply():
            self.document.anchors.extend((a,b))
            self.document.joins.append([a.id,b.id])
        return self.commit(apply)

    def superimpose(self,over=True):
        p=self.document.find(self._selected)
        if p is None:raise ValueError('Select a piece first.')
        partners=[edge.pattern for seam in self.document.seams for side in (0,1) if any(e.pattern==p.id for e in seam.side(1-side)) for edge in seam.side(side) if edge.pattern!=p.id]
        target=next((self.document.find(identity) for identity in partners if self.document.find(identity).arrangement),None)
        if target is None or target.arrangement.get('version')!=3:raise ValueError('Sew this piece to an arranged piece first.')
        record=target.arrangement;raised=dict(record,clearance=(record['clearance'] or 0.0)+.005)
        def apply():
            p.arrangement=raised if over else dict(record)
            if not over:target.arrangement=raised
        return self.commit(apply)

    def merge_pieces(self,edge):
        seam=next((s for s in self.document.seams if any(e.full()==edge.full() for side in (0,1) for e in s.side(side))),None)
        if seam is None or len(seam.side(0))!=1 or len(seam.side(1))!=1:raise ValueError('Sew one whole edge to one whole edge first.')
        first,second=seam.side(0)[0],seam.side(1)[0]
        if first.pattern==second.pattern or {round(first.t0,6),round(first.t1,6)}!={0,1} or {round(second.t0,6),round(second.t1,6)}!={0,1}:
            raise ValueError('Merge needs one whole edge sewn to a whole edge of another piece.')
        if not seam.reverse:raise ValueError('Reverse this seam before merging.')
        keep,gone=self.document.find(first.pattern),self.document.find(second.pattern)
        a0,a1=self.document.edge_vertices(first.full());b0,b1=self.document.edge_vertices(second.full())
        before,after=(a1.x-a0.x,a1.y-a0.y),(b0.x-b1.x,b0.y-b1.y)
        if abs(math.hypot(*before)-math.hypot(*after))>.002:raise ValueError('The sewn edges must be the same length to merge.')
        turn=math.atan2(before[1],before[0])-math.atan2(after[1],after[0]);cos,sin=math.cos(turn),math.sin(turn)
        spin=lambda v:None if v is None else (v[0]*cos-v[1]*sin,v[0]*sin+v[1]*cos)
        origin,pivot=(a0.x,a0.y),(b1.x,b1.y)
        place=lambda x,y:(origin[0]+(x-pivot[0])*cos-(y-pivot[1])*sin,origin[1]+(x-pivot[0])*sin+(y-pivot[1])*cos)
        def apply():
            for _,nodes,_,_ in gone.loops():
                for v in nodes:
                    v.x,v.y=place(v.x,v.y);v.incoming=spin(v.incoming);v.outgoing=spin(v.outgoing)
            for anchor in self.document.anchors:
                if anchor.pattern==gone.id:anchor.x,anchor.y=place(anchor.x,anchor.y);anchor.pattern=keep.id
            nodes=keep.vertices;start=nodes.index(a1);walk=nodes[start:]+nodes[:start]
            others=gone.vertices;start=others.index(b1);rest=(others[start:]+others[:start])[1:-1]
            a0.outgoing=b1.outgoing;a1.incoming=b0.incoming
            keep.vertices=walk+rest
            keep.paths.extend(gone.paths);keep.features.extend(gone.features)
            swap={b0.id:a1.id,b1.id:a0.id}
            def remap(item):
                if item.pattern!=gone.id:return item
                return EdgeRef(keep.id,swap.get(item.start,item.start),swap.get(item.end,item.end),item.t0,item.t1,item.path)
            self.document.seams.remove(seam)
            for other in self.document.seams:
                other.chain_a=tuple(remap(item) for item in other.side(0));other.chain_b=tuple(remap(item) for item in other.side(1))
                other.a,other.b=other.chain_a[0],other.chain_b[0]
            for record in self.document.elastics:
                if record['pattern']==gone.id:
                    record.update(pattern=keep.id,start=swap.get(record['start'],record['start']),end=swap.get(record['end'],record['end']))
            self.document.linked_pairs=[pair for pair in self.document.linked_pairs if gone.id not in pair['members']]
            self.document.patterns.remove(gone)
        result=self.commit(apply)
        self.clear_selection();self.selected_patterns.add(keep.id)
        self.selected,self.path,self.corner=keep.id,'OUTER',None
        return result

    def auto_sew(self):
        doc=self.document
        sewn={edge.full() for seam in doc.seams for side in (0,1) for edge in seam.side(side)}
        free=[]
        for pattern in doc.patterns:
            for edge in doc.edges(pattern.id):
                if edge in sewn:continue
                a,b=doc.edge_point(edge,0),doc.edge_point(edge,1)
                if abs(b[1]-a[1])<abs(b[0]-a[0])*.18:continue
                free.append((edge,doc.edge_length(edge),(a[1]+b[1])/2))
        pairs=[];used=set()
        for index,(edge,length,height) in enumerate(free):
            if index in used:continue
            options=[(abs(length-other[1])+abs(height-other[2]),position) for position,other in enumerate(free)
                     if position>index and position not in used and other[0].pattern!=edge.pattern and abs(length-other[1])<.01 and abs(height-other[2])<.03]
            if options:
                match=min(options)[1];used.update((index,match));pairs.append((edge,free[match][0]))
        if not pairs:raise ValueError('No matching free edges found.')
        def apply():
            for first,second in pairs:doc.seams.append(Seam(first,second,True))
        self.commit(apply)
        return len(pairs)

    def add_pins(self,items):
        anchors=[Anchor(pattern,x,y,'PIN') for pattern,x,y in items]
        if not anchors:raise ValueError('No fabric to pin there.')
        return self.commit(lambda:self.document.anchors.extend(anchors))

    def pins_in_box(self,a,b,spacing=.02):
        x0,x1=sorted((a[0],b[0]));y0,y1=sorted((a[1],b[1]));items=[]
        columns=max(1,round((x1-x0)/spacing));rows=max(1,round((y1-y0)/spacing))
        for column in range(columns+1):
            for row in range(rows+1):
                point=(x0+(x1-x0)*column/columns,y0+(y1-y0)*row/rows)
                owner=next((pattern for pattern in reversed(self.document.patterns) if pattern.contains(point)),None)
                if owner:items.append((owner.id,*point))
        return self.add_pins(items)

    def add_anchor(self,point,kind='PIN',target=None,binding=None):
        if not self._selected:raise ValueError('Select a pattern for the anchor.')
        anchor=Anchor(self._selected,*point,kind,target,binding=binding)
        self.commit(lambda:self.document.anchors.append(anchor));return anchor

    def replace_document(self,document):
        self.undo_stack.append(self.document.dumps());self.undo_stack=self.undo_stack[-100:]
        self._undo_selections.append(self.get_selection_state());self._undo_selections=self._undo_selections[-100:]
        self.redo_stack.clear();self._redo_selections.clear()
        self._committed_selection=None;self.last_repairs=0
        self.document=document
        self.clear_selection()
        if document.patterns:self.select_piece(document.patterns[0].id)

    def history(self,redo=False):
        self.last_repairs=0
        source,target=(self.redo_stack,self.undo_stack) if redo else (self.undo_stack,self.redo_stack)
        sel_source,sel_target=(self._redo_selections,self._undo_selections) if redo else (self._undo_selections,self._redo_selections)
        if not source:return False
        committed=self._committed_selection
        current=self.document.dumps()
        target.append(current)
        sel_target.append(committed[1] if not redo and committed and committed[0]==current else self.get_selection_state())
        self._committed_selection=None
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
            new=Seam(a[0],b[0],seam.reverse,chain_a=tuple(a),chain_b=tuple(b),shrink=seam.shrink,active=seam.active)
            document.seams.append(new);seam_map[seam.id]=new.id
    for feature in source.features:
        if feature.get('seam') and feature['seam'] not in seam_map:continue
        new=copy.deepcopy(feature);new['id']=uid()
        if new.get('seam'):new['seam']=seam_map[new['seam']]
        if new.get('apex'):new['apex']=mapping.get(new['apex'],new['apex'])
        target.features.append(new)
