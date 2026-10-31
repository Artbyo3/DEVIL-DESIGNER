import bmesh
from mathutils import Matrix
from .meshing import distance_to_segment
from .presets import resolve_preset
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


def apply_presets(obj,cloth,pieces,custom_presets=None):
    for key,group_name,property_name,base_names in [
        ('structural','DD Structural','vertex_group_structural_stiffness',('tension','compression')),
        ('shear','DD Shear','vertex_group_shear_stiffness',('shear',)),
        ('bending','DD Bending','vertex_group_bending',('bending',))]:
        values=[resolve_preset(preset,custom_presets)[key] for _,_,preset in pieces]
        low,high=min(values),max(values)
        for base in base_names:
            setattr(cloth.settings,base+'_stiffness',low)
            setattr(cloth.settings,base+'_stiffness_max',high)
        group=obj.vertex_groups.new(name=group_name)
        for ids,_,preset in pieces:
            val=resolve_preset(preset,custom_presets)[key]
            weight=(val-low)/(high-low) if high>low else 1
            group.add(ids,weight,'REPLACE')
        setattr(cloth.settings,property_name,group.name)
    area_total=sum(area for _,area,_ in pieces)
    cloth.settings.mass=sum(area*resolve_preset(preset,custom_presets)['density'] for _,area,preset in pieces)/max(area_total,1e-12)
    obj['dd_preset_note']='Structural, shear and bending vary by piece. Native cloth mass density is an area-weighted shared value.'


def add_anchors(context,obj,cloth,doc,anchor_indices):
    from . import garment
    scene=context.scene
    if not doc.anchors:return
    bindings={anchor.id:tack_binding.resolve_binding(context,scene.dd_avatar,anchor)
              for anchor in doc.anchors if anchor.kind=='TACK' and anchor.id in anchor_indices}
    group=obj.vertex_groups.get('DD Pins') or obj.vertex_groups.new(name='DD Pins')
    for anchor in doc.anchors:
        if anchor.id not in anchor_indices:continue
        index=anchor_indices[anchor.id];group.add([index],1,'REPLACE')
        if anchor.kind!='TACK':continue
        avatar=scene.dd_avatar
        empty=tack_binding.create_target(context,avatar,bindings[anchor.id],garment.collection(scene),garment.tag)
        empty.empty_display_size=.008/garment.metres_per_unit(scene)
        hook=obj.modifiers.new('DD Tack','HOOK');hook.object=empty
        hook.vertex_indices_set([index]);hook.falloff_type='NONE'
        hook.matrix_inverse=Matrix.Translation(-obj.data.vertices[index].co)
        obj.modifiers.move(len(obj.modifiers)-1,0)
    cloth.settings.vertex_group_mass=group.name
