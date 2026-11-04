import re
import time
import blf
import bpy
from bpy_extras import view3d_utils
from .canvas import Rect

LABEL = 'Avatar'
SEARCH = 'SEARCH'
EYEDROPPER = 'EYEDROPPER'
CLEAR = 'CLEAR'
FIELD = 'FIELD'
VISIBLE_ROWS = 10
ROW_PITCH = 20
ROW_HEIGHT = 18
FIELD_HEIGHT = 18
POPUP_TOP = 12
POPUP_BOTTOM = 10
POPUP_GAP = 2
POPUP_MARGIN = 4
TEXT_OFFSET = 25
TEXT_SIZE = 11
EXTRA_WIDTH = 22
LABEL_WIDTH = 62
TOOLTIP_DELAY = .8
OFFSCREEN = (-100000,-100000)
STATUS = 'Esc  Cancel        Left Mouse  Start Sampling'
HANDLED = {'RUNNING_MODAL'}


def avatar_poll(self,obj):
    return obj.type=='MESH' and obj.get('dd_kind') not in {'panel','simulation','final'}


def match_rank(name,query):
    lowered=name.casefold()
    words=[word for word in re.split(r'[\W_]+',lowered) if word]
    rank=0
    for part in query.casefold().split():
        letters=iter(lowered)
        if any(word.startswith(part) for word in words):continue
        if part in lowered:rank=max(rank,1)
        elif all(letter in letters for letter in part):rank=2
        else:return None
    return rank


class AvatarField:
    def __init__(self,editor):
        self.editor=editor
        self.mode=None
        self.armed=None
        self.text=''
        self.cursor=0
        self.anchor=0
        self.filtering=False
        self.results=[]
        self.active=-1
        self.offset=0
        self.sampling=False
        self.sample=None
        self.mouse=OFFSCREEN
        self.dragging=False
        self.text_cursor=False
        self.hover_start=None

    @property
    def scale(self):
        return self.editor.canvas_layout.scale

    @property
    def avatar(self):
        return self.editor._scene.dd_avatar

    def candidates(self):
        return sorted((obj for obj in self.editor._scene.objects if avatar_poll(None,obj)),key=lambda obj:obj.name.casefold())

    def control(self):
        if self.editor.card_kind!='BODY':return None
        card=self.editor.minimal_card()
        return next((rect for rect,row in card[2] if row[0]=='AVATAR_FIELD'),None) if card else None

    def box(self,control):
        left=round(control.x+LABEL_WIDTH*self.scale)
        height=round(FIELD_HEIGHT*self.scale)
        return Rect(left,round(control.y+(control.h-height)/2),control.x+control.w-left,height)

    def extra_rect(self,box):
        width=round(EXTRA_WIDTH*self.scale)
        return Rect(box.x+box.w-width,box.y,width,box.h)

    def popup(self,box):
        scale=self.scale
        panel=self.editor.canvas_layout.panel
        below=box.y-panel.y-(POPUP_GAP+POPUP_MARGIN)*scale
        above=panel.y+panel.h-box.y-box.h-(POPUP_GAP+POPUP_MARGIN)*scale
        full=(VISIBLE_ROWS*ROW_PITCH+POPUP_TOP+POPUP_BOTTOM)*scale
        downward=below>=full or below>=above
        room=below if downward else above
        rows=max(1,min(VISIBLE_ROWS,int((room/scale-POPUP_TOP-POPUP_BOTTOM)/ROW_PITCH)))
        height=round((rows*ROW_PITCH+POPUP_TOP+POPUP_BOTTOM)*scale)
        gap=round(POPUP_GAP*scale)
        return Rect(box.x,box.y-gap-height if downward else box.y+box.h+gap,box.w,height),rows

    def row_rect(self,popup,index):
        scale=self.scale
        top=popup.y+popup.h-(POPUP_TOP+index*ROW_PITCH)*scale
        return Rect(round(popup.x+3*scale),round(top-(ROW_PITCH-1)*scale),round(popup.w-6*scale),round(ROW_HEIGHT*scale))

    def part(self,box):
        if not box.contains(*self.mouse):return None
        if self.extra_rect(box).contains(*self.mouse):
            return CLEAR if self.avatar is not None else EYEDROPPER
        return FIELD

    def row_at(self,popup,rows):
        for index in range(min(rows,len(self.results)-self.offset)):
            if self.row_rect(popup,index).contains(*self.mouse):return self.offset+index
        return None

    def refresh(self):
        objects=self.candidates()
        if self.filtering and self.text.strip():
            ranked=[(match_rank(obj.name,self.text),obj) for obj in objects]
            self.results=[obj for rank,obj in sorted((item for item in ranked if item[0] is not None),key=lambda item:item[0])]
        else:
            self.results=objects
        self.active=-1
        self.offset=0

    def open(self,box):
        name=self.avatar.name if self.avatar else ''
        self.mode=SEARCH
        self.text=name
        self.cursor=len(name)
        self.anchor=0
        self.filtering=False
        self.refresh()
        if self.avatar in self.results:
            self.active=self.results.index(self.avatar)
            self.reveal(self.popup(box)[1])

    def reveal(self,rows):
        self.offset=max(self.active-rows+1,min(self.offset,self.active),0)

    def step(self,delta,box):
        if self.results:
            self.active=max(0,min(len(self.results)-1,self.active+delta))
            self.reveal(self.popup(box)[1])

    def tooltip_ready(self):
        return self.mode is None and self.hover_start is not None and time.monotonic()-self.hover_start>=TOOLTIP_DELAY

    def sync_cursor(self,part):
        wanted=part==FIELD
        if wanted==self.text_cursor:return
        self.text_cursor=wanted
        if wanted:self.editor._window.cursor_modal_set('TEXT')
        else:self.editor._window.cursor_modal_restore()

    def close(self):
        self.sync_cursor(None)
        if self.mode==EYEDROPPER:
            self.editor._window.cursor_modal_restore()
            bpy.context.workspace.status_text_set(None)
        self.mode=None
        self.armed=None
        self.dragging=False
        self.hover_start=None
        self.sampling=False
        self.sample=None

    def choose(self,obj):
        self.close()
        if obj==self.avatar:return
        pending=self.editor.pending_simulation
        self.editor.choose_body(obj,bpy.context)
        if pending and obj is not None:self.editor.card_kind=None

    def start_eyedropper(self):
        self.close()
        self.mode=EYEDROPPER
        self.editor._window.cursor_modal_set('EYEDROPPER')
        bpy.context.workspace.status_text_set(STATUS)

    def activate(self,part,box):
        if part==CLEAR:self.choose(None)
        elif part==EYEDROPPER:self.start_eyedropper()
        else:self.open(box)

    def event(self,context,event):
        self.mouse=self.editor.pointer
        if event.type=='WINDOW_DEACTIVATE':
            self.close()
            return None
        control=self.control()
        if control is None:
            self.close()
            return None
        if event.type.startswith('TIMER'):
            if self.tooltip_ready():self.editor._area.tag_redraw()
            return None
        result=self.route(context,event,self.box(control))
        if self.mode:self.editor.pointer=OFFSCREEN
        return result

    def route(self,context,event,box):
        if self.mode==EYEDROPPER:return self.eyedropper_event(context,event)
        part=self.part(box)
        self.sync_cursor(part)
        if self.mode==SEARCH:return self.search_event(context,event,box)
        return self.idle_event(event,box,part)

    def idle_event(self,event,box,part):
        press=event.value in {'PRESS','DOUBLE_CLICK'}
        if event.type=='MOUSEMOVE':
            self.hover_start=time.monotonic() if part else None
        if event.type=='LEFTMOUSE':
            if press:
                self.hover_start=None
                self.armed=None if part==FIELD else part
                if part==FIELD:self.open(box)
                return HANDLED if part else None
            if event.value=='RELEASE' and self.armed:
                armed,self.armed=self.armed,None
                if armed==part:self.activate(part,box)
                return HANDLED
            return None
        if press and part and event.type=='E':
            self.start_eyedropper()
            return HANDLED
        if press and part and event.type=='BACK_SPACE' and self.avatar is not None:
            self.choose(None)
            return HANDLED
        return None

    def search_event(self,context,event,box):
        press=event.value in {'PRESS','DOUBLE_CLICK'}
        popup,rows=self.popup(box)
        row=self.row_at(popup,rows)
        if event.type=='MOUSEMOVE':
            if self.dragging:self.cursor=self.text_index(box)
            elif row is not None:self.active=row
        elif event.type in {'WHEELUPMOUSE','WHEELDOWNMOUSE'}:
            self.step(-1 if event.type=='WHEELUPMOUSE' else 1,box)
        elif event.type=='LEFTMOUSE':
            self.search_click(event,press,box,popup,row)
        elif press and event.type in {'ESC','RIGHTMOUSE'}:
            self.close()
        elif press and event.type in {'RET','NUMPAD_ENTER'}:
            self.confirm()
        elif press and event.type in {'UP_ARROW','DOWN_ARROW'}:
            self.step(-1 if event.type=='UP_ARROW' else 1,box)
        elif press:
            self.text_event(context,event)
        return HANDLED

    def search_click(self,event,press,box,popup,row):
        part=self.part(box)
        if event.value=='DOUBLE_CLICK' and part==FIELD:
            self.select_word(self.text_index(box))
        elif press:
            self.armed=SEARCH if popup.contains(*self.mouse) else part
            if part==FIELD:
                self.cursor=self.anchor=self.text_index(box)
                self.dragging=True
            elif self.armed is None:self.close()
        elif event.value=='RELEASE':
            self.dragging=False
            armed,self.armed=self.armed,None
            if armed==SEARCH and row is not None:self.choose(self.results[row])
            elif armed==part and part in {CLEAR,EYEDROPPER}:self.activate(part,box)

    def confirm(self):
        name=self.text.strip()
        if 0<=self.active<len(self.results):self.choose(self.results[self.active])
        elif not name:self.choose(None)
        else:self.choose(next((obj for obj in self.candidates() if obj.name==name),self.avatar))

    def text_index(self,box):
        target=self.mouse[0]-box.x-TEXT_OFFSET*self.scale
        blf.size(0,TEXT_SIZE*self.scale)
        return min(range(len(self.text)+1),key=lambda index:abs(blf.dimensions(0,self.text[:index])[0]-target))

    def select_word(self,index):
        start=end=index
        while start>0 and self.text[start-1].isalnum():start-=1
        while end<len(self.text) and self.text[end].isalnum():end+=1
        self.anchor,self.cursor=start,end

    def selection(self):
        return min(self.anchor,self.cursor),max(self.anchor,self.cursor)

    def replace(self,value):
        start,end=self.selection()
        self.text=self.text[:start]+value+self.text[end:]
        self.cursor=self.anchor=start+len(value)
        self.filtering=True
        self.refresh()

    def word_edge(self,delta):
        index=self.cursor
        look=-1 if delta<0 else 0
        for wanted in (False,True):
            while 0<=index+look<len(self.text) and self.text[index+look].isalnum()==wanted:index+=delta
        return index

    def move_cursor(self,event):
        start,end=self.selection()
        delta=-1 if event.type=='LEFT_ARROW' else 1
        if event.type=='HOME':target=0
        elif event.type=='END':target=len(self.text)
        elif event.ctrl:target=self.word_edge(delta)
        elif start!=end and not event.shift:target=start if delta<0 else end
        else:target=max(0,min(len(self.text),self.cursor+delta))
        self.cursor=target
        if not event.shift:self.anchor=target

    def text_event(self,context,event):
        start,end=self.selection()
        manager=context.window_manager
        if event.ctrl and event.type=='A':
            self.anchor,self.cursor=0,len(self.text)
        elif event.ctrl and event.type in {'C','X'}:
            manager.clipboard=self.text[start:end]
            if event.type=='X':self.replace('')
        elif event.ctrl and event.type=='V':
            self.replace(' '.join(manager.clipboard.split()))
        elif event.type in {'LEFT_ARROW','RIGHT_ARROW','HOME','END'}:
            self.move_cursor(event)
        elif event.type in {'BACK_SPACE','DEL'}:
            if start==end:
                delta=-1 if event.type=='BACK_SPACE' else 1
                self.cursor=self.word_edge(delta) if event.ctrl else max(0,min(len(self.text),self.cursor+delta))
            self.replace('')
        elif event.unicode and event.unicode.isprintable() and not event.ctrl and not event.alt:
            self.replace(event.unicode)

    def eyedropper_event(self,context,event):
        press=event.value=='PRESS'
        if press and event.type in {'ESC','RIGHTMOUSE'}:
            self.close()
        elif event.type=='MOUSEMOVE':
            self.sample=self.sample_at(context,event)
        elif event.type=='LEFTMOUSE' and press:
            self.sampling=True
            self.sample=self.sample_at(context,event)
        elif event.type=='LEFTMOUSE' and event.value=='RELEASE' and self.sampling:
            picked=self.sample_at(context,event)
            if picked is None:self.close()
            else:self.choose(picked)
        return HANDLED

    def sample_at(self,context,event):
        editor=self.editor
        for area in editor._window.screen.areas:
            inside=area.x<=event.mouse_x<area.x+area.width and area.y<=event.mouse_y<area.y+area.height
            if area.type!='VIEW_3D' or not inside:continue
            if area==editor._area and editor.canvas_layout.panel.contains(*self.mouse):return None
            region=next(item for item in area.regions if item.type=='WINDOW')
            view=area.spaces.active.region_3d
            mouse=(event.mouse_x-region.x,event.mouse_y-region.y)
            origin=view3d_utils.region_2d_to_origin_3d(region,view,mouse)
            direction=view3d_utils.region_2d_to_vector_3d(region,view,mouse)
            hit=editor._scene.ray_cast(context.evaluated_depsgraph_get(),origin,direction)
            obj=hit[4].original if hit[0] else None
            return obj if obj is not None and avatar_poll(None,obj) else None
        return None
