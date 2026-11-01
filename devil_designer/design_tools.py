import copy
import math
import bpy
from . import curves
from .core import EdgeRef, update_auto_handles
from .construction import chain_range,path_range,sew_reverse
from .presets import PRESETS

class DesignTools:
    def initialize_design(self):
        self.hit_path='OUTER';self.hit_segment=None;self.hit_handle=None
        self.handle_preview=None;self.selected_anchor=None
        self.chain_a=[];self.chain_b=[];self.chain_stage=None
        self.free_clicks=[];self.dart_base=[];self.pending_place=None;self.pending_tack=None
        self.library_items=[]
        self.cut_preview=None
        self.trace_points=None

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

    def design_info(self,key):
        doc=self.session.document;p=doc.find(self.session.selected)
        if key=='PATTERN_INFO':
            if not p:return 'Select a pattern / point.','C curves, Q splits, Shift-click merges.'
            detail=p.path(self.session.path).name if self.session.path!='OUTER' else 'Outer boundary'
            if self.session.segment:
                try:detail=f'Selected segment: {doc.edge_length(self.session.segment)*100:.3f} cm'
                except ValueError:pass
            return p.name,detail
        if key=='CHAIN_INFO':return f'Chain A: {len(self.chain_a)} / B: {len(self.chain_b)} segments',('Free mode: start/end A, start/end B.' if self._scene.dd_free_sewing else 'Pair mode: pick an edge, then its partner.')
        if key=='PRESET_INFO':return (p.preset.title() if p else 'Select a pattern for a preset.'),'Stretch/bend per piece; mass shared.'
        if key=='LIBRARY_INFO':
            if not self.library_items:return 'No saved garments.','Save stores editable source and UVs.'
            index=min(self._scene.dd_library_selected,len(self.library_items)-1)
            return f'{index+1} / {len(self.library_items)}',self.library_items[index].name.replace('.garment.json','')
        return '',''

    def refresh_library(self):
        from . import library
        try:self.library_items=library.entries(self._scene)
        except OSError as exc:self.library_items=[];self.message='Library unavailable: '+str(exc)
        self._scene.dd_library_selected=min(self._scene.dd_library_selected,max(0,len(self.library_items)-1))

    def design_action(self,action):
        scene=self._scene;doc=self.session.document;p=doc.find(self.session.selected)
        def operation():
            if action in {'STARTER_TEE', 'STARTER_TANK', 'STARTER_SKIRT'}:
                from .starters import STARTER_GENERATORS
                label,generator=STARTER_GENERATORS[action][:2]
                measurements = None
                if hasattr(self, 'reference') and getattr(self.reference, 'measurements', None):
                    measurements = self.reference.measurements
                elif scene.dd_avatar:
                    from .measurements import estimate_body_measurements
                    measurements = estimate_body_measurements(scene.dd_avatar, scene)
                before = scene.dd_document
                self.session.undo_stack.append(before)
                self.session.redo_stack.clear()
                starter_doc = generator(measurements, getattr(self.session.document, 'preset', 'COTTON'))
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
                self.message = f"{label} starter created. Pre-sewn and placed on avatar."
                return
            elif action in {'ADD_PANEL', 'DEMO_PANEL'}:
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
            elif action == 'START_PANEL':
                ref_bounds = getattr(self.reference, 'bounds', None) if hasattr(self, 'reference') else None
                ref_h = (ref_bounds[1][1] - ref_bounds[0][1]) if ref_bounds else 0.0
                ref_y = scene.dd_reference_y
                ref_x = scene.dd_reference_x
                base_y = (ref_y + max(0.20, ref_h * 0.50)) if ref_h > 0 else 0.0
                base_x = ref_x if ref_h > 0 else 0.0
                self.session.add([(base_x - .2, base_y), (base_x + .2, base_y),
                                  (base_x + .2, base_y + .45), (base_x - .2, base_y + .45)])
                self.session.document.find(self.session.selected).name = 'Front panel'
            elif action in {'NUM_RECT','NUM_ELLIPSE'}:
                a=(scene.dd_point_x,scene.dd_point_y);b=(a[0]+scene.dd_width,a[1]+scene.dd_height)
                if action=='NUM_ELLIPSE':self.session.add_ellipse(a,b,scene.dd_internal_mode)
                elif scene.dd_internal_mode:self.session.add_path([a,(b[0],a[1]),b,(a[0],b[1])],True)
                else:self.session.add([a,(b[0],a[1]),b,(a[0],b[1])])
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
            elif action.startswith('POINT_TYPE_'):
                ptype=action.removeprefix('POINT_TYPE_').upper()
                self.session.set_point_type(ptype)
                self.message=f"Point type: {ptype.title()}."
            elif action=='SPLIT':
                if not self.session.segment:raise ValueError('Select a segment to split.')
                self.session.split_segment(self.session.segment);self.session.segment=None
            elif action=='SET_LENGTH':
                if not self.session.segment:raise ValueError('Select a segment to set its length.')
                self.session.set_length(self.session.segment,scene.dd_segment_length)
            elif action=='MERGE':self.session.merge_points(self.session.point_selection)
            elif action=='OFFSET':self.session.offset(scene.dd_offset)
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
            elif action in {'ROTATE_CW','ROTATE_90'}:
                if not p and not self.session.selected_patterns and not self.session.selected_points and self.session.corner is None:raise ValueError('Select a piece or points to rotate.')
                self.session.rotate_90(clockwise=True)
                self.message = 'Pattern rotated 90 degrees clockwise.'
            elif action == 'ROTATE_CCW':
                if not p and not self.session.selected_patterns and not self.session.selected_points and self.session.corner is None:raise ValueError('Select a piece or points to rotate.')
                self.session.rotate_90(clockwise=False)
                self.message = 'Pattern rotated 90 degrees counter-clockwise.'
            elif action.startswith('SET_PRESET_'):
                p_val = action.replace('SET_PRESET_', '')
                if not p:raise ValueError('Select a pattern to change fabric.')
                self.session.commit(lambda: setattr(p, 'preset', p_val))
                self.message = f"Fabric changed to {p_val.title()}."
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
            elif action=='WRAP':
                if not p:raise ValueError('Select a pattern to wrap.')
                if p.placement_mode!='LEGACY':
                    self.reveal_3d();self.message='Click an arrangement point to wrap this piece around its bounding volume.';return
                self.session.commit(lambda:setattr(p,'wrap_radius',scene.dd_wrap_radius))
                self.persist();bpy.ops.devil_designer.build_panels('EXEC_DEFAULT')
            elif action=='REMOVE_ANCHOR':
                anchor=next((a for a in doc.anchors if a.id==self.selected_anchor),None)
                if anchor is None:raise ValueError('Select a pin or tack using K or T.')
                self.session.commit(lambda:doc.anchors.remove(anchor));self.selected_anchor=None
            elif action=='PRESET':
                if not p:raise ValueError('Select a pattern for its cloth preset.')
                names=list(PRESETS);value=names[(names.index(p.preset)+1)%len(names)]
                self.session.commit(lambda:setattr(p,'preset',value))
            elif action in {'CHAIN_A','CHAIN_B'}:
                self.choose_tool('SEW');self.chain_stage='A' if action=='CHAIN_A' else 'B'
                self.message='Click connected edges in order for chain '+self.chain_stage+'. Enter switches sides.';return
            elif action=='CHAIN_SEW':
                if not self.chain_a or not self.chain_b:raise ValueError('Pick at least one edge on each side.')
                a=chain_range(doc,self.chain_a,scene.dd_sew_a0,scene.dd_sew_a1)
                b=chain_range(doc,self.chain_b,scene.dd_sew_b0,scene.dd_sew_b1)
                self.session.sew_chains(a,b,sew_reverse(doc,a,b,scene.dd_sew_reverse));self.chain_stage=None;self.chain_a=[];self.chain_b=[]
                self.seam_selected=doc.seams[-1].id
            elif action=='CHAIN_CLEAR':
                self.chain_a=[];self.chain_b=[];self.free_clicks=[];self.pending_edge=None;self.chain_stage=None
            elif action.startswith('LIBRARY_'):
                from . import library
                self.refresh_library()
                if action=='LIBRARY_SAVE':library.save(bpy.context,scene.dd_library_name);self.refresh_library()
                elif action in {'LIBRARY_PREV','LIBRARY_NEXT'} and self.library_items:
                    scene.dd_library_selected=(scene.dd_library_selected+(1 if action=='LIBRARY_NEXT' else -1))%len(self.library_items)
                elif action=='LIBRARY_LOAD':
                    before=scene.dd_document
                    scene['dd_backup_document']=before
                    loaded=library.load(bpy.context,scene.dd_library_selected)
                    self.clear_interaction_references()
                    self.session.undo_stack.append(before);self.session.redo_stack.clear()
                    self.session.document=loaded;self.session.selected=loaded.patterns[0].id if loaded.patterns else None
                    self.session.path='OUTER';self.session.corner=None;self.session.segment=None
                    self.session.point_selection=[]
                    self._stored=scene.dd_document;self.update_reference(bpy.context,align=True);self.fit()
            else:return
            self.persist();self.sync_selection();self.refresh_controls()
            self.message=self.sewing_message(self.session.document.seams[-1]) if action=='CHAIN_SEW' else 'Done: '+action.replace('_',' ').lower()+'.'
            if scene.get('dd_arrangement_message'):self.message+=' '+scene['dd_arrangement_message']
            if self.session.last_repairs:self.message+=f' {self.session.last_repairs} affected sewing pair(s) removed; re-pair edited edges.'
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
        if self.chain_stage:
            chain=self.chain_a if self.chain_stage=='A' else self.chain_b
            if edge in chain:chain.remove(edge)
            else:
                if chain:
                    end=doc.edge_points(chain[-1])[1];a,b=doc.edge_points(edge)
                    if math.dist(end,b)<math.dist(end,a):edge=EdgeRef(edge.pattern,edge.start,edge.end,1,0,edge.path)
                chain.append(edge)
            self.message=f'Chain {self.chain_stage}: {len(chain)} segments. Enter switches side / sews.';return
        if scene.dd_free_sewing:
            point=doc.edge_point(edge,viewport_hit[1]) if viewport_hit is not None else self.view.world(self.pointer,self.canvas_layout.canvas)
            t,_=curves.closest_fraction(doc.edge_curve(edge),point)
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

    def design_pending_event(self,context,event,panel):
        press=event.value=='PRESS'
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
        if press and event.type=='ESC' and (self.chain_stage or self.free_clicks or self.dart_base):
            self.perform_action('CANCEL_DRAFT');return {'RUNNING_MODAL'}
        if press and event.type in {'RET','NUMPAD_ENTER'} and self.chain_stage:
            if self.chain_stage=='A':self.chain_stage='B';self.message='Now pick chain B, then Enter to sew.'
            else:self.design_action('CHAIN_SEW')
            return {'RUNNING_MODAL'}
        if not self.numeric and press:
            if event.type == 'D' and event.shift and not event.ctrl and not event.alt:
                self.perform_action('DUPLICATE');return {'RUNNING_MODAL'}
            if event.type == 'H' and event.shift and not event.ctrl and not event.alt:
                self.perform_action('FLIP_H');return {'RUNNING_MODAL'}
            if event.type == 'V' and event.shift and not event.ctrl and not event.alt:
                self.perform_action('FLIP_V');return {'RUNNING_MODAL'}
            if event.type == 'R' and event.shift and not event.ctrl and not event.alt:
                self.perform_action('ROTATE_CW');return {'RUNNING_MODAL'}
            if event.type in {'LEFT_BRACKET','RIGHT_BRACKET'}:
                self.perform_action('ROTATE_CW' if event.type=='RIGHT_BRACKET' else 'ROTATE_CCW');return {'RUNNING_MODAL'}
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
            if event.type=='L':self._scene.dd_lengths_visible=not self._scene.dd_lengths_visible;return {'RUNNING_MODAL'}
        return None

    def design_canvas_click(self,event):
        doc=self.session.document
        point=self.world_pointer(event)
        if self.tool in {'PIN','TACK'}:
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
                if len(self.handle_preview)==7:
                    h_idx,h_name,h_val,o_name,o_val,pid,path_id=self.handle_preview
                else:
                    h_idx,h_name,h_val=self.handle_preview;o_name,o_val,pid,path_id=None,None,self.session.selected,'OUTER'
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
            if len(self.handle_preview)==7:
                h_idx,h_name,h_val,o_name,o_val,pid,path_id=self.handle_preview
            else:
                h_idx,h_name,h_val=self.handle_preview;o_name,o_val,pid,path_id=None,None,self.session.selected,'OUTER'
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
        if pattern.id!=self.session.selected:return pattern
        if not self.preview:return pattern
        result=copy.deepcopy(pattern)
        return result
