import copy
import math


def pair_for(document,identity):
    return next((pair for pair in document.linked_pairs if identity in pair['members']),None)


def validate_pairs(document):
    if not isinstance(document.linked_pairs,list):raise ValueError('Invalid linked editing pairs.')
    used=set()
    for pair in document.linked_pairs:
        if not isinstance(pair,dict) or set(pair)!={'members','enabled','transform','mapping'}:
            raise ValueError('Invalid linked editing pair.')
        members=pair['members'];transform=pair['transform'];mapping=pair['mapping']
        if not isinstance(members,list) or len(members)!=2 or any(not isinstance(member,str) or not document.find(member) or member in used for member in members) or members[0]==members[1]:
            raise ValueError('Linked editing requires two unique existing pieces.')
        used.update(members)
        if type(pair['enabled']) is not bool or not isinstance(transform,list) or len(transform)!=2 or any(type(value) not in (int,float) or not math.isfinite(value) for value in transform):
            raise ValueError('Invalid linked editing transform.')
        if not isinstance(mapping,dict) or any(not isinstance(key,str) or not isinstance(value,str) or not key or not value for key,value in mapping.items()) or len(set(mapping.values()))!=len(mapping):
            raise ValueError('Invalid linked editing point correspondence.')


def _geometry(pattern):
    return [(identity,closed,role,[(vertex.id,vertex.x,vertex.y,vertex.incoming,vertex.outgoing,vertex.point_type) for vertex in nodes])
            for identity,nodes,closed,role in pattern.loops()]


def _translation(before,after):
    if not before.vertices or not after.vertices:return None
    old=_geometry(before);new=_geometry(after)
    if [(identity,closed,role,len(nodes)) for identity,closed,role,nodes in old]!=[(identity,closed,role,len(nodes)) for identity,closed,role,nodes in new]:return None
    delta=(after.vertices[0].x-before.vertices[0].x,after.vertices[0].y-before.vertices[0].y)
    for previous,current in zip(old,new):
        for source,target in zip(previous[3],current[3]):
            if source[0]!=target[0] or source[3:]!=target[3:] or math.dist((target[1]-source[1],target[2]-source[2]),delta)>1e-9:return None
    return delta


def _mirror(document,pair,source_id):
    from .core import Path,uid
    first,second=pair['members'];forward=source_id==first
    source=document.find(source_id);target=document.find(second if forward else first)
    mapping=pair['mapping'] if forward else {value:key for key,value in pair['mapping'].items()}
    horizontal,vertical=pair['transform'];vertical=vertical if forward else -vertical
    def identity(value):
        if value not in mapping:mapping[value]=uid()
        return mapping[value]
    def vertices(nodes):
        result=copy.deepcopy(nodes)
        for vertex in result:
            vertex.id=identity(vertex.id);vertex.x=horizontal-vertex.x;vertex.y+=vertical
            for key in ('incoming','outgoing'):
                handle=getattr(vertex,key)
                if handle is not None:setattr(vertex,key,(-handle[0],handle[1]))
        return result
    target.vertices=vertices(source.vertices)
    target.paths=[Path(path.name,vertices(path.vertices),path.closed,path.role,identity(path.id)) for path in source.paths]
    pair['mapping']=mapping if forward else {value:key for key,value in mapping.items()}


def synchronize(document,before,selected):
    document.linked_pairs=[pair for pair in document.linked_pairs if all(document.find(member) for member in pair['members'])]
    for pair in document.linked_pairs:
        previous=next((old for old in before.linked_pairs if old['members']==pair['members']),None)
        if not pair['enabled'] or previous is None or not previous['enabled']:continue
        patterns=[document.find(member) for member in pair['members']]
        originals=[before.find(member) for member in pair['members']]
        changed=[_geometry(old)!=_geometry(new) for old,new in zip(originals,patterns)]
        if not any(changed):continue
        translations=[_translation(old,new) for old,new in zip(originals,patterns)]
        for index,delta in enumerate(translations):
            if delta is not None:
                pair['transform'][0]+=delta[0]
                pair['transform'][1]+=delta[1]*(1 if index else -1)
        shaped=[index for index in range(2) if changed[index] and translations[index] is None]
        if shaped:
            source=next((index for index in shaped if patterns[index].id==selected),shaped[0])
            _mirror(document,pair,patterns[source].id)


def split_partner(document,edge,fraction,vertex):
    from .core import EdgeRef
    pair=pair_for(document,edge.pattern)
    if pair is None or not pair['enabled'] or getattr(document,'_splitting_link',False):return
    forward=pair['members'][0]==edge.pattern
    mapping=pair['mapping'] if forward else {value:key for key,value in pair['mapping'].items()}
    if edge.start not in mapping or edge.end not in mapping:return
    other=pair['members'][1 if forward else 0]
    partner=EdgeRef(other,mapping[edge.start],mapping[edge.end],path=mapping.get(edge.path,edge.path))
    document._splitting_link=True
    try:created=document.split_edge(partner,fraction)
    finally:document._splitting_link=False
    if forward:pair['mapping'][vertex.id]=created.id
    else:pair['mapping'][created.id]=vertex.id


def _pair_transform(source,target):
    source_points=source.outline();target_points=target.outline()
    source_center=[(min(point[axis] for point in source_points)+max(point[axis] for point in source_points))/2 for axis in (0,1)]
    target_center=[(min(point[axis] for point in target_points)+max(point[axis] for point in target_points))/2 for axis in (0,1)]
    return [source_center[0]+target_center[0],target_center[1]-source_center[1]]


def _new_pair(document,source,target,mapping=None):
    if mapping is None:
        mapping={source_vertex.id:target_vertex.id for source_vertex,target_vertex in zip(source.vertices,target.vertices)}
        for source_path,target_path in zip(source.paths,target.paths):
            mapping[source_path.id]=target_path.id
            mapping.update((source_vertex.id,target_vertex.id) for source_vertex,target_vertex in zip(source_path.vertices,target_path.vertices))
    pair=dict(members=[source.id,target.id],enabled=True,transform=_pair_transform(source,target),mapping=mapping)
    document.linked_pairs.append(pair)
    return pair


def clone_twin(session,as_back=False):
    from .core import arrangement_record,clone_pattern
    source=session.document.find(session.selected)
    if source is None:raise ValueError('Select a piece to clone as a linked twin.')
    previous=pair_for(session.document,source.id)
    if previous and previous['enabled']:raise ValueError('This piece already has a twin. Use Linked twin On/Off.')
    points=source.outline();right=max(point[0] for point in points)
    horizontal=right+max(point[0] for pattern in session.document.patterns for point in pattern.outline())+.03
    target=clone_pattern(source,reflection=((horizontal/2,0),(horizontal/2,1)))
    target.name=source.name+' twin';target.arrangement=None;target.panel_origin=None;target.placement_mode='LAYOUT'
    if as_back and source.arrangement:
        if source.arrangement['point']!='front':raise ValueError('Clone as Back requires a front arrangement point.')
        target.arrangement=arrangement_record(source.arrangement['volume'],'back',source.arrangement['flat'],version=source.arrangement['version'])
    def apply():
        if previous:session.document.linked_pairs.remove(previous)
        session.document.patterns.append(target)
        mapping={key:value for key,value in target._id_map.items() if key!=source.id}
        _new_pair(session.document,source,target,mapping)
    session.commit(apply)
    session.clear_selection();session.selected=target.id
    return target


def toggle_link(session):
    document=session.document;source=document.find(session.selected)
    if source is None:raise ValueError('Select a piece for linked editing.')
    pair=pair_for(document,source.id)
    def apply():
        nonlocal pair
        others=[document.find(identity) for identity in session.selected_patterns if identity!=source.id]
        replacement=others[0] if len(others)==1 and len(session.selected_patterns)==2 else None
        if replacement and (pair is None or replacement.id not in pair['members']):
            target_pair=pair_for(document,replacement.id)
            if pair and pair['enabled'] or target_pair and target_pair['enabled']:
                raise ValueError('Switch Linked twin Off before linking a piece to a different twin.')
            for previous in (pair,target_pair):
                if previous:document.linked_pairs.remove(previous)
            pair=_new_pair(document,source,replacement)
        elif pair and pair['enabled']:
            pair['enabled']=False
            return
        if pair is None:
            raise ValueError('Select two pieces to apply linked editing; the active piece replaces the other outline.')
        pair['enabled']=True
        target=document.find(next(member for member in pair['members'] if member!=source.id))
        pair['transform']=_pair_transform(source,target)
        _mirror(document,pair,source.id)
        try:document.validate_seams()
        except ValueError as exc:raise ValueError('Relinking would invalidate existing sewing. Unsew affected edges first.') from exc
    return session.commit(apply)


def duplicate_pairs(document,pattern_map,id_map):
    for pair in list(document.linked_pairs):
        if not all(member in pattern_map for member in pair['members']):continue
        cloned=copy.deepcopy(pair)
        cloned['members']=[pattern_map[member] for member in pair['members']]
        cloned['mapping']={id_map[key]:id_map[value] for key,value in pair['mapping'].items() if key in id_map and value in id_map}
        cloned['transform'][0]+=.06
        document.linked_pairs.append(cloned)
