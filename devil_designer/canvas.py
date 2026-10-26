"""Viewport-local layout shared by drawing and input handling."""
from dataclasses import dataclass
import math

@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    w: float
    h: float
    def contains(self,x,y):
        return self.x <= x <= self.x+self.w and self.y <= y <= self.y+self.h

def clamp_window(bounds, available, scale):
    """Keep every window edge accessible after dragging, resizing, or changing monitors."""
    x,y,w,h = bounds
    minimum_w,minimum_h = min(420*scale,available.w),min(320*scale,available.h)
    w,h = min(available.w,max(minimum_w,w)),min(available.h,max(minimum_h,h))
    x = max(available.x,min(available.x+available.w-w,x))
    y = max(available.y,min(available.y+available.h-h,y))
    return Rect(x,y,w,h)


class Layout:
    def __init__(self,width,height,scale=1.0,full=False,left=0,right=0,top=0,bottom=0,
                 position=None,settings=False):
        self.scale = s = scale
        usable_h = max(1,height-top-bottom)
        usable_w = max(1,width-left-right)
        margin = min(12*s,usable_w/20,usable_h/20)
        self.available = available = Rect(left+margin,bottom+margin,
                                         max(1,usable_w-2*margin),max(1,usable_h-2*margin))
        if full:
            self.panel = available
        else:
            w = min(available.w,max(620*s,available.w*.65))
            h = min(available.h,max(440*s,available.h*.86))
            default = (available.x+available.w-w,available.y+(available.h-h)/2,w,h)
            self.panel = clamp_window(position or default,available,s)
        p = self.panel
        inspector_w = min(248*s,p.w*.40) if settings else 0
        content_w = max(1,p.w-inspector_w)
        self.header = Rect(p.x,p.y+p.h-54*s,p.w,54*s)
        self.inspector = Rect(p.x+content_w,p.y+48*s,inspector_w,max(1,p.h-102*s)) if settings else None
        self.toolbar = Rect(p.x,self.header.y-42*s,content_w,42*s)
        self.workflow = Rect(p.x,self.toolbar.y-36*s,content_w,36*s)
        self.footer = Rect(p.x,p.y,p.w,48*s)
        self.canvas = Rect(p.x+25*s,self.footer.y+self.footer.h,
                           max(1,content_w-25*s),max(1,p.h-205*s))
        self.ruler_top = Rect(self.canvas.x,self.canvas.y+self.canvas.h,self.canvas.w,25*s)
        self.resize = Rect(p.x+p.w-18*s,p.y,18*s,18*s)
        self.buttons = {}
        compact = content_w<500*s
        specs = ([("SELECT","V",30),("POLYGON","P",30),("RECTANGLE","R",30),
                  ("SEW","Sew J",48),("SNAP","Snap",49),("FIT","Fit",36)] if compact else
                 [("SELECT","Select V",73),("POLYGON","Polygon P",82),
                  ("RECTANGLE","Rect R",64),("SEW","Sew J",55),("SNAP","Snap",49),("FIT","Fit",36)])
        if content_w>=310*s:
            specs += [("UNDO","<",26),("REDO",">",26)]
        self.button_row(specs,self.toolbar,7,28)
        self.button_row([("BUILD","Build 3D",70),("ARRANGE","Arrange",62),("SIMULATE","Simulate",65),
                         ("STOP","Stop",39),("RESET","Reset",44),("KEEP","Keep mesh",74)],self.workflow,5,26)
        self.buttons["CLOSE"] = (Rect(p.x+p.w-36*s,self.header.y+13*s,25*s,28*s),"X")
        self.buttons["FULL"] = (Rect(p.x+p.w-102*s,self.header.y+13*s,60*s,28*s),"Restore" if full else "Expand")
        self.buttons["SETTINGS"] = (Rect(p.x+p.w-180*s,self.header.y+13*s,72*s,28*s),"Settings")

    def button_row(self,specs,region,offset,height):
        s = self.scale
        factor = min(1,max(.05,(region.w-24*s)/(sum(item[2]+5 for item in specs)*s)))
        x = region.x+12*s
        for name,label,units in specs:
            self.buttons[name] = (Rect(x,region.y+offset*s,units*s*factor,height*s),label)
            x += (units+5)*s*factor

    def button(self,x,y):
        return next((name for name,(r,_) in self.buttons.items() if r.contains(x,y)),None)

class View:
    def __init__(self):
        self.cx = self.cy = 0.0
        self.zoom = 800.0
    def screen(self,point,rect):
        return (rect.x+rect.w/2+(point[0]-self.cx)*self.zoom,
                rect.y+rect.h/2+(point[1]-self.cy)*self.zoom)
    def world(self,point,rect):
        return ((point[0]-rect.x-rect.w/2)/self.zoom+self.cx,
                (point[1]-rect.y-rect.h/2)/self.zoom+self.cy)
    def pan(self,dx,dy):
        self.cx -= dx/self.zoom
        self.cy -= dy/self.zoom
    def zoom_at(self,point,rect,factor):
        before = self.world(point,rect)
        self.zoom = min(80000,max(20,self.zoom*factor))
        after = self.world(point,rect)
        self.cx += before[0]-after[0]
        self.cy += before[1]-after[1]
    def fit(self,points,rect):
        if not points:
            self.cx = self.cy = 0
            self.zoom = min(rect.w,rect.h)/.65
            return
        xs,ys = [p[0] for p in points],[p[1] for p in points]
        self.cx,self.cy = (min(xs)+max(xs))/2,(min(ys)+max(ys))/2
        self.zoom = min(80000,max(20,min(rect.w/max(.03,max(xs)-min(xs)),
                                       rect.h/max(.03,max(ys)-min(ys)))*.72))

def grid_step(zoom):
    target = 55/zoom
    power = 10**math.floor(math.log10(target))
    return next(v*power for v in (1,2,5,10) if v*power >= target)
