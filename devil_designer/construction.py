import copy
import hashlib
import math
from . import curves

class ConstructionMixin:
    def knife_preview(self,points):
        points=[(point.x,point.y) if hasattr(point,'x') else tuple(point) for point in points]
        selected=set(self.selected_patterns)
        if self.selected:selected.add(self.selected)
        previews=[]
        for pattern in self.document.patterns:
            if selected and pattern.id not in selected:continue
            hits=[];reason='';clipped=[]
            try:
                if len(points)<2:raise ValueError('Place at least two cut points.')
                if any(not all(math.isfinite(value) for value in point) for point in points):
                    raise ValueError('Cut points must have finite coordinates.')
                for index,(start,end) in enumerate(zip(points,points[1:])):
                    if math.dist(start,end)<1e-8:raise ValueError('Cut points must be distinct.')
                    for edge in self.document.edges(pattern.id):
                        control=self.document.edge_curve(edge)
                        for fraction,point,parameter in _knife_edge_hits(control,start,end):
                            position=index+fraction
                            if not any(abs(position-other[0])<1e-7 and math.dist(point,other[1])<1e-7 for other in hits):
                                table,cumulative=curves.arc_table(control)
                                lower=max(index for index,(value,_) in enumerate(table) if value<=parameter)
                                arc_fraction=(cumulative[lower]+curves.integral(control,table[lower][0],parameter))/cumulative[-1]
                                hits.append((position,point,edge,arc_fraction))
                hits.sort(key=lambda hit:hit[0])
                if len(hits)!=2:
                    raise ValueError(f'Cut must cross the outline exactly twice; found {len(hits)} intersections.')
                first,last=hits
                if math.dist(first[1],last[1])<1e-7:raise ValueError('Cut crossings must be distinct.')
                clipped=[first[1]]+[point for index,point in enumerate(points) if first[0]+1e-7<index<last[0]-1e-7]+[last[1]]
                for index,(start,end) in enumerate(zip(points,points[1:])):
                    for other in range(index+2,len(points)-1):
                        if _cut_intersection(start,end,points[other],points[other+1]) is not None:
                            raise ValueError('The cut line must not cross or touch itself.')
                    if index+2<len(points) and _cut_point_on_segment(points[index+2],start,end):
                        raise ValueError('The cut line must not double back.')
                    bounds=sorted({0.0,1.0,*[hit[0]-index for hit in hits if index<hit[0]<index+1]})
                    for lower,upper in zip(bounds,bounds[1:]):
                        position=index+(lower+upper)/2
                        inside=pattern.contains(curves.mix(start,end,(lower+upper)/2))
                        if inside!=(first[0]<position<last[0]):
                            raise ValueError('Cut must cross into and out of the piece, not just touch its outline.')
                for path in pattern.paths:
                    if path.role!='HOLE':continue
                    for edge in self.document.edges(pattern.id,path.id):
                        if any(_knife_edge_hits(self.document.edge_curve(edge),start,end) for start,end in zip(clipped,clipped[1:])):
                            raise ValueError('Knife cuts cannot cross holes. Use the existing internal path Cut instead.')
            except ValueError as failure:
                reason=str(failure)
            previews.append(dict(pattern=pattern.id,points=clipped,hits=[hit[1] for hit in hits],
                                 boundary=[(hit[2],hit[3]) for hit in hits],reason=reason))
        return previews

    def knife_cut(self,points,with_seam=True):
        from .core import Path,Vertex,Seam,EdgeRef
        previews=self.knife_preview(points)
        selected=bool(self.selected_patterns or self.selected)
        invalid=[preview for preview in previews if preview['reason'] and (selected or len(preview['hits'])>=2)]
        if invalid:
            pattern=self.document.find(invalid[0]['pattern'])
            raise ValueError(pattern.name+': '+invalid[0]['reason'])
        targets=[preview for preview in previews if not preview['reason']]
        if not targets:raise ValueError('No piece is fully crossed. Cut must cross the outline exactly twice.')
        staged=self._cut_trial();results=set()
        if staged.document.uv_layout is None:
            outline=[point for pattern in staged.document.patterns for point in pattern.outline()]
            minimum=[min(point[axis] for point in outline) for axis in (0,1)]
            extent=max(max(point[axis] for point in outline)-minimum[axis] for axis in (0,1))
            staged.document.uv_layout=dict(origin=minimum,scale=max(extent,.001))
        for preview in targets:
            pattern=staged.document.find(preview['pattern']);name=pattern.name
            boundaries={};cut_points=list(preview['points'])
            for endpoint,(edge,fraction) in sorted(enumerate(preview['boundary']),key=lambda item:item[1][1],reverse=True):
                current,upper=boundaries.get(edge,(edge,1.0))
                start,end=staged.document.edge_vertices(current)
                relative=fraction/upper
                node=start if relative<1e-8 else end if relative>1-1e-8 else staged.document.split_edge(current,relative)
                cut_points[0 if endpoint==0 else -1]=(node.x,node.y)
                if node.id not in (start.id,end.id):boundaries[edge]=(EdgeRef(pattern.id,start.id,node.id),fraction)
            path=Path('Knife cut',[Vertex(*point) for point in cut_points],False)
            pattern.paths.append(path)
            staged._selected=pattern.id;staged.path=path.id
            staged.cut()
            other=staged.document.patterns[-1]
            pattern.name=name+' 1';other.name=name+' 2'
            results.update((pattern.id,other.id))
            if with_seam:
                chains=[]
                segments=list(zip(cut_points,cut_points[1:]))
                for half in (pattern,other):
                    chain=[]
                    for edge in staged.document.edges(half.id):
                        start,end=staged.document.edge_points(edge)
                        if any((math.dist(start,a)<1e-6 and math.dist(end,b)<1e-6) or
                               (math.dist(start,b)<1e-6 and math.dist(end,a)<1e-6) for a,b in segments):
                            chain.append(edge)
                    if len(chain)!=len(segments):raise ValueError('Unable to pair the new cut edges; no cut was applied.')
                    first_index=next(index for index,edge in enumerate(chain) if not any(other_edge.end==edge.start for other_edge in chain))
                    chain=chain[first_index:]+chain[:first_index]
                    chains.append(chain)
                staged.document.seams.append(Seam(chains[0][0],chains[1][0],True,chain_a=tuple(chains[0]),chain_b=tuple(chains[1])))
        staged.document.validate()
        changed=self.commit(lambda:setattr(self,'document',staged.document))
        self.clear_selection();self.selected_patterns=results;self._selected=next(iter(results))
        return changed

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
        staged.selected_patterns=set(self.selected_patterns)
        staged.selected_points=set(self.selected_points)
        staged.point_selection=list(self.point_selection)
        staged.undo_stack=[];staged.redo_stack=[]
        staged._undo_selections=[];staged._redo_selections=[]
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
        result=Pattern(source.name+' traced',nodes,preset=p.preset,wrap_radius=p.wrap_radius,mesh_density=p.mesh_density,fabric_override=getattr(p,'fabric_override',False))
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
            if p.panel_origin is None:
                p.panel_origin=dict(source=p.id,bounds=[min(point[0] for point in p.points),min(point[1] for point in p.points),
                                                       max(point[0] for point in p.points),max(point[1] for point in p.points)])
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
            new=Pattern(p.name+' cut',new_nodes,preset=p.preset,wrap_radius=p.wrap_radius,mesh_density=p.mesh_density,fabric_override=getattr(p,'fabric_override',False),
                        placement_mode=p.placement_mode,arrangement=copy.deepcopy(p.arrangement),panel_origin=copy.deepcopy(p.panel_origin))
            new.panel_origin['source']=p.id
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


def _knife_edge_hits(control,start,end):
    direction=curves.sub(end,start);squared=sum(value*value for value in direction)
    def distance(point):
        offset=curves.sub(point,start)
        return offset[0]*direction[1]-offset[1]*direction[0]
    values=[distance(point) for point in control]
    tolerance=1e-11*max(1,math.sqrt(squared))
    if max(abs(value) for value in values)<tolerance:
        projected=[sum(value*axis for value,axis in zip(curves.sub(point,start),direction))/squared for point in control]
        if max(projected)>=0 and min(projected)<=1:
            raise ValueError('Cut overlaps an outline edge. Move the line across the outline instead.')
        return []
    cubic=-values[0]+3*values[1]-3*values[2]+values[3]
    quadratic=3*values[0]-6*values[1]+3*values[2]
    linear=-3*values[0]+3*values[1]
    boundaries=[0.0,1.0]
    if abs(cubic)>1e-15:
        discriminant=4*quadratic*quadratic-12*cubic*linear
        if discriminant>=0:
            boundaries.extend(root for root in ((-2*quadratic-math.sqrt(discriminant))/(6*cubic),
                                                 (-2*quadratic+math.sqrt(discriminant))/(6*cubic)) if 0<root<1)
    elif abs(quadratic)>1e-15:
        root=-linear/(2*quadratic)
        if 0<root<1:boundaries.append(root)
    boundaries.sort();roots=[]
    for lower,upper in zip(boundaries,boundaries[1:]):
        lower_value=distance(curves.evaluate(control,lower));upper_value=distance(curves.evaluate(control,upper))
        if abs(lower_value)<tolerance:roots.append(lower)
        if abs(upper_value)<tolerance:roots.append(upper)
        if lower_value*upper_value<0:
            for iteration in range(48):
                middle=(lower+upper)/2;value=distance(curves.evaluate(control,middle))
                if lower_value*value<=0:upper=middle
                else:lower=middle;lower_value=value
            roots.append((lower+upper)/2)
    hits=[]
    for root in roots:
        point=curves.evaluate(control,root)
        fraction=sum(value*axis for value,axis in zip(curves.sub(point,start),direction))/squared
        if -1e-8<=fraction<=1+1e-8 and not any(math.dist(point,other[1])<1e-8 for other in hits):
            hits.append((max(0,min(1,fraction)),point,root))
    return hits


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


def sew_reverse(document,chain_a,chain_b,scene_reverse=True):
    side_a=[chain_a] if hasattr(chain_a,'full') else list(chain_a)
    side_b=[chain_b] if hasattr(chain_b,'full') else list(chain_b)
    if not side_a or not side_b:return bool(scene_reverse)
    pa0=document.edge_point(side_a[0],side_a[0].t0)
    pa1=document.edge_point(side_a[-1],side_a[-1].t1)
    pb0=document.edge_point(side_b[0],side_b[0].t0)
    pb1=document.edge_point(side_b[-1],side_b[-1].t1)
    same_dir=((pa1[0]-pa0[0])*(pb1[0]-pb0[0])+(pa1[1]-pa0[1])*(pb1[1]-pb0[1]))>=0
    return not scene_reverse if same_dir else bool(scene_reverse)
