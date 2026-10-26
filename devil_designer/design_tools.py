"""Complete pattern construction and sewing tools for the custom editor."""
import copy
import math
import bpy
from . import curves
from .core import Document,Session,EdgeRef,contains
from .construction import chain_range,path_range
from .presets import PRESETS

class DesignTools:
    def initialize_design(self):
        self.hit_path='OUTER';self.hit_segment=None;self.hit_handle=None
        self.handle_preview=None;self.selected_anchor=None
        self.chain_a=[];self.chain_b=[];self.chain_stage=None
        self.free_clicks=[];self.dart_base=[];self.pending_place=None;self.pending_tack=None
        self.library_items=[]

    def design_hit(self):
        self.hit_path='OUTER';self.hit_segment=None;self.hit_handle=None
        c=self.canvas_layout.canvas;s=self.canvas_layout.scale
        selected=self.session.document.find(self.session.selected)
        if selected and self.session.corner is not None:
            try:
                v=selected.path(self.session.path).vertices[self.session.corner]
                for name in ('incoming','outgoing'):
                    vector=getattr(v,name)
                    if vector and math.dist(self.view.screen(curves.add((v.x,v.y),vector),c),self.pointer)<8*s:
                        self.hit_path=self.session.path;self.hit_handle=name
                        return selected,self.session.corner
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
            if action in {'NUM_RECT','NUM_ELLIPSE'}:
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
            elif action=='CURVE':self.session.curve_point()
            elif action=='SPLIT':
                if not self.session.segment:raise ValueError('Select a segment to split.')
                self.session.split_segment(self.session.segment);self.session.segment=None
            elif action=='SET_LENGTH':
                if not self.session.segment:raise ValueError('Select a segment to set its length.')
                self.session.set_length(self.session.segment,scene.dd_segment_length)
            elif action=='MERGE':self.session.merge_points(self.session.point_selection)
            elif action=='OFFSET':self.session.offset(scene.dd_offset)
            elif action == 'DUPLICATE':
                if not p:raise ValueError('Select a pattern to duplicate.')
                self.session.duplicate()
                self.message = 'Pattern duplicated (Shift D).'
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
            elif action=='CUT':self.session.cut()
            elif action=='TRACE':self.session.trace()
            elif action=='PLACE':
                if not p:raise ValueError('Select the pattern you want to place.')
                self.pending_place=p.id;self.message='Click the avatar in the 3D view to place this pattern. Escape cancels.';return
            elif action=='WRAP':
                if not p:raise ValueError('Select a pattern to wrap.')
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
                self.session.sew_chains(a,b,scene.dd_sew_reverse);self.chain_stage=None;self.chain_a=[];self.chain_b=[]
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
            if self.session.last_repairs:self.message+=f' {self.session.last_repairs} affected sewing pair(s) removed; re-pair edited edges.'
        try:operation()
        except (ValueError,RuntimeError,OSError) as exc:self.message=str(exc).replace('Error: ','').strip()

    def sewing_message(self,seam):
        a,b,difference,percent=self.session.document.seam_stats(seam)
        return f'Seam: {a*100:.2f} / {b*100:.2f} cm; difference {difference*100:.2f} cm ({percent:.1f}%).'+(' Gather warning; sewing allowed.' if percent>1 else '')

    def design_sew_click(self):
        edge=self.design_hit_edge()
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
            t,_=curves.closest_fraction(doc.edge_curve(edge),self.view.world(self.pointer,self.canvas_layout.canvas))
            self.free_clicks.append((edge,t))
            if len(self.free_clicks)==4:
                try:
                    a=path_range(doc,*self.free_clicks[:2]);b=path_range(doc,*self.free_clicks[2:])
                    self.session.sew_chains(a,b,scene.dd_sew_reverse);self.persist()
                    self.seam_selected=doc.seams[-1].id;self.message=self.sewing_message(doc.seams[-1])
                except ValueError as exc:self.message=str(exc)
                self.free_clicks=[]
            else:self.message=f'Free sewing: {len(self.free_clicks)}/4 points. Click '+('end A' if len(self.free_clicks)==1 else 'start B' if len(self.free_clicks)==2 else 'end B')+'.'
            return
        if self.pending_edge is None:
            existing=next((s for s in doc.seams if any(e.full()==edge for i in (0,1) for e in s.side(i))),None)
            if existing:
                self.seam_selected=existing.id;self.message=self.sewing_message(existing)+' B flips; X removes.'
            else:self.pending_edge=edge;self.seam_selected=None;self.message='First edge selected. Click its sewing partner.'
            return
        try:
            a=chain_range(doc,[self.pending_edge],scene.dd_sew_a0,scene.dd_sew_a1)
            b=chain_range(doc,[edge],scene.dd_sew_b0,scene.dd_sew_b1)
            self.session.sew_chains(a,b,scene.dd_sew_reverse);self.persist()
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
                        anchor=self.session.add_anchor(source,'TACK',placement.normalized_target(self._scene,point));self.select_anchor(anchor);self.persist()
                    self.pending_place=self.pending_tack=None;self.message='Placement / tack attached to the avatar.'
                except ValueError as exc:self.message=str(exc)
                return {'RUNNING_MODAL'}
        if not panel:return None
        if press and event.type=='ESC' and (self.chain_stage or self.free_clicks or self.dart_base):
            self.chain_stage=None;self.free_clicks=[];self.dart_base=[];self.message='Tool selection cancelled.';return {'RUNNING_MODAL'}
        if press and event.type in {'RET','NUMPAD_ENTER'} and self.chain_stage:
            if self.chain_stage=='A':self.chain_stage='B';self.message='Now pick chain B, then Enter to sew.'
            else:self.design_action('CHAIN_SEW')
            return {'RUNNING_MODAL'}
        if not self.numeric and press:
            if event.type == 'D' and event.shift and not event.ctrl and not event.alt:
                self.perform_action('DUPLICATE');return {'RUNNING_MODAL'}
            if event.type in {'E','I','K','T','D','G'} and not event.ctrl and not event.alt:
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
        if pattern.id!=self.session.selected:return pattern
        if not self.preview and not self.handle_preview:return pattern
        result=copy.deepcopy(pattern)
        nodes=result.path(self.session.path).vertices
        if self.gesture and self.gesture['mode']=='MOVE' and self.preview:
            old=[(v.x,v.y) for v in nodes]
            for v,point in zip(nodes,self.preview):v.x,v.y=point
            if self.session.path=='OUTER' and self.session.corner is None:
                dx,dy=curves.sub(self.preview[0],old[0])
                for path in result.paths:
                    for v in path.vertices:v.x+=dx;v.y+=dy
        if self.handle_preview:
            index,name,value=self.handle_preview;setattr(nodes[index],name,value)
        return result
