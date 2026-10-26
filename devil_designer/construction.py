"""Transactional pattern construction on editable paths."""
import copy
import math
from . import curves

class ConstructionMixin:
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
        result=Pattern(source.name+' traced',nodes,preset=p.preset)
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
            new=Pattern(p.name+' cut',new_nodes,preset=p.preset)
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
