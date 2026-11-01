from pathlib import Path
import json
import re
import math
from datetime import datetime, timezone
import bpy
from mathutils import Matrix
from .core import Document
from . import garment,live_panels


def directory(scene,create=False):
    if scene.dd_library_dir:
        path=Path(bpy.path.abspath(scene.dd_library_dir)).expanduser()
    else:
        path=Path(bpy.utils.user_resource('DATAFILES',path='devil_designer/garments',create=False))
    if create:path.mkdir(parents=True,exist_ok=True)
    return path


def entries(scene):
    path=directory(scene)
    if path.exists() and not path.is_dir():raise NotADirectoryError('Choose a folder for the garment library, not a file.')
    return sorted(path.glob('*.garment.json'),key=lambda p:p.name.casefold()) if path.exists() else []


def scale_document(doc,factor):
    for pair in doc.linked_pairs:pair['transform']=[value*factor for value in pair['transform']]
    for p in doc.patterns:
        for _,nodes,_,_ in p.loops():
            for v in nodes:
                v.x*=factor;v.y*=factor
                if v.incoming is not None:v.incoming=tuple(x*factor for x in v.incoming)
                if v.outgoing is not None:v.outgoing=tuple(x*factor for x in v.outgoing)
        p.wrap_radius*=factor
        if p.panel_origin:p.panel_origin['bounds']=[value*factor for value in p.panel_origin['bounds']]
    for a in doc.anchors:a.x*=factor;a.y*=factor
    if doc.uv_layout:
        doc.uv_layout['origin']=[x*factor for x in doc.uv_layout['origin']]
        doc.uv_layout['scale']*=factor
    doc.validate()


def preview(path):
    result=dict(name=path.name.removesuffix('.garment.json'),loops=[],pieces=0,seams=0,body='Unspecified body',date='',tags=[],error='')
    try:
        if path.stat().st_size>10_000_000:raise ValueError('Design exceeds the 10 MB limit.')
        data=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data,dict) or data.get('format')!='devil-designer-garment' or type(data.get('version')) is not int or data['version'] not in (1,2):
            raise ValueError('Unsupported garment library format.')
        document=Document.loads(json.dumps(data['document']))
        if not document.patterns:raise ValueError('Design has no pattern pieces.')
        metadata=data.get('library',{})
        if not isinstance(metadata,dict):metadata={}
        name=data.get('name',result['name'])
        tags=metadata.get('tags',[])
        height=data.get('body_height_m',0)
        body=metadata.get('body','')
        if not isinstance(body,str):body=''
        if type(height) in (int,float) and math.isfinite(height) and height>0:
            body=(body or 'Body')+f' | {height*100:.0f} cm'
        result.update(name=name if isinstance(name,str) else result['name'],
                      loops=[pattern.outline() for pattern in document.patterns],
                      pieces=len(document.patterns),seams=len(document.seams),body=body or result['body'],
                      date=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).strftime('%Y-%m-%d'),
                      tags=[tag for tag in tags if isinstance(tag,str)][:20] if isinstance(tags,list) else [])
        timestamp=metadata.get('saved_at')
        if isinstance(timestamp,str):
            try:result['date']=datetime.fromisoformat(timestamp).strftime('%Y-%m-%d')
            except ValueError:pass
        captured=metadata.get('thumbnail')
        if isinstance(captured,list) and len(captured)==len(document.patterns) and all(
                isinstance(loop,list) and len(loop)>=3 and all(isinstance(point,list) and len(point)==2 and
                all(type(value) in (int,float) and math.isfinite(value) for value in point) for point in loop) for loop in captured):
            result['loops']=captured
    except (OSError,ValueError,TypeError,KeyError,AttributeError,OverflowError) as exc:
        result['error']='Cannot preview: '+str(exc)
    return result


def save(context,name,tags=()):
    scene=context.scene
    safe=re.sub(r'[^A-Za-z0-9_-]+','-',name.strip()).strip('-')[:80]
    if not safe:raise ValueError('Enter a garment name using letters or numbers.')
    doc=live_panels.capture(context);doc.validate()
    if not doc.patterns:raise ValueError('Create a garment before saving it to the library.')
    data=dict(format='devil-designer-garment',version=2,name=name.strip(),document=json.loads(doc.dumps()),panels=[])
    data['library']=dict(saved_at=datetime.now(timezone.utc).isoformat(),
                         body=scene.dd_avatar.name if scene.dd_avatar else '',
                         tags=list(dict.fromkeys(tag.strip()[:40] for tag in tags if tag.strip()))[:20],
                         thumbnail=[pattern.outline() for pattern in doc.patterns])
    if scene.dd_avatar:
        low,high=garment.bounds(scene.dd_avatar)
        data['body_height_m']=(high.z-low.z)*garment.metres_per_unit(scene)
        identities={pattern.id for pattern in doc.patterns}
        for panel in garment.generated(scene,'panel'):
            if panel.get('dd_pattern_id') not in identities:continue
            if doc.find(panel['dd_pattern_id']).placement_mode!='LEGACY':continue
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
        if not isinstance(data,dict) or data.get('format')!='devil-designer-garment' or type(data.get('version')) is not int or data['version'] not in (1,2):raise ValueError('Unsupported garment library format.')
        doc=Document.loads(json.dumps(data['document']))
        if not doc.patterns:raise ValueError('This garment design has no patterns.')
        name=data.get('name',path.stem)
        if not isinstance(name,str):raise ValueError('Invalid stored garment name.')
        height=data.get('body_height_m',0)
        if type(height) not in (int,float) or not math.isfinite(height) or height<0:raise ValueError('Invalid stored body height.')
        settings=data.get('settings',{})
        if not isinstance(settings,dict):raise ValueError('Invalid stored garment settings.')
        supported=('dd_spacing','dd_quality','dd_frames','dd_self_collision','dd_pin_top','dd_weld_distance','dd_thickness')
        float_bounds={'dd_spacing':(.003,.2),'dd_weld_distance':(.0001,.05),'dd_thickness':(0,.01)}
        settings={key:value for key,value in settings.items() if key in supported}
        for key,value in settings.items():
            prop=scene.bl_rna.properties[key]
            valid=type(value) is bool if prop.type=='BOOLEAN' else type(value) is int if prop.type=='INT' else type(value) in (int,float)
            if prop.type!='BOOLEAN':
                lower,upper=prop.hard_min,prop.hard_max
                if key in float_bounds:
                    lower=min(lower,float_bounds[key][0]);upper=max(upper,float_bounds[key][1])
            if not valid or prop.type!='BOOLEAN' and (not math.isfinite(value) or not lower<=value<=upper):
                raise ValueError('Invalid stored garment setting: '+key+'.')
        poses=data.get('panels',[])
        if not isinstance(poses,list):raise ValueError('Invalid stored garment placement.')
        identities={pattern.id for pattern in doc.patterns}
        placed=set()
        for pose in poses:
            if not isinstance(pose,dict):raise ValueError('Invalid stored garment placement.')
            identity=pose.get('pattern')
            matrix=pose.get('orientation');position=pose.get('position')
            if not isinstance(identity,str) or identity in placed:
                raise ValueError('Invalid stored garment placement pattern.')
            if identity in identities:placed.add(identity)
            if not isinstance(matrix,list) or len(matrix)!=3 or any(not isinstance(row,list) or len(row)!=3 for row in matrix) or not isinstance(position,list) or len(position)!=3:
                raise ValueError('Invalid stored garment placement.')
            if any(type(value) not in (int,float) or not math.isfinite(value) or abs(value)>3.402823466e38 for row in matrix+[position] for value in row):
                raise ValueError('Invalid stored garment placement.')
        avatar=scene.dd_avatar
        if avatar:
            low,high=garment.bounds(avatar)
            if scene.dd_library_refit and height>1e-6:
                factor=(high.z-low.z)*garment.metres_per_unit(scene)/height
                if not .05<factor<20:raise ValueError('Avatar scale differs too much. Correct the scene/body units before refitting.')
                scale_document(doc,factor)
        placements={}
        if avatar:
            for pose in poses:
                if pose['pattern'] not in identities:continue
                if doc.find(pose['pattern']).placement_mode!='LEGACY':continue
                matrix=Matrix(pose['orientation']).to_4x4()
                translation=tuple(low[axis]+(high[axis]-low[axis])*pose['position'][axis] for axis in range(3))
                if any(not math.isfinite(value) or abs(value)>3.402823466e38 for value in translation):raise ValueError('Invalid stored garment placement.')
                matrix.translation=translation
                placements[pose['pattern']]=matrix
        incoming=doc.dumps()
        previous={key:getattr(scene,key) for key in (*supported,'dd_document','dd_library_name')}
        try:
            for key,value in settings.items():setattr(scene,key,value)
            scene.dd_library_name=name
            scene.dd_document=incoming
            panels=garment.build_panels(context)
            for obj in panels:
                matrix=placements.get(obj['dd_pattern_id'])
                if matrix is not None:obj.matrix_world=matrix
            context.view_layer.update()
            return garment.document(scene)
        except Exception:
            for key,value in previous.items():setattr(scene,key,value)
            raise
    except UnicodeError as exc:raise ValueError('Cannot read this garment design: invalid UTF-8 text.') from exc
    except (KeyError,TypeError,AttributeError,OverflowError,json.JSONDecodeError,OSError) as exc:raise ValueError('Cannot read this garment design.') from exc
