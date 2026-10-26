"""Input for the floating window and its own settings; no native property panels."""
import bpy
from .canvas import Rect
from .controls import Inspector, BodyMenu, SETTINGS

RUNNING = {'RUNNING_MODAL'}


class OverlayControls:
    def initialize_controls(self):
        saved=tuple(self._scene.dd_ui_rect)
        self.window_rect=saved if saved[2]>0 and saved[3]>0 else None
        self.settings_open=self._scene.dd_ui_settings
        self.inspector_scroll=0
        self.inspector_tab='DESIGN'
        self.inspector=None
        self.numeric=None
        self.window_gesture=None
        self.body_open=False
        self.body_offset=0
        self.body_menu=None

    def refresh_controls(self):
        self.inspector=None
        self.body_menu=None
        if self.canvas_layout.inspector:
            self.inspector=Inspector(self.canvas_layout.inspector,self.canvas_layout.scale,
                                     self.inspector_scroll,self.session.document.seams,self.inspector_tab)
            self.inspector_scroll=self.inspector.scroll
            if self.body_open:
                anchor=next(c.value_rect for c in self.inspector.controls if c.kind=='body')
                objects=sorted((o for o in self._scene.objects if o.type=='MESH' and
                                o.get('dd_kind') not in {'panel','simulation','final'}),key=lambda o:o.name.casefold())
                self.body_menu=BodyMenu(self.canvas_layout.panel,anchor,self.canvas_layout.scale,objects,self.body_offset)

    def set_window(self,rect):
        s=self.canvas_layout.scale
        self.window_rect=tuple(value/s for value in (rect.x,rect.y,rect.w,rect.h))
        self.canvas_layout=self.make_layout()
        self.refresh_controls()

    def save_window(self):
        if not self.full:
            p=self.canvas_layout.panel
            s=self.canvas_layout.scale
            self.window_rect=(p.x/s,p.y/s,p.w/s,p.h/s)
        if self.window_rect is not None:
            self._scene.dd_ui_rect=self.window_rect
        self._scene.dd_ui_settings=self.settings_open

    def toggle_full(self):
        if not self.full:
            self.save_window()
        self.full=not self.full
        self.canvas_layout=self.make_layout()
        self.refresh_controls()

    def commit_numeric(self):
        if not self.numeric:
            return True
        key=self.numeric['key']
        try:
            value=SETTINGS[key].parse(self.numeric['text'])
        except ValueError as exc:
            self.message=str(exc)
            return False
        setattr(self._scene,key,value)
        self.numeric=None
        self.message=SETTINGS[key].label+' updated.'
        return True

    def step_setting(self,key,direction,event):
        spec=SETTINGS[key]
        amount=spec.step/spec.factor
        if event.shift and not spec.integer:
            amount*=.1
        if event.ctrl:
            amount*=10
        value=max(spec.low,min(spec.high,getattr(self._scene,key)+direction*amount))
        setattr(self._scene,key,int(round(value)) if spec.integer else round(value,8))
        self.message=spec.label+' updated.'

    def numeric_event(self,event):
        if not self.numeric:
            return None
        press=event.value=='PRESS'
        state=self.numeric
        if press and event.type in {'ESC','RIGHTMOUSE'}:
            self.numeric=None
            self.message='Setting edit cancelled.'
            return RUNNING
        if press and event.type in {'RET','NUMPAD_ENTER'}:
            self.commit_numeric()
            return RUNNING
        if event.ctrl and event.type=='S' and press:
            return {'PASS_THROUGH'} if self.commit_numeric() else RUNNING
        if press and event.type=='LEFTMOUSE':
            return None if self.commit_numeric() else RUNNING
        if press and event.ctrl and event.type=='A':
            state['selected']=True
            return RUNNING
        if press and event.type in {'LEFT_ARROW','RIGHT_ARROW','HOME','END'}:
            n=len(state['text'])
            state['cursor']=(0 if event.type=='HOME' else n if event.type=='END' else
                             max(0,min(n,state['cursor']+(-1 if event.type=='LEFT_ARROW' else 1))))
            state['selected']=False
            return RUNNING
        if press and event.type in {'BACK_SPACE','DEL'}:
            text,cursor=state['text'],state['cursor']
            if state['selected']:
                text,cursor='',0
            elif event.type=='BACK_SPACE' and cursor>0:
                text,cursor=text[:cursor-1]+text[cursor:],cursor-1
            elif event.type=='DEL':
                text=text[:cursor]+text[cursor+1:]
            state.update(text=text,cursor=cursor,selected=False)
            return RUNNING
        char=getattr(event,'unicode','')
        if press and char and (state['key']=='dd_library_name' or all(c in '0123456789.,eE+-' for c in char)):
            text,cursor=state['text'],state['cursor']
            if state['selected']:
                text,cursor='',0
            state.update(text=text[:cursor]+char+text[cursor:],cursor=cursor+len(char),selected=False)
        return RUNNING

    def controls_event(self,context,event):
        press=event.value=='PRESS'
        l=self.canvas_layout
        x,y=self.pointer
        if self.window_gesture:
            gesture=self.window_gesture
            if press and event.type in {'ESC','RIGHTMOUSE'}:
                self.full=gesture['full']
                if gesture['kind']=='SCROLL':
                    self.inspector_scroll=gesture['scroll']
                else:
                    self.window_rect=gesture['placement']
                self.canvas_layout=self.make_layout()
                self.refresh_controls()
                self.window_gesture=None
                self.message='Window movement cancelled.'
                return RUNNING
            if event.type=='MOUSEMOVE':
                dx,dy=x-gesture['pointer'][0],y-gesture['pointer'][1]
                r=gesture['rect']
                if gesture['kind']=='MOVE':
                    requested=Rect(r.x+dx,r.y+dy,r.w,r.h)
                elif gesture['kind']=='RESIZE':
                    available=l.available
                    w=min(available.x+available.w-r.x,max(min(420*l.scale,available.w),r.w+dx))
                    h=min(r.y+r.h-available.y,max(min(420*l.scale,available.h),r.h-dy))
                    requested=Rect(r.x,r.y+r.h-h,w,h)
                else:
                    self.inspector_scroll=max(0,min(self.inspector.max_scroll,
                        gesture['scroll']-dy*self.inspector.total/max(1,self.inspector.content.h)))
                    self.refresh_controls()
                    return RUNNING
                self.set_window(requested)
                return RUNNING
            if event.type=='LEFTMOUSE' and event.value=='RELEASE':
                self.window_gesture=None
                self.save_window()
                return RUNNING
            return RUNNING
        if self.numeric:
            result=self.numeric_event(event)
            if result is not None:
                return result
        if self.body_menu:
            if press and event.type in {'ESC','RIGHTMOUSE'}:
                self.body_open=False
                self.refresh_controls()
                return RUNNING
            if event.type in {'WHEELUPMOUSE','WHEELDOWNMOUSE'}:
                self.body_offset=max(0,min(max(0,len(self.body_menu.objects)-6),
                    self.body_offset+(-1 if event.type=='WHEELUPMOUSE' else 1)))
                self.refresh_controls()
                return RUNNING
            if press and event.type=='LEFTMOUSE':
                for r,obj,_ in self.body_menu.rows:
                    if r.contains(x,y):
                        self.choose_body(obj,context)
                        self.message='Avatar body selected.' if obj else 'Avatar body cleared.'
                        break
                self.body_open=False
                self.refresh_controls()
                return RUNNING if l.panel.contains(x,y) else {'PASS_THROUGH'}
            return RUNNING if l.panel.contains(x,y) else None
        button=l.button(x,y)
        if event.type=='LEFTMOUSE' and event.value=='DOUBLE_CLICK' and l.header.contains(x,y) and not button:
            self.toggle_full()
            return RUNNING
        if press and event.type=='LEFTMOUSE':
            if button=='SETTINGS':
                self.settings_open=not self.settings_open
                self.body_open=False
                self.canvas_layout=self.make_layout()
                self.refresh_controls()
                self.save_window()
                return RUNNING
            if l.header.contains(x,y) and not button:
                original=l.panel
                placement=self.window_rect
                was_full=self.full
                if self.full:
                    ratio=(x-original.x)/max(1,original.w)
                    self.full=False
                    self.canvas_layout=self.make_layout()
                    restored=self.canvas_layout.panel
                    self.set_window(Rect(x-ratio*restored.w,y+20*l.scale-restored.h,restored.w,restored.h))
                self.window_gesture=dict(kind='MOVE',pointer=(x,y),rect=self.canvas_layout.panel,
                                         original=original,full=was_full,placement=placement)
                return RUNNING
            if l.resize.contains(x,y) and not self.full:
                self.window_gesture=dict(kind='RESIZE',pointer=(x,y),rect=l.panel,original=l.panel,full=False,placement=self.window_rect)
                return RUNNING
        if self.inspector and self.inspector.rect.contains(x,y):
            if event.type in {'WHEELUPMOUSE','WHEELDOWNMOUSE'}:
                self.inspector_scroll+=(-38 if event.type=='WHEELUPMOUSE' else 38)*l.scale
                self.refresh_controls()
                return RUNNING
            if press and event.type=='LEFTMOUSE':
                if x>=self.inspector.scrollbar.x-5*l.scale and self.inspector.max_scroll:
                    self.window_gesture=dict(kind='SCROLL',pointer=(x,y),scroll=self.inspector_scroll,
                                             rect=l.panel,original=l.panel,full=self.full)
                    return RUNNING
                hit=self.inspector.hit((x,y))
                if hit:
                    action,key=hit
                    if action=='TAB':
                        self.inspector_tab=key;self.inspector_scroll=0
                        if key=='LIBRARY':self.refresh_library()
                    elif action in {'STEP_UP','STEP_DOWN'}:
                        self.step_setting(key,1 if action=='STEP_UP' else -1,event)
                    elif action=='EDIT':
                        text=SETTINGS[key].format(getattr(self._scene,key))
                        self.numeric=dict(key=key,text=text,cursor=len(text),selected=True)
                        self.message='Type a value. Enter applies it; Escape cancels.'
                    elif action=='TOGGLE':
                        setattr(self._scene,key,not getattr(self._scene,key))
                    elif action=='BODY':
                        self.body_open=True
                        self.body_offset=0
                    elif action=='BODY_USE':
                        obj=context.view_layer.objects.active
                        if obj and obj.type=='MESH' and obj in list(self._scene.objects) and obj.get('dd_kind') not in {'panel','simulation','final'}:
                            self.choose_body(obj,context)
                            self.message='Selected mesh assigned as avatar body.'
                        else:
                            self.message='Select a body mesh in 3D or choose one from the Avatar body list.'
                    elif action in {'REFERENCE_VIEW','REFERENCE_ALIGN','REFERENCE_FRAME','REFERENCE_REFRESH'}:
                        self.reference_action(action)
                    elif action=='DEMO':
                        if self.session.document.patterns:
                            self.message='The demo needs an empty pattern document. Open a new scene to try it.'
                        else:
                            self.workflow_action('DEMO')
                    elif action=='SEAM_FLIP':
                        self.run_edit(lambda:self.session.reverse_seam(key),'Seam direction reversed.')
                    elif action=='SEAM_REMOVE':
                        self.run_edit(lambda:self.session.remove_seam(key),'Seam removed.')
                    elif action=='SEAM_SELECT':
                        self.choose_tool('SEW');self.seam_selected=key
                        self.message='Seam selected. B: reverse. X: remove.'
                    else:
                        self.design_action(action)
                    self.refresh_controls()
            if event.type not in {'LEFTMOUSE','RIGHTMOUSE','MIDDLEMOUSE','MOUSEMOVE','INBETWEEN_MOUSEMOVE'}:
                return None
            return RUNNING
        return None
