import copy
import math
import bpy
from . import curves
from .canvas import Rect
from .ui_system import TRANSFORM_FRAME_PAD,TRANSFORM_KNOB_OFFSET,TRANSFORM_HIT_RADIUS,TRANSFORM_PIVOT_HIT_RADIUS
from .core import update_auto_handles
from .construction import chain_range,path_range,sew_reverse,ordered_sewing_chain

class DesignTools:
    def initialize_design(self):
        self.hit_path='OUTER';self.hit_segment=None;self.hit_handle=None
        self.handle_preview=None;self.selected_anchor=None
        self.free_clicks=[];self.dart_base=[];self.pending_place=None;self.pending_tack=None
        self.library_items=[]
        self.cut_preview=None
        self.trace_points=None
        self.trace_drag=None
        self.mn_sewing=False
        self.mn_chain=[]
        self.mn_first=None
        self.pending_join=None
        self.pen_mode=None
        self.error_rect=None
        self.message_rect=None
        self.pen_points=[]

    def design_hit(self):
        self.hit_path='OUTER';self.hit_segment=None;self.hit_handle=None
        c=self.canvas_layout.canvas;s=self.canvas_layout.scale
        candidates=[]
        if self.session.selected and self.session.corner is not None:
            candidates.append((self.session.selected,self.session.path,self.session.corner))
        for pid,path_id,idx in self.session.selected_points:
            if (pid,path_id,idx) not in candidates:candidates.append((pid,path_id,idx))
        if self.session.segment:
            seg=self.session.segment
            p_seg=self.session.document.find(seg.pattern)
            if p_seg:
                try:
                    nodes=p_seg.path(seg.path).vertices
                    for vid in (seg.start,seg.end):
                        idx=next((i for i,nd in enumerate(nodes) if nd.id==vid),None)
                        if idx is not None and (seg.pattern,seg.path,idx) not in candidates:
                            candidates.append((seg.pattern,seg.path,idx))
                except (ValueError,KeyError):pass
        for pid,path_id,idx in candidates:
            p_cand=self.session.document.find(pid)
            if not p_cand:continue
            try:
                v=p_cand.path(path_id).vertices[idx]
                if getattr(v,'point_type','CORNER')=='AUTO':continue
                for name in ('incoming','outgoing'):
                    vector=getattr(v,name)
                    if vector and math.dist(self.view.screen(curves.add((v.x,v.y),vector),c),self.pointer)<8*s:
                        self.hit_path=path_id;self.hit_handle=name
                        return p_cand,idx
            except (ValueError,IndexError):pass
        for p in reversed(self.session.document.patterns):
            for path,nodes,_,_ in p.loops():
                for index,v in enumerate(nodes):
                    if math.dist(self.view.screen((v.x,v.y),c),self.pointer)<9*s:
                        self.hit_path=path;return p,index
        edge=self.design_hit_edge()
        if edge:
            self.hit_path=edge.path;self.hit_segment=edge
            return self.session.document.find(edge.pattern),None
        point=self.view.world(self.pointer,c)
        for p in reversed(self.session.document.patterns):
            if p.contains(point):return p,None
        return None,None

    def design_hit_edge(self):
        point=self.view.world(self.pointer,self.canvas_layout.canvas)
        best=None;distance=11*self.canvas_layout.scale/self.view.zoom
        for p in reversed(self.session.document.patterns):
            for path,_,_,_ in p.loops():
                for edge in self.session.document.edges(p.id,path):
                    t,d=curves.closest_fraction(self.session.document.edge_curve(edge),point)
                    if d<distance:best,distance=edge,d
        return best

    def sync_selection(self):
        p=self.session.document.find(self.session.selected)
        if p and self.session.corner is not None:
            v=p.path(self.session.path).vertices[self.session.corner]
            self._scene.dd_point_x,self._scene.dd_point_y=v.x,v.y
        if self.session.segment:
            try:self._scene.dd_segment_length=self.session.document.edge_length(self.session.segment)
            except ValueError:self.session.segment=None

    def select_anchor(self, anchor):
        self.seam_selected = None
        self.selected_anchor = anchor.id
        self.session.selected = anchor.pattern
        self.session.corner = None
        self.session.path = 'OUTER'
        self.session.segment = None
        self.session.point_selection = []

    def refresh_library(self):
        from . import library
        self.library_error=''
        try:self.library_items=library.entries(self._scene)
        except OSError as exc:
            self.library_items=[];self.library_error=str(exc);self.message='Library unavailable: '+str(exc)
        previous=self.library_previews
        updated={}
        for path in self.library_items:
            try:
                stat=path.stat()
                signature=(stat.st_mtime_ns,stat.st_size)
            except OSError:
                signature=None
            cached=previous.get(path)
            if not cached or cached['signature']!=signature:
                cached=dict(signature=signature,**library.preview(path))
            updated[path]=cached
        self.library_previews=updated
        self._scene.dd_library_selected=min(self._scene.dd_library_selected,max(0,len(self.library_items)-1))

    def design_action(self,action):
        scene=self._scene;doc=self.session.document;p=doc.find(self.session.selected)
        def operation():
            if action.startswith('STARTER_'):
                from .starters import STARTER_GENERATORS
                label,generator=STARTER_GENERATORS[action][:2]
                measurements = None
                if hasattr(self, 'reference') and getattr(self.reference, 'measurements', None):
                    measurements = self.reference.measurements
                elif scene.dd_avatar:
                    from .measurements import estimate_body_measurements
                    measurements = estimate_body_measurements(scene.dd_avatar, scene)
                starter_doc = generator(measurements, getattr(self.session.document, 'preset', 'COTTON'))
                self.session.undo_stack.append(scene.dd_document)
                self.session.redo_stack.clear()
                self.clear_interaction_references()
                self.session.document = starter_doc
                self.session.selected = starter_doc.patterns[0].id if starter_doc.patterns else None
                self.session.path = 'OUTER'
                self.session.corner = None
                self.session.segment = None
                self.session.point_selection = []
                self.persist()
                if scene.dd_avatar:
                    self.reveal_3d()
                self.update_reference(bpy.context, align=False)
                self.fit()
                self.choose_tool('SELECT')
                self.message = f"{label} starter created. Pre-sewn and placed on avatar." if scene.dd_avatar else f"{label} starter created in a standard size. Choose your avatar under Garment, Body to fit and place it."
                return
            elif action == 'DEMO_PANEL':
                ref_bounds = getattr(self.reference, 'bounds', None) if hasattr(self, 'reference') else None
                ref_h = (ref_bounds[1][1] - ref_bounds[0][1]) if ref_bounds else 0.0
                ref_y = scene.dd_reference_y
                ref_x = scene.dd_reference_x
                base_y = (ref_y + max(0.20, ref_h * 0.50)) if ref_h > 0 else 0.0
                base_x = ref_x if ref_h > 0 else 0.0
                self.session.add([(base_x - .20, base_y), (base_x + .20, base_y),
                                  (base_x + .20, base_y + .45), (base_x - .20, base_y + .45)])
                self.session.document.find(self.session.selected).name = 'Basic panel'
                self.fit()
            elif action=='POINT_APPLY':
                point=(scene.dd_point_x,scene.dd_point_y)
                if self.draft or self.tool in {'POLYGON','INTERNAL'} and self.session.corner is None:
                    if not self.draft or math.dist(self.draft[-1],point)>.000001:self.draft.append(point)
                elif p and self.session.corner is not None:
                    points=p.path(self.session.path).points;points[self.session.corner]=point;self.session.move(points)
                else:raise ValueError('Select a point or a drawing tool for numeric entry.')
            elif action=='CURVE':
                new_t=self.session.curve_point()
                self.message=f"Point type: {new_t.title()}."
            elif action=='SPLIT':
                if not self.session.segment:raise ValueError('Select a segment to split.')
                self.session.split_segment(self.session.segment);self.session.segment=None
            elif action=='SET_LENGTH':
                if not self.session.segment:raise ValueError('Select a segment to set its length.')
                self.session.set_length(self.session.segment,scene.dd_segment_length)
            elif action=='MERGE':self.session.merge_points(self.session.point_selection)
            elif action == 'DUPLICATE':
                if not p and not self.session.selected_patterns:raise ValueError('Select a pattern to duplicate.')
                self.session.duplicate()
                self.message = 'Pattern duplicated (Shift D).'
            elif action == 'FLIP_H':
                if not p and not self.session.selected_patterns and not self.session.selected_points and self.session.corner is None:raise ValueError('Select a piece or points to flip.')
                self.session.flip_horizontal()
                self.message = 'Pattern flipped horizontally.'
            elif action == 'FLIP_V':
                if not p and not self.session.selected_patterns and not self.session.selected_points and self.session.corner is None:raise ValueError('Select a piece or points to flip.')
                self.session.flip_vertical()
                self.message = 'Pattern flipped vertically.'
            elif action == 'SELECT_CONNECTED_PATH':
                self.session.select_connected('PATH')
                self.sync_selection()
                self.message = 'Connected path selected.'
            elif action == 'SELECT_CONNECTED_SEWN':
                self.session.select_connected('SEWN')
                self.sync_selection()
                self.message = 'Sewn pieces selected.'
            elif action == 'SELECT_INVERT':
                self.session.invert_selection()
                self.sync_selection()
                self.message = f"{self.session.acquisition_target.title()} selection inverted."
            elif action == 'SELECT_ALL':
                self.session.select_all()
                self.sync_selection()
                self.message = 'All items selected.'
            elif action == 'SELECT_CLEAR':
                self.session.clear_selection()
                self.sync_selection()
                self.message = 'Selection cleared.'
            elif action == 'SELECT_BOX':
                self.choose_tool('SELECT')
                c = self.canvas_layout.canvas
                self.gesture = dict(mode='BOX_SELECT', start=self.pointer,
                                    world_start=self.view.world(self.pointer, c),
                                    shift=False, alt=False)
                self.message = 'Drag to box select. Left-to-right encloses, right-to-left crosses.'
            elif action == 'SELECT_LASSO':
                self.choose_tool('SELECT')
                c = self.canvas_layout.canvas
                w = self.view.world(self.pointer, c)
                self.gesture = dict(mode='LASSO_SELECT', points=[w], screen_points=[self.pointer],
                                    shift=False, alt=False, rule='ENCLOSE')
                self.message = 'Drag lasso to select. Escape cancels.'
            elif action == 'TRANSFORM_MOVE':
                self.start_transform('MOVE')
            elif action == 'TRANSFORM_ROTATE':
                self.start_transform('ROTATE')
            elif action == 'TRANSFORM_SCALE':
                self.start_transform('SCALE')
            elif action == 'TRANSFORM_SET_PIVOT':
                self.start_set_pivot()
            elif action == 'TRANSFORM_RESET_PIVOT':
                self.session.reset_pivot()
                self.message = 'Pivot reset to selection center.'
            elif action == 'BEND_EDGE':
                self.start_bend_edge()
            elif action == 'APPLY_MISMATCH':
                self.commit_preflighted_transform()
            elif action == 'CANCEL_TRANSFORM':
                self.cancel_transform()
            elif action == 'INCLUDE_SEWN':
                pending = getattr(self, 'pending_transform', None)
                if not pending:return
                self.pending_transform = None
                self.card_kind = None
                self.session.select_connected(mode='SEWN')
                if self.stage_transform(pending.get('op', 'MOVE'), pending.get('param'), pending.get('pivot')):return
            elif action == 'CONVERT_AUTO':
                self.convert_pending_auto_points()
                return
            elif action in {'UNFOLD','MIRROR_SEW'}:
                if not self.session.segment and p:
                    self.session.segment = self.session.document.edge(p.id, 0)
                if not self.session.segment:raise ValueError('Select a straight outer fold edge.')
                self.session.unfold(self.session.segment,action=='MIRROR_SEW');self.session.segment=None
            elif action=='CUT':
                self.cut_preview=self.session.preview_cut()
                if self.cut_preview['status']=='READY':
                    self.session.cut()
                    self.cut_preview=None
                else:
                    self.show_card('CUT_RECOVERY')
                    self.message=self.cut_preview['reason']
                    return
            elif action=='CUT_RETRY':
                self.session.retry_cut(self.cut_preview)
                self.cut_preview=None
                self.card_kind=None
            elif action=='TRACE':self.session.trace()
            elif action=='PLACE':
                if not p:raise ValueError('Select the pattern you want to place.')
                if p.placement_mode!='LEGACY':
                    self.reveal_3d();self.message='Click an arrangement point to place this piece. Right-click a point for Arrange flat.';return
                self.pending_place=p.id;self.message='Click the avatar in the 3D view to place this pattern. Escape cancels.';return
            elif action=='REMOVE_ANCHOR':
                anchor=next((a for a in doc.anchors if a.id==self.selected_anchor),None)
                if anchor is None:raise ValueError('Select a pin or tack using K or T.')
                self.session.commit(lambda:doc.anchors.remove(anchor));self.selected_anchor=None
            elif action=='CHAIN_CLEAR':
                self.free_clicks=[];self.pending_edge=None;self.mn_chain=[];self.mn_first=None
            elif action.startswith('LIBRARY_'):
                from . import library
                self.refresh_library()
                if action=='LIBRARY_SAVE':
                    library.save(bpy.context,scene.dd_library_name,getattr(self,'library_tags','').split(','))
                    self.library_previews={}
                    self.refresh_library()
                elif action=='LIBRARY_LOAD':
                    chosen=getattr(self,'library_load_path',None)
                    if chosen is not None:
                        if chosen not in self.library_items:raise ValueError('This garment is no longer available.')
                        if self.library_previews[chosen]['signature']!=self.library_load_signature:
                            raise ValueError('This saved design changed. Preview it again before loading.')
                        scene.dd_library_selected=self.library_items.index(chosen)
                    before=scene.dd_document
                    scene['dd_backup_document']=before
                    loaded=library.load(bpy.context,scene.dd_library_selected)
                    metadata=self.library_previews[self.library_items[scene.dd_library_selected]]
                    self.library_tags=', '.join(metadata['tags'])
                    self.library_load_path=None
                    self.clear_interaction_references()
                    self.session.undo_stack.append(before);self.session.redo_stack.clear()
                    self.session.document=loaded;self.session.selected=loaded.patterns[0].id if loaded.patterns else None
                    self.session.path='OUTER';self.session.corner=None;self.session.segment=None
                    self.session.point_selection=[]
                    self._stored=scene.dd_document;self.update_reference(bpy.context,align=True);self.fit()
            else:return
            self.persist();self.sync_selection()
            self.message='Done: '+action.replace('_',' ').lower()+'.'
            if scene.get('dd_arrangement_message'):self.message+=' '+scene['dd_arrangement_message']
            if self.session.last_repairs:self.message+=f' {self.session.last_repairs} affected sewing pair(s) or elastic edge(s) removed; review edited edges.'
        try:
            operation()
            return True
        except (ValueError,RuntimeError,OSError) as exc:
            self.message=str(exc).replace('Error: ','').strip()
            return False

    def sewing_message(self,seam):
        a,b,difference,percent=self.session.document.seam_stats(seam)
        return f'Seam: {a*100:.2f} / {b*100:.2f} cm; difference {difference*100:.2f} cm ({percent:.1f}%).'+(' Gather warning; sewing allowed.' if percent>1 else '')

    def design_sew_click(self,viewport_hit=None):
        edge=viewport_hit[0] if viewport_hit is not None else self.design_hit_edge()
        if edge is None:self.message='Click near an outer or internal segment.';return
        scene=self._scene;doc=self.session.document
        if self.mn_sewing:
            full=edge.full()
            if full in self.mn_chain:self.mn_chain.remove(full)
            else:self.mn_chain.append(full)
            self.message=f"{len(self.mn_chain)} edge(s) on this side. Enter "+('sews.' if self.mn_first else 'ends the side.')
            return
        if scene.dd_free_sewing:
            point=doc.edge_point(edge,viewport_hit[1]) if viewport_hit is not None else self.view.world(self.pointer,self.canvas_layout.canvas)
            t,_=curves.closest_fraction(doc.edge_curve(edge),point)
            length=doc.edge_length(edge.full())
            t=next((guide for guide in self.free_guides(edge) if abs(guide-t)*length<.01),t)
            self.free_clicks.append((edge,t))
            if len(self.free_clicks)==4:
                try:
                    a=path_range(doc,*self.free_clicks[:2]);b=path_range(doc,*self.free_clicks[2:])
                    self.session.sew_chains(a,b,sew_reverse(doc,a,b,scene.dd_sew_reverse));self.persist()
                    self.seam_selected=doc.seams[-1].id;self.message=self.sewing_message(doc.seams[-1])
                except ValueError as exc:self.message=str(exc)
                self.free_clicks=[]
            else:self.message=f'Free sewing: {len(self.free_clicks)}/4 points. Click '+('end A' if len(self.free_clicks)==1 else 'start B' if len(self.free_clicks)==2 else 'end B')+'.'
            return
        if self.pending_edge is None:
            existing=next((s for s in doc.seams if any(e.full()==edge for i in (0,1) for e in s.side(i))),None)
            if existing:
                self.seam_selected=existing.id;self.message=self.sewing_message(existing)+' B flips; X removes.'
            else:self.pending_edge=edge;self.seam_selected=None;self.message='First edge selected. Click partner edge (B flips, Esc cancels).'
            return
        if self.pending_edge.full() == edge.full():
            self.pending_edge=None;self.message='Seam selection cleared.';return
        try:
            a=chain_range(doc,[self.pending_edge],scene.dd_sew_a0,scene.dd_sew_a1)
            b=chain_range(doc,[edge],scene.dd_sew_b0,scene.dd_sew_b1)
            self.session.sew_chains(a,b,sew_reverse(doc,a,b,scene.dd_sew_reverse));self.persist()
            self.pending_edge=None;self.seam_selected=doc.seams[-1].id;self.message=self.sewing_message(doc.seams[-1])
        except ValueError as exc:self.message=str(exc)

    def seam_end_points(self):
        doc=self.session.document
        seam=next((item for item in doc.seams if item.id==self.seam_selected),None)
        if seam is None or self.tool not in {'SEW','SELECT'}:return []
        canvas=self.canvas_layout.canvas;gesture=self.gesture if self.gesture and self.gesture.get('mode')=='SEAM_END' else {}
        points=[]
        for side in (0,1):
            chain=seam.side(side)
            for last,edge,fraction in ((False,chain[0],chain[0].t0),(True,chain[-1],chain[-1].t1)):
                if gesture.get('side')==side and gesture.get('last')==last and gesture.get('fraction') is not None:fraction=gesture['fraction']
                points.append((self.view.screen(doc.edge_point(edge.full(),fraction),canvas),side,last,edge))
        return points

    def seam_end_hit(self):
        return next((item for item in self.seam_end_points() if math.dist(item[0],self.pointer)<9*self.canvas_layout.scale),None)

    def free_guides(self,edge):
        if edge is None or not self._scene.dd_free_sewing or len(self.free_clicks)!=3 or self.free_clicks[2][0].full()!=edge.full():return []
        doc=self.session.document
        try:span=doc.chain_length(path_range(doc,*self.free_clicks[:2]))/doc.edge_length(edge.full())
        except ValueError:return []
        start=self.free_clicks[2][1]
        return [fraction for fraction in (start-span,start+span) if 0<=fraction<=1]

    def mn_commit(self):
        if not self.mn_chain:
            self.message='Click at least one edge first.'
        elif self.mn_first is None:
            try:self.mn_first=ordered_sewing_chain(self.session.document,self.mn_chain)
            except ValueError as exc:
                self.message=str(exc);return
            self.mn_chain=[]
            self.message='Now click the partner edges, then press Enter.'
        else:
            doc=self.session.document
            try:
                a=chain_range(doc,ordered_sewing_chain(doc,self.mn_first),0,1);b=chain_range(doc,ordered_sewing_chain(doc,self.mn_chain),0,1)
                self.session.sew_chains(a,b,sew_reverse(doc,a,b,self._scene.dd_sew_reverse));self.persist()
                self.seam_selected=doc.seams[-1].id;self.message=self.sewing_message(doc.seams[-1])
            except ValueError as exc:self.message=str(exc)
            self.mn_first=None;self.mn_chain=[]

    def pen_event(self,context,event):
        from bpy_extras import view3d_utils
        press=event.value=='PRESS'
        if not press:return None
        if event.type in {'ESC','RIGHTMOUSE'}:
            self.pen_points=[];self.pen_mode=None;self.choose_tool('SELECT');self.message='Drawing cancelled.'
            return {'RUNNING_MODAL'}
        if event.type in {'RET','NUMPAD_ENTER'}:
            finish=self.pen_finish_avatar if self.pen_mode=='AVATAR' else self.pen_finish_garment
            try:finish(context)
            except ValueError as exc:self.message=str(exc);return {'RUNNING_MODAL'}
            self.pen_points=[];self.pen_mode=None;self.choose_tool('SELECT')
            return {'RUNNING_MODAL'}
        if event.type!='LEFTMOUSE':return None
        space=self._area.spaces.active
        if self.pen_mode=='AVATAR':
            from . import placement
            try:point,normal,_=placement.ray_body(context,self._region,space,self.pointer)
            except ValueError as exc:self.message=str(exc);return {'RUNNING_MODAL'}
            self.pen_points.append(dict(world=tuple(point),normal=tuple(normal)))
        else:
            from . import garment
            from .xpbd_live import ClothGrab
            simulations=garment.generated(self._scene,'simulation')
            if not simulations:
                self.message='Start a drape before drawing on the garment.';return {'RUNNING_MODAL'}
            origin=view3d_utils.region_2d_to_origin_3d(self._region,space.region_3d,self.pointer)
            direction=view3d_utils.region_2d_to_vector_3d(self._region,space.region_3d,self.pointer)
            hit=ClothGrab(simulations[0]).pick(context,origin,direction)
            if hit is None:
                self.message='Click on the cloth.';return {'RUNNING_MODAL'}
            identity,point=self.cloth_point(simulations[0],hit[0])
            if self.pen_points and self.pen_points[0]['pattern']!=identity:
                self.message='Keep the line on one piece.';return {'RUNNING_MODAL'}
            self.pen_points.append(dict(world=tuple(hit[1]),pattern=identity,point=point))
        self.message=f'{len(self.pen_points)} point(s). Enter finishes.'
        self._area.tag_redraw()
        return {'RUNNING_MODAL'}

    def pen_finish_garment(self,context):
        if len(self.pen_points)<2:raise ValueError('Click at least two points on the cloth.')
        self.session.selected=self.pen_points[0]['pattern']
        self.run_edit(lambda:self.session.add_path([item['point'] for item in self.pen_points],False),'Line added to the pattern. Right-click it for Cut or Fold.')

    def pen_finish_avatar(self,context):
        from mathutils import Vector
        from . import garment,placement
        if len(self.pen_points)<3:raise ValueError('Click at least three points on the avatar.')
        unit=garment.metres_per_unit(self._scene)
        world=[Vector(item['world']) for item in self.pen_points]
        center=sum(world,Vector())/len(world)
        normal=sum((Vector(item['normal']) for item in self.pen_points),Vector()).normalized()
        across=Vector((0,0,1)).cross(normal).normalized() if abs(normal.z)<.95 else Vector((1,0,0))
        up=normal.cross(across).normalized()
        flat=[((point-center).dot(across)*unit,(point-center).dot(up)*unit) for point in world]
        area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(flat,flat[1:]+flat[:1]))
        if area<0:flat.reverse()
        patterns=self.session.document.patterns
        right=max((p[0] for piece in patterns for p in piece.outline()),default=0)
        left=min(p[0] for p in flat)
        self.run_edit(lambda:self.session.add([(x-left+right+.1,y) for x,y in flat]),'Pattern made from the avatar outline.')
        piece=self.session.document.find(self.session.selected)
        piece.placement_mode='LEGACY'
        self.persist()
        placement.place(context,piece.id,center,normal)

    def cloth_point(self,source,vertex):
        import json
        from .piece_states import piece_indices
        saved=json.loads(source['dd_run_rest'])
        identity,position=next((key,indices.index(vertex)) for key,indices in piece_indices(source).items() if vertex in indices)
        point=saved[identity][position][:2]
        pattern=self.session.document.find(identity)
        outline=pattern.outline()
        center=(sum(item[0] for item in outline)/len(outline),sum(item[1] for item in outline)/len(outline))
        placed=next((candidate for candidate in (curves.mix(point,center,share) for share in (0,.01,.03,.06)) if pattern.contains(candidate)),None)
        if placed is None:raise ValueError('That point is too close to the edge.')
        return identity,placed

    def design_pending_event(self,context,event,panel):
        press=event.value=='PRESS'
        if self.pen_mode and not panel:
            result=self.pen_event(context,event)
            if result is not None:return result
        if self.pending_place or self.pending_tack:
            if press and event.type in {'ESC','RIGHTMOUSE'}:
                self.pending_place=self.pending_tack=None;self.message='Placement cancelled.';return {'RUNNING_MODAL'}
            if press and event.type=='LEFTMOUSE' and not panel:
                from . import placement
                try:
                    point,normal,_=placement.ray_body(context,self._region,self._area.spaces.active,self.pointer)
                    if self.pending_place:placement.place(context,self.pending_place,point,normal)
                    else:
                        owner,source=self.pending_tack
                        self.session.selected=owner
                        from . import tack_binding
                        binding=tack_binding.bind_target(context,self._scene.dd_avatar,point)
                        anchor=self.session.add_anchor(source,'TACK',placement.normalized_target(self._scene,point),binding=binding);self.select_anchor(anchor);self.persist()
                    self.pending_place=self.pending_tack=None;self.message='Placement / tack attached to the avatar.'
                except ValueError as exc:self.message=str(exc)
                return {'RUNNING_MODAL'}
        if not panel:return None
        if press and event.type=='ESC' and (self.free_clicks or self.dart_base):
            self.perform_action('CANCEL_DRAFT');return {'RUNNING_MODAL'}
        if not self.numeric and press:
            if event.type == 'D' and event.shift and not event.ctrl and not event.alt:
                self.perform_action('DUPLICATE');return {'RUNNING_MODAL'}
            if event.type == 'H' and event.shift and not event.ctrl and not event.alt:
                self.perform_action('FLIP_H');return {'RUNNING_MODAL'}
            if event.type == 'V' and event.shift and not event.ctrl and not event.alt:
                self.perform_action('FLIP_V');return {'RUNNING_MODAL'}
            if event.type in {'E','I','K','T','D','G'} and not event.ctrl and not event.alt:
                if event.type == 'E':
                    self.draw_shape = 'ELLIPSE'
                elif event.type in {'I','D'}:
                    self.internal_tool = {'I':'INTERNAL','D':'DART'}[event.type]
                elif event.type in {'K','T'}:
                    self.pin_tool = {'K':'PIN','T':'TACK'}[event.type]
                self.choose_tool({'E':'ELLIPSE','I':'INTERNAL','K':'PIN','T':'TACK','D':'DART','G':'PLACE'}[event.type]);return {'RUNNING_MODAL'}
            if event.type in {'C','Q','M','U'} and not event.ctrl:
                self.perform_action({'C':'CURVE','Q':'SPLIT','M':'MERGE','U':'MIRROR_SEW' if event.shift else 'UNFOLD'}[event.type]);return {'RUNNING_MODAL'}
            if event.type=='L' and not event.ctrl:self._scene.dd_lengths_visible=not self._scene.dd_lengths_visible;return {'RUNNING_MODAL'}
        return None

    def design_canvas_click(self,event):
        doc=self.session.document
        point=self.world_pointer(event)
        if self.tool=='TACK_FABRIC':
            p,_=self.design_hit()
            if p is None or not p.contains(point):raise ValueError('Click inside the fabric.')
            if self.pending_join is None:
                self.pending_join=(p.id,*point);self.message='Now click the point to tie it to.'
            else:
                self.session.add_join(self.pending_join,(p.id,*point));self.pending_join=None
                self.persist();self.message='Fabric tacked.'
        elif self.tool=='PIN_EDGE':
            edge=self.design_hit_edge()
            if edge is None:raise ValueError('Click an edge to pin along it.')
            steps=max(2,round(doc.edge_length(edge)/.02))
            owner=doc.find(edge.pattern);items=[]
            for index in range(steps+1):
                x,y=doc.edge_point(edge,index/steps)
                inside=next((candidate for candidate in ((x+dx,y+dy) for dx,dy in ((.002,0),(-.002,0),(0,.002),(0,-.002),(.002,.002),(-.002,-.002),(.002,-.002),(-.002,.002))) if owner.contains(candidate)),None)
                if inside:items.append((edge.pattern,*inside))
            self.session.add_pins(items)
            self.persist();self.message=f'{len(items)} pins added along the edge.'
        elif self.tool in {'PIN','TACK'}:
            for anchor in doc.anchors:
                if math.dist(self.view.screen((anchor.x,anchor.y),self.canvas_layout.canvas),self.pointer)<10*self.canvas_layout.scale:
                    self.select_anchor(anchor);self.message='Anchor selected. Delete removes this pin or tack.';return
            p,index=self.design_hit()
            if p is None:raise ValueError('Click inside the fabric to add a pin or tack.')
            self.session.selected=p.id
            if self.tool=='PIN':
                anchor=self.session.add_anchor(point);self.select_anchor(anchor);self.persist();self.message='Pin added.'
            else:self.pending_tack=(p.id,point);self.message='Now click the avatar in 3D to attach this tack.'
        elif self.tool=='DART':
            if len(self.dart_base)<2:
                edge=self.design_hit_edge()
                if edge is None or edge.path!='OUTER':raise ValueError('Click the dart mouth on an outer segment.')
                if self.dart_base and self.dart_base[0][0]!=edge:raise ValueError('Pick both dart base points on the same segment.')
                t,_=curves.closest_fraction(doc.edge_curve(edge),point)
                self.dart_base.append((edge,t));self.message='Click the other base point.' if len(self.dart_base)==1 else 'Click the dart apex inside the pattern.'
            else:
                (edge,a),(_,b)=self.dart_base
                self.session.dart(edge,a,b,point);self.persist();self.dart_base=[];self.message='Dart created with automatic closing sewing.'

    def preview_pattern(self,pattern):
        from .linked_editing import pair_for,synchronize
        pair=pair_for(self.session.document,pattern.id)
        if not pair or not pair['enabled'] or not (self.gesture or self.handle_preview):
            return self._unlinked_preview(pattern)
        staged=copy.copy(self.session.document)
        staged.linked_pairs=copy.deepcopy(self.session.document.linked_pairs)
        staged.patterns=[copy.deepcopy(self._unlinked_preview(piece)) if piece.id in pair['members'] else piece for piece in self.session.document.patterns]
        synchronize(staged,self.session.document,self.session.selected)
        return staged.find(pattern.id)

    def _unlinked_preview(self,pattern):
        if self.gesture and self.gesture.get('mode')=='EDGE_BEND':
            edge=self.gesture.get('edge')
            if edge and pattern.id==edge.pattern:
                result=copy.deepcopy(pattern)
                try:
                    nodes=result.path(edge.path).vertices
                except ValueError:
                    return pattern
                a=next((v for v in nodes if v.id==edge.start),None)
                b=next((v for v in nodes if v.id==edge.end),None)
                if a and b:
                    a.outgoing=self.gesture.get('new_outgoing')
                    b.incoming=self.gesture.get('new_incoming')
                return result
        if self.gesture and self.gesture.get('mode')=='MOVE':
            dx,dy=self.gesture.get('delta',(0,0))
            is_piece=pattern.id in self.session.selected_patterns or (not self.session.selected_patterns and pattern.id==self.session.selected and self.session.corner is None and not self.session.selected_points)
            pts_on_pat={idx for (pid,path_id,idx) in self.session.selected_points if pid==pattern.id}
            if not is_piece and not pts_on_pat and pattern.id==self.session.selected and self.session.corner is not None:
                pts_on_pat.add(self.session.corner)
            if not is_piece and not pts_on_pat and (pattern.id!=self.session.selected or not self.handle_preview):
                return pattern
            result=copy.deepcopy(pattern)
            if abs(dx)>1e-9 or abs(dy)>1e-9:
                if is_piece:
                    for _,nodes,_,_ in result.loops():
                        for v in nodes:v.x+=dx;v.y+=dy
                else:
                    for pid,path_id,idx in self.session.selected_points:
                        if pid==pattern.id:
                            try:
                                nodes=result.path(path_id).vertices
                                if 0<=idx<len(nodes):nodes[idx].x+=dx;nodes[idx].y+=dy
                            except (ValueError,KeyError,IndexError):pass
                    if not self.session.selected_points and pattern.id==self.session.selected and self.session.corner is not None:
                        try:
                            nodes=result.path(self.session.path).vertices
                            if 0<=self.session.corner<len(nodes):nodes[self.session.corner].x+=dx;nodes[self.session.corner].y+=dy
                        except (ValueError,KeyError,IndexError):pass
            elif self.preview and pattern.id==self.session.selected:
                try:
                    nodes=result.path(self.session.path).vertices
                except ValueError:
                    return pattern
                old=[(v.x,v.y) for v in nodes]
                for v,point in zip(nodes,self.preview):v.x,v.y=point
                if self.session.path=='OUTER' and self.session.corner is None and old:
                    pdx,pdy=curves.sub(self.preview[0],old[0])
                    for path in result.paths:
                        for v in path.vertices:v.x+=pdx;v.y+=pdy
            for _,loop_nodes,closed,_ in result.loops():
                update_auto_handles(loop_nodes,closed)
            if self.handle_preview:
                h_idx,h_name,h_val,o_name,o_val,pid,path_id=self.handle_preview
                if pattern.id==pid:
                    try:
                        target_nodes=result.path(path_id).vertices
                        if 0<=h_idx<len(target_nodes):
                            setattr(target_nodes[h_idx],h_name,h_val)
                            if o_name and o_val is not None:
                                setattr(target_nodes[h_idx],o_name,o_val)
                    except ValueError:
                        pass
            return result
        if self.handle_preview:
            h_idx,h_name,h_val,o_name,o_val,pid,path_id=self.handle_preview
            if pattern.id==pid:
                result=copy.deepcopy(pattern)
                try:
                    target_nodes=result.path(path_id).vertices
                    if 0<=h_idx<len(target_nodes):
                        setattr(target_nodes[h_idx],h_name,h_val)
                        if o_name and o_val is not None:
                            setattr(target_nodes[h_idx],o_name,o_val)
                except ValueError:
                    return pattern
                return result
        if self.gesture and self.gesture.get('candidate'):
            cand = self.gesture['candidate'].find(pattern.id)
            if cand:return cand
        if pattern.id!=self.session.selected:return pattern
        if not self.preview:return pattern
        result=copy.deepcopy(pattern)
        return result

    def start_transform(self,kind):
        if not self.session.has_selection():
            self.message='Select geometry to transform.'
            return
        c=self.canvas_layout.canvas
        w=self.view.world(self.pointer,c)
        self.gesture=dict(mode='TRANSFORM',kind=kind,start=w,pointer_start=self.pointer,
                          numeric_text='',axis_lock=None,preflight=None,candidate=None)
        self.message=f"Transform {kind.title()}: drag cursor or enter value. Enter commits, Esc cancels."

    def transform_frame(self):
        if self.tool!='SELECT' or self.seam_selected or self.gesture or getattr(self,'pending_transform',None) or not self.session.has_selection():return None
        bounds=self.session.selection_bounds()
        if bounds is None:return None
        c=self.canvas_layout.canvas;scale=self.canvas_layout.scale
        x0,y0=self.view.screen((bounds[0],bounds[1]),c);x1,y1=self.view.screen((bounds[2],bounds[3]),c)
        if max(x1-x0,y1-y0)<6*scale:return None
        pad=TRANSFORM_FRAME_PAD*scale
        rect=Rect(x0-pad,y0-pad,x1-x0+2*pad,y1-y0+2*pad)
        top=(rect.x+rect.w/2,rect.y+rect.h)
        return dict(rect=rect,corners=[(rect.x,rect.y),(rect.x+rect.w,rect.y),(rect.x+rect.w,rect.y+rect.h),(rect.x,rect.y+rect.h)],
                    stem=top,knob=(top[0],top[1]+TRANSFORM_KNOB_OFFSET*scale),pivot=self.view.screen(self.session.get_pivot(),c))

    def transform_frame_hit(self,frame=None):
        frame=frame or self.transform_frame()
        if frame is None:return None
        scale=self.canvas_layout.scale
        if math.dist(self.pointer,frame['pivot'])<=TRANSFORM_PIVOT_HIT_RADIUS*scale:return 'PIVOT'
        if math.dist(self.pointer,frame['knob'])<=TRANSFORM_HIT_RADIUS*scale:return 'ROTATE'
        if any(math.dist(self.pointer,corner)<=TRANSFORM_HIT_RADIUS*scale for corner in frame['corners']):return 'SCALE'
        return None

    def start_frame_gesture(self,handle):
        if handle=='PIVOT':
            self.start_set_pivot()
            self.message='Drag the pivot. It snaps to corners, midpoints and the selection center.'
            return
        self.start_transform(handle)
        self.gesture['handle']=True
        self.message=('Rotating around the pivot. Shift snaps to 15 degrees; type a number for an exact angle.' if handle=='ROTATE'
                      else 'Scaling around the pivot. Shift snaps to 10 percent; type a number for an exact factor.')

    def start_set_pivot(self):
        if not self.session.has_selection():
            self.message='Select geometry before placing pivot.'
            return
        self.gesture=dict(mode='SET_PIVOT',start=self.pointer,chosen=self.session.get_pivot(),label='Default')
        self.message='Click to place pivot. Snaps to vertices, midpoints, or selection center.'

    def start_bend_edge(self):
        if not self.session.segment:
            self.message='Select an edge to bend.'
            return
        edge=self.session.segment
        a,b=self.session.document.edge_vertices(edge)
        ctrl=self.session.document.edge_curve(edge)
        click_w=curves.evaluate(ctrl,0.5)
        t_frac,_=curves.closest_fraction(ctrl,click_w)
        t0=max(0.15,min(0.85,curves.parameter(ctrl,t_frac)))
        p_orig=curves.evaluate(ctrl,t0)
        self.gesture=dict(
            mode='EDGE_BEND',edge=edge,start=click_w,t0=t0,p_orig=p_orig,
            orig_c1=ctrl[1],orig_c2=ctrl[2],anchor_a=(a.x,a.y),anchor_b=(b.x,b.y),
            moved=False,new_outgoing=a.outgoing,new_incoming=b.incoming
        )
        self.message='Drag to bend edge. Escape cancels.'

    def stage_transform(self,kind,param,pivot=None):
        pivot=pivot or self.session.get_pivot()
        cand,pre=self.session.build_transform_candidate(kind,param,pivot=pivot)
        if cand is None or pre['status']=='BLOCK':raise ValueError(pre.get('reason','This transform is blocked.'))
        if pre['status']=='WARN':
            self.pending_transform=dict(candidate=cand,report=pre,op=kind,param=param,pivot=pivot,
                                        source=self.session.document.dumps(),selection=self.session.get_selection_state())
            self.card_kind='SEAM_WARNING'
            self.message=self.transform_warning_message(pre)
            return True
        self.apply_transform_candidate(cand,kind,param)
        return False

    def transform_warning_message(self,report):
        parts=[]
        if report.get('details'):parts.append(f"seam mismatch {report.get('diff_cm',0.0):.2f} cm")
        if report.get('curve_deviation_mm') is not None:parts.append(f"selected curve changes {report['curve_deviation_mm']:.3f} mm")
        return 'Review before applying: '+', '.join(parts)+'.'

    def convert_pending_auto_points(self):
        pending=getattr(self,'pending_transform',None)
        exact=pending['report'].get('exact_candidate') if pending else None
        if exact is None:raise ValueError('There are no AUTO points to convert.')
        if pending['source']!=self.session.document.dumps() or pending['selection']!=self.session.get_selection_state():
            self.cancel_transform()
            raise ValueError('Transform cancelled because its source selection changed.')
        nodes,whole=self.session.resolve_selection(exact)
        pre=self.session.preflight_transform(exact,whole,nodes)
        if pre['status']=='BLOCK':
            self.cancel_transform()
            raise ValueError(pre.get('reason','This transform is blocked.'))
        count=pending['report'].get('auto_point_count',0)
        if pre['status']=='WARN':
            self.pending_transform=dict(pending,candidate=exact,report=pre)
            self.card_kind='SEAM_WARNING'
            self.message=f'{count} AUTO point(s) will become Smooth. '+self.transform_warning_message(pre)
            return
        self.pending_transform=dict(pending,candidate=exact)
        self.commit_preflighted_transform()
        self.message=f'Transform applied; {count} AUTO point(s) converted to Smooth to keep the selected curve exact.'

    def apply_transform_candidate(self,cand,op,param):
        pivot=self.session.placed_pivot
        changed=self.session.commit_candidate(cand)
        if changed and op=='MOVE' and pivot is not None and param:
            self.session.placed_pivot=(round(pivot[0]+param[0],7),round(pivot[1]+param[1],7))
            self.session.remember_committed_selection()
        return changed

    def commit_preflighted_transform(self):
        pre=getattr(self,'pending_transform',None)
        if pre and pre.get('candidate'):
            if pre['source']!=self.session.document.dumps() or pre['selection']!=self.session.get_selection_state():
                self.cancel_transform()
                self.message='Transform cancelled because its source selection changed.'
                return
            self.run_edit(lambda: self.apply_transform_candidate(pre['candidate'],pre.get('op'),pre.get('param')), 'Transform committed with accepted mismatch.')
            self.pending_transform=None
            self.card_kind=None

    def cancel_transform(self):
        self.pending_transform=None
        self.card_kind=None
        self.gesture=None
        self.preview=None
        self.sync_selection()
        self.message='Transform cancelled.'
