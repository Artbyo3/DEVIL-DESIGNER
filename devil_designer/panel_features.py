import bmesh
from .meshing import distance_to_segment
from . import tack_binding


def decorate_mesh(mesh,piece,coords,metadata):
    attr=mesh.attributes.new(name='dd_rest',type='FLOAT_VECTOR',domain='POINT')
    for item,point in zip(attr.data,coords):item.vector=(point[0],point[1],0)
    for name in ('dd_piece','.sculpt_face_set'):
        attr=mesh.attributes.new(name=name,type='INT',domain='FACE')
        for item in attr.data:item.value=piece+1
    if not metadata['slits']:return metadata
    bm=bmesh.new()
    try:
        bm.from_mesh(mesh);bm.verts.ensure_lookup_table()
        origin=bm.verts.layers.int.new('dd_source_index')
        for v in bm.verts:v[origin]=v.index
        rest=bm.verts.layers.float_vector.get('dd_rest')
        segments=[]
        for chain in metadata['slits']:
            segments.extend((coords[a],coords[b]) for a,b in zip(chain,chain[1:]))
        edges=[]
        for e in bm.edges:
            a,b=(tuple(v[rest])[:2] for v in e.verts)
            if any(distance_to_segment(a,p,q)<1e-6 and distance_to_segment(b,p,q)<1e-6 for p,q in segments):edges.append(e)
        if edges:bmesh.ops.split_edges(bm,edges=edges)
        bm.verts.index_update()
        mapping={}
        for v in bm.verts:mapping.setdefault(v[origin],[]).append(v.index)
        bm.to_mesh(mesh)
        metadata=dict(metadata)
        metadata['samples']={key:[[t,mapping[i][0]] for t,i in values] for key,values in metadata['samples'].items()}
        metadata['anchors']={key:mapping[i][0] for key,i in metadata['anchors'].items()}
        metadata['coords']=[tuple(v.vector)[:2] for v in mesh.attributes['dd_rest'].data]
        return metadata
    finally:bm.free()


def add_anchors(context,obj,doc,anchor_indices):
    from . import garment
    scene=context.scene
    tacks={}
    for anchor in doc.anchors:
        if anchor.id not in anchor_indices or anchor.kind!='TACK':continue
        binding=tack_binding.resolve_binding(context,scene.dd_avatar,anchor)
        empty=tack_binding.create_target(context,scene.dd_avatar,binding,garment.collection(scene),garment.tag)
        empty.empty_display_size=.008/garment.metres_per_unit(scene)
        tacks[anchor_indices[anchor.id]]=binding
    return tacks
