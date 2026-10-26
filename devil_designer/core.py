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

@dataclass
class Vertex:
    x: float
    y: float
    id: str = field(default_factory=uid)

@dataclass
class Pattern:
    name: str
    vertices: list
    id: str = field(default_factory=uid)

    @property
    def points(self):
        return [(v.x,v.y) for v in self.vertices]

@dataclass(frozen=True)
class EdgeRef:
    pattern: str
    start: str
    end: str

@dataclass
class Seam:
    a: EdgeRef
    b: EdgeRef
    reverse: bool = True
    id: str = field(default_factory=uid)

class Document:
    def __init__(self, patterns=None, seams=None):
        self.patterns = patterns or []
        self.seams = seams or []

    def dumps(self):
        return json.dumps({"version":2,"patterns":[
            {"id":p.id,"name":p.name,"vertices":[{"x":float(v.x),"y":float(v.y),"id":v.id} for v in p.vertices]}
            for p in self.patterns],"seams":[
            {"id":s.id,"a":vars(s.a),"b":vars(s.b),"reverse":s.reverse}
            for s in self.seams]},separators=(",",":"),allow_nan=False)

    @classmethod
    def loads(cls, value):
        if not value:
            return cls()
        try:
            data = json.loads(value)
            if data["version"] not in (1,2):
                raise ValueError("Unsupported pattern document version.")
            patterns,ids = [],set()
            for item in data["patterns"]:
                vertices = [Vertex(float(v["x"]),float(v["y"]),v["id"]) for v in item["vertices"]]
                p = Pattern(item["name"],vertices,item["id"])
                if not isinstance(p.name,str) or not p.name.strip():
                    raise ValueError("Pattern names must contain text.")
                for identity in [p.id]+[v.id for v in vertices]:
                    if not isinstance(identity,str) or not identity or identity in ids:
                        raise ValueError("Pattern and corner IDs must be unique.")
                    ids.add(identity)
                validate_polygon(p.points)
                patterns.append(p)
            document = cls(patterns)
            if data["version"] == 2:
                for item in data["seams"]:
                    seam = Seam(EdgeRef(**item["a"]),EdgeRef(**item["b"]),item["reverse"],item["id"])
                    if not isinstance(seam.id,str) or not seam.id or seam.id in ids or not isinstance(seam.reverse,bool):
                        raise ValueError("Invalid seam identity or direction.")
                    ids.add(seam.id)
                    document.seams.append(seam)
            document.validate_seams()
            return document
        except (KeyError,TypeError,json.JSONDecodeError,OverflowError) as exc:
            raise ValueError("Cannot read the saved pattern document.") from exc

    def find(self, identity):
        return next((p for p in self.patterns if p.id == identity),None)

    def edge(self, pattern, index):
        p = self.find(pattern)
        if p is None:
            raise ValueError("The pattern no longer exists.")
        return EdgeRef(p.id,p.vertices[index].id,p.vertices[(index+1)%len(p.vertices)].id)

    def edge_points(self, edge):
        p = self.find(edge.pattern)
        if p:
            for i,v in enumerate(p.vertices):
                if v.id == edge.start and p.vertices[(i+1)%len(p.vertices)].id == edge.end:
                    return p.points[i],p.points[(i+1)%len(p.vertices)]
        raise ValueError("A sewn edge was removed. Pair the replacement edge again.")

    def validate_seams(self):
        used = set()
        for seam in self.seams:
            if seam.a.pattern == seam.b.pattern:
                raise ValueError("Pair edges from two different patterns.")
            for edge in (seam.a,seam.b):
                self.edge_points(edge)
                if edge in used:
                    raise ValueError("An edge can belong to only one seam.")
                used.add(edge)

    def prune_seams(self):
        valid = []
        for seam in self.seams:
            try:
                self.edge_points(seam.a)
                self.edge_points(seam.b)
                valid.append(seam)
            except ValueError:
                pass
        self.seams = valid

class Session:
    """One completed edit per undo step. Invalid edits leave no history."""
    def __init__(self, document=None):
        self.document = document or Document()
        self.selected = self.corner = None
        self.undo_stack,self.redo_stack = [],[]

    def commit(self, operation):
        before = self.document.dumps()
        try:
            operation()
            for p in self.document.patterns:
                validate_polygon(p.points)
            self.document.prune_seams()
            self.document.validate_seams()
        except Exception:
            self.document = Document.loads(before)
            raise
        if self.document.dumps() != before:
            self.undo_stack.append(before)
            self.undo_stack = self.undo_stack[-100:]
            self.redo_stack.clear()
            return True
        return False

    def add(self, points):
        validate_polygon(points)
        names = {p.name for p in self.document.patterns}
        index = 1
        while f"Pattern {index:02d}" in names:
            index += 1
        p = Pattern(f"Pattern {index:02d}",[Vertex(*point) for point in points])
        self.commit(lambda: self.document.patterns.append(p))
        self.selected,self.corner = p.id,None

    def move(self, points):
        p = self.document.find(self.selected)
        if p is None or len(points) != len(p.vertices):
            raise ValueError("Select a pattern to edit.")
        validate_polygon(points)
        def apply():
            for v,point in zip(p.vertices,points):
                v.x,v.y = point
        return self.commit(apply)

    def duplicate(self):
        source = self.document.find(self.selected)
        if source is None:
            return False
        p = Pattern(source.name+" copy",[Vertex(v.x+.03,v.y-.03) for v in source.vertices])
        self.commit(lambda: self.document.patterns.append(p))
        self.selected,self.corner = p.id,None
        return True

    def delete(self):
        p = self.document.find(self.selected)
        if p is None:
            return False
        if self.corner is not None:
            i = self.corner
            self.commit(lambda: p.vertices.pop(i))
            self.corner = None
        else:
            self.commit(lambda: self.document.patterns.remove(p))
            self.selected = None
        return True

    def sew(self, a, b):
        self.document.edge_points(a)
        self.document.edge_points(b)
        seam = Seam(a,b)
        return self.commit(lambda: self.document.seams.append(seam))

    def remove_seam(self, identity):
        seam = next((s for s in self.document.seams if s.id==identity),None)
        if seam is None:
            raise ValueError("That seam no longer exists.")
        return self.commit(lambda: self.document.seams.remove(seam))

    def reverse_seam(self, identity):
        seam = next((s for s in self.document.seams if s.id==identity),None)
        if seam is None:
            raise ValueError("That seam no longer exists.")
        return self.commit(lambda: setattr(seam,'reverse',not seam.reverse))

    def history(self, redo=False):
        source,target = (self.redo_stack,self.undo_stack) if redo else (self.undo_stack,self.redo_stack)
        if not source:
            return False
        target.append(self.document.dumps())
        self.document = Document.loads(source.pop())
        self.corner = None
        if not self.document.find(self.selected):
            self.selected = None
        return True
