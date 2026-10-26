"""True-size body reference from the selected avatar's evaluated mesh.

Projection preserves individual triangles and concave gaps (arms/legs), rather
than replacing the body with a convex hull. No images or scene objects are created.
"""
import math

VIEWS = ('FRONT','BACK','LEFT','RIGHT')


def project_vertices(vertices,view='FRONT'):
    if view not in VIEWS:
        raise ValueError('Unknown body reference view.')
    if not vertices:
        return [],None
    if any(not math.isfinite(v) for p in vertices for v in p):
        raise ValueError('Body contains non-finite coordinates.')
    axis=0 if view in {'FRONT','BACK'} else 1
    sign=-1 if view in {'BACK','LEFT'} else 1
    horizontal=[sign*p[axis] for p in vertices]
    center=(min(horizontal)+max(horizontal))/2
    floor=min(p[2] for p in vertices)
    points=[(x-center,p[2]-floor) for x,p in zip(horizontal,vertices)]
    low=(min(p[0] for p in points),0.0)
    high=(max(p[0] for p in points),max(p[1] for p in points))
    return points,(low,high)


def torso_alignment(bounds,pattern_points):
    if not bounds or not pattern_points:
        return 0.0,0.0
    low,high=bounds
    height=high[1]-low[1]
    cx=(min(p[0] for p in pattern_points)+max(p[0] for p in pattern_points))/2
    cy=(min(p[1] for p in pattern_points)+max(p[1] for p in pattern_points))/2
    return cx,cy-(low[1]+height*(.72 if height>1 else .68))


class BodyReference:
    def __init__(self):
        self.key=None
        self.vertices=[]
        self.triangles=[]
        self.bounds=None
        self.revision=0
        self.error=''

    def refresh(self,context,force=False):
        scene=context.scene
        body=scene.dd_avatar
        transform=tuple(v for row in body.matrix_world for v in row) if body else ()
        shape_keys=body.data.shape_keys if body and body.type=='MESH' else None
        shapes=tuple(k.value for k in shape_keys.key_blocks) if shape_keys else ()
        rigs=[m.object for m in body.modifiers if m.type=='ARMATURE' and m.object] if body else []
        poses=tuple(tuple(v for row in bone.matrix for v in row) for rig in rigs for bone in rig.pose.bones)
        rig_transforms=tuple(tuple(v for row in rig.matrix_world for v in row) for rig in rigs)
        mesh_key=(body.data.as_pointer(),len(body.data.vertices),len(body.data.polygons)) if body and body.type=='MESH' else None
        key=(body.as_pointer() if body else None,mesh_key,scene.dd_reference_view,
             scene.unit_settings.scale_length,transform,shapes,poses,rig_transforms)
        if key==self.key and not force:
            return False
        self.key=key
        self.vertices,self.triangles,self.bounds=[],[],None
        self.error=''
        self.revision+=1
        if body is None:
            return True
        if body.type!='MESH' or body not in list(scene.objects):
            self.error='Choose a body mesh in this scene.'
            return True
        evaluated=None
        try:
            depsgraph=context.evaluated_depsgraph_get()
            evaluated=body.evaluated_get(depsgraph)
            mesh=evaluated.to_mesh()
            if mesh is None or not mesh.polygons:
                raise ValueError('The selected body has no surface faces.')
            mesh.calc_loop_triangles()
            unit=max(1e-6,scene.unit_settings.scale_length)
            matrix=evaluated.matrix_world
            world=[tuple((matrix @ v.co)*unit) for v in mesh.vertices]
            used=sorted({i for tri in mesh.loop_triangles for i in tri.vertices})
            mapping={index:new for new,index in enumerate(used)}
            self.vertices,self.bounds=project_vertices([world[i] for i in used],scene.dd_reference_view)
            self.triangles=[tuple(mapping[i] for i in tri.vertices) for tri in mesh.loop_triangles]
            if not self.bounds or self.bounds[1][1]<=1e-8:
                raise ValueError('The body has no usable height in this view.')
        except (ValueError,RuntimeError,ReferenceError) as exc:
            self.vertices,self.triangles,self.bounds=[],[],None
            self.error=str(exc)
        finally:
            if evaluated is not None:
                evaluated.to_mesh_clear()
        return True

    def corners(self,x=0,y=0):
        if not self.bounds:
            return []
        low,high=self.bounds
        return [(low[0]+x,low[1]+y),(high[0]+x,high[1]+y)]
