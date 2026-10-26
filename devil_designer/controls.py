"""Pure layout and values for the settings inside the floating editor."""
from dataclasses import dataclass
import math
from .canvas import Rect

@dataclass(frozen=True)
class Setting:
    key: str
    label: str
    factor: float
    unit: str
    step: float
    low: float
    high: float
    integer: bool = False

    def format(self,value):
        value = value*self.factor
        return f"{int(value)}" if self.integer else f"{value:g}"

    def parse(self,text):
        try:
            value = float(text.replace(',','.'))
        except ValueError as exc:
            raise ValueError('Enter a number for '+self.label.lower()+'.') from exc
        value /= self.factor
        if not math.isfinite(value) or not self.low<=value<=self.high:
            raise ValueError(f'{self.label}: enter {self.low*self.factor:g} to {self.high*self.factor:g} {self.unit}.')
        if self.integer and not value.is_integer():
            raise ValueError(self.label+' needs a whole number.')
        return int(value) if self.integer else value

SETTINGS = {
    spec.key:spec for spec in (
        Setting('dd_spacing','Mesh spacing',100,'cm',.1,.003,.2),
        Setting('dd_clearance','Body clearance',100,'cm',.5,.005,.3),
        Setting('dd_quality','Quality steps',1,'',1,5,40,True),
        Setting('dd_frames','Frames',1,'',10,10,1000,True),
        Setting('dd_weld_distance','Weld distance',1000,'mm',.5,.0001,.05),
        Setting('dd_thickness','Thickness',1000,'mm',.1,0,.01),
    )
}

@dataclass
class Control:
    kind: str
    key: str
    rect: Rect
    label: str
    value_rect: Rect = None
    minus: Rect = None
    plus: Rect = None

class Inspector:
    def __init__(self,rect,scale,scroll,seams):
        self.rect,self.scale = rect,scale
        self.controls=[]
        # Build in logical rows first; clamp scrolling against actual content height.
        rows=[('title','','GARMENT'),('body','BODY','Avatar body'),
              ('button','BODY_USE','Use selected body'),('number','dd_spacing',''),
              ('number','dd_clearance',''),('section','','SIMULATION'),
              ('number','dd_quality',''),('number','dd_frames',''),
              ('toggle','dd_self_collision','Self collision'),('toggle','dd_pin_top','Pin highest points'),
              ('section','','OUTPUT'),('number','dd_weld_distance',''),('number','dd_thickness',''),
              ('section','','TRY IT'),('button','DEMO','Create sewing demo'),
              ('section','','SEWING PAIRS')]
        rows += [('seam',seam.id,str(index+1)) for index,seam in enumerate(seams)]
        if not seams:
            rows += [('hint','','Use Sew / J to pair edges.')]
        s=scale
        heights={'title':32,'body':54,'section':32,'number':56,'toggle':32,'button':31,'hint':32,'seam':42}
        self.total=(sum(heights[kind] for kind,_,_ in rows)+12)*s
        self.max_scroll=max(0,self.total-rect.h)
        self.scroll=max(0,min(self.max_scroll,scroll))
        y=rect.y+rect.h+self.scroll-8*s
        for kind,key,label in rows:
            h=heights[kind]*s
            y-=h
            r=Rect(rect.x+12*s,y, max(1,rect.w-29*s),h)
            item=Control(kind,key,r,label)
            if kind=='number':
                item.label=SETTINGS[key].label
                item.value_rect=Rect(r.x,r.y+4*s,max(1,r.w-52*s),25*s)
                item.minus=Rect(r.x+r.w-49*s,r.y+4*s,23*s,25*s)
                item.plus=Rect(r.x+r.w-23*s,r.y+4*s,23*s,25*s)
            elif kind=='body':
                item.value_rect=Rect(r.x,r.y+4*s,r.w,27*s)
            self.controls.append(item)
        self.scrollbar=Rect(rect.x+rect.w-7*s,rect.y+4*s,4*s,max(1,rect.h-8*s))
        track=self.scrollbar
        thumb_h=max(22*s,track.h*min(1,rect.h/self.total))
        self.thumb=Rect(track.x,track.y+(track.h-thumb_h)*(1-self.scroll/max(1,self.max_scroll)),track.w,thumb_h)

    def hit(self,point):
        if not self.rect.contains(*point):
            return None
        for item in self.controls:
            if not item.rect.contains(*point):
                continue
            if item.kind=='number':
                if item.minus.contains(*point): return 'STEP_DOWN',item.key
                if item.plus.contains(*point): return 'STEP_UP',item.key
                if item.value_rect.contains(*point): return 'EDIT',item.key
            if item.kind=='body' and item.value_rect.contains(*point): return 'BODY',item.key
            if item.kind=='button': return item.key,item.key
            if item.kind=='toggle': return 'TOGGLE',item.key
            if item.kind=='seam':
                if point[0]>item.rect.x+item.rect.w-25*self.scale: return 'SEAM_REMOVE',item.key
                if point[0]>item.rect.x+item.rect.w-68*self.scale: return 'SEAM_FLIP',item.key
                return 'SEAM_SELECT',item.key
        return None

class BodyMenu:
    def __init__(self,panel,anchor,scale,objects,offset=0):
        self.objects=objects
        self.offset=max(0,min(max(0,len(objects)-6),offset))
        self.entries=[(None,'Clear body')]+[(obj,obj.name) for obj in objects[self.offset:self.offset+6]]
        width=anchor.w
        height=(len(self.entries)*30+8)*scale
        y=max(panel.y+52*scale,anchor.y-height)
        height=min(height,panel.y+panel.h-54*scale-y)
        self.rect=Rect(anchor.x,y,width,max(1,height))
        self.rows=[]
        top=y+height-4*scale
        for obj,label in self.entries:
            top-=30*scale
            if top>=y:
                self.rows.append((Rect(anchor.x+3*scale,top,width-6*scale,30*scale),obj,label))
