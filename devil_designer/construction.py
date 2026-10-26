import copy
import hashlib
import math
from . import curves

class ConstructionMixin:
    def preview_cut(self):
        preview=dict(pattern=self.selected,path=self.path,
                     fingerprint=hashlib.sha256(self.document.dumps().encode()).hexdigest(),
                     status='REFUSED',can_retry=False,crossing_paths=[],split_count=0,reason='')
        try:
            staged=self._cut_trial()
            staged.cut()
            self._validate_cut_trial(staged)
            preview.update(status='READY',reason='The selected cut needs no split. Use Cut.')
            return preview
        except ValueError as failure:
            preview['reason']=str(failure)
        try:
            staged,crossings,count=self._split_cut_trial()
            preview.update(status='SPLIT_REQUIRED',can_retry=True,crossing_paths=crossings,
                           split_count=count,reason='Split the crossing internal lines and retry the cut.')
        except ValueError as failure:
            preview['reason']=str(failure)
        return preview

    def retry_cut(self,preview):
        fingerprint=hashlib.sha256(self.document.dumps().encode()).hexdigest()
        if not isinstance(preview,dict) or any(preview.get(key)!=value for key,value in
                (('pattern',self.selected),('path',self.path),('fingerprint',fingerprint))):
            raise ValueError('The cut preview is out of date. Preview the selected cut again.')
        if not preview.get('can_retry') or preview.get('status')!='SPLIT_REQUIRED':
            raise ValueError('Preview a supported crossing cut before choosing Split and retry.')
        staged,crossings,count=self._split_cut_trial()
        def apply():
            self.document=staged.document
        document=self.document
        undo_stack=list(self.undo_stack);redo_stack=list(self.redo_stack);last_repairs=self.last_repairs
        try:
            changed=self.commit(apply)
        except Exception:
            self.document=document
            self.undo_stack=undo_stack;self.redo_stack=redo_stack;self.last_repairs=last_repairs
            raise
        self.path='OUTER';self.corner=None
        return changed

    def _cut_trial(self):
        staged=copy.copy(self)
        staged.document=copy.deepcopy(self.document)
        staged.undo_stack=[];staged.redo_stack=[]
        return staged

    def _validate_cut_trial(self,staged):
        if {seam.id for seam in staged.document.seams}!={seam.id for seam in self.document.seams}:
            raise ValueError('This cut would remove sewing. Unpair the affected sewing before retrying.')
        if {anchor.id for anchor in staged.document.anchors}!={anchor.id for anchor in self.document.anchors}:
            raise ValueError('This cut would remove pins or tacks. Move them before retrying.')
        staged.document.validate()
        original_seams={seam.id:seam for seam in self.document.seams}
        for seam in staged.document.seams:
            original=original_seams[seam.id]
            for side in (0,1):
                before=original.side(side);after=seam.side(side)
                old_points=self.document.edge_points(before[0])[:1]+self.document.edge_points(before[-1])[1:]
                new_points=staged.document.edge_points(after[0])[:1]+staged.document.edge_points(after[-1])[1:]
                if any(math.dist(old,new)>1e-7 for old,new in zip(old_points,new_points)) or not math.isclose(
                        self.document.chain_length(before),staged.document.chain_length(after),rel_tol=1e-7,abs_tol=1e-8):
                    raise ValueError('This cut would change a sewing range. Split and pair that sewing manually first.')

    def _split_cut_trial(self):
        from .core import EdgeRef,Path,uid
        staged=self._cut_trial()
        pattern=staged.document.find(staged.selected)
        if pattern is None or staged.path=='OUTER':
            raise ValueError('Select an internal line to split and retry the cut.')
        cutter=pattern.path(staged.path)
        if cutter.closed:
            raise ValueError('Split and retry supports open cuts, not closed shapes or holes.')
        if pattern.features:
            raise ValueError('This piece has construction features. Split its lines manually to preserve those relationships.')
        if any(vertex.incoming is not None or vertex.outgoing is not None for vertex in cutter.vertices):
            raise ValueError('Curved cuts need manual splitting. Split and retry supports straight segments only.')
        boundary=staged.document.edges(pattern.id)
        if any(min(curves.closest_fraction(staged.document.edge_curve(edge),point)[1] for edge in boundary)>1e-5
               for point in (cutter.points[0],cutter.points[-1])):
            raise ValueError('Split and retry needs a boundary-to-boundary cut. Extend the cut to the piece edges.')
        cut_segments=list(zip(cutter.points,cutter.points[1:]))
        for anchor in staged.document.anchors:
            if anchor.pattern==pattern.id and any(_cut_point_on_segment((anchor.x,anchor.y),start,end)
                                                  for start,end in cut_segments):
                raise ValueError('A pin or tack lies on the cut. Move it to one side before retrying.')
        crossings=[];split_count=0
        for path in list(pattern.paths):
            if path.id==cutter.id:continue
            intersections=[]
            for index,(start,end) in enumerate(zip(path.points,path.points[1:]+(path.points[:1] if path.closed else []))):
                for cut_start,cut_end in cut_segments:
                    fraction=_cut_intersection(start,end,cut_start,cut_end)
                    if fraction is not None:intersections.append(index+fraction)
            if not intersections:
                if any(vertex.incoming is not None or vertex.outgoing is not None for vertex in path.vertices):
                    raise ValueError('Curved internal paths need manual splitting before retrying this cut.')
                continue
            if path.closed or path.role=='HOLE':
                raise ValueError('The cut touches a closed internal shape or hole. Split that shape manually first.')
            if any(vertex.incoming is not None or vertex.outgoing is not None for vertex in path.vertices):
                raise ValueError('A crossing internal path is curved. Split that path manually first.')
            positions=sorted({round(value,10) for value in intersections if 1e-8<value<len(path.vertices)-1-1e-8})
            if not positions:continue
            crossings.append(dict(id=path.id,name=path.name))
            upper_fractions={}
            for position in reversed(positions):
                index=int(math.floor(position));fraction=position-index
                if fraction<1e-8 or fraction>1-1e-8:continue
                edge=staged.document.edge(pattern.id,index,path.id)
                staged.document.split_edge(edge,fraction/upper_fractions.get(index,1))
                upper_fractions[index]=fraction
            split_indices=[index for index,vertex in enumerate(path.vertices)
                           if 0<index<len(path.vertices)-1 and any(
                               _cut_point_on_segment((vertex.x,vertex.y),start,end) for start,end in cut_segments)]
            fragments=[];edge_map={};start_index=0
            for end_index in split_indices+[len(path.vertices)-1]:
                original=path.vertices[start_index:end_index+1]
                nodes=list(original)
                if start_index:
                    nodes[0]=copy.deepcopy(nodes[0]);nodes[0].id=uid()
                fragment=Path(path.name if not fragments else path.name+' split',nodes,False,path.role,
                              path.id if not fragments else uid())
                fragments.append(fragment)
                for original_start,original_end,new_start,new_end in zip(original,original[1:],nodes,nodes[1:]):
                    edge_map[(original_start.id,original_end.id)]=(fragment.id,new_start.id,new_end.id)
                start_index=end_index
            def remap(edge):
                if edge.pattern!=pattern.id or edge.path!=path.id:return edge
                identity,start,end=edge_map[(edge.start,edge.end)]
                return EdgeRef(pattern.id,start,end,edge.t0,edge.t1,identity)
            for seam in staged.document.seams:
                seam.chain_a=tuple(remap(edge) for edge in seam.side(0))
                seam.chain_b=tuple(remap(edge) for edge in seam.side(1))
                seam.a,seam.b=seam.chain_a[0],seam.chain_b[0]
            pattern.paths[pattern.paths.index(path):pattern.paths.index(path)+1]=fragments
            split_count+=len(fragments)-1
        if not crossings:
            raise ValueError('No supported crossing internal lines were found. Adjust the cut or split the shape manually.')
        staged.cut()
        self._validate_cut_trial(staged)
        return staged,crossings,split_count

    def unfold(self,edge,with_seam=False):
        from .core import clone_pattern,clone_relationships,uid,Seam,EdgeRef
        if edge.path!='OUTER':raise ValueError('Choose an outer straight fold edge.')
        p=self.document.find(edge.pattern); a,b=self.document.edge_vertices(edge)
        if a.outgoing is not None or b.incoming is not None:raise ValueError('Choose a straight fold edge.')
        axis=((a.x,a.y),(b.x,b.y))
        reflected=clone_pattern(p,reflection=axis)
        reflected.name=p.name+' mirrored'
        if with_seam:
            index=p.vertices.index(a)
            partner=EdgeRef(reflected.id,reflected.vertices[index].id,reflected.vertices[(index+1)%len(p.vertices)].id)
            def apply():
                self.document.patterns.append(reflected)
                clone_relationships(self.document,p,reflected)
                self.document.seams.append(Seam(edge,partner,False))
            self.commit(apply);self.selected=reflected.id;return
        def apply():
            index=p.vertices.index(a)
            order=[(index+1+i)%len(p.vertices) for i in range(len(p.vertices))]
            original=[p.vertices[i] for i in order]
            mirror=[reflected.vertices[i] for i in reversed(order)]
            for v in mirror:v.incoming,v.outgoing=v.outgoing,v.incoming
            original[-1].outgoing=curves.reflect(a.incoming,*axis,vector=True) if a.incoming else None
            original[0].incoming=curves.reflect(b.outgoing,*axis,vector=True) if b.outgoing else None
            p.vertices=original+mirror[1:-1]
            p.paths+=reflected.paths
            proxy=copy.copy(reflected);proxy.id=p.id;proxy.vertices=p.vertices;proxy.paths=p.paths;proxy.features=[]
            clone_relationships(self.document,p,proxy)
            p.features+=proxy.features
            p.features.append(dict(id=uid(),type='UNFOLD'))
        self.commit(apply);self.path='OUTER';self.corner=None

    def trace(self):
        from .core import Pattern,uid
        p=self.document.find(self.selected)
        if p is None or self.path=='OUTER':raise ValueError('Select a closed internal shape to trace.')
        source=p.path(self.path)
        if not source.closed:raise ValueError('Trace a closed internal shape as a pattern.')
        nodes=copy.deepcopy(source.vertices)
        for v in nodes:v.id=uid();v.x+=.03;v.y-=.03
        result=Pattern(source.name+' traced',nodes,preset=p.preset,wrap_radius=p.wrap_radius,mesh_density=p.mesh_density)
        self.commit(lambda:self.document.patterns.append(result));self.selected,self.path,self.corner=result.id,'OUTER',None

    def cut(self):
        from .core import Pattern,Vertex,uid,EdgeRef
        p=self.document.find(self.selected)
        if p is None or self.path=='OUTER':raise ValueError('Select an internal line or shape to cut.')
        path=p.path(self.path)
        if path.closed:
            return self.commit(lambda:setattr(path,'role','HOLE'))
        endpoints=[path.points[0],path.points[-1]]
        hits=[]
        for point in endpoints:
            options=[(edge,*curves.closest_fraction(self.document.edge_curve(edge),point)) for edge in self.document.edges(p.id)]
            hit=min(options,key=lambda value:value[2])
            hits.append(hit)
        if any(distance>1e-5 for _,_,distance in hits):
            return self.commit(lambda:setattr(path,'role','SLIT'))
        def apply():
            original_id=p.id
            ends=[]
            for point in endpoints:
                edges=self.document.edges(p.id)
                edge,t,distance=min(((e,*curves.closest_fraction(self.document.edge_curve(e),point)) for e in edges),key=lambda value:value[2])
                a,b=self.document.edge_vertices(edge)
                node=a if t<1e-5 else b if t>1-1e-5 else self.document.split_edge(edge,t)
                ends.append(node)
            a,b=ends
            if a.id==b.id:raise ValueError('Cut endpoints must be distinct.')
            nodes=p.vertices;ia,ib=nodes.index(a),nodes.index(b)
            def route(start,end):
                result=[nodes[start]]
                while start!=end:
                    start=(start+1)%len(nodes);result.append(nodes[start])
                return result
            left,right=route(ia,ib),route(ib,ia)
            inside=path.vertices[1:-1]
            originals={a.id:copy.deepcopy(a),b.id:copy.deepcopy(b)}
            backwards=copy.deepcopy(list(reversed(inside)))
            for v in backwards:v.incoming,v.outgoing=v.outgoing,v.incoming
            p.vertices=left+backwards
            a.incoming=path.vertices[0].outgoing
            b.outgoing=path.vertices[-1].incoming
            new_nodes=[];mapping={}
            for v in right+inside:
                if v in (a,b) or v in inside:
                    other=copy.deepcopy(originals.get(v.id,v));other.id=uid();mapping[v.id]=other.id;new_nodes.append(other)
                else:new_nodes.append(v)
            new=Pattern(p.name+' cut',new_nodes,preset=p.preset,wrap_radius=p.wrap_radius,mesh_density=p.mesh_density)
            next(v for v in new.vertices if v.id==mapping[a.id]).outgoing=path.vertices[0].outgoing
            next(v for v in new.vertices if v.id==mapping[b.id]).incoming=path.vertices[-1].incoming
            cut_map={path.vertices[0].id:mapping[a.id],path.vertices[-1].id:mapping[b.id]}
            cut_map.update({v.id:mapping[v.id] for v in inside})
            remaining=[q for q in p.paths if q.id!=path.id]
            p.paths=[]
            for q in remaining:
                if all(p.contains(pt) for pt in q.outline()):p.paths.append(q)
                elif all(new.contains(pt) for pt in q.outline()):new.paths.append(q)
                else:raise ValueError('The cut crosses another internal shape. Split that shape first.')
            self.document.patterns.append(new)
            def remap(edge):
                if edge.pattern!=original_id:return edge
                if edge.path==path.id:
                    return EdgeRef(new.id,cut_map[edge.start],cut_map[edge.end],edge.t0,edge.t1,'OUTER')
                for candidate in (p,new):
                    start=mapping.get(edge.start,edge.start) if candidate is new else edge.start
                    end=mapping.get(edge.end,edge.end) if candidate is new else edge.end
                    result=EdgeRef(candidate.id,start,end,edge.t0,edge.t1,edge.path)
                    try:self.document.edge_vertices(result);return result
                    except ValueError:pass
                return edge
            for seam in self.document.seams:
                seam.chain_a=tuple(remap(e) for e in seam.side(0));seam.chain_b=tuple(remap(e) for e in seam.side(1))
                seam.a,seam.b=seam.chain_a[0],seam.chain_b[0]
            for anchor in self.document.anchors:
                if anchor.pattern==p.id and not p.contains((anchor.x,anchor.y)):anchor.pattern=new.id
        result=self.commit(apply);self.path='OUTER';self.corner=None;return result

    def dart(self,edge,start,end,apex):
        from .core import Vertex,EdgeRef,Seam,uid
        if edge.path!='OUTER':raise ValueError('Place the dart base on an outer edge.')
        start,end=sorted((start,end))
        if end-start<.001:raise ValueError('Give the dart a nonzero mouth width.')
        p=self.document.find(edge.pattern)
        if not p.contains(apex):raise ValueError('Place the dart apex inside the pattern.')
        def apply():
            a,b=self.document.edge_vertices(edge)
            base_b=b if end>1-1e-8 else self.document.split_edge(edge,end)
            left=EdgeRef(p.id,a.id,base_b.id)
            base_a=a if start<1e-8 else self.document.split_edge(left,start/end)
            middle=Vertex(*apex)
            middle_index=p.vertices.index(base_a)+1
            base_a.outgoing=None;base_b.incoming=None
            p.vertices.insert(middle_index,middle)
            leg_a=EdgeRef(p.id,base_a.id,middle.id);leg_b=EdgeRef(p.id,middle.id,base_b.id)
            self.document.prune_seams()
            seam=Seam(leg_a,leg_b,True)
            self.document.seams.append(seam)
            p.features.append(dict(id=uid(),type='DART',seam=seam.id,apex=middle.id))
        result=self.commit(apply);self.selected,self.path,self.corner=p.id,'OUTER',None;return result


def _cut_point_on_segment(point,start,end):
    delta=curves.sub(end,start);squared=sum(value*value for value in delta)
    if squared<1e-20:return math.dist(point,start)<1e-8
    fraction=sum(value*direction for value,direction in zip(curves.sub(point,start),delta))/squared
    return -1e-8<=fraction<=1+1e-8 and math.dist(point,curves.mix(start,end,fraction))<1e-8


def _cut_intersection(start,end,cut_start,cut_end):
    direction=curves.sub(end,start);cut_direction=curves.sub(cut_end,cut_start)
    determinant=direction[0]*cut_direction[1]-direction[1]*cut_direction[0]
    if abs(determinant)<1e-12:
        if any(_cut_point_on_segment(point,start,end) for point in (cut_start,cut_end)) or any(
                _cut_point_on_segment(point,cut_start,cut_end) for point in (start,end)):
            raise ValueError('An internal line overlaps the cut. Move or split the overlapping line manually.')
        return None
    offset=curves.sub(cut_start,start)
    fraction=(offset[0]*cut_direction[1]-offset[1]*cut_direction[0])/determinant
    cut_fraction=(offset[0]*direction[1]-offset[1]*direction[0])/determinant
    if -1e-8<=fraction<=1+1e-8 and -1e-8<=cut_fraction<=1+1e-8:
        return max(0,min(1,fraction))
    return None


def chain_range(document,chain,start,end):
    from .core import EdgeRef
    if not 0<=start<=1 or not 0<=end<=1 or abs(start-end)<1e-8:raise ValueError('Use a nonzero sewing range between 0 and 100 percent.')
    reverse=start>end;low,high=sorted((start,end));total=document.chain_length(chain)
    at=0;result=[]
    for edge in chain:
        length=document.edge_length(edge);lo=max(low*total,at);hi=min(high*total,at+length)
        if hi-lo>1e-10:
            a=(lo-at)/length;b=(hi-at)/length
            result.append(EdgeRef(edge.pattern,edge.start,edge.end,edge.t0+(edge.t1-edge.t0)*a,
                                  edge.t0+(edge.t1-edge.t0)*b,edge.path))
        at+=length
    if reverse:result=[EdgeRef(e.pattern,e.start,e.end,e.t1,e.t0,e.path) for e in reversed(result)]
    return result


def path_range(document,start,end):
    from .core import EdgeRef
    edge_a,t_a=start;edge_b,t_b=end
    if edge_a.pattern!=edge_b.pattern or edge_a.path!=edge_b.path:raise ValueError('Each free sewing side must follow one connected path.')
    if edge_a.full()==edge_b.full():return [EdgeRef(edge_a.pattern,edge_a.start,edge_a.end,t_a,t_b,edge_a.path)]
    edges=document.edges(edge_a.pattern,edge_a.path)
    ia,ib=edges.index(edge_a.full()),edges.index(edge_b.full())
    p=document.find(edge_a.pattern).path(edge_a.path)
    closed=edge_a.path=='OUTER' or p.closed
    if not closed and ib<ia:
        forward=path_range(document,end,start)
        return [EdgeRef(e.pattern,e.start,e.end,e.t1,e.t0,e.path) for e in reversed(forward)]
    result=[EdgeRef(edge_a.pattern,edge_a.start,edge_a.end,t_a,1,edge_a.path)]
    i=(ia+1)%len(edges)
    while i!=ib:result.append(edges[i]);i=(i+1)%len(edges)
    result.append(EdgeRef(edge_b.pattern,edge_b.start,edge_b.end,0,t_b,edge_b.path))
    return [e for e in result if abs(e.t1-e.t0)>1e-8]
