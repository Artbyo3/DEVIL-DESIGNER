"""Portable local garment designs: editable source, UV layout, and body-relative placement."""
from pathlib import Path
import json
import re
import math
import bpy
from mathutils import Matrix
from .core import Document
from . import garment


def directory(scene,create=False):
    if scene.dd_library_dir:
        path=Path(bpy.path.abspath(scene.dd_library_dir)).expanduser()
    else:
        path=Path(bpy.utils.user_resource('DATAFILES',path='devil_designer/garments',create=False))
    if create:path.mkdir(parents=True,exist_ok=True)
    return path


def entries(scene):
    path=directory(scene)
    return sorted(path.glob('*.garment.json'),key=lambda p:p.name.casefold()) if path.exists() else []


def scale_document(doc,factor):
    for p in doc.patterns:
        for _,nodes,_,_ in p.loops():
            for v in nodes:
                v.x*=factor;v.y*=factor
                if v.incoming is not None:v.incoming=tuple(x*factor for x in v.incoming)
                if v.outgoing is not None:v.outgoing=tuple(x*factor for x in v.outgoing)
        p.wrap_radius*=factor
    for a in doc.anchors:a.x*=factor;a.y*=factor
    if doc.uv_layout:
        doc.uv_layout['origin']=[x*factor for x in doc.uv_layout['origin']]
        doc.uv_layout['scale']*=factor
    doc.validate()


def save(context,name):
    scene=context.scene
    safe=re.sub(r'[^A-Za-z0-9_-]+','-',name.strip()).strip('-')[:80]
    if not safe:raise ValueError('Enter a garment name using letters or numbers.')
    doc=garment.document(scene);doc.validate()
    if not doc.patterns:raise ValueError('Create a garment before saving it to the library.')
    data=dict(format='devil-designer-garment',version=1,name=name.strip(),document=json.loads(doc.dumps()),panels=[])
    if scene.dd_avatar:
        low,high=garment.bounds(scene.dd_avatar)
        data['body_height_m']=(high.z-low.z)*garment.metres_per_unit(scene)
        for panel in garment.generated(scene,'panel'):
            point=panel.matrix_world.translation
            data['panels'].append(dict(pattern=panel['dd_pattern_id'],position=[(point[i]-low[i])/max(1e-6,high[i]-low[i]) for i in range(3)],
                orientation=[list(row) for row in panel.matrix_world.to_3x3()]))
    data['settings']={key:getattr(scene,key) for key in ('dd_spacing','dd_quality','dd_frames','dd_self_collision','dd_pin_top','dd_weld_distance','dd_thickness')}
    output=directory(scene,True)/(safe+'.garment.json')
    temporary=output.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,indent=2,allow_nan=False),encoding='utf-8')
    temporary.replace(output)
    scene.dd_library_selected=entries(scene).index(output)
    return output


def load(context,index):
    scene=context.scene
    files=entries(scene)
    if not files:raise ValueError('The local garment library is empty.')
    if not 0<=index<len(files):raise ValueError('Choose a valid library item.')
    path=files[index]
    if path.stat().st_size>10_000_000:raise ValueError('This garment file exceeds the 10 MB design limit.')
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
        if data.get('format')!='devil-designer-garment' or data.get('version')!=1:raise ValueError('Unsupported garment library format.')
        doc=Document.loads(json.dumps(data['document']))
        avatar=scene.dd_avatar
        if avatar:
            low,high=garment.bounds(avatar)
            if scene.dd_library_refit and data.get('body_height_m',0)>1e-6:
                factor=(high.z-low.z)*garment.metres_per_unit(scene)/data['body_height_m']
                if not .05<factor<20:raise ValueError('Avatar scale differs too much. Correct the scene/body units before refitting.')
                scale_document(doc,factor)
        for pose in data.get('panels',[]):
            matrix=pose.get('orientation');position=pose.get('position')
            if not isinstance(matrix,list) or len(matrix)!=3 or any(len(row)!=3 for row in matrix) or len(position)!=3 or any(not math.isfinite(float(v)) for row in matrix for v in row) or any(not math.isfinite(float(v)) for v in position):
                raise ValueError('Invalid stored garment placement.')
            pose['orientation']=[[float(v) for v in row] for row in matrix]
            pose['position']=[float(v) for v in position]
        previous=scene.dd_document
        previous_spacing=scene.dd_spacing
        stored_spacing=float(data.get('settings',{}).get('dd_spacing',scene.dd_spacing))
        if not math.isfinite(stored_spacing) or not .003<=stored_spacing<=.2:raise ValueError('Invalid stored mesh spacing.')
        scene.dd_spacing=stored_spacing
        scene.dd_document=doc.dumps()
        try:panels=garment.build_panels(context)
        except Exception:scene.dd_document=previous;scene.dd_spacing=previous_spacing;raise
        if avatar:
            by_id={o['dd_pattern_id']:o for o in panels}
            for pose in data.get('panels',[]):
                obj=by_id.get(pose['pattern'])
                if obj:
                    matrix=Matrix(pose['orientation']).to_4x4()
                    matrix.translation=tuple(low[i]+(high[i]-low[i])*pose['position'][i] for i in range(3))
                    obj.matrix_world=matrix
        for key,value in data.get('settings',{}).items():
            if key in {'dd_quality','dd_frames','dd_self_collision','dd_pin_top','dd_weld_distance','dd_thickness'}:setattr(scene,key,value)
        scene.dd_library_name=data.get('name',path.stem)
        context.view_layer.update()
        return garment.document(scene)
    except (KeyError,TypeError,json.JSONDecodeError,OSError) as exc:raise ValueError('Cannot read this garment design.') from exc
